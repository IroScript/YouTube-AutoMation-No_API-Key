"""
🤖 Cohere Fallback LLM Client — Groq fail হলে এটা ব্যবহার হবে
================================================================

Cohere v2 API wrapper — `command-a-reasoning-08-2025` model দিয়ে
reasoning + JSON output দেয়। thinking চালু থাকে (CoT)।

এই client সাধারণত সরাসরি ব্যবহার হয় না — GroqClient.reason() Groq fail
করলে (TPM limit / 413 / rate-limit) এটাকে auto-call করে।
"""

import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

try:
    from cohere import (
        ClientV2,
        Thinking,
        JsonObjectResponseFormatV2,
        ImageUrlContent,
        ImageUrl,
        TextContent,
        ToolV2,
        ToolV2Function,
        ToolChatMessageV2,
    )
except ImportError:
    raise ImportError(
        "cohere package install করা নেই! Run করুন: pip install cohere"
    )

# Local imports
from web_tools import TOOL_DEFINITIONS, invoke_tool


# .env load (CloakBrowser parent folder) — robust: commented lines থেকেও নেয়
try:
    from env_loader import load_env_robust
    load_env_robust()
except ImportError:
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


class CohereClient:
    """Cohere v2 wrapper — command-a-reasoning fallback + vision + tool use"""

    # Reasoning-capable model with thinking support (text-only)
    REASONING_MODEL = "command-a-reasoning-08-2025"

    # Vision-capable model (separate — Cohere split reasoning from vision)
    VISION_MODEL = "command-a-vision-07-2025"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "❌ COHERE_API_KEY পাওয়া যায়নি!\n"
                "   .env ফাইলে যোগ করুন:\n"
                "   COHERE_API_KEY=..."
            )
        # v7 SDK-তে v2 client হলো ClientV2
        self.client = ClientV2(api_key=self.api_key)
        self.call_count = 0
        self.total_tokens = 0
        # Cohere requires: thinking.token_budget <= max_tokens
        # তাই effective reasoning token = max_tokens - thinking_token_budget
        # Default: max_tokens=4096, thinking_budget=2000 → 2096 for actual answer
        self.max_tokens_default = 4096
        self.thinking_budget_default = 2000

    # Reasoning client-এর জন্য expected output schema।
    # Cohere response যদি এই keys contain না করে, retry করা হবে।
    EXPECTED_SCHEMA_KEYS = {"thought", "action"}

    def reason(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.6,
        max_tokens: int = 4096,
        thinking_token_budget: int = 2000,
        use_json_mode: bool = True,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Cohere command-a-reasoning দিয়ে reasoning call করে।
        Returns parsed JSON dict (use_json_mode=True হলে)।

        Schema mismatch হলে max_retries পর্যন্ত আবার চেষ্টা করে।

        ⚠️ Cohere rule: thinking.token_budget <= max_tokens
        — caller যদি violate করে, আমরা silently max_tokens বাড়িয়ে দিই।

        Args:
            system_prompt: agent mission/rules
            user_content: DOM + history + URL (string)
            temperature: 0.6 reasoning-এর জন্য ভালো
            max_tokens: completion token cap
            thinking_token_budget: CoT budget (thinking-এ খরচ হবে)
            use_json_mode: response_format=json_object — strict JSON
            max_retries: schema mismatch হলে auto-retry limit
        """
        # Enforce Cohere rule: thinking_budget <= max_tokens.
        # Reserve at least 800 tokens for the actual JSON answer.
        if thinking_token_budget >= max_tokens:
            max_tokens = thinking_token_budget + 800
            print(f"  ⚠️ Cohere: max_tokens raised to {max_tokens} "
                  f"(thinking_budget={thinking_token_budget})")

        last_err = None
        for attempt in range(max_retries + 1):
            self.call_count += 1

            # v2 messages: SystemChatMessageV2 + UserChatMessageV2 (string content)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            kwargs: Dict[str, Any] = {
                "model": self.REASONING_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "thinking": Thinking(
                    type="enabled",
                    token_budget=thinking_token_budget,
                ),
                # Safety mode CONTEXTUAL default — agent কাজে hinder করে না
            }
            if use_json_mode:
                # Strict JSON output (Cohere v2 native)
                kwargs["response_format"] = JsonObjectResponseFormatV2()

            try:
                resp = self.client.chat(**kwargs)

                # Token tracking
                if hasattr(resp, "usage") and resp.usage:
                    u = resp.usage
                    if hasattr(u, "tokens"):
                        t = u.tokens
                        self.total_tokens += (
                            getattr(t, "input_tokens", 0) or 0
                        ) + (
                            getattr(t, "output_tokens", 0) or 0
                        )

                # Extract text content (skip thinking blocks)
                content = self._extract_text(resp)

                if not use_json_mode:
                    return {"text": content}

                # JSON parse + schema validation
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    last_err = f"JSON parse: {e}"
                    print(f"⚠️ Cohere JSON parse failed (attempt {attempt+1}): {e}")
                    print(f"   Raw: {content[:200]}")
                    continue

                if not self._validate_schema(parsed):
                    last_err = f"schema mismatch (missing {self.EXPECTED_SCHEMA_KEYS})"
                    print(f"⚠️ Cohere schema mismatch (attempt {attempt+1})")
                    print(f"   Got keys: {list(parsed.keys())}")
                    continue

                return parsed

            except Exception as e:
                print(f"❌ Cohere API error (attempt {attempt+1}): {str(e)[:200]}")
                last_err = str(e)
                # Network/API error হলে retry না করে return করি
                return {
                    "thought": f"Cohere API error: {str(e)[:100]}",
                    "action": "wait",
                    "seconds": 5,
                    "_error": str(e),
                }

        # সব retry শেষ — final fallback
        return {
            "thought": f"Cohere schema invalid after {max_retries+1} attempts: {last_err}",
            "action": "wait",
            "seconds": 5,
            "_error": last_err,
        }

    @staticmethod
    def _validate_schema(parsed: Any) -> bool:
        """
        Cohere response valid agent-action schema কিনা check করে।
        Required: 'thought' (str) + 'action' (one of known actions)
        """
        if not isinstance(parsed, dict):
            return False
        if "thought" not in parsed or not isinstance(parsed.get("thought"), str):
            return False
        action = parsed.get("action")
        if action not in ("click", "type", "navigate", "wait", "finish"):
            return False
        return True

    # ─── Vision perception ────────────────────────────────────────
    def vision_perceive(
        self,
        screenshot_b64: str,
        hint: str = "",
        url: str = "",
        title: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Screenshot Cohere vision model-এ পাঠিয়ে grounded element list আনো।

        Cohere vision model (command-a-vision-07-2025) শুধু image দেখে
        enumerate করে — arrow-only buttons, icon-only buttons, hidden
        submit, dynamic UI সব identify করতে পারে (DOM পারে না)।

        Returns:
            {
              "elements": [
                {"label": "...", "role": "button|input|...", "type": "submit|email|...",
                 "region": "top-right|center|...", "has_icon_only": bool, "hint": "..."}
              ],
              "summary": "brief page description",
              "page_type": "login|form|editor|..."
            }

        Args:
            screenshot_b64: base64-encoded image (PNG/JPEG)
            hint: extra context (e.g. "this is a Google login page")
            url/page title: optional context
        """
        self.call_count += 1

        # Build prompt asking for structured JSON
        prompt_parts = [
            "You are a UI perception module. Look at the screenshot and "
            "enumerate EVERY visible interactive element, including:",
            "  • Buttons (text OR icon-only OR arrow-only)",
            "  • Input fields (email, password, search, text, file)",
            "  • Links and navigation",
            "  • Dropdowns, checkboxes, radio buttons, toggles",
            "  • Hidden submit triggers (Enter-key buttons, arrow submit)",
            "",
            "Return JSON only:",
            "{",
            '  "summary": "1-2 sentence page description",',
            '  "page_type": "login|form|editor|dashboard|consent|pricing|other",',
            '  "elements": [',
            "    {",
            '      "label": "visible text OR icon description",',
            '      "role": "button|input|link|select|checkbox|...",',
            '      "type": "submit|email|password|text|search|... (if applicable)",',
            '      "region": "top-left|top-center|top-right|center|... (relative)",',
            '      "is_primary": true/false (is this the main CTA?),',
            '      "needs_text": true/false (for input — what to type)',
            "    }",
            "  ]",
            "}",
        ]
        if hint:
            prompt_parts.append(f"\nContext: {hint}")
        if url:
            prompt_parts.append(f"URL: {url}")
        if title:
            prompt_parts.append(f"Title: {title}")

        prompt_text = "\n".join(prompt_parts)

        # Build message with image + text content
        # Detect format from b64 prefix or default to jpeg
        img_format = "image/jpeg"
        if screenshot_b64.startswith("iVBOR"):
            img_format = "image/png"

        messages = [{
            "role": "user",
            "content": [
                TextContent(type="text", text=prompt_text),
                ImageUrlContent(
                    type="image_url",
                    image_url=ImageUrl(
                        url=f"data:{img_format};base64,{screenshot_b64}",
                        detail="low",  # halves token cost
                    ),
                ),
            ],
        }]

        try:
            resp = self.client.chat(
                model=self.VISION_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                # NOTE: Cohere rejects strict JSON response_format with image content.
                # Vision model-এ JSON mode নেই — prompt instruction rely করি।
            )

            if hasattr(resp, "usage") and resp.usage:
                u = resp.usage
                if hasattr(u, "tokens"):
                    t = u.tokens
                    self.total_tokens += (
                        getattr(t, "input_tokens", 0) or 0
                    ) + (
                        getattr(t, "output_tokens", 0) or 0
                    )

            content = self._extract_text(resp)

            # Try parse JSON
            try:
                parsed = json.loads(content)
                return parsed
            except json.JSONDecodeError:
                # Fallback: extract JSON from text
                m = re.search(r"\{.*\}", content, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except json.JSONDecodeError:
                        pass
                print(f"⚠️ Cohere vision JSON parse failed")
                print(f"   Raw: {content[:200]}")
                return {
                    "summary": "vision parse failed",
                    "page_type": "other",
                    "elements": [],
                    "_raw": content[:500],
                }

        except Exception as e:
            print(f"❌ Cohere vision error: {str(e)[:200]}")
            return {
                "summary": "vision error",
                "page_type": "other",
                "elements": [],
                "_error": str(e),
            }

    # ─── Reasoning with tool-use loop ─────────────────────────────
    def reason_with_tools(
        self,
        system_prompt: str,
        user_content: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.6,
        max_tokens: int = 4096,
        thinking_token_budget: int = 2000,
        max_tool_turns: int = 3,
    ) -> Dict[str, Any]:
        """
        Cohere reasoning model দিয়ে plan আনো — প্রয়োজনে tool call করতে পারবে
        (web_search, fetch_url)। max_tool_turns পর্যন্ত tool loop চলবে।

        Returns: parsed JSON dict {thought, action, selector_idx, text, ...}
        """
        # Default tools: web_search + fetch_url
        if tools is None:
            tools = TOOL_DEFINITIONS

        # Cohere ToolV2 objects convert
        cohere_tools = []
        for t in tools:
            if t.get("type") == "function":
                fn = t["function"]
                cohere_tools.append(
                    ToolV2(
                        type="function",
                        function=ToolV2Function(
                            name=fn["name"],
                            description=fn.get("description", ""),
                            parameters=fn.get("parameters", {}),
                        ),
                    )
                )

        # Token budget clamp (Cohere rule)
        if thinking_token_budget >= max_tokens:
            max_tokens = thinking_token_budget + 800
            print(f"  ⚠️ Cohere: max_tokens raised to {max_tokens} "
                  f"(thinking_budget={thinking_token_budget})")

        # Initial messages
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        for turn in range(max_tool_turns + 1):
            self.call_count += 1

            kwargs: Dict[str, Any] = {
                "model": self.REASONING_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "thinking": Thinking(
                    type="enabled",
                    token_budget=thinking_token_budget,
                ),
            }
            if cohere_tools:
                kwargs["tools"] = cohere_tools

            try:
                resp = self.client.chat(**kwargs)
            except Exception as e:
                print(f"❌ Cohere reason_with_tools error (turn {turn}): "
                      f"{str(e)[:200]}")
                return {
                    "thought": f"Cohere error: {str(e)[:100]}",
                    "action": "wait",
                    "seconds": 5,
                    "_error": str(e),
                }

            if hasattr(resp, "usage") and resp.usage:
                u = resp.usage
                if hasattr(u, "tokens"):
                    t = u.tokens
                    self.total_tokens += (
                        getattr(t, "input_tokens", 0) or 0
                    ) + (
                        getattr(t, "output_tokens", 0) or 0
                    )

            msg = resp.message
            tool_calls = getattr(msg, "tool_calls", None) or []
            finish_reason = getattr(resp, "finish_reason", None)

            # Case 1: Model wants to call tools
            if tool_calls:
                # Append assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": getattr(msg, "content", None) or [],
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                # Execute each tool call locally
                for tc in tool_calls:
                    fn_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    print(f"  🔧 Tool call: {fn_name}({json.dumps(args)[:80]})")
                    result = invoke_tool(fn_name, args)
                    result_str = json.dumps(result, ensure_ascii=False)

                    # Append tool result message as plain dict — Cohere SDK
                    # accepts both ToolChatMessageV2 object and dict.
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })

                # Loop again with tool results
                continue

            # Case 2: Final answer (no more tool calls)
            content = self._extract_text(resp)

            # Cohere reasoning model sometimes emits MULTIPLE JSON objects
            # (e.g. one for the action, one as "next step suggestion").
            # We only want the FIRST valid one that matches our schema.
            parsed = self._extract_first_valid_json(content)
            if parsed and self._validate_schema(parsed):
                return parsed

            # Couldn't parse — return safe fallback
            return {
                "thought": f"Cohere output invalid after {turn+1} turns",
                "action": "wait",
                "seconds": 3,
                "_raw": content[:300],
            }

    @staticmethod
    def _extract_first_valid_json(content: str) -> Optional[Dict[str, Any]]:
        """
        Cohere reasoning output থেকে first valid JSON object extract করে।
        Cohere কখনো কখনো extra content emit করে (multiple JSON, prose, etc)।
        """
        if not content:
            return None

        # First try: whole content
        try:
            obj = json.loads(content)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        # Second try: find first {...} block
        m = re.search(r"\{[\s\S]*?\}", content)
        if m:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        # Third try: find first { and try parsing progressively
        idx = content.find("{")
        if idx >= 0:
            depth = 0
            for i in range(idx, len(content)):
                ch = content[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = content[idx:i+1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict):
                                return obj
                        except json.JSONDecodeError:
                            break

        return None

        # Exhausted tool turns
        return {
            "thought": f"Tool loop exhausted after {max_tool_turns} turns",
            "action": "wait",
            "seconds": 5,
        }

    @staticmethod
    def _extract_text(resp) -> str:
        """
        Cohere v2 response থেকে final text বের করি (thinking blocks বাদ দিয়ে)।
        response.message.content হলো list of {type: "text" | "thinking", ...}
        """
        try:
            msg = resp.message
            content = getattr(msg, "content", None) or []
        except Exception:
            return ""

        parts = []
        for item in content:
            # Pydantic-style attribute access
            t = getattr(item, "type", None)
            if t == "text":
                parts.append(getattr(item, "text", "") or "")
            # thinking blocks intentionally skipped — final answer-ই দরকার
        return "\n".join(p for p in parts if p).strip()

    def get_stats(self) -> Dict[str, int]:
        return {
            "call_count": self.call_count,
            "total_tokens": self.total_tokens,
        }


# ─── Standalone test ─────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Cohere Fallback Client — standalone test\n")
    try:
        client = CohereClient()
        print(f"✓ API key loaded (length={len(client.api_key)})")
        print(f"✓ Reasoning model: {client.REASONING_MODEL}\n")

        print("→ Test reasoning call...")
        result = client.reason(
            system_prompt=(
                "তুমি একজন helpful assistant। "
                'সবসময় এই JSON schema-তে reply দাও: '
                '{"thought": str, "action": str, "answer": str}'
            ),
            user_content='{"question": "৫ আর ৭ কেন বেশি ১০ এর চেয়ে কম?"}',
            max_tokens=1024,
            thinking_token_budget=800,
        )
        print(f"✓ Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print(f"\n📊 Stats: {client.get_stats()}")
    except Exception as e:
        print(f"❌ Test failed: {e}")