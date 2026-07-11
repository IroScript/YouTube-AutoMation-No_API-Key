"""
📝 Prompt Templates — Veo 3 Agent এর System + User Prompts
=============================================================

LLM-কে কী mission দেব, কী format-এ reply চাই — সব এখানে।
প্রতিটা prompt বাংলা + English mix (কারণ LLM দুটোই পারে, user-friendly)।
"""


# ─── SYSTEM PROMPT ─────────────────────────────────────────────
# GPT OSS 120B reasoning-এর জন্য। প্রতিটা LLM call-এ এটাই system role হিসেবে যায়।

SYSTEM_PROMPT = """তুমি একজন Veo 3 video generation agent। তোমার দায়িত্ব:

🎯 MISSION:
1. Google Flow-এ login করো (email + password)
2. একটা নতুন video project তৈরি করো ("নতুন প্রজেক্ট" / "New project" / "+" icon)
3. User-এর prompt textarea-তে লেখো
4. Model dropdown থেকে "Veo 3.1 - Fast" select করো (exact label UI-তে যা আছে)
5. "Generate" / "Create video" / "Submit" বাটনে ক্লিক করো
6. Video ready হলে "Download" / "Save" বাটনে ক্লিক করো

📋 OUTPUT FORMAT — সবসময় এই JSON schema-তে reply দাও:
{
  "thought": "কেন এই action নিচ্ছ (1-2 sentences)",
  "action": "click" | "type" | "navigate" | "wait" | "finish",
  "selector_idx": 5,                    // DOM-এর কোন element (শুধু click/type-এ)
  "text": "cinematic sunset",          // type-এর জন্য prompt/email/password
  "url": "https://...",                // navigate-এর জন্য
  "seconds": 3,                        // wait-এর জন্য
  "verify": "url_contains:/tools/flow/project",  // success check (optional)
  "is_done": false                     // শুধু finish action-এ true
}

🔍 DOM UNDERSTANDING — compact keys:
  i   = element index (0, 1, 2, ...)
  t   = tag (BUTTON, A, INPUT, TEXTAREA, SELECT, DIV)
  tx  = visible text (truncated 60 chars)
  a   = aria-label (most reliable, prefer this)
  p   = placeholder (input fields-এর জন্য)
  tp  = type (email, password, text, submit, ...)
  r   = role (button, textbox, link)
  c   = CSS class (truncated 40 chars)
  b   = [x, y, width, height] position
  v   = in_viewport (true/false)

⚠️ CRITICAL RULES:
1. শুধু visible + interactive elements-এ click করো (b[3] > 0 && v == true)
2. যেটা BUTTON tag বা role="button" — সেগুলোতে prefer করো
3. Pricing / upgrade / "Get more credits" pages skip করো
   → navigate action দিয়ে সরাসরি https://labs.google/fx/tools/flow যাও
4. Login form flow: email → Next → password → Next → consent Continue
5. "নতুন প্রজেক্ট", "New project", "+ নতুন", "Create new" — যেকোনোটাতেই ক্লিক করো (CTA বাটন)
6. Pricing page-এর "Create" button (যেমন sc-a5d8816b-31 eovqGJ class) — এড়িয়ে যাও
7. Cookie/consent screen: "Accept all" / "I agree" / "Continue" বাটনে ক্লিক করো
8. Model selector: dropdown থেকে "Veo 3.1" বা "Veo 3.1 Fast" option select করো
9. "is_done": true দাও শুধু তখনই, যখন video সত্যিই download হয়ে গেছে বা URL-এ "/tools/flow" এবং "video" বা "result" আছে

10. Material icon font names (add, add_2, add_circle, edit, more_vert, refresh) selector-e add korona.
🤔 DECISION HEURISTICS:
- Already logged in? (email field নেই) → সরাসরি project create-এ যাও
- Pricing/upgrade page-এ আটকে গেছো? → navigate action দিয়ে মূল URL-এ ফিরে যাও
- Same element-এ ৩ বার click fail করেছে? → অন্য element try করো অথবা wait করো
- Video generation চলছে (progress bar / spinner)? → ৩০ সেকেন্ড wait করো
- Download button পাচ্ছো কিন্তু URL বদলাচ্ছে না? → click + is_done=true

🎯 FINAL CHECK:
- "is_done": true সেট করার আগে verify করো যে video file (.mp4 / .webm) সত্যিই saved হয়েছে
- শুধু "Download" বাটন click করলেই done না — file save confirm করো

Remember: UI প্রতিনিয়ত বদলায়। Selector match না করলেও DOM context থেকে বুঝে নাও।

⚠️ OUTPUT FORMAT (CRITICAL — read carefully):
Your FINAL response (after any tool calls) MUST be ONLY a single valid JSON object.
No prose, no markdown code blocks, no bullet points, no explanations outside JSON.
The JSON must match the schema above (thought, action, selector_idx, text, ...).
After using web_search / fetch_url tools, return ONLY the JSON — nothing else.

🔧 TOOL USAGE RULES:
- Use web_search ONLY when you don't recognize a UI element (icon-only button, hidden submit, unfamiliar widget).
- After AT MOST 1-2 tool calls, you MUST commit to a JSON action plan.
- Don't keep searching — pick the most plausible action and return JSON.
"""


# ─── USER PROMPT TEMPLATE ─────────────────────────────────────
# প্রতিটা step-এ LLM-কে current state দেওয়া হবে।

USER_PROMPT_TEMPLATE = """📍 CURRENT STATE:
URL    : {url}
Title  : {title}
Step   : {step_num}/{max_steps}
{vision_block}

🌐 DOM ELEMENTS ({n_elements} visible + interactive):
```json
{dom_json}
```

📜 HISTORY (last {n_history} actions):
{history}

🎬 USER MISSION CONTEXT:
- Video prompt: "{video_prompt}"
- Target model: "{target_model}"

🤔 এখন কী করবে? শুধু JSON action plan দাও — no extra text outside JSON।"""


# ─── VISION FALLBACK PROMPT ───────────────────────────────────
# Llama 4 Scout-কে দেওয়া হবে যখন DOM-only reasoning fail করে।

VISION_FALLBACK_TEMPLATE = """তুমি একজন browser agent। নিচের screenshot দেখো।

URL: {url}
Last attempted action: {last_action} (failed: {fail_reason})

DOM-এ standard selectors match হচ্ছে না। Screenshot দেখে বলো:

1. পেজে কী দেখাচ্ছে? (login form / pricing / editor / etc.)
2. কোন element-এ click করা উচিত? (CSS selector বা aria-label suggest করো)
3. কি একটা popup / modal / consent screen আছে?

JSON-এ reply দাও:
{{
  "page_type": "login|pricing|editor|popup|other",
  "suggested_click": "button:has-text('...') | input[type='...'] | etc.",
  "reasoning": "কেন এই selector"
}}"""


# ─── ERROR / RECOVERY PROMPTS ─────────────────────────────────

RECOVERY_PROMPT_TEMPLATE = """⚠️ LAST ACTION FAILED:
Action : {action}
Target : {target}
Error  : {error}

📍 CURRENT STATE:
URL    : {url}

🌐 DOM NOW ({n_elements} elements):
```json
{dom_json}
```

বিকল্প পথ খোঁজো:
- Same goal অন্য element দিয়ে achieve করা যায় কি?
- Wait করে আবার try করা উচিত?
- Navigate করে ভিন্ন URL-এ যাওয়া উচিত?

JSON action plan দাও।"""


# ─── MISSION SUMMARY ──────────────────────────────────────────

MISSION_SUMMARY = """তুমি Veo 3 video বানানোর agent। প্রতিটা decision-ই UI context-aware হবে।
Google UI বদলালেও তোমাকে adapt করতে হবে — static selector-এ নির্ভর করো না।
সবসময় JSON-এ reply দাও।"""


# ─── Helpers ──────────────────────────────────────────────────

def build_vision_perception_prompt(url: str = "", title: str = "",
                                     hint: str = "") -> str:
    """
    Cohere vision model-এর জন্য perception prompt — screenshot থেকে
    element list extract করার instruction।
    """
    parts = [
        "You are a UI perception module for a browser automation agent.",
        "",
        "Look at the screenshot and enumerate EVERY visible interactive",
        "element — including icons, arrows, hidden submits, image-only",
        "buttons, and dynamic JavaScript-rendered controls.",
        "",
        "Return STRICT JSON only:",
        "{",
        '  "summary": "<1-2 sentence description of what page shows>",',
        '  "page_type": "login|form|editor|dashboard|consent|pricing|video|other",',
        '  "elements": [',
        "    {",
        '      "label": "<visible text OR icon description like \'right arrow\'>",',
        '      "role": "button|input|link|select|checkbox|tab|menu|icon",',
        '      "type": "<submit|email|password|text|search|... if applicable>",',
        '      "region": "top-left|top-center|top-right|center|bottom-left|bottom-center|bottom-right",',
        '      "is_primary": true_or_false,',
        '      "needs_text": true_or_false_for_inputs',
        "    }",
        "  ]",
        "}",
    ]
    if url:
        parts.append(f"\nURL: {url}")
    if title:
        parts.append(f"Title: {title}")
    if hint:
        parts.append(f"Context: {hint}")
    return "\n".join(parts)


def build_user_prompt(
    url: str,
    title: str,
    step_num: int,
    max_steps: int,
    dom_elements: list,
    history: list,
    video_prompt: str,
    target_model: str,
    vision_elements: list = None,
    vision_summary: str = "",
    page_type: str = "",
) -> str:
    """User prompt construct করো — সব state inject করে"""

    import json as _json

    # DOM compact JSON (LLM-friendly)
    dom_json = _json.dumps(dom_elements, indent=1, ensure_ascii=False)

    # History summary
    if history:
        history_lines = []
        for i, h in enumerate(history[-10:], 1):
            action = h.get("action", "?")
            target = h.get("target", h.get("selector_idx", "?"))
            ok = "✓" if h.get("success") else "✗"
            history_lines.append(f"  {i}. {ok} {action} → {target}")
        history_str = "\n".join(history_lines)
    else:
        history_str = "  (none — this is the first action)"

    # Vision-grounded elements (if any) — this is the GROUND TRUTH
    if vision_elements:
        import json as _json2
        vision_block = (
            f"\n👁️ VISION-GROUNDED ELEMENTS ({len(vision_elements)} seen):\n"
            f"Page type: {page_type or 'unknown'}\n"
            f"Summary: {vision_summary or 'n/a'}\n"
            f"```json\n{_json2.dumps(vision_elements, ensure_ascii=False, indent=1)}\n```\n"
            f"⚠️ These are from screenshot — treat as GROUND TRUTH. "
            f"Match vision elements with DOM elements by label/role/region."
        )
    else:
        vision_block = ""

    return USER_PROMPT_TEMPLATE.format(
        url=url,
        title=title,
        step_num=step_num,
        max_steps=max_steps,
        vision_block=vision_block,
        n_elements=len(dom_elements),
        dom_json=dom_json,
        n_history=len(history),
        history=history_str,
        video_prompt=video_prompt,
        target_model=target_model,
    )


def build_recovery_prompt(
    failed_action: dict,
    error: str,
    url: str,
    dom_elements: list,
) -> str:
    """Recovery prompt — last action fail হলে"""
    import json as _json
    return RECOVERY_PROMPT_TEMPLATE.format(
        action=failed_action.get("action", "?"),
        target=failed_action.get("selector_idx", failed_action.get("text", "?")),
        error=error[:200],
        url=url,
        n_elements=len(dom_elements),
        dom_json=_json.dumps(dom_elements[:30], indent=1, ensure_ascii=False),
    )


def build_vision_prompt(
    url: str,
    last_action: str,
    fail_reason: str,
) -> str:
    """Vision fallback prompt — Llama 4 Scout-এর জন্য"""
    return VISION_FALLBACK_TEMPLATE.format(
        url=url,
        last_action=last_action,
        fail_reason=fail_reason[:150],
    )


# ─── Standalone test ──────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Prompt Templates — sanity check\n")
    print("=" * 60)
    print(f"SYSTEM_PROMPT length: {len(SYSTEM_PROMPT)} chars")
    print(f"USER_TEMPLATE length: {len(USER_PROMPT_TEMPLATE)} chars")
    print(f"VISION_TEMPLATE length: {len(VISION_FALLBACK_TEMPLATE)} chars")
    print("=" * 60)

    # Test build_user_prompt
    sample_dom = [
        {"i": 0, "t": "BUTTON", "tx": "Sign in", "a": "sign in", "v": True},
        {"i": 1, "t": "INPUT", "tp": "email", "p": "Email", "v": True},
    ]
    sample_history = [
        {"action": "navigate", "url": "https://labs.google/fx/tools/flow", "success": True},
        {"action": "click", "selector_idx": 0, "success": True},
    ]

    prompt = build_user_prompt(
        url="https://accounts.google.com/",
        title="Sign in - Google Accounts",
        step_num=3,
        max_steps=50,
        dom_elements=sample_dom,
        history=sample_history,
        video_prompt="A cat playing piano",
        target_model="Veo 3.1 - Fast",
    )
    print("\n📝 Sample user prompt:")
    print("-" * 60)
    print(prompt[:500] + "...")
    print("-" * 60)
    print(f"✓ Total length: {len(prompt)} chars")