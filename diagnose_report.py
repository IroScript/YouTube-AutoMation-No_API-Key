"""
🔍 Diagnose Report Generator — Google Flow Bot
==============================================

bot fail হলে যে diag_*.json ফাইল তৈরি হয়, এই tool সেটা পড়ে:
  1. UI তে কী কী interactive element ছিল summary দেখায়
  2. প্রতিটা failure type অনুযায়ী "সম্ভাব্য best selector" suggest করে
  3. সরাসরি google_flow_bot.py তে paste করার জন্য ready snippet দেয়

ব্যবহার:
    python diagnose_report.py
    python diagnose_report.py --file downloads/diag_step3_no_create_button_20260705.json
    python diagnose_report.py --latest     # সবার নতুন JSON দেখায়
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from glob import glob


# ─── Failure-specific suggestion rules ───
FAILURE_RULES = {
    "step1_no_create_button": {
        "target_keywords": [
            "create", "flow", "try", "start", "get started", "begin",
            "নতুন", "তৈরি", "শুরু", "continue", "sign in", "login",
        ],
        "prefer_tags": ["button", "a"],
        "expect_input": False,
        "selector_template": 'button:has-text("{text}"), a:has-text("{text}")',
    },
    "step3_no_create_button": {
        "target_keywords": [
            "new", "create", "নতুন", "+", "plus", "project", "start", "begin",
            "compose", "new project", "create new",
        ],
        "prefer_tags": ["button", "a", "div"],
        "expect_input": False,
        "selector_template": 'button:has-text("{text}"), [aria-label*="{text}" i]',
    },
    "step4_no_prompt_field": {
        "target_keywords": [
            "prompt", "describe", "video", "type", "write", "message", "scene",
            "ভিডিও", "লিখুন", "বর্ণনা", "enter", "input", "what", "imagine",
            "story", "idea",
        ],
        "prefer_tags": ["textarea", "input", "div"],
        "expect_input": True,
        "selector_template": 'textarea[placeholder*="{text}" i], [contenteditable="true"][aria-label*="{text}" i], input[placeholder*="{text}" i]',
    },
    "step5_no_download_button": {
        "target_keywords": [
            "download", "save", "export", "সেভ", "ডাউনলোড", "get", "fetch",
            "open", "view",
        ],
        "prefer_tags": ["button", "a"],
        "expect_input": False,
        "selector_template": 'button:has-text("{text}"), a:has-text("{text}"), [aria-label*="{text}" i]',
    },
}


# ─── URL pattern → page state hints ───
URL_HINTS = {
    "#pricing": "💰 PRICING PAGE — Bot pricing section এ আছে! prompt editor না।",
    "/tools/flow/project": "🎬 FLOW PROJECT EDITOR — video generation editor এ।",
    "/tools/flow": "🌐 FLOW HOMEPAGE — public landing এ আছে, project editor না।",
    "accounts.google.com": "🔐 GOOGLE LOGIN — email/password prompt।",
    "/signin": "🔐 SIGN-IN PAGE — Google login flow।",
    "/consent": "📋 CONSENT PAGE — Google permission prompt।",
    "/o/oauth": "🔐 OAUTH PAGE — token grant।",
    "/fx/": "🌐 FLOW LANDING — public homepage।",
}


# ─── Generic viewport (fallback when element bbox doesn't match) ───
DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


def colorize(text, color):
    """Simple ANSI color (terminal-এ readable করতে)"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "reset": "\033[0m",
        "bold": "\033[1m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def load_diag_file(path):
    """JSON diag file load করো"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(colorize(f"❌ ফাইল পড়া যায়নি: {e}", "red"))
        return None


def score_element(elem, rules):
    """
    একটা element কে failure type অনুযায়য় 0-100 score দাও।
    বেশি score = বেশি সম্ভাব্য candidate

    নতুন rules:
      • expect_input=True হলে TEXTAREA/INPUT অগ্রাধিকার পায়
      • Bbox viewport এর বাইরে (negative Y বা > viewport height) হলে penalty
      • Empty text (শুধু icon বা "more_vert" type) হলে button হলে +penalty
    """
    score = 0
    text = (elem.get("text") or "").lower().strip()
    aria = (elem.get("aria") or "").lower().strip()
    placeholder = (elem.get("placeholder") or "").lower().strip()
    tag = (elem.get("tag") or "").lower()
    role = (elem.get("role") or "").lower()
    bbox = elem.get("bbox", {})
    combined = f"{text} {aria} {placeholder}"
    expect_input = rules.get("expect_input", False)

    # 1. Tag preference
    if expect_input:
        # Input case: TEXTAREA / INPUT / [contenteditable] কে highest priority
        if tag in ("textarea", "input"):
            score += 35
        elif "[contenteditable]" in (elem.get("classes") or "") or role == "textbox":
            score += 30
        elif tag == "div":
            score += 5
        else:
            score -= 5  # button/a হলে কম
    else:
        # Button case: BUTTON/A কে priority
        if tag in rules["prefer_tags"]:
            score += 20

    # 2. Keyword matching
    for kw in rules["target_keywords"]:
        if kw.lower() in combined:
            if kw.lower() == text or kw.lower() == aria:
                score += 40
            else:
                score += 25
            break

    # 3. Bbox viewport heuristic — বাইরের element কে penalty
    w = bbox.get("w", 0)
    h = bbox.get("h", 0)
    x = bbox.get("x", 0)
    y = bbox.get("y", 0)
    vw = DEFAULT_VIEWPORT["width"]
    vh = DEFAULT_VIEWPORT["height"]

    # Element scrollable region এ আছে কিনা (negative Y বা far below)
    off_screen = (y < -50) or (y > vh + 50) or (x < -50) or (x > vw + 50)
    if off_screen:
        score -= 30   # viewport-এর বাইরে — কম সম্ভাব্য
    else:
        # On-screen size heuristic
        if expect_input:
            # Prompt input সাধারণত বড় (textarea wide)
            if w >= 200 and h >= 40:
                score += 15
            elif w < 50 or h < 20:
                score -= 10
        else:
            # Button সাধারণত 30-400px wide, 20-80px tall
            if 30 < w < 400 and 20 < h < 80:
                score += 15
            elif w > 500:  # full-width = container
                score -= 10

    # 4. Text/aria length penalty — icon-only text (more_vert, play_arrow) সাধারণত
    # কাজের button না
    icon_only = text in ("play_arrow", "more_vert", "chevron_left", "chevron_right",
                         "arrow_forward", "arrow_back", "menu", "close", "settings")
    if icon_only and not expect_input:
        score -= 15

    # 5. Empty text ও কোনো aria নেই — কম confidence
    if not text and not aria and not placeholder:
        score -= 20

    # 6. Interactive attribute bonus
    if elem.get("type") or role in ("button", "textbox", "searchbox"):
        score += 10

    # 7. Material icon indicator (কাজের button সাধারণত icon class এ থাকে না)
    classes = elem.get("classes") or ""
    if "material-icons" in classes or "icon-" in classes:
        if not expect_input and icon_only:
            score -= 10

    return max(0, min(score, 100))


def generate_suggestions(data):
    """JSON data থেকে selector suggestions generate করো"""
    reason = data.get("reason", "unknown")
    rules = FAILURE_RULES.get(reason)
    if not rules:
        print(colorize(f"⚠️ অজানা reason '{reason}' — generic matching ব্যবহার করছি", "yellow"))
        rules = {
            "target_keywords": ["create", "submit", "next", "continue", "start", "go"],
            "prefer_tags": ["button", "a"],
            "expect_input": False,
            "selector_template": 'button:has-text("{text}"), a:has-text("{text}")',
        }

    elements = data.get("elements", [])
    if not elements:
        print(colorize("❌ JSON-এ কোনো element পাওয়া যায়নি", "red"))
        return [], rules

    # প্রতিটা element score করো
    scored = []
    for elem in elements:
        s = score_element(elem, rules)
        if s > 15:  # threshold slightly lower
            scored.append((s, elem))

    # Top 5 সাজাও
    scored.sort(key=lambda x: -x[0])
    return scored[:5], rules


def print_report(data, scored, rules):
    """Human-readable report print করো"""
    print("\n" + "=" * 70)
    print(colorize("🔍 DIAGNOSTIC REPORT", "bold"))
    print("=" * 70)
    print(f"📅 Timestamp : {data.get('timestamp', '?')}")
    print(f"🌐 URL       : {data.get('url', '?')}")

    # ─── 🆕 URL context hint ───
    url = data.get("url", "")
    matched_hint = None
    for pattern, hint in URL_HINTS.items():
        if pattern in url:
            matched_hint = hint
            break
    if matched_hint:
        print(f"💡 URL hint  : {colorize(matched_hint, 'magenta')}")

    print(f"❓ Reason    : {colorize(data.get('reason', '?'), 'yellow')}")
    print(f"📊 Total elements visible : {len(data.get('elements', []))}")

    if data.get("screenshot"):
        print(f"📸 Screenshot: {colorize(data['screenshot'], 'cyan')}")

    # ─── 🆕 Page-specific warning ───
    reason = data.get("reason", "")
    if "step4" in reason and "#pricing" in url:
        print()
        print(colorize("⚠️  CRITICAL: Bot pricing page এ আছে!", "red"))
        print(colorize("    Step 4 prompt input editor page এ পাওয়া যাবে, pricing এ না।", "yellow"))
        print(colorize("    Step 3-এ '+ New Project' বা similar button এ ক্লিক হয়নি।", "yellow"))
        print(colorize("    Screenshot-এ manually check করো Flow editor লোড হয়েছে কিনা।", "yellow"))
    elif "step3" in reason and "#pricing" in url:
        print()
        print(colorize("⚠️  Bot pricing page এ আছে — Step 3 create button fail হয়েছে।", "yellow"))

    print("\n" + "-" * 70)
    print(colorize(f"🎯 TOP CANDIDATES (scored by relevance)", "bold"))
    print("-" * 70)

    if not scored:
        print(colorize("\n  ⚠️ কোনো relevant candidate পাওয়া যায়নি।", "yellow"))
        print(colorize("      হতে পারে কারণ:", "yellow"))
        print(colorize("      • Bot সঠিক page এ নেই (URL hint দেখো)", "yellow"))
        print(colorize("      • Page load হচ্ছে (আরেকবার retry করো)", "yellow"))
        print(colorize("      • Material icons / icon-only buttons বেশি — actual element গুলো text-less", "yellow"))

    for i, (score, elem) in enumerate(scored, 1):
        text = (elem.get("text") or "").strip()[:50]
        aria = (elem.get("aria") or "").strip()[:40]
        tag = elem.get("tag", "?")
        placeholder = elem.get("placeholder", "")[:30]
        bbox = elem.get("bbox", {})

        # Score color
        if score >= 70:
            score_color = "green"
        elif score >= 40:
            score_color = "yellow"
        else:
            score_color = "red"

        # ─── 🆕 Viewport-এ আছে কিনা দেখাও ───
        vw = DEFAULT_VIEWPORT["width"]
        vh = DEFAULT_VIEWPORT["height"]
        x = bbox.get("x", 0)
        y = bbox.get("y", 0)
        in_view = (0 <= x <= vw) and (0 <= y <= vh)
        view_mark = "✅ in-view" if in_view else "⚠️ off-screen"

        print(f"\n  {colorize(f'#{i}', 'bold')} | Score: {colorize(f'{score}/100', score_color)}  [{view_mark}]")
        print(f"       Tag       : {colorize(tag, 'cyan')}")
        if text:
            print(f"       Text      : \"{text}\"")
        if aria:
            print(f"       Aria-label: \"{aria}\"")
        if placeholder:
            print(f"       Placeholder: \"{placeholder}\"")
        print(f"       BBox      : ({bbox.get('x',0)},{bbox.get('y',0)}) {bbox.get('w',0)}x{bbox.get('h',0)}")

        # Selector suggestion
        sel_text = text or aria or placeholder or "unknown"
        selector = rules["selector_template"].format(text=sel_text)
        print(f"       {colorize('Selector:', 'green')} {colorize(selector, 'cyan')}")

        if not in_view:
            print(f"       {colorize('💡 scroll-to element করতে হবে আগে', 'yellow')}")

    print("\n" + "=" * 70)
    print(colorize("💡 NEXT STEP", "bold"))
    print("=" * 70)

    # ─── 🆕 Off-screen check + actionable advice ───
    in_view_scored = [s for s in scored if _is_in_viewport(s[1])]
    if not scored:
        print(colorize("⚠️ কোনো confident candidate পাওয়া যায়নি। Screenshot ম্যানুয়ালি দেখো।", "yellow"))
    elif not in_view_scored:
        print(colorize("⚠️ সব candidate off-screen।", "yellow"))
        print(colorize("   Bot step 3 এ scroll করেনি বা editor পেজে navigate করেনি।", "yellow"))
        print()
        print(colorize("   সম্ভাব্য কারণ:", "yellow"))
        print(colorize("   • Pricing page anchor (#pricing) এ আটকে আছে", "yellow"))
        print(colorize("   • Project create হয়নি — pricing section-এ redirect হয়েছে", "yellow"))
        print(colorize("   • A/B test variation — অন্য UI loaded", "yellow"))
    else:
        best = in_view_scored[0][1]
        sel_text = (best.get("text") or best.get("aria") or best.get("placeholder") or "").strip()
        selector = rules["selector_template"].format(text=sel_text)

        print("\nতোমার google_flow_bot.py তে এই selector যোগ করো:\n")
        print(colorize(f"  wait_and_click(page, '{selector}', ...)", "cyan"))
        print("\nঅথবা নিরাপদ fallback chain:\n")
        chain = ",\n    ".join([
            rules["selector_template"].format(text=(e[1].get("text") or e[1].get("aria") or "").strip())
            for e in in_view_scored[:3]
        ])
        print(colorize(f"  flow_selectors = [\n    {chain}\n  ]", "cyan"))

    print()


def _is_in_viewport(elem, viewport=None):
    """Element viewport এর ভিতরে আছে কিনা"""
    vw = (viewport or DEFAULT_VIEWPORT)["width"]
    vh = (viewport or DEFAULT_VIEWPORT)["height"]
    bbox = elem.get("bbox", {})
    x = bbox.get("x", 0)
    y = bbox.get("y", 0)
    return (0 <= x <= vw) and (0 <= y <= vh)


def list_diag_files(downloads_dir):
    """সব diag JSON খুঁজে list করো"""
    pattern = str(downloads_dir / "diag_*.json")
    files = sorted(glob(pattern), key=lambda f: Path(f).stat().st_mtime, reverse=True)
    return files


def main():
    parser = argparse.ArgumentParser(description="Google Flow Bot Diagnostic Report Generator")
    parser.add_argument("--file", type=str, help="Specific diag JSON file to analyze")
    parser.add_argument("--latest", action="store_true", help="Analyze the most recent diag JSON")
    parser.add_argument("--list", action="store_true", help="List all available diag JSON files")
    parser.add_argument("--downloads", type=str, default="./downloads", help="Path to downloads folder")
    args = parser.parse_args()

    downloads_dir = Path(args.downloads)
    if not downloads_dir.exists():
        print(colorize(f"❌ Downloads folder পাওয়া যায়নি: {downloads_dir.absolute()}", "red"))
        print("   Bot আগে চালান যাতে diag JSON তৈরি হয়।")
        return 1

    diag_files = list_diag_files(downloads_dir)

    if args.list:
        print(colorize(f"\n📁 Available diag files in {downloads_dir}:", "bold"))
        if not diag_files:
            print(colorize("  (কোনো diag JSON নেই — bot আগে fail হয়নি বা চলেনি)", "yellow"))
        else:
            for f in diag_files:
                size = Path(f).stat().st_size
                print(f"  • {colorize(Path(f).name, 'cyan')} ({size:,} bytes)")
        return 0

    if not diag_files:
        print(colorize("❌ কোনো diag JSON পাওয়া যায়নি।", "red"))
        print(f"   ফোল্ডার: {downloads_dir.absolute()}")
        print("\n💡 Bot চালান, fail হলে diag JSON auto-create হবে।")
        return 1

    # File select
    target_file = None
    if args.file:
        target_file = args.file
    elif args.latest or not args.file:
        target_file = diag_files[0]
        if not args.latest and not args.file:
            # interactive
            print(colorize("\n📁 Available diag files:", "bold"))
            for i, f in enumerate(diag_files[:10], 1):
                print(f"  {i}. {colorize(Path(f).name, 'cyan')}")
            print(f"\nসবার নতুন analyze করতে Enter, অথবা number দিন (1-{min(10, len(diag_files))}):")
            try:
                choice = input("> ").strip()
                if choice and choice.isdigit() and 1 <= int(choice) <= min(10, len(diag_files)):
                    target_file = diag_files[int(choice) - 1]
            except (EOFError, KeyboardInterrupt):
                print()

    if not target_file:
        target_file = diag_files[0]

    print(colorize(f"\n📄 Analyzing: {target_file}", "cyan"))

    data = load_diag_file(target_file)
    if not data:
        return 1

    scored, rules = generate_suggestions(data)
    print_report(data, scored, rules)

    return 0


if __name__ == "__main__":
    sys.exit(main())