"""
🌐 Flow Explorer — Interactive Diagnostic Tool
==============================================

CloakBrowser launch করে Flow editor navigate করে, **video generate করে না**,
শুধু সব interactive element dump করে যাতে তুমি সঠিক selector বের করতে পারো।

✅ Already-logged-in হলে কাজ করে (credentials চাইবে না)
✅ প্রতিটা page state-এ screenshot + JSON save করে
✅ Interactive element গুলোর full details (text, aria, role, type, placeholder, bbox)
✅ Bangla-friendly — বাংলা text element গুলোও dump হয়
✅ Manual mode — browser বন্ধ করতে Ctrl+C

ব্যবহার:
    python flow_explorer.py                  # শুধু default URL
    python flow_explorer.py --url <URL>      # custom URL
    python flow_explorer.py --steps          # Flow editor পর্যন্ত navigate করো step-by-step
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from cloakbrowser import launch


# ─── Setup ───
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
HUMANIZE = os.getenv("HUMANIZE", "true").lower() == "true"
PROXY = os.getenv("PROXY", "")

DEFAULT_URL = "https://labs.google/fx/tools/flow"
SAVE_DIR = Path(__file__).parent / "downloads" / "explorer"


def colorize(text, color):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
        "bold": "\033[1m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def snapshot_page(page, label, save_dir):
    """Current page state capture করো: screenshot + elements JSON"""
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace(" ", "_").replace("/", "-")[:30]

    print(f"\n{'=' * 70}")
    print(colorize(f"📸 Snapshot: {label}", "cyan"))
    print(f"{'=' * 70}")
    print(f"🌐 URL: {page.url}")

    # 1️⃣ Title
    try:
        title = page.title()
        print(f"📄 Title: {title[:80]}")
    except Exception:
        title = ""

    # 2️⃣ Visible elements — শুধু visible + interactive
    try:
        elements = page.evaluate(
            """
            () => {
                const sels = 'button, a, input, textarea, [role="button"], [contenteditable="true"], select, [role="textbox"]';
                return Array.from(document.querySelectorAll(sels))
                    .filter(el => {
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return r.width > 0 && r.height > 0 &&
                               s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
                    })
                    .map((el, i) => {
                        const r = el.getBoundingClientRect();
                        return {
                            idx: i,
                            tag: el.tagName,
                            text: (el.innerText || el.value || '').slice(0, 100),
                            aria: el.getAttribute('aria-label') || '',
                            role: el.getAttribute('role') || '',
                            type: el.getAttribute('type') || '',
                            placeholder: el.getAttribute('placeholder') || '',
                            name: el.getAttribute('name') || '',
                            href: el.getAttribute('href') || '',
                            classes: (typeof el.className === 'string' ? el.className : '').slice(0, 80),
                            id: el.id || '',
                            in_viewport: r.y >= 0 && r.y <= window.innerHeight,
                            bbox: {
                                x: Math.round(r.x),
                                y: Math.round(r.y),
                                w: Math.round(r.width),
                                h: Math.round(r.height)
                            }
                        };
                    });
            }
            """
        )
    except Exception as js_err:
        elements = []
        print(colorize(f"⚠️ DOM scan failed: {str(js_err)[:80]}", "yellow"))

    # 3️⃣ Screenshot
    try:
        ss_path = save_dir / f"{safe_label}_{timestamp}.png"
        page.screenshot(path=str(ss_path), full_page=False)
        print(f"📸 Screenshot: {ss_path.name}")
    except Exception as ss_err:
        ss_path = None
        print(colorize(f"⚠️ screenshot failed: {str(ss_err)[:60]}", "yellow"))

    # 4️⃣ JSON dump
    try:
        json_path = save_dir / f"{safe_label}_{timestamp}.json"
        json_path.write_text(
            json.dumps(
                {
                    "label": label,
                    "url": page.url,
                    "title": title,
                    "timestamp": datetime.now().isoformat(),
                    "elements": elements,
                    "screenshot": ss_path.name if ss_path else None,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"💾 JSON: {json_path.name}")
    except Exception as json_err:
        json_path = None
        print(colorize(f"⚠️ JSON save failed: {str(json_err)[:60]}", "yellow"))

    # 5️⃣ Print visible elements (interactive ones first)
    in_view = [e for e in elements if e["in_viewport"]]
    off_screen = [e for e in elements if not e["in_viewport"]]

    print(f"\n📊 Visible elements: {len(elements)} total")
    print(f"   ├── In viewport  : {len(in_view)}")
    print(f"   └── Off-screen   : {len(off_screen)}")

    # Sort: visible buttons/interactive আগে
    def sort_key(e):
        priority = 0
        if e["in_viewport"]:
            priority -= 1000  # in-viewport first
        if e["tag"] in ("BUTTON", "A"):
            priority -= 100
        if e["text"] or e["aria"]:
            priority -= 10
        return priority + e["bbox"]["y"]  # top-to-bottom

    sorted_elems = sorted(elements, key=sort_key)

    print(f"\n{'─' * 70}")
    print(colorize("🎯 INTERACTIVE ELEMENTS (top→bottom, in-viewport first)", "bold"))
    print(f"{'─' * 70}")

    for i, e in enumerate(sorted_elems[:40], 1):  # top 40
        mark = "✅" if e["in_viewport"] else "  "
        text = (e["text"] or "").strip()[:50]
        aria = (e["aria"] or "").strip()[:35]
        placeholder = (e["placeholder"] or "").strip()[:25]
        tag = e["tag"]
        bbox_str = f"({e['bbox']['x']},{e['bbox']['y']}) {e['bbox']['w']}x{e['bbox']['h']}"

        print(f"\n{mark} {colorize(f'#{i:>2}', 'bold')} [{colorize(tag, 'cyan')}] {bbox_str}")
        if text:
            print(f"      Text       : \"{text}\"")
        if aria:
            print(f"      Aria-label : \"{aria}\"")
        if placeholder:
            print(f"      Placeholder: \"{placeholder}\"")
        if e.get("type"):
            print(f"      Type       : {e['type']}")
        if e.get("href"):
            print(f"      Href       : {e['href'][:60]}")

    if len(sorted_elems) > 40:
        print(f"\n  ... {len(sorted_elems) - 40} more elements (full list in JSON)")

    # 6️⃣ Highlight likely Create buttons
    print(f"\n{'─' * 70}")
    print(colorize("💡 LIKELY 'CREATE NEW PROJECT' CANDIDATES", "bold"))
    print(f"{'─' * 70}")

    candidates = []
    keywords = [
        "create", "new", "নতুন", "project", "start", "begin", "compose",
        "তৈরি", "শুরু", "video", "flow", "agent", "+", "plus",
    ]

    for e in elements:
        combined = f"{e['text']} {e['aria']} {e['placeholder']}".lower()
        score = 0
        for kw in keywords:
            if kw.lower() in combined:
                score += 25
        if e["tag"] in ("BUTTON", "A"):
            score += 20
        if e["in_viewport"]:
            score += 15
        if e["bbox"]["w"] < 500:  # not full-width
            score += 5
        if 30 < e["bbox"]["w"] < 400 and 20 < e["bbox"]["h"] < 100:
            score += 10

        if score >= 30:
            candidates.append((score, e))

    candidates.sort(key=lambda x: -x[0])

    if not candidates:
        print(colorize("  ⚠️ কোনো clear 'Create' candidate পাওয়া যায়নি।", "yellow"))
        print(colorize("     হতে পারে:", "yellow"))
        print(colorize("     • Login required (browser-এ login করো)", "yellow"))
        print(colorize("     • Pricing/landing page এ আছো", "yellow"))
        print(colorize("     • Recent projects page এ already আছো", "yellow"))
    else:
        for i, (score, e) in enumerate(candidates[:5], 1):
            text = (e["text"] or "").strip()[:40] or "(no text)"
            aria = (e["aria"] or "").strip()[:30]
            sel_text = (e["text"] or e["aria"] or "").strip()
            sel = f'button:has-text("{sel_text}")' if e["tag"] == "BUTTON" else (
                f'a:has-text("{sel_text}")' if e["tag"] == "A" else f'[aria-label*="{sel_text}" i]'
            )
            print(f"\n  {colorize(f'#{i}', 'bold')} | Score: {colorize(f'{score}', 'green')}")
            print(f"      Tag    : {e['tag']}")
            print(f"      Text   : \"{text}\"")
            if aria:
                print(f"      Aria   : \"{aria}\"")
            print(f"      {colorize('Try:', 'cyan')} {colorize(sel, 'magenta')}")

    print(f"\n{'=' * 70}")
    return {
        "label": label,
        "url": page.url,
        "title": title,
        "elements": elements,
        "candidates": [{"score": s, **e} for s, e in candidates[:5]],
        "json_file": json_path.name if json_path else None,
        "screenshot": ss_path.name if ss_path else None,
    }


def run_steps_mode(browser, save_dir):
    """Step-by-step navigation + snapshot at each step"""
    page = browser.new_page()
    captures = []

    try:
        print(colorize("\n🚀 STEPS MODE — Flow editor পর্যন্ত navigate করো", "bold"))
        print("=" * 70)

        # Step 0: Default URL
        print(colorize("\n🌐 Step 0: Loading default URL...", "cyan"))
        try:
            page.goto(DEFAULT_URL, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(colorize(f"  ⚠️ load issue: {e}", "yellow"))
        time.sleep(5)
        captures.append(snapshot_page(page, "step0_landing", save_dir))

        # Step 1: Manual hint
        print(colorize("\n📌 Manual action দরকার হতে পারে:", "yellow"))
        print(colorize("   • Already logged in? Flow UI automatically load হবে।", "yellow"))
        print(colorize("   • Login দরকার? Browser-এ manually login করো।", "yellow"))
        print(colorize("   • তারপর Enter চাপো এই prompt এ, আমি snapshot নেব।", "yellow"))

        try:
            input("\n⏸️  Enter চাপো (Flow UI loaded হলে)...")
        except EOFError:
            print("  (auto-continuing in 10s)")
            time.sleep(10)

        captures.append(snapshot_page(page, "step1_after_login", save_dir))

        # Step 2: Try to find Create Project button
        print(colorize("\n🔍 Step 2: Create Project button খুঁজছি...", "cyan"))
        try:
            # Try several known selectors
            selectors_to_try = [
                'button:has-text("নতুন")',
                'button:has-text("New project")',
                'button:has-text("Create")',
                'button:has-text("Start")',
                'a:has-text("Create")',
            ]
            clicked = False
            for sel in selectors_to_try:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        print(f"  🎯 found: {sel}")
                        btn.click()
                        clicked = True
                        print(f"  ✅ clicked")
                        break
                except Exception:
                    continue
            if not clicked:
                print(colorize("  ⚠️ auto-click ব্যর্থ — manually click করো browser এ", "yellow"))
                try:
                    input("⏸️  Enter চাপো (editor open হলে)...")
                except EOFError:
                    time.sleep(10)
        except Exception as e:
            print(colorize(f"  ⚠️ {e}", "yellow"))

        time.sleep(5)
        captures.append(snapshot_page(page, "step2_after_create_click", save_dir))

        # Step 3: Wait for editor
        print(colorize("\n🎬 Step 3: Editor loaded snapshot...", "cyan"))
        time.sleep(3)
        captures.append(snapshot_page(page, "step3_editor", save_dir))

        # Final summary
        print(colorize("\n📊 CAPTURE SUMMARY", "bold"))
        print("=" * 70)
        for cap in captures:
            n = len(cap.get("elements", []))
            cand_n = len(cap.get("candidates", []))
            print(f"  {cap['label']:<30} | {n:>3} elements | {cand_n} create candidates")
            print(f"    URL: {cap['url']}")
            print(f"    JSON: {cap.get('json_file')}")

    except KeyboardInterrupt:
        print(colorize("\n⛔ User interrupted", "yellow"))
    finally:
        pass

    return captures


def run_simple_mode(browser, url, save_dir):
    """Simple mode — just load URL, snapshot, exit"""
    page = browser.new_page()
    try:
        print(colorize(f"\n🌐 Loading: {url}", "cyan"))
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(colorize(f"  ⚠️ {e}", "yellow"))
        time.sleep(5)
        snapshot_page(page, "simple_load", save_dir)
    except KeyboardInterrupt:
        print(colorize("\n⛔ User interrupted", "yellow"))


def main():
    parser = argparse.ArgumentParser(description="Flow Explorer — diagnostic-only mode")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="URL to load")
    parser.add_argument("--steps", action="store_true", help="Step-by-step navigation mode")
    args = parser.parse_args()

    print("=" * 70)
    print(colorize("🌐 FLOW EXPLORER — Diagnostic Mode", "bold"))
    print("=" * 70)
    print(f"🎯 Mode: {'Steps' if args.steps else 'Simple'}")
    print(f"🌐 URL : {args.url}")
    print(f"📁 Save: {SAVE_DIR.absolute()}")
    print(f"🌐 Proxy: {PROXY or '(none)'}")
    print("=" * 70)
    print(colorize("ℹ️  Browser-এ login থাকলে automatically logged in detect হবে।", "cyan"))
    print(colorize("ℹ️  কোনো credentials এই tool এ লাগবে না।", "cyan"))
    print(colorize("ℹ️  Video generate হবে না। শুধু UI inspect করবে।", "cyan"))
    print("=" * 70)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    # ─── Launch browser ───
    print(colorize("\n🌐 CloakBrowser launching...", "cyan"))
    launch_kwargs = {
        "headless": HEADLESS,
        "humanize": HUMANIZE,
    }
    if PROXY:
        launch_kwargs["proxy"] = PROXY
        launch_kwargs["geoip"] = True

    browser = launch(**launch_kwargs)

    try:
        if args.steps:
            run_steps_mode(browser, SAVE_DIR)
        else:
            run_simple_mode(browser, args.url, SAVE_DIR)

    except KeyboardInterrupt:
        print(colorize("\n\n⛔ User interrupted — exiting", "yellow"))
    finally:
        try:
            browser.close()
        except Exception:
            pass
        print(colorize("\n👋 Browser closed", "green"))
        print(colorize(f"📁 All artifacts saved in: {SAVE_DIR}", "cyan"))
        print(colorize(f"💡 JSON files diagnose_report.py দিয়ে analyze করতে পারো:", "cyan"))
        print(colorize(f"   python diagnose_report.py --list", "cyan"))


if __name__ == "__main__":
    main()