"""
🔧 Robust .env loader — comment-সহ সব lines scan করে KEY=VALUE খোঁজে।

python-dotenv কেবল uncommented lines parse করে — user যদি `# COHERE_API_KEY=...`
রেখে দেয় (uncomment করতে ভুলে যায়), তখন key load হয় না।

এই loader fallback: প্রথমে dotenv দিয়ে proper parse, তারপর regex দিয়ে
commented lines থেকেও key extract করে os.environ-এ set করে।

⚠️ SECURITY: শুধু allowlisted keys (API tokens, credentials) commented থেকে
নেওয়া হয়। Connection strings (PROXY, DATABASE_URL etc.) skip হয় — কারণ
example/placeholder URL legitimately commented থাকে।

ব্যবহার:
    from env_loader import load_env_robust
    load_env_robust()  # call once at startup
"""

import os
import re
from pathlib import Path
from typing import Optional, Iterable
from dotenv import load_dotenv


# ─── Allowlist: commented lines থেকে নেওয়া হবে শুধু এই keys-ই ──────
# বাকি keys (PROXY, DATABASE_URL, REDIS_URL, SAVE_DIR ইত্যাদি) skip হবে
# কারণ commented example values (যেমন socks5://user:pass@host:port) legitimately
# document হিসেবে `.env.example`-এ থাকে।
COMMENTED_KEY_ALLOWLIST = frozenset({
    # LLM provider keys
    "GROQ_API_KEY",
    "COHERE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "DEEPSEEK_API_KEY",
    "HUGGINGFACE_API_KEY",
    "HUGGINGFACEHUB_API_TOKEN",
    "REPLICATE_API_TOKEN",
    "PERPLEXITY_API_KEY",
    # CloakBrowser
    "CLOAKBROWSER_LICENSE_KEY",
    # Misc credentials
    "USER_ID",
    "PASSWORD",
    "EMAIL",
    "GITHUB_TOKEN",
})


def _scan_commented_env(env_path: Path, allowlist: Iterable[str]) -> dict:
    """
    .env file scan করে commented `# KEY=VALUE` lines থেকে values extract করে।
    শুধু allowlist-এর keys নেয় (PROXY etc. skip)।

    Returns dict of {KEY: VALUE}।
    """
    allowlist = frozenset(allowlist)
    found = {}
    if not env_path.exists():
        return found

    # Pattern: optional leading `# ` followed by KEY=VALUE
    # Group 1 = KEY (uppercase letters, digits, underscore)
    # Group 2 = VALUE (everything after =, stripped of whitespace)
    pattern = re.compile(
        r'^\s*#\s*([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*$',
        re.MULTILINE,
    )

    try:
        content = env_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = env_path.read_text(encoding='cp1252', errors='replace')

    placeholder_values = (
        'your_key_here',
        'your_cohere_key_here',
        'your_groq_api_key_here',
        'your_openai_api_key_here',
        'your_anthropic_api_key_here',
        'your_email_here',
        'your_password_here',
        'your_username_here',
        'your_token_here',
    )

    for match in pattern.finditer(content):
        key, value = match.group(1), match.group(2).strip()
        # Filter 1: শুধু allowlisted keys
        if key not in allowlist:
            continue
        # Filter 2: skip empty / placeholder values
        if not value or value.lower() in placeholder_values:
            continue
        # Filter 3: value must look like a real credential
        #   - API keys typically start with a known prefix (sk-, gsk-, xai-, etc.)
        #     অথবা hex/base62 string ≥ 20 chars।
        #   - তবে কিছু service (Cohere) random-looking prefix দেয় না, তাই
        #     length threshold ≥ 16 যথেষ্ট।
        if len(value) < 16:
            continue
        # Filter 4: example URLs / connection strings skip
        if any(scheme in value.lower() for scheme in
               ('://', 'http://', 'https://', 'socks5://', '@host', 'localhost')):
            continue
        found[key] = value
    return found


def load_env_robust(env_path: Optional[str] = None, override: bool = False) -> dict:
    """
    Robust .env loader:
      1. python-dotenv দিয়ে uncommented lines load করে
      2. commented `# KEY=VALUE` lines (allowlisted keys only) থেকে key extract
         করে os.environ-এ set করে (শুধু তখনই যখন os.environ-এ সেই key absent)।

    Args:
        env_path: .env file path (default: same dir as this script)
        override: True হলে commented value os.environ-এর existing value ও overwrite করবে

    Returns:
        dict of {KEY: VALUE} যা commented lines থেকে extract হয়েছে
    """
    if env_path is None:
        env_path = Path(__file__).parent / ".env"
    else:
        env_path = Path(env_path)

    # Step 1: standard dotenv load
    if env_path.exists():
        load_dotenv(env_path, override=override)

    # Step 2: commented fallback (allowlisted keys only)
    commented = _scan_commented_env(env_path, COMMENTED_KEY_ALLOWLIST)
    injected = {}
    for key, value in commented.items():
        if override or not os.getenv(key):
            os.environ[key] = value
            injected[key] = value
    return injected


if __name__ == "__main__":
    injected = load_env_robust(override=False)
    print(f"🔧 Injected from commented lines: {list(injected.keys())}")
    print(f"   COHERE_API_KEY present: {bool(os.getenv('COHERE_API_KEY'))}")
    print(f"   GROQ_API_KEY present:   {bool(os.getenv('GROQ_API_KEY'))}")
    print(f"   PROXY present (should be False): {bool(os.getenv('PROXY'))}")