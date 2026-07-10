"""
Google Flow Video Generation Bot — CloakBrowser
স্বয়ংক্রিয়ভাবে Google Flow-এ লগইন করে নতুন প্রজেক্ট তৈরি করে,
প্রম্পট দিয়ে ভিডিও জেনারেট করে এবং ডাউনলোড করে।

ব্যবহার:
    1. .env ফাইলে পাসওয়ার্ড ও প্রম্পট দিন
    2. python google_flow_bot.py
    3. ব্রাউজারে সব অটোমেটিক হবে
"""

import os
import time
import json
import random
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from cloakbrowser import launch

# ─── .env থেকে সেটিংস লোড ───
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print("❌ .env ফাইল পাওয়া যায়নি!")
    print("📄 .env.example কপি করে .env তৈরি করুন")
    exit(1)

LOGIN_URL = os.getenv("LOGIN_URL", "https://labs.google/fx/tools/flow")
USER_ID = os.getenv("USER_ID", "")
PASSWORD = os.getenv("PASSWORD", "")
VIDEO_PROMPT = os.getenv("VIDEO_PROMPT", "A cinematic sunset over the ocean with gentle waves")
SAVE_DIR = os.getenv("SAVE_DIR", "./downloads")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
HUMANIZE = os.getenv("HUMANIZE", "true").lower() == "true"
PROXY = os.getenv("PROXY", "")

if not all([USER_ID, PASSWORD]):
    print("❌ .env ফাইলে USER_ID এবং PASSWORD সেট করুন!")
    exit(1)

# ডাউনলোড ফোল্ডার তৈরি
save_path = Path(__file__).parent / SAVE_DIR
save_path.mkdir(parents=True, exist_ok=True)


def wait_and_click(page, selector, timeout=15000, description=""):
    """এলিমেন্ট খুঁজে ক্লিক করে"""
    if description:
        print(f"  🔍 {description} খুঁজছি...")
    try:
        el = page.locator(selector).first
        el.wait_for(state="visible", timeout=timeout)
        time.sleep(0.5)
        el.click()
        if description:
            print(f"  ✅ {description} ক্লিক হয়েছে")
        return True
    except Exception as e:
        if description:
            print(f"  ⚠️ {description} পাওয়া যায়নি: {str(e)[:80]}")
        return False


def safe_diagnose(page, reason="unknown", save_dir=None):
    """
    🔍 বট-ডিটেকশন-সেফ ডায়াগনস্টিক — শুধু ফেইল মোডে কল হয়।

    কেন safe:
      • Random human-like delay (2-5 sec) আগে — মানুষ pause নেয়
      • শুধু visible + interactive elements (hidden গুলো query করলে suspicious)
      • CDP-level browser-context JS — remote detection hard
      • শুধু failure mode এ trigger — pattern recognition এ "diagnose" হিসেবে ধরা পড়বে না
      • Output local JSON-এ — server-এ কিছু যায় না
      • screenshot + elements snapshot একসাথে — পরে analyze করা যায়

    Args:
        page: Playwright page object
        reason: কোন step এ ফেইল হয়েছে (e.g. "step3_no_create_button")
        save_dir: কোথায় save হবে (default: global save_path)

    Returns:
        dict: snapshot data (elements + url + reason + timestamp)
    """
    target_dir = save_dir or save_path

    # 1️⃣ Random human-like delay (2-5 sec) — মানুষ pause নেয়
    delay = random.uniform(2.0, 5.0)
    print(f"  🔍 ডায়াগনস্টিক শুরু (random pause {delay:.1f}s — মানুষের মতো)...")
    time.sleep(delay)

    timestamp = datetime.now().isoformat()

    # 2️⃣ শুধু visible + interactive elements query
    snapshot = {"reason": reason, "url": page.url, "timestamp": timestamp, "elements": []}

    try:
        snapshot["elements"] = page.evaluate(
            """
            () => {
                const elements = document.querySelectorAll(
                    'button, a, input, textarea, [role="button"], [contenteditable="true"], select'
                );
                return Array.from(elements)
                    .filter(el => {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        return rect.width > 0 &&
                               rect.height > 0 &&
                               style.visibility !== 'hidden' &&
                               style.display !== 'none' &&
                               style.opacity !== '0';
                    })
                    .map(el => ({
                        tag: el.tagName,
                        text: (el.innerText || el.value || '').slice(0, 80),
                        aria: el.getAttribute('aria-label') || '',
                        role: el.getAttribute('role') || '',
                        type: el.getAttribute('type') || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        name: el.getAttribute('name') || '',
                        classes: (typeof el.className === 'string' ? el.className : '').slice(0, 60),
                        bbox: {
                            x: Math.round(el.getBoundingClientRect().x),
                            y: Math.round(el.getBoundingClientRect().y),
                            w: Math.round(el.getBoundingClientRect().width),
                            h: Math.round(el.getBoundingClientRect().height)
                        }
                    }));
            }
            """
        )
    except Exception as js_err:
        snapshot["js_error"] = str(js_err)[:200]
        print(f"  ⚠️ DOM snapshot ব্যর্থ: {str(js_err)[:80]}")

    # 3️⃣ Screenshot সেভ (full page)
    try:
        screenshot_path = target_dir / f"diag_{reason}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path), full_page=False)
        snapshot["screenshot"] = str(screenshot_path.name)
        print(f"  📸 ডায়াগনস্টিক স্ক্রিনশট: {screenshot_path.name}")
    except Exception as ss_err:
        snapshot["screenshot_error"] = str(ss_err)[:200]

    # 4️⃣ JSON dump — local only
    try:
        json_path = target_dir / f"diag_{reason}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
        print(f"  💾 ডায়াগনস্টিক JSON: {json_path.name}")
    except Exception as json_err:
        print(f"  ⚠️ JSON dump ব্যর্থ: {str(json_err)[:80]}")

    print(f"  ✅ ডায়াগনস্টিক সম্পন্ন — {len(snapshot.get('elements', []))}টি visible element পাওয়া গেছে")
    return snapshot


def safe_input(prompt=""):
    """ব্যাকগ্রাউন্ডে চললে input() EOFError দেয় — এটা সেফলি হ্যান্ডেল করে"""
    try:
        return input(prompt)
    except EOFError:
        print("(ব্যাকগ্রাউন্ড মোড — Enter ছাড়াই এগিয়ে যাচ্ছি)")
        return ""


def wait_for_page(page, url_contains, timeout=30000):
    """নির্দিষ্ট URL লোড হওয়া পর্যন্ত অপেক্ষা করে"""
    print(f"  ⏳ পেজ লোড হচ্ছে ({url_contains})...")
    start = time.time()
    while time.time() - start < timeout / 1000:
        if url_contains in page.url:
            print(f"  ✅ পেজ লোড হয়েছে: {page.url[:80]}")
            return True
        time.sleep(0.5)
    print(f"  ⚠️ টাইমআউট! বর্তমান URL: {page.url[:80]}")
    return False


# ─── Run-level state for step-by-step comparison ───
_current_run_state = {
    "run_id": None,
    "started_at": None,
    "step_captures": [],   # প্রতিটা step এর metadata
}


def _init_run_state():
    """প্রতিটা bot run এর জন্য unique run_id তৈরি করো"""
    _current_run_state["run_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
    _current_run_state["started_at"] = datetime.now().isoformat()
    _current_run_state["step_captures"] = []
    # Run-level folder তৈরি
    run_dir = save_path / f"run_{_current_run_state['run_id']}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def step_change_capture(page, step_name, step_num, save_dir=None):
    """
    📸 প্রতিটা step এর পরে cropped screenshot + metadata সেভ করো।
    পরবর্তী run এ এই function আবার কল হলে previous run এর সাথে compare করে delta দেখায়।

    সেভ করে:
      • run_{run_id}/step_{num}_{name}.png  — full-page screenshot
      • run_{run_id}/step_{num}_{name}_crop.png  — interactive elements area cropped
      • run_{run_id}/step_{num}_{name}.json  — elements + metadata
      • run_{run_id}/_run_meta.json  — overall run summary

    Returns:
        dict: capture metadata (also stored in _current_run_state)
    """
    run_dir = save_dir or save_path / f"run_{_current_run_state['run_id']}"
    run_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H%M%S")
    safe_step = step_name.replace(" ", "_").replace("/", "-")

    capture = {
        "step_num": step_num,
        "step_name": step_name,
        "timestamp": datetime.now().isoformat(),
        "url": page.url,
        "title": "",
        "elements_count": 0,
        "screenshot": "",
        "crop": "",
        "elements_json": "",
        "previous_compare": None,  # delta vs previous run
    }

    # 1️⃣ Page title
    try:
        capture["title"] = page.title()[:80]
    except Exception:
        pass

    # 2️⃣ Visible elements snapshot
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
                    .map(el => ({
                        tag: el.tagName,
                        text: (el.innerText || el.value || '').slice(0, 60),
                        aria: el.getAttribute('aria-label') || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        type: el.getAttribute('type') || '',
                        role: el.getAttribute('role') || '',
                        classes: (typeof el.className === 'string' ? el.className : '').slice(0, 50)
                    }));
            }
            """
        )
        capture["elements_count"] = len(elements)
    except Exception as js_err:
        elements = []
        print(f"  ⚠️ element snapshot ব্যর্থ: {str(js_err)[:60]}")

    # 3️⃣ Full-page screenshot
    try:
        ss_path = run_dir / f"step{step_num:02d}_{safe_step}_{timestamp}.png"
        page.screenshot(path=str(ss_path), full_page=False)
        capture["screenshot"] = ss_path.name
    except Exception as ss_err:
        print(f"  ⚠️ screenshot ব্যর্থ: {str(ss_err)[:60]}")

    # 4️⃣ Interactive area crop (viewport এর মাঝখান + interactive elements area)
    try:
        crop_path = run_dir / f"step{step_num:02d}_{safe_step}_{timestamp}_crop.png"
        # ব্রাউজার viewport এর interactive area clip করো
        viewport = page.viewport_size or {"width": 1280, "height": 720}
        page.screenshot(
            path=str(crop_path),
            clip={
                "x": 0,
                "y": max(0, viewport["height"] // 4),
                "width": viewport["width"],
                "height": viewport["height"] // 2,
            },
        )
        capture["crop"] = crop_path.name
    except Exception as crop_err:
        # fallback — viewport size না পেলে element bbox থেকে বের করো
        try:
            if elements:
                # শুধু visible elements এর union bbox
                bboxes = page.evaluate(
                    """
                    () => {
                        const sels = 'button, a, input, textarea, [role="button"]';
                        const rects = Array.from(document.querySelectorAll(sels))
                            .map(el => el.getBoundingClientRect())
                            .filter(r => r.width > 0 && r.height > 0);
                        if (!rects.length) return null;
                        const minX = Math.min(...rects.map(r => r.x));
                        const minY = Math.min(...rects.map(r => r.y));
                        const maxX = Math.max(...rects.map(r => r.x + r.width));
                        const maxY = Math.max(...rects.map(r => r.y + r.height));
                        return {x: minX, y: minY, width: maxX - minX, height: maxY - minY};
                    }
                    """
                )
                if bboxes and bboxes.get("width", 0) > 0:
                    crop_path = run_dir / f"step{step_num:02d}_{safe_step}_{timestamp}_crop.png"
                    page.screenshot(path=str(crop_path), clip=bboxes)
                    capture["crop"] = crop_path.name
        except Exception:
            pass

    # 5️⃣ Elements JSON
    try:
        elem_path = run_dir / f"step{step_num:02d}_{safe_step}_{timestamp}.json"
        elem_path.write_text(
            json.dumps(
                {"capture": capture, "elements": elements},
                indent=2,
                default=str,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        capture["elements_json"] = elem_path.name
    except Exception:
        pass

    # 6️⃣ Compare with previous run (যদি থাকে)
    capture["previous_compare"] = _compare_with_previous_run(capture, elements)

    # 7️⃣ Run-meta update
    _current_run_state["step_captures"].append(capture)
    try:
        meta_path = run_dir / "_run_meta.json"
        meta_path.write_text(
            json.dumps(_current_run_state, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

    # Summary print
    delta_note = ""
    if capture["previous_compare"] and capture["previous_compare"].get("status") == "diff":
        d = capture["previous_compare"]
        delta_note = f" | Δ +{d['added']}/-{d['removed']}/~{d['changed']}"
    print(f"  📸 Step {step_num} captured ({capture['elements_count']} elements){delta_note}")

    return capture


def _compare_with_previous_run(current_capture, current_elements):
    """
    এই step এর জন্য সবচেয়ে recent previous run খোঁজো এবং element diff বের করো।

    Returns:
        dict | None: {status, added, removed, changed, samples} বা None (প্রথম run)
    """
    if not _current_run_state["run_id"]:
        return None

    current_run_id = _current_run_state["run_id"]
    step_num = current_capture["step_num"]
    step_name = current_capture["step_name"]

    # সব run folder scan (lexical order = chronological mostly)
    all_runs = sorted(
        [p for p in save_path.iterdir() if p.is_dir() and p.name.startswith("run_")],
        key=lambda p: p.name,
    )

    # শুধু previous run গুলো (current বাদ)
    previous_runs = [r for r in all_runs if r.name != f"run_{current_run_id}"]
    if not previous_runs:
        return {"status": "first_run", "message": "এই প্রথম run — previous data নেই"}

    latest_prev = previous_runs[-1]
    # একই step এর JSON খোঁজো (same step_num)
    prev_step_files = sorted(latest_prev.glob(f"step{step_num:02d}_*.json"))
    # _run_meta বাদ
    prev_step_files = [f for f in prev_step_files if "_run_meta" not in f.name]
    if not prev_step_files:
        return {
            "status": "no_previous_step",
            "message": f"previous run-এ step {step_num} এর data নেই",
            "previous_run": latest_prev.name,
        }

    prev_step_file = prev_step_files[-1]
    try:
        prev_data = json.loads(prev_step_file.read_text(encoding="utf-8"))
        prev_elements = prev_data.get("elements", [])
    except Exception:
        return {"status": "read_error", "previous_run": latest_prev.name}

    # Element signature: (tag, text, aria, placeholder, type)
    def sig(e):
        return (
            e.get("tag", ""),
            (e.get("text") or "").strip(),
            (e.get("aria") or "").strip(),
            (e.get("placeholder") or "").strip(),
            e.get("type", ""),
        )

    prev_sigs = {sig(e): e for e in prev_elements}
    curr_sigs = {sig(e): e for e in current_elements}

    added = [curr_sigs[s] for s in curr_sigs if s not in prev_sigs]
    removed = [prev_sigs[s] for s in prev_sigs if s not in curr_sigs]
    changed = []

    for s in curr_sigs:
        if s in prev_sigs:
            prev_classes = (prev_sigs[s].get("classes") or "").strip()
            curr_classes = (curr_sigs[s].get("classes") or "").strip()
            if prev_classes != curr_classes:
                changed.append(
                    {
                        "signature": s,
                        "prev_classes": prev_classes,
                        "curr_classes": curr_classes,
                    }
                )

    return {
        "status": "diff" if (added or removed or changed) else "same",
        "previous_run": latest_prev.name,
        "previous_step_file": prev_step_file.name,
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "added_samples": [{"text": a.get("text", "")[:40], "aria": a.get("aria", "")[:30]} for a in added[:3]],
        "removed_samples": [{"text": r.get("text", "")[:40], "aria": r.get("aria", "")[:30]} for r in removed[:3]],
        "changed_samples": changed[:3],
    }


def step1_land_and_login(page):
    """ধাপ ১: ল্যান্ডিং পেজ → "Create with Google Flow" ক্লিক → Google লগইন"""
    print("\n" + "=" * 50)
    print("🚀 ধাপ ১: সাইটে যাচ্ছি...")
    print("=" * 50)

    try:
        page.goto(LOGIN_URL, timeout=90000, wait_until="domcontentloaded")
    except Exception as nav_err:
        print(f"  ⚠️ প্রথম লোড সমস্যা: {nav_err} — আবার চেষ্টা করছি (load mode)...")
        try:
            page.goto(LOGIN_URL, timeout=60000, wait_until="load")
        except Exception as nav_err2:
            print(f"  ❌ পেজ লোড হচ্ছে না: {nav_err2}")
    time.sleep(5)

    # 📸 Step 1 capture (initial landing page state)
    step_change_capture(page, step_name="landing_page", step_num=1)

    # "Create with Google Flow" বাটন ক্লিক
    clicked = wait_and_click(
        page,
        'button:has-text("Create with Google Flow"), button:has-text("Try Google Flow")',
        timeout=10000,
        description="Create with Google Flow বাটন"
    )

    if not clicked:
        # অন্য বাটন ট্রাই করি
        clicked = wait_and_click(
            page,
            'a:has-text("Get started"), button:has-text("Get started")',
            timeout=5000,
            description="Get started বাটন"
        )

    if not clicked:
        print("❌ Create/Get started বাটন পাওয়া যায়নি!")
        page.screenshot(path=str(save_path / "error_landing.png"))
        # 🔍 ডায়াগনস্টিক — landing page-এ কী কী interactive element আছে দেখি
        safe_diagnose(page, reason="step1_no_create_button")
        return False

    time.sleep(3)

    # 📸 Step 1 capture (after create button click — should now be on sign-in or app)
    step_change_capture(page, step_name="after_create_click", step_num=1)

    # Google লগইন পেজ এসেছে কিনা চেক — accounts.google.com অথবা সরাসরি Flow-তে (যদি আগে লগইন থাকে)
    if "accounts.google.com" in page.url:
        print(f"  ✅ Google লগইন পেজে এসেছি: {page.url[:60]}...")
        return True
    elif "labs.google" in page.url:
        print(f"  ⚠️ এখনো Flow পেজে আছি — হয়তো আগে থেকেই লগইন আছে। ইমেইল ফিল্ড খুঁজে দেখি...")
        # Flow পেজে থাকলে ইমেইল ফিল্ড থাকলে True, না থাকলে True (পরের ধাপে দেখবে)
        return True
    else:
        print(f"  ⚠️ অজানা URL: {page.url[:80]}... তবে এগিয়ে যাচ্ছি (পরের ধাপে ইমেইল ফিল্ড খুঁজবে)")
        return True  # বরং এগিয়ে যাই, পরের ধাপে বুঝবে

    time.sleep(3)

    # Google লগইন পেজ এসেছে কিনা চেক — accounts.google.com অথবা সরাসরি Flow-তে (যদি আগে লগইন থাকে)
    if "accounts.google.com" in page.url:
        print(f"  ✅ Google লগইন পেজে এসেছি: {page.url[:60]}...")
        return True
    elif "labs.google" in page.url:
        print(f"  ⚠️ এখনো Flow পেজে আছি — হয়তো আগে থেকেই লগইন আছে। ইমেইল ফিল্ড খুঁজে দেখি...")
        # Flow পেজে থাকলে ইমেইল ফিল্ড থাকলে True, না থাকলে True (পরের ধাপে দেখবে)
        return True
    else:
        print(f"  ⚠️ অজানা URL: {page.url[:80]}... তবে এগিয়ে যাচ্ছি (পরের ধাপে ইমেইল ফিল্ড খুঁজবে)")
        return True  # বরং এগিয়ে যাই, পরের ধাপে বুঝবে


def step2_google_signin(page):
    """ধাপ ২: Google এ সাইন ইন (ইমেইল → পাসওয়ার্ড)। আগে থেকে logged in থাকলে skip করে।"""
    print("\n" + "=" * 50)
    print("🔑 ধাপ ২: Google সাইন ইন...")
    print("=" * 50)

    # ── 🆕 আগে থেকে logged in কিনা detect করো ──
    try:
        email_visible = page.locator('input[type="email"], input[name="identifier"]').first.is_visible(timeout=3000)
    except Exception:
        email_visible = False

    if not email_visible:
        # Email field নেই → সম্ভবত আগে থেকেই logged in, বা অন্য পেজে আছি
        # Flow UI element আছে কিনা দেখো (project button, prompt input ইত্যাদি)
        try:
            flow_already_loaded = page.locator(
                'button:has-text("নতুন"), button:has-text("New project"), button:has-text("Create"), textarea'
            ).first.is_visible(timeout=2000)
        except Exception:
            flow_already_loaded = False

        if flow_already_loaded:
            print("  ✅ আগে থেকেই logged in — Flow UI visible। Step 2 skip করছি...")
            step_change_capture(page, step_name="already_signed_in", step_num=2)
            return True

        # Email নেই, Flow UI-ও নেই — হয়তো consent screen বা অন্য কিছু
        print("  ⚠️ Email field নেই, Flow UI-ও নেই — পেজ state unclear")
        page.screenshot(path=str(save_path / "error_no_login_form.png"))
        safe_diagnose(page, reason="step2_no_login_form")
        # তবুও এগিয়ে যাই — পরের step গুলো handle করবে
        return True

    # ── ইমেইল দেওয়া ──
    print("  ✏️ ইমেইল দেওয়া হচ্ছে...")
    try:
        email_field = page.locator('input[type="email"], input[name="identifier"]').first
        email_field.wait_for(state="visible", timeout=15000)
        email_field.type(USER_ID, delay=80)
        time.sleep(0.5)
        print(f"  ✅ ইমেইল দেওয়া হয়েছে: {USER_ID}")
    except Exception as e:
        print(f"  ⚠️ ইমেইল ফিল্ড পাওয়া যায়নি: {e}")
        page.screenshot(path=str(save_path / "error_email.png"))
        # 🔍 ডায়াগনস্টিক — কী কী input আছে দেখি
        safe_diagnose(page, reason="step2_no_email_field")
        return False

    # Next বাটন ক্লিক
    wait_and_click(page, '#identifierNext, button:has-text("Next")', description="Next বাটন (ইমেইল)")
    time.sleep(2)

    # 📸 Step 2 capture (after email submitted — should now ask for password)
    step_change_capture(page, step_name="password_page", step_num=2)

    # ── পাসওয়ার্ড দেওয়া ──
    print("  🔐 পাসওয়ার্ড দেওয়া হচ্ছে...")
    try:
        pass_field = page.locator('input[type="password"], input[name="Passwd"]').first
        pass_field.wait_for(state="visible", timeout=15000)
        pass_field.type(PASSWORD, delay=60)
        time.sleep(0.5)
        print("  ✅ পাসওয়ার্ড দেওয়া হয়েছে")
    except Exception as e:
        print(f"  ⚠️ পাসওয়ার্ড ফিল্ড পাওয়া যায়নি: {e}")
        page.screenshot(path=str(save_path / "error_password.png"))
        # 🔍 ডায়াগনস্টিক
        safe_diagnose(page, reason="step2_no_password_field")
        return False

    # Next বাটন ক্লিক (পাসওয়ার্ড)
    wait_and_click(page, '#passwordNext, button:has-text("Next")', description="Next বাটন (পাসওয়ার্ড)")
    time.sleep(3)

    # কনসেন্ট স্ক্রিন থাকলে "Continue" ক্লিক
    wait_and_click(page, 'button:has-text("Continue"), button:has-text("Accept")', timeout=5000, description="Consent Continue")
    time.sleep(3)

    # 📸 Step 2 capture (after full sign-in — should now be in Flow app)
    step_change_capture(page, step_name="after_signin", step_num=2)

    return True


def step3_create_project(page):
    """ধাপ ৩: Google Flow ক্যারাউজেল থেকে "+ নতুন প্রজেক্ট" বা কোনো Create বাটনে ক্লিক"""
    print("\n" + "=" * 50)
    print("📂 ধাপ ৩: নতুন প্রজেক্ট তৈরি...")
    print("=" * 50)

    # Google Flow অ্যাপ লোড হওয়া পর্যন্ত অপেক্ষা
    print("  ⏳ Google Flow লোড হচ্ছে...")
    time.sleep(7)

    # ── UI অনুযায়ী আপডেট করা সিলেক্টর তালিকা ──
    # স্ক্রিনশট অনুযায়ী: "+ নতুন প্রজেক্ট" বাটন মাঝখানে, ক্যারাউজেলে একাধিক স্লাইড
    clicked = False
    flow_selectors = [
        # বাংলা বাটন — মূল প্রবেশদ্বার
        # 🚀 exact aria-label first (Material icon text hallucination-proof)
        'button[aria-label="নতুন প্রজেক্ট"]',
        'button[aria-label="নতুন"]',
        'button[aria-label="New project"]',
        'button[aria-label="New"]',
        'button:has-text("নতুন প্রজেক্ট")',
        'button:has-text("+ নতুন প্রজেক্ট")',
        'button[aria-label*="নতুন"]',
        'button[aria-label*="New project" i]',
        'button[aria-label*="Create" i]',
        # ইংরেজি / সাধারণ বাটন
        'button:has-text("Try the Google Flow Agent")',
        'button:has-text("Create a character")',
        'button:has-text("Create New")',
        'button:has-text("Create new")',
        'button:has-text("New project")',
        'button:has-text("New Project")',
        'button:has-text("Start")',
        'a:has-text("Create")',
        'a:has-text("Start")',
        # আইকন / div বাটন
        'button[aria-label="Create"]',
        'button[aria-label="New"]',
        '[role="button"]:has-text("Create")',
        '[role="button"]:has-text("নতুন")',
        'div[role="button"]',
    ]

    for selector_text in flow_selectors:
        clicked = wait_and_click(page, selector_text, timeout=4000, description=f"Create বাটন ({selector_text[:50]})")
        if clicked:
            break

    if not clicked:
        # শেষ চেষ্টা — সব বাটন ডায়াগনস্টিক ডাম্প + "+" বাটন খোঁজা
        try:
            all_buttons = page.locator("button").all()
            print(f"  🔍 শেষ চেষ্টা: পেজে {len(all_buttons)}টি বাটন আছে, ডায়াগনস্টিক ডাম্প:")
            # ─── ডায়াগনস্টিক: সব বাটনের তথ্য প্রিন্ট ───
            for i, btn in enumerate(all_buttons):
                try:
                    txt = (btn.inner_text() or "").replace("\n", " | ").strip()
                    aria = btn.get_attribute("aria-label") or ""
                    cls = btn.get_attribute("class") or ""
                    print(f"      [{i}] text='{txt[:50]}' aria='{aria[:40]}' class='{cls[:30]}'")
                except Exception:
                    pass

            # নতুন প্রজেক্ট বাটন — ক্লাসে "new" বা aria-label এ "+" থাকতে পারে
            print("  🔍 এখন '+ নতুন প্রজেক্ট' বাটন খুঁজছি...")
            for btn in all_buttons:
                try:
                    txt = (btn.inner_text() or "")
                    aria = (btn.get_attribute("aria-label") or "")
                    combined = (txt + " " + aria).lower()
                    # ফ্লোটিং অ্যাকশন বাটন — সাধারণত শুধু "+" চিহ্ন থাকে
                    has_plus = "+" in txt or "+" in aria or "plus" in combined
                    has_new_word = "নতুন" in txt or "new project" in combined
                    if (has_plus and has_new_word) or ("+ নতুন" in txt):
                        btn.click()
                        clicked = True
                        print(f"  ✅ '+ নতুন প্রজেক্ট' বাটনে ক্লিক হয়েছে (text='{txt[:30]}', aria='{aria[:30]}')")
                        break
                except Exception:
                    continue

            if not clicked:
                print("  ⚠️ '+ নতুন প্রজেক্ট' বাটন নির্দিষ্টভাবে পাওয়া যায়নি")
        except Exception as e:
            print(f"  ⚠️ ফলব্যাক ত্রুটি: {e}")

    if not clicked:
        print("  ⚠️ Create New বাটন পাওয়া যায়নি — হয়তো ইতিমধ্যে কোনো প্রজেক্ট খোলা আছে")
        print("  📸 স্ক্রিনশট সেভ হচ্ছে...")
        page.screenshot(path=str(save_path / "after_login.png"))
        # 🔍 ডায়াগনস্টিক — Flow homepage-এ কী কী interactive element আছে দেখি
        safe_diagnose(page, reason="step3_no_create_button")
        return True  # এগিয়ে যাই, হয়তো সরাসরি প্রম্পট দেওয়া যাবে

    time.sleep(3)
    # 📸 Step 3 capture (after create button click — should now be in editor)
    step_change_capture(page, step_name="after_create_project", step_num=3)
    return True


def step4_enter_prompt(page):
    """ধাপ ৪: ভিডিও জেনারেশন প্রম্পট দেওয়া"""
    print("\n" + "=" * 50)
    print("🎬 ধাপ ৪: প্রম্পট দেওয়া...")
    print("=" * 50)

    # 📸 Step 4 capture (editor page — should have prompt input visible)
    step_change_capture(page, step_name="editor_page", step_num=4)

    # টেক্সট এরিয়া / প্রম্পট বক্স খোঁজা
    print(f"  ✏️ প্রম্পট: \"{VIDEO_PROMPT}\"")

    try:
        # বিভিন্ন সম্ভাব্য প্রম্পট ফিল্ড ট্রাই করা
        prompt_selectors = [
            # সবচেয়ে সাধারণ — textarea
            'textarea',
            # Google Flow-স্টাইল ক্যারাউজেল ইনপুট
            'textarea[aria-label*="prompt" i]',
            'textarea[aria-label*="Describe" i]',
            'textarea[aria-label*="video" i]',
            'textarea[placeholder*="prompt" i]',
            'textarea[placeholder*="Describe" i]',
            'textarea[placeholder*="video" i]',
            # contenteditable (Gemini / Flow স্টাইল)
            'div[contenteditable="true"]',
            'div[contenteditable="true"][aria-label*="prompt" i]',
            # input বক্স
            'input[type="text"][placeholder*="prompt" i]',
            'input[type="text"][placeholder*="Describe" i]',
            # ARIA roles
            'div[role="textbox"]',
            '[aria-label="Prompt"]',
            '[aria-label="prompt"]',
            '[aria-label*="Prompt" i]',
            # সর্বশেষ চেষ্টা — যেকোনো বড় textarea
        ]

        prompt_typed = False
        for sel in prompt_selectors:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=4000)
                el.click()
                time.sleep(0.5)
                el.type(VIDEO_PROMPT, delay=40)
                prompt_typed = True
                print(f"  ✅ প্রম্পট দেওয়া হয়েছে ({sel})")
                break
            except:
                continue

        if not prompt_typed:
            print("  ⚠️ প্রম্পট ফিল্ড পাওয়া যায়নি — স্ক্রিনশট সেভ হচ্ছে...")
            page.screenshot(path=str(save_path / "error_prompt.png"))
            # 🔍 ডায়াগনস্টিক — কোন ধরনের input/textarea আছে দেখি
            safe_diagnose(page, reason="step4_no_prompt_field")
            return False

    except Exception as e:
        print(f"  ⚠️ প্রম্পট দেওয়ায় সমস্যা: {e}")
        page.screenshot(path=str(save_path / "error_prompt.png"))
        return False

    time.sleep(1)

    # Generate / Create / Submit বাটন ক্লিক
    for btn_text in [
        'button:has-text("Generate")',
        'button:has-text("Create")',
        'button:has-text("Generate video")',
        'button:has-text("Create video")',
        'button:has-text("Go")',
        'button:has-text("Run")',
    ]:
        if wait_and_click(page, btn_text, timeout=3000, description=f"Generate বাটন ({btn_text})"):
            break

    time.sleep(2)
    # 📸 Step 5 capture (after generate button click — generation should be starting)
    step_change_capture(page, step_name="after_generate_click", step_num=5)

    return True


def step5_wait_and_download(page):
    """ধাপ ৫: ভিডিও জেনারেশন শেষ হওয়া পর্যন্ত অপেক্ষা এবং ডাউনলোড"""
    print("\n" + "=" * 50)
    print("⏳ ধাপ ৫: ভিডিও জেনারেশন চলছে...")
    print("=" * 50)
    print("  🎬 এটি কয়েক মিনিট সময় নিতে পারে...")

    # ৫ মিনিট পর্যন্ত অপেক্ষা
    max_wait = 300  # seconds
    start = time.time()
    download_found = False

    while time.time() - start < max_wait:
        elapsed = int(time.time() - start)
        print(f"  ⏱️  {elapsed}s অতিবাহিত...")

        # ডাউনলোড / সেভ বাটন চেক করা
        for btn_text in [
            'button:has-text("Download")',
            'button:has-text("Save")',
            'button:has-text("Export")',
            'a:has-text("Download")',
            '[aria-label="Download"]',
            '[aria-label="Save"]',
        ]:
            try:
                el = page.locator(btn_text).first
                if el.is_visible(timeout=1000):
                    el.click()
                    download_found = True
                    print(f"  📥 Download বাটন পাওয়া গেছে! ডাউনলোড শুরু...")
                    break
            except:
                continue

        if download_found:
            break

        # লোডিং শেষ হয়েছে কিনা চেক (progress bar / spinner চলছে কিনা)
        time.sleep(10)

    # স্ক্রিনশট সেভ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_file = save_path / f"flow_result_{timestamp}.png"
    page.screenshot(path=str(screenshot_file))
    print(f"  📸 স্ক্রিনশট সেভ হয়েছে: {screenshot_file}")

    # 📸 Step 5 final capture (final state — generated video or wait timeout)
    step_change_capture(
        page,
        step_name="after_generation" if download_found else "generation_timeout",
        step_num=5,
    )

    # 🔍 ডায়াগনস্টিক — যদি download button একদম না পাওয়া যায়, কী কী button আছে দেখি
    if not download_found:
        safe_diagnose(page, reason="step5_no_download_button")

    # ডাউনলোড ফোল্ডারে ফাইল চেক
    downloaded = list(save_path.glob("*.mp4")) + list(save_path.glob("*.webm"))
    if downloaded:
        print(f"  ✅ ডাউনলোড হয়েছে: {[f.name for f in downloaded]}")
    elif download_found:
        print("  ✅ ডাউনলোড বাটন ক্লিক হয়েছে — ফাইল ডাউনলোড ফোল্ডারে চেক করুন")
    else:
        print("  ⚠️ ডাউনলোড বাটন পাওয়া যায়নি — ব্রাউজারে ম্যানুয়ালি ডাউনলোড করুন")

    return True


def main():
    print("=" * 50)
    print("🎬 Google Flow Video Bot")
    print("   CloakBrowser — Stealth Chromium")
    print("=" * 50)
    print(f"📧 ইউজার: {USER_ID}")
    print(f"🎬 প্রম্পট: {VIDEO_PROMPT}")
    print(f"📁 সেভ: {save_path}")
    print("=" * 50)

    # ─── 🆕 Run state init — run-level folder ও metadata তৈরি ───
    run_dir = _init_run_state()
    print(f"📂 Run folder: {run_dir.name}")

    # ─── ব্রাউজার লঞ্চ ───
    print("\n🌐 CloakBrowser চালু হচ্ছে...")
    launch_kwargs = {
        "headless": HEADLESS,
        "humanize": HUMANIZE,
    }
    if PROXY:
        launch_kwargs["proxy"] = PROXY
        launch_kwargs["geoip"] = True

    browser = launch(**launch_kwargs)
    page = browser.new_page()

    try:
        # ধাপ ১: ল্যান্ডিং পেজ → লগইন
        if not step1_land_and_login(page):
            print("\n❌ ধাপ ১-এ সমস্যা! ব্রাউজার খোলা রাখছি — ম্যানুয়ালি দেখুন।")
            safe_input("📌 Enter চাপুন বন্ধ করতে...")
            _safe_browser_close(browser)
            return

        # ধাপ ২: Google সাইন ইন
        if not step2_google_signin(page):
            print("\n❌ ধাপ ২-এ সমস্যা! (লগইন ব্যর্থ) ব্রাউজার খোলা রাখছি...")
            safe_input("📌 Enter চাপুন বন্ধ করতে...")
            _safe_browser_close(browser)
            return

        # ধাপ ৩: Create New Project
        step3_create_project(page)

        # ধাপ ৪: প্রম্পট দেওয়া
        step4_enter_prompt(page)

        # ধাপ ৫: ভিডিও জেনারেশন ও ডাউনলোড
        step5_wait_and_download(page)

        # ─── সম্পন্ন ───
        print("\n" + "=" * 50)
        print("✅ সব ধাপ সম্পন্ন!")
        print("=" * 50)
        print(f"📁 সেভ লোকেশন: {save_path.absolute()}")
        print(f"📂 Run artifacts: {run_dir}")
        print("\n🔍 ব্রাউজার এখনো খোলা আছে।")
        print("📌 আপনি চাইলে ম্যানুয়ালি কাজ করতে পারেন।")
        print("📌 বন্ধ করতে Enter চাপুন...")
        safe_input()

    except KeyboardInterrupt:
        print("\n\n⛔ ব্যবহারকারী দ্বারা বন্ধ হয়েছে।")
    except Exception as e:
        print(f"\n❌ ত্রুটি: {e}")
        # এরর স্ক্রিনশট
        try:
            page.screenshot(path=str(save_path / "error_final.png"))
            print(f"  📸 এরর স্ক্রিনশট: {save_path / 'error_final.png'}")
        except Exception:
            pass
        safe_input("\n📌 Enter চাপুন বন্ধ করতে...")
    finally:
        _safe_browser_close(browser)
        print("👋 ব্রাউজার বন্ধ হয়েছে।")
        # 🆕 Run summary print
        _print_run_summary(run_dir)


def _safe_browser_close(browser):
    """KeyboardInterrupt বা event loop error এ browser.close() gracefully handle করো"""
    try:
        browser.close()
    except Exception as close_err:
        # 'Event loop is closed' বা অন্য কোনো error হলে চুপ থাকো — bot এর main কাজ complete
        if "Event loop is closed" in str(close_err) or "already stopped" in str(close_err):
            pass  # expected on Ctrl+C
        else:
            print(f"  ⚠️ browser close warning: {str(close_err)[:80]}")


def _print_run_summary(run_dir):
    """Run শেষে step-capture summary print করো"""
    try:
        meta_files = list(run_dir.glob("_run_meta.json"))
        if not meta_files:
            return
        meta = json.loads(meta_files[0].read_text(encoding="utf-8"))
        captures = meta.get("step_captures", [])
        print("\n" + "=" * 50)
        print("📊 RUN SUMMARY — Step Captures")
        print("=" * 50)
        for cap in captures:
            delta = ""
            pc = cap.get("previous_compare") or {}
            if pc.get("status") == "diff":
                delta = f"  [Δ +{pc['added']}/-{pc['removed']}/~{pc['changed']}]"
            elif pc.get("status") == "first_run":
                delta = "  [first run]"
            print(
                f"  Step {cap['step_num']:>2} | {cap['step_name']:<25} | "
                f"{cap['elements_count']:>3} elements{delta}"
            )
        print(f"\n📂 Full artifacts: {run_dir}")
        print(f"💡 Diagnose করতে: python diagnose_report.py --list")
    except Exception as e:
        print(f"  ⚠️ summary print error: {str(e)[:60]}")


if __name__ == "__main__":
    main()
