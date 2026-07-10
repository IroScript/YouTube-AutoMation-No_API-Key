"""
CloakBrowser Login Bot - Stealth browser automation with login support.
Credentials are loaded from .env file for security.

Usage:
    1. Copy .env.example to .env and fill in your credentials
    2. python login_bot.py
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from cloakbrowser import launch

# ─── Load credentials from .env ───
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print("❌ .env ফাইল পাওয়া যায়নি!")
    print("📄 .env.example কপি করে .env তৈরি করুন এবং তথ্য দিন:")
    print("   copy .env.example .env")
    exit(1)

LOGIN_URL = os.getenv("LOGIN_URL", "")
USER_ID = os.getenv("USER_ID", "")
PASSWORD = os.getenv("PASSWORD", "")
USER_ID_SELECTOR = os.getenv("USER_ID_SELECTOR", 'input[name="username"], input[type="text"], input[name="email"]')
PASSWORD_SELECTOR = os.getenv("PASSWORD_SELECTOR", 'input[type="password"]')
SUBMIT_SELECTOR = os.getenv("SUBMIT_SELECTOR", 'button[type="submit"], input[type="submit"]')
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
HUMANIZE = os.getenv("HUMANIZE", "true").lower() == "true"
PROXY = os.getenv("PROXY", "")

if not all([LOGIN_URL, USER_ID, PASSWORD]):
    print("❌ .env ফাইলে LOGIN_URL, USER_ID, PASSWORD সেট করুন!")
    exit(1)

# ─── Launch stealth browser ───
print("🚀 CloakBrowser চালু হচ্ছে...")

launch_kwargs = {
    "headless": HEADLESS,
    "humanize": HUMANIZE,
}

if PROXY:
    launch_kwargs["proxy"] = PROXY
    launch_kwargs["geoip"] = True

browser = launch(**launch_kwargs)
page = browser.new_page()

# ─── Navigate to login page ───
print(f"🌐 লগইন পেজে যাচ্ছি: {LOGIN_URL}")
page.goto(LOGIN_URL)
time.sleep(2)

# ─── Fill login form ───
print("✏️ ইউজার আইডি দেওয়া হচ্ছে...")
try:
    user_field = page.locator(USER_ID_SELECTOR).first
    user_field.wait_for(state="visible", timeout=10000)
    user_field.type(USER_ID, delay=50)
except Exception as e:
    print(f"⚠️ ইউজার আইডি ফিল্ড পাওয়া যায়নি: {e}")
    print("💡 .env তে USER_ID_SELECTOR আপডেট করুন")

print("🔐 পাসওয়ার্ড দেওয়া হচ্ছে...")
try:
    pass_field = page.locator(PASSWORD_SELECTOR).first
    pass_field.wait_for(state="visible", timeout=10000)
    pass_field.type(PASSWORD, delay=50)
except Exception as e:
    print(f"⚠️ পাসওয়ার্ড ফিল্ড পাওয়া যায়নি: {e}")
    print("💡 .env তে PASSWORD_SELECTOR আপডেট করুন")

time.sleep(1)

# ─── Submit login ───
print("🖱️ লগইন বাটনে ক্লিক করা হচ্ছে...")
try:
    submit_btn = page.locator(SUBMIT_SELECTOR).first
    submit_btn.wait_for(state="visible", timeout=10000)
    submit_btn.click()
except Exception as e:
    print(f"⚠️ সাবমিট বাটন পাওয়া যায়নি: {e}")
    print("💡 .env তে SUBMIT_SELECTOR আপডেট করুন")

time.sleep(3)

# ─── Post-login actions ───
print(f"📄 বর্তমান URL: {page.url}")
print(f"📝 পেজ টাইটেল: {page.title()}")

# Take a screenshot after login
screenshot_path = Path(__file__).parent / "login_result.png"
page.screenshot(path=str(screenshot_path))
print(f"📸 স্ক্রিনশট সেভ হয়েছে: {screenshot_path}")

# ─── Keep browser open for manual use ───
print("\n✅ লগইন সম্পন্ন!")
print("🔍 ব্রাউজার খোলা আছে — আপনি নিজে কাজ করতে পারেন")
print("📌 বন্ধ করতে এই উইন্ডোতে Enter চাপুন...")
input()

browser.close()
print("👋 ব্রাউজার বন্ধ হয়েছে।")
