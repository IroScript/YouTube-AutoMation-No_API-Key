"""
🤖 Groq LLM Client — Veo 3 Agent এর Reasoning Engine
========================================================

Groq API wrapper — দুটো model use করে:
  • GPT OSS 120B (openai/gpt-oss-120b) — main reasoning, text-only DOM input
  • Llama 4 Scout (meta-llama/llama-4-scout-17b-16e-instruct) — vision fallback

🔁 Auto-fallback: Groq TPM limit / 413 / 429 hit করলে Cohere
`command-a-reasoning-08-2025` (thinking enabled) silently use হয়।
User-এর দেওয়া Groq dashboard config অনুযায়ী।
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# .env load (CloakBrowser parent folder) — robust: commented lines থেকেও নেয়
try:
    from env_loader import load_env_robust
    load_env_robust()
except ImportError:
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

try:
    from groq import Groq
except ImportError:
    raise ImportError(
        "groq package install করা নেই! Run করুন: pip install groq"
    )


class GroqClient:
    """Groq API wrapper — reasoning + vision models"""

    # User-নির্দিষ্ট model names (Groq dashboard অনুযায়ী)
    REASONING_MODEL = "openai/gpt-oss-120b"
    VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "❌ GROQ_API_KEY পাওয়া যায়নি!\n"
                "   .env ফাইলে যোগ করুন:\n"
                "   GROQ_API_KEY=gsk_..."
            )
        self.client = Groq(api_key=self.api_key)
        self.call_count = 0
        self.total_tokens = 0

        # Cohere fallback — lazy, optional. Enabled iff key present.
        self.cohere = None
        cohere_key = os.getenv("COHERE_API_KEY")
        if cohere_key:
            try:
                from cohere_client import CohereClient  # local module
                self.cohere = CohereClient(api_key=cohere_key)
                print("  ✓ Cohere fallback: enabled (command-a-reasoning)")
            except Exception as e:
                # Don't crash — Groq might still work
                print(f"  ⚠️ Cohere fallback disabled: {e}")
                self.cohere = None
        else:
            print("  ℹ️ Cohere fallback: disabled (no COHERE_API_KEY in .env)")

        # Track which backend last succeeded (debugging)
        self.last_backend = "groq"
        # Sticky fallback: once we hit a quota/TPM error, stay on Cohere
        # for the rest of the session to avoid wasted Groq calls.
        self.cohere_sticky = False

    def reason(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 1.0,
        max_tokens: int = 8192,
        reasoning_effort: str = "medium",
        use_json_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        GPT OSS 120B দিয়ে reasoning call করে।
        Returns parsed JSON dict (use_json_mode=True হলে)।

        Args:
            system_prompt: agent-এর mission, rules, output schema
            user_content: current state (DOM JSON + history + URL)
            temperature: 1.0 default (GPT OSS recommended)
            max_tokens: 8192 (reasoning requires lots)
            reasoning_effort: "low" | "medium" | "high"
            use_json_mode: True হলে response_format={"type":"json_object"}
        """
        self.call_count += 1
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        kwargs = {
            "model": self.REASONING_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "top_p": 1,
            "reasoning_effort": reasoning_effort,
            "stream": False,
        }
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # Sticky fallback: previously hit Groq quota — go straight to Cohere
        if self.cohere and self.cohere_sticky:
            print("  🔁 Sticky Cohere fallback (Groq quota exhausted)...")
            result = self.cohere.reason(
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=temperature,
                max_tokens=max_tokens,
                use_json_mode=use_json_mode,
            )
            if isinstance(result, dict):
                result["_backend"] = "cohere_fallback"
            self.last_backend = "cohere"
            return result

        try:
            resp = self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content

            # Token tracking
            if hasattr(resp, "usage") and resp.usage:
                self.total_tokens += (
                    getattr(resp.usage, "prompt_tokens", 0) +
                    getattr(resp.usage, "completion_tokens", 0)
                )

            self.last_backend = "groq"

            if use_json_mode:
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON parse failed: {e}")
                    print(f"   Raw content: {content[:300]}")
                    # Fallback — wrap as text in dict
                    return {
                        "thought": "JSON parse failed",
                        "action": "wait",
                        "seconds": 3,
                        "_raw": content,
                    }
            else:
                return {"text": content}

        except Exception as e:
            err_str = str(e)
            err_short = err_str[:200]
            print(f"❌ Groq API error: {err_short}")

            # ── Cohere fallback: TPM / 413 / 429 / rate-limit / overloaded ──
            if self.cohere and self._is_quota_error(e, err_str):
                print("  🔁 Groq quota/TPM hit → falling back to Cohere "
                      "(command-a-reasoning, thinking enabled)...")
                result = self.cohere.reason(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_json_mode=use_json_mode,
                )
                # Mark which backend answered (debugging)
                if isinstance(result, dict):
                    result["_backend"] = "cohere_fallback"
                self.last_backend = "cohere"
                # If Cohere succeeded (not another error dict), lock to it
                if not result.get("_error"):
                    self.cohere_sticky = True
                return result

            # No fallback possible — return safe wait action
            return {
                "thought": f"API error: {err_str[:100]}",
                "action": "wait",
                "seconds": 5,
                "_error": err_str,
            }

    @staticmethod
    def _is_quota_error(exc: Exception, msg: str) -> bool:
        """
        Heuristic: এই error গুলোতে Cohere fallback trigger হবে।
        - 413 (Request too large / TPM)
        - 429 (rate limit)
        - Groq SDK-র specific RateLimitError class
        - 'tokens per minute' / 'rate limit' keywords
        """
        # Class-name check (works for groq SDK exception types)
        cls_name = type(exc).__name__.lower()
        if "rate" in cls_name or "limit" in cls_name or "quota" in cls_name:
            return True

        # Status code attribute (some clients expose .status_code)
        code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if code in (413, 429):
            return True

        # String-pattern fallback
        low = msg.lower()
        quota_markers = (
            "request too large",  # 413 body
            "tokens per minute",
            "tpm",
            "rate limit",
            "rate_limit",
            "too many requests",
            "quota",
            "overloaded",
            "service unavailable",
            "capacity",
        )
        return any(m in low for m in quota_markers)

    def vision_reason(
        self,
        system_prompt: str,
        text: str,
        screenshot_b64: str,
        temperature: float = 1.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        Llama 4 Scout দিয়ে vision reasoning — DOM confused হলে fallback।

        Args:
            system_prompt: same mission prompt
            text: brief context (URL, last action)
            screenshot_b64: base64-encoded PNG screenshot

        Returns:
            Raw text response (vision model may not support JSON mode reliably)
        """
        self.call_count += 1
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
                        },
                    },
                ],
            },
        ]

        try:
            resp = self.client.chat.completions.create(
                model=self.VISION_MODEL,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=1,
                stream=False,
            )
            content = resp.choices[0].message.content

            if hasattr(resp, "usage") and resp.usage:
                self.total_tokens += (
                    getattr(resp.usage, "prompt_tokens", 0) +
                    getattr(resp.usage, "completion_tokens", 0)
                )

            return content

        except Exception as e:
            print(f"❌ Groq vision error: {str(e)[:200]}")
            return json.dumps({
                "thought": f"Vision API error: {str(e)[:100]}",
                "action": "wait",
                "seconds": 5,
            })

    def get_stats(self) -> Dict[str, int]:
        """Call stats — debugging / monitoring-এর জন্য"""
        return {
            "call_count": self.call_count,
            "total_tokens": self.total_tokens,
        }


# ─── Standalone test ──────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Groq Client — standalone test\n")

    try:
        client = GroqClient()
        print(f"✓ API key loaded (length={len(client.api_key)})")
        print(f"✓ Reasoning model: {client.REASONING_MODEL}")
        print(f"✓ Vision model    : {client.VISION_MODEL}\n")

        # Simple test call
        print("→ Test reasoning call...")
        result = client.reason(
            system_prompt="তুমি একজন helpful assistant। সবসময় JSON-এ reply দাও।",
            user_content='{"mission": "Say hello in Bengali"}',
            max_tokens=512,
            reasoning_effort="low",
        )
        print(f"✓ Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print(f"\n📊 Stats: {client.get_stats()}")

    except Exception as e:
        print(f"❌ Test failed: {e}")