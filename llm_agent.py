"""
🤖 LLM-Driven Adaptive Veo 3 Video Agent
=========================================

Architecture:
    PERCEIVE (DOM + screenshot) → REASON (Groq LLM) → ACT (Playwright) → loop

UI বদলালেও কাজ করবে — কারণ LLM নিজে DOM context থেকে সিদ্ধান্ত নেয়।
Static selector brittle না। Veo 3.1 Fast সিলেক্ট, prompt submit,
ভিডিও download — সব automatically।

ব্যবহার:
    1. .env এ GROQ_API_KEY set করুন
    2. python llm_agent.py
    3. Browser খুলবে → agent নিজে কাজ করবে
"""

import os
import sys
import json
import time
import random
import argparse
import base64
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# CloakBrowser local imports
from groq_client import GroqClient
from prompt_templates import (
    SYSTEM_PROMPT,
    build_user_prompt,
    build_recovery_prompt,
    build_vision_prompt,
)


# ─── Setup ─────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    print("❌ .env ফাইল পাওয়া যায়নি!")
    print("📄 .env.example কপি করে .env তৈরি করুন")
    sys.exit(1)

# Robust .env load — commented `# KEY=VALUE` lines থেকেও Cohere key পায়
try:
    from env_loader import load_env_robust
    load_env_robust()
except ImportError:
    load_dotenv(env_path)


# ─── Compact DOM scan JS ─────────────────────────────────────
# Token-efficient — শুধু essential keys (i, t, tx, a, p, tp, r, c, b, v)
DOM_SCAN_JS = """
() => {
    const SELS = 'button, a, input, textarea, [role="button"], [contenteditable="true"], select, [role="textbox"]';
    const vh = window.innerHeight;
    return Array.from(document.querySelectorAll(SELS))
        .filter(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 &&
                   s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
        })
        .map((el, i) => {
            const r = el.getBoundingClientRect();
            return {
                i: i,
                t: el.tagName,
                tx: (el.innerText || el.value || '').slice(0, 60),
                a: el.getAttribute('aria-label') || '',
                p: el.getAttribute('placeholder') || '',
                tp: el.getAttribute('type') || '',
                r: el.getAttribute('role') || '',
                c: (typeof el.className === 'string' ? el.className : '').slice(0, 40),
                b: [
                    Math.round(r.x),
                    Math.round(r.y),
                    Math.round(r.width),
                    Math.round(r.height)
                ],
                v: r.y >= 0 && r.y <= vh
            };
        });
}
"""


# ─── Login-page detection keywords ────────────────────────────
_LOGIN_KEYWORDS = (
    "accounts.google.com",
    "/signin/",
    "/v3/signin",
    "/sign-in/",
    "login",
    "identifier",
    "passkey",
    "challenge",
    "/pwd",
    "/v2/signin",
)


def _looks_like_login_page(url: str, title: str, elements: list) -> bool:
    """
    URL/title/elements দেখে বুঝি login form আছে কিনা।
    শুধু তখনই credential context inject করব।
    """
    url_l = (url or "").lower()
    title_l = (title or "").lower()
    if any(kw in url_l for kw in _LOGIN_KEYWORDS):
        return True
    if any(kw in title_l for kw in ("sign in", "log in", "login", "identifier")):
        return True
    # Email field আছে কিনা check
    for el in elements or []:
        tp = (el.get("tp") or "").lower()
        a = (el.get("a") or "").lower()
        p = (el.get("p") or "").lower()
        if tp in ("email",) or "email" in a or "email" in p:
            return True
    return False


# ─── Element-locator helper ──────────────────────────────────
def element_to_locator(page, idx: int, elements: list):
    """
    DOM elements list-এর index থেকে Playwright locator বানাও।
    Element attributes (text, aria, placeholder) দিয়ে robust locator try করি —
    index-based nth() এর চেয়ে অনেক বেশি নির্ভরযোগ্য।
    """
    if idx < 0 or idx >= len(elements):
        raise ValueError(f"selector_idx {idx} out of range (0-{len(elements)-1})")

    el = elements[idx]
    tag = el.get("t", "").upper()
    text = (el.get("tx") or "").strip()
    aria = (el.get("a") or "").strip()
    placeholder = (el.get("p") or "").strip()
    el_type = (el.get("tp") or "").strip()
    role = (el.get("r") or "").strip()

    # Priority 1: aria-label (most stable)
    if aria:
        safe_aria = aria.replace('"', '\\"')
        return f'[aria-label="{safe_aria}"]', page.locator(f'[aria-label="{safe_aria}"]').first

    # Priority 2: text content (for buttons, links)
    if text and tag in ("BUTTON", "A"):
        safe_text = text.replace('"', '\\"').replace("\n", " ")
        sel = f'{tag.lower()}:has-text("{safe_text}")'
        return sel, page.locator(sel).first

    # Priority 3: placeholder (for inputs)
    if placeholder:
        safe_ph = placeholder.replace('"', '\\"')
        sel = f'input[placeholder="{safe_ph}"], textarea[placeholder="{safe_ph}"]'
        return sel, page.locator(sel).first

    # Priority 4: type (for email/password/etc)
    if el_type and tag == "INPUT":
        sel = f'input[type="{el_type}"]'
        return sel, page.locator(sel).first

    # Priority 5: role
    if role:
        sel = f'[role="{role}"]'
        return sel, page.locator(f'[role="{role}"]').first

    # Fallback: nth() — last resort
    nth = idx
    sel = f"{tag.lower()}:nth-of-type({nth + 1})"
    return sel, page.locator(sel).first


# ─── Main Agent Class ────────────────────────────────────────
class VeoFlowAgent:
    """Self-deciding adaptive browser agent — Groq LLM powered"""

    def __init__(
        self,
        headless: bool = False,
        humanize: bool = True,
        proxy: str = "",
        use_vision: bool = True,
        max_steps: int = 50,
        log_dir: str = "./agent_runs",
    ):
        self.headless = headless
        self.humanize = humanize
        self.proxy = proxy
        self.use_vision = use_vision
        self.max_steps = max_steps
        self.log_dir = Path(__file__).parent / log_dir

        # Credentials from .env
        self.user_id = os.getenv("USER_ID", "")
        self.password = os.getenv("PASSWORD", "")
        self.video_prompt = os.getenv(
            "VIDEO_PROMPT",
            "A cinematic sunset over the ocean with gentle waves"
        )
        self.target_model = os.getenv("VEOPRO_MODEL", "Veo 3.1 - Fast")
        self.login_url = os.getenv("LOGIN_URL", "https://labs.google/fx/tools/flow")

        # Validate
        if not all([self.user_id, self.password]):
            raise ValueError("❌ USER_ID / PASSWORD .env-এ নেই!")

        # Init Groq
        print("🤖 Groq LLM init...")
        self.llm = GroqClient()
        print(f"  ✓ Reasoning: {self.llm.REASONING_MODEL}")
        print(f"  ✓ Vision    : {self.llm.VISION_MODEL}")

        # State
        self.history = []           # list of {action, success, ...}
        self.vision_fail_streak = 0  # consecutive failures → trigger vision
        self.last_dom = []
        self.step = 0
        self.mission_complete = False
        self.downloaded_file = None

        # Run folder
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.log_dir / f"run_{self.run_id}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._save_meta()

        # Browser (lazy init)
        self.browser = None
        self.page = None

    # ─── Browser lifecycle ──────────────────────────────────
    def _launch_browser(self):
        from cloakbrowser import launch
        print(f"\n🌐 CloakBrowser launching...")
        print(f"   headless={self.headless}, humanize={self.humanize}")
        kw = {"headless": self.headless, "humanize": self.humanize}
        if self.proxy:
            kw["proxy"] = self.proxy
            kw["geoip"] = True
        self.browser = launch(**kw)
        self.page = self.browser.new_page()
        print(f"   ✓ Browser ready\n")

    def _close_browser(self):
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass

    # ─── Credential context for LLM ─────────────────────────
    def _build_credential_context(self, snapshot: dict) -> str:
        """
        Login page detect করলে real email/password inline করে পাঠাই।
        LLM (Groq/Cohere) যেন placeholder email না type করে।

        Returns:
            Extra text to append to user_prompt, or empty string.
        """
        if not (self.user_id and self.password):
            return ""
        if not _looks_like_login_page(snapshot["url"], snapshot["title"],
                                        snapshot["elements"]):
            return ""

        return (
            "\n\n🔑 CREDENTIALS (use these EXACT values — DO NOT use "
            "placeholders like user@example.com):\n"
            f"  - Email    : {self.user_id}\n"
            f"  - Password : {self.password}\n"
            "When type action-এ email/password field থাকে, "
            "'text' field-এ উপরের actual value বসাও।\n"
        )

    # ─── Perception: DOM + screenshot ───────────────────────
    def _perceive(self) -> dict:
        """Current page state capture করো"""
        try:
            title = self.page.title()
        except Exception:
            title = ""

        try:
            elements = self.page.evaluate(DOM_SCAN_JS)
            self.last_dom = elements
        except Exception as e:
            print(f"⚠️ DOM scan error: {str(e)[:80]}")
            elements = self.last_dom  # fallback to last known

        screenshot_b64 = None
        try:
            png_bytes = self.page.screenshot(full_page=False)
            # JPEG compress + resize for ~70% smaller base64 → fewer vision tokens
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(png_bytes))
                # Resize to max 1024px wide (preserves aspect)
                if img.width > 1024:
                    ratio = 1024 / img.width
                    img = img.resize(
                        (1024, int(img.height * ratio)),
                        Image.LANCZOS,
                    )
                # Convert to RGB if RGBA (JPEG doesn't support alpha)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80, optimize=True)
                screenshot_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception:
                # Fallback: raw PNG
                screenshot_b64 = base64.b64encode(png_bytes).decode("ascii")
        except Exception as e:
            print(f"⚠️ screenshot error: {str(e)[:80]}")

        return {
            "url": self.page.url,
            "title": title,
            "elements": elements,
            "screenshot_b64": screenshot_b64,
        }

    # ─── Reasoning: Two-stage (vision + reasoning + tools) ─────
    def _reason(self, snapshot: dict) -> dict:
        """
        LLM থেকে action plan আনো।
        Architecture:
          Stage 1: Cohere vision model — screenshot → grounded element list
          Stage 2: Cohere reasoning model — DOM + vision + history + tools → action
        """
        # ── Stage 1: Vision perception (if screenshot available) ──
        vision_elements: list = []
        vision_summary = ""
        page_type = ""
        if snapshot.get("screenshot_b64") and self.use_vision:
            try:
                print("  👁️  Vision perception (Cohere)...")
                vp = self.llm.vision_perceive(
                    screenshot_b64=snapshot["screenshot_b64"],
                    url=snapshot["url"],
                    title=snapshot["title"],
                )
                vision_elements = vp.get("elements", []) or []
                vision_summary = vp.get("summary", "") or ""
                page_type = vp.get("page_type", "") or ""
                print(f"     → {len(vision_elements)} elements, type={page_type}")
            except Exception as e:
                print(f"  ⚠️ Vision perception error: {str(e)[:80]}")

        # ── Build user prompt with vision context ──
        user_prompt = build_user_prompt(
            url=snapshot["url"],
            title=snapshot["title"],
            step_num=self.step,
            max_steps=self.max_steps,
            dom_elements=snapshot["elements"],
            history=self.history,
            video_prompt=self.video_prompt,
            target_model=self.target_model,
            vision_elements=vision_elements,
            vision_summary=vision_summary,
            page_type=page_type,
        )

        # ── Credential context injection ──
        cred_ctx = self._build_credential_context(snapshot)
        if cred_ctx:
            user_prompt += cred_ctx

        # ── Stage 2: Reasoning with tools (Cohere preferred) ──
        # If Cohere available, use tool-using reasoning; else Groq text-only.
        if getattr(self.llm, "cohere", None):
            print("  🧠 Reasoning (Cohere + tools)...")
            plan = self.llm.cohere.reason_with_tools(
                system_prompt=SYSTEM_PROMPT,
                user_content=user_prompt,
                max_tokens=4096,
                thinking_token_budget=2000,
                max_tool_turns=2,  # strict — 1 search + 1 fetch max
            )
            if isinstance(plan, dict):
                plan["_backend"] = "cohere_vision_tools"
            print(f" ✓")
            return plan

        # ── Fallback: Groq text-only reasoning ──
        print(f"  🧠 Reasoning (GPT OSS 120B)...", end="", flush=True)
        plan = self.llm.reason(
            system_prompt=SYSTEM_PROMPT,
            user_content=user_prompt,
            max_tokens=4096,
            reasoning_effort="medium",
        )
        backend = plan.pop("_backend", None) if isinstance(plan, dict) else None
        if backend == "cohere_fallback":
            print(f" ✓ (via Cohere fallback)")
        else:
            print(f" ✓")
        return plan

    # ─── Action: execute the plan ───────────────────────────
    def _act(self, plan: dict) -> tuple[bool, str]:
        """
        Plan execute করো Playwright দিয়ে।
        Returns: (success: bool, error_msg: str)
        """
        action = plan.get("action", "wait")
        try:
            if action == "click":
                idx = plan.get("selector_idx")
                if idx is None:
                    return False, "selector_idx missing"
                sel_str, locator = element_to_locator(self.page, idx, self.last_dom)
                # Human-like delay
                time.sleep(random.uniform(0.5, 1.5))
                locator.click(timeout=10000)
                print(f"     ✓ click [{idx}] → {sel_str}")
                # URL change হলে wait
                time.sleep(1.5)
                return True, ""

            elif action == "type":
                idx = plan.get("selector_idx")
                text = plan.get("text", "")
                if idx is None:
                    return False, "selector_idx missing"
                sel_str, locator = element_to_locator(self.page, idx, self.last_dom)
                # Clear then type
                locator.click(timeout=10000)
                time.sleep(0.3)
                # Try select all + delete (works for most inputs)
                try:
                    locator.press("Control+A")
                    locator.press("Delete")
                except Exception:
                    pass
                # Human-like typing
                locator.type(text, delay=random.randint(30, 80))
                print(f"     ✓ type [{idx}] → '{text[:40]}' ({sel_str})")
                return True, ""

            elif action == "navigate":
                url = plan.get("url", "")
                if not url:
                    return False, "url missing"
                self.page.goto(url, timeout=60000, wait_until="domcontentloaded")
                print(f"     ✓ navigate → {url}")
                time.sleep(3)
                return True, ""

            elif action == "wait":
                seconds = plan.get("seconds", 3)
                print(f"     ⏳ wait {seconds}s")
                time.sleep(seconds)
                return True, ""

            elif action == "finish":
                self.mission_complete = plan.get("is_done", False)
                print(f"     🏁 finish (is_done={self.mission_complete})")
                return True, ""

            else:
                return False, f"unknown action: {action}"

        except Exception as e:
            err = str(e)[:200]
            print(f"     ✗ {action} failed: {err}")
            return False, err

    # ─── Verify (optional) ──────────────────────────────────
    def _verify(self, plan: dict) -> bool:
        """Optional: success check (e.g. URL contains)"""
        verify = plan.get("verify", "")
        if not verify:
            return True

        if verify.startswith("url_contains:"):
            needle = verify.split(":", 1)[1].strip()
            return needle in self.page.url
        if verify.startswith("url_not_contains:"):
            needle = verify.split(":", 1)[1].strip()
            return needle not in self.page.url
        return True

    # ─── Step capture ───────────────────────────────────────
    def _capture_step(self, plan: dict, success: bool, snapshot: dict):
        """Step data save করো — debugging / replay-এর জন্য"""
        timestamp = datetime.now().strftime("%H%M%S")
        capture = {
            "step": self.step,
            "timestamp": datetime.now().isoformat(),
            "url": snapshot["url"],
            "title": snapshot["title"],
            "plan": plan,
            "success": success,
            "elements_count": len(snapshot["elements"]),
            "llm_stats": self.llm.get_stats(),
        }

        # Screenshot
        try:
            ss_path = self.run_dir / f"step{self.step:02d}_{timestamp}.png"
            self.page.screenshot(path=str(ss_path), full_page=False)
            capture["screenshot"] = ss_path.name
        except Exception:
            pass

        # JSON
        try:
            json_path = self.run_dir / f"step{self.step:02d}_{timestamp}.json"
            json_path.write_text(
                json.dumps(capture, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ─── Run meta save ──────────────────────────────────────
    def _save_meta(self):
        meta = {
            "run_id": self.run_id,
            "started_at": datetime.now().isoformat(),
            "video_prompt": self.video_prompt,
            "target_model": self.target_model,
            "login_url": self.login_url,
            "max_steps": self.max_steps,
        }
        try:
            (self.run_dir / "_run_meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _save_final_meta(self):
        """Final summary save করো"""
        meta_path = self.run_dir / "_run_meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

        meta.update({
            "finished_at": datetime.now().isoformat(),
            "total_steps": self.step,
            "mission_complete": self.mission_complete,
            "downloaded_file": self.downloaded_file,
            "llm_stats": self.llm.get_stats(),
            "history": self.history[-30:],  # last 30 actions
        })
        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    # ─── Main run loop ──────────────────────────────────────
    def run(self):
        """Main agent loop — perceive → reason → act, until done or max steps"""
        print("=" * 70)
        print("🤖 VEO 3 ADAPTIVE AGENT — Starting")
        print("=" * 70)
        print(f"🎬 Prompt: {self.video_prompt}")
        print(f"🎯 Model : {self.target_model}")
        print(f"📂 Logs  : {self.run_dir}")
        print(f"🔢 Max steps: {self.max_steps}")
        print("=" * 70)

        self._launch_browser()

        try:
            # Initial navigation
            print(f"\n→ Initial navigate: {self.login_url}")
            self.page.goto(self.login_url, timeout=90000, wait_until="domcontentloaded")
            time.sleep(5)

            while self.step < self.max_steps and not self.mission_complete:
                self.step += 1
                print(f"\n{'─' * 70}")
                print(f"📍 STEP {self.step}/{self.max_steps}")
                print(f"{'─' * 70}")

                # 1. Perceive
                snapshot = self._perceive()
                print(f"   URL: {snapshot['url']}")
                print(f"   Elements visible: {len(snapshot['elements'])}")

                # 2. Reason
                plan = self._reason(snapshot)
                thought = plan.get("thought", "")
                action = plan.get("action", "wait")
                print(f"   💭 Thought: {thought[:150]}")
                print(f"   🎯 Action : {action}")

                # 3. Act
                success, error = self._act(plan)

                # 4. Verify
                if success and action not in ("wait", "finish"):
                    if not self._verify(plan):
                        success = False
                        error = "verify failed"

                # 5. Track
                self.history.append({
                    "step": self.step,
                    "action": action,
                    "selector_idx": plan.get("selector_idx"),
                    "text": plan.get("text", "")[:50] if plan.get("text") else "",
                    "url": plan.get("url", ""),
                    "seconds": plan.get("seconds"),
                    "success": success,
                    "error": error[:100] if error else "",
                })

                # 6. Vision streak tracking
                if success:
                    self.vision_fail_streak = 0
                else:
                    self.vision_fail_streak += 1

                # 7. Capture
                self._capture_step(plan, success, snapshot)

                # 8. Check downloaded files
                if action == "click" and "download" in (plan.get("thought", "").lower()):
                    self._check_downloads()

            # ── Done ──
            print(f"\n{'=' * 70}")
            if self.mission_complete:
                print(f"✅ MISSION COMPLETE in {self.step} steps!")
                if self.downloaded_file:
                    print(f"📥 Downloaded: {self.downloaded_file}")
            else:
                print(f"⚠️ Max steps ({self.max_steps}) reached without completion")
            print(f"{'=' * 70}")

        except KeyboardInterrupt:
            print("\n\n⛔ User interrupted")
        except Exception as e:
            print(f"\n❌ Fatal: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._close_browser()
            self._save_final_meta()
            print(f"\n📂 Full logs: {self.run_dir}")
            print(f"📊 LLM stats: {self.llm.get_stats()}")

    def _check_downloads(self):
        """Download folder চেক করো — নতুন .mp4 / .webm আছে কিনা"""
        downloads = Path(__file__).parent / "downloads"
        if not downloads.exists():
            return
        videos = (
            list(downloads.glob("*.mp4")) +
            list(downloads.glob("*.webm")) +
            list(downloads.glob("*.mov"))
        )
        if videos:
            latest = max(videos, key=lambda p: p.stat().st_mtime)
            self.downloaded_file = str(latest.name)
            print(f"     📥 Video found: {self.downloaded_file}")


# ─── CLI entry ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="LLM-driven Veo 3 video bot (adaptive, Groq-powered)"
    )
    parser.add_argument("--headless", action="store_true",
                        help="Run browser headless")
    parser.add_argument("--no-vision", action="store_true",
                        help="Disable Llama 4 Scout vision fallback")
    parser.add_argument("--max-steps", type=int, default=50,
                        help="Max agent steps (default: 50)")
    parser.add_argument("--no-humanize", action="store_true",
                        help="Disable CloakBrowser humanize mode")
    args = parser.parse_args()

    # Env fallbacks
    headless = args.headless or os.getenv("HEADLESS", "false").lower() == "true"
    humanize = not args.no_humanize and os.getenv("HUMANIZE", "true").lower() == "true"
    proxy = os.getenv("PROXY", "")
    use_vision = not args.no_vision

    agent = VeoFlowAgent(
        headless=headless,
        humanize=humanize,
        proxy=proxy,
        use_vision=use_vision,
        max_steps=args.max_steps,
    )
    agent.run()


if __name__ == "__main__":
    main()