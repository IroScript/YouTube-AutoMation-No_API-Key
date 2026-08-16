r"""
browser-use Web Interface Chat Automation
==========================================
Target Chrome Executable: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe
Profile Path: C:\\Users\Irak\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 7

Features:
1. Uses AI Browser Agent (`browser-use` library).
2. Connects to existing Chrome session via CDP or launches Chrome with Profile 7.
3. Automates reading prompt, sending to AI chat interface (ChatGPT, Claude, Gemini),
   waiting for response, copying text, and writing to browser-use/output.txt.
"""

import os
import sys
import asyncio
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"C:\Users\Irak\AppData\Local\Google\Chrome\User Data"
PROFILE_NAME = "Profile 7"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "output.txt")
DEFAULT_PROMPT_FILE = os.path.join(SCRIPT_DIR, "prompt.txt")

def get_prompt(prompt_arg=None):
    if prompt_arg:
        return prompt_arg
    if os.path.exists(DEFAULT_PROMPT_FILE):
        with open(DEFAULT_PROMPT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return content
    return "Hello! Write a 2-line short poem about AI."

async def run_browser_use_agent(prompt_text, url="https://chatgpt.com", output_file=DEFAULT_OUTPUT_FILE):
    try:
        from browser_use import Agent, Browser
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        print(f"[browser-use] Import error: {e}")
        print("[browser-use] Please ensure 'pip install browser-use langchain-openai' completes.")
        sys.exit(1)

    print(f"[browser-use] Starting AI Browser Agent...")
    print(f"[browser-use] Target URL: {url}")
    print(f"[browser-use] Prompt: {prompt_text}")

    # Configure Browser
    try:
        browser = Browser.from_system_chrome()
        print("[browser-use] Browser initialized via system Chrome.")
    except Exception as e:
        print(f"[browser-use] System Chrome initialization note ({e}). Using default Browser...")
        browser = Browser()

    task_description = (
        f"Go to {url}. "
        f"Find the chat prompt input box, paste the following prompt: '{prompt_text}', "
        f"and click the send button or press enter. "
        f"Wait until the AI stops generating the response. "
        f"Extract the full text of the AI response and print it."
    )

    # Initialize LLM for Agent (Gemini, OpenRouter, or OpenAI API)
    gemini_key = os.getenv("GEMINI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    llm = None
    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            print("[browser-use] Using Gemini API (gemini-2.5-flash) for LLM Agent...")
            llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=gemini_key)
            object.__setattr__(llm, 'provider', 'google')
            object.__setattr__(llm, 'model_name', 'gemini-2.5-flash')
        except Exception as e:
            print(f"[browser-use] Gemini initialization note: {e}")

    if not llm and openrouter_key:
        print("[browser-use] Using OpenRouter API (openai/gpt-4o) for LLM Agent...")
        llm = ChatOpenAI(
            model="openai/gpt-4o",
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1"
        )
        object.__setattr__(llm, 'provider', 'openai')
    elif not llm and openai_key:
        print("[browser-use] Using OpenAI API for LLM Agent...")
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_key)
        object.__setattr__(llm, 'provider', 'openai')
    elif not llm:
        print("[browser-use] Warning: No valid LLM API key (GEMINI_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY) found.")

    try:
        if llm:
            agent = Agent(
                task=task_description,
                llm=llm,
                browser=browser
            )
            print("[browser-use] Agent running task...")
            result = await agent.run()
            response_text = str(result)
        else:
            response_text = f"[browser-use Script Configured]\nTask: {task_description}\nChrome Path: {CHROME_PATH}\nProfile: {PROFILE_NAME}"

        print("\n" + "="*50)
        print("[browser-use] AGENT RESULT:")
        print("="*50)
        print(response_text)
        print("="*50 + "\n")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response_text)
        print(f"[browser-use] Saved output to {output_file}")

    finally:
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="browser-use AI Chat Automation")
    parser.add_argument("--prompt", type=str, help="Prompt text to send")
    parser.add_argument("--url", type=str, default="https://chatgpt.com", help="Target URL")
    args = parser.parse_args()

    prompt = get_prompt(args.prompt)
    asyncio.run(run_browser_use_agent(prompt, url=args.url))
