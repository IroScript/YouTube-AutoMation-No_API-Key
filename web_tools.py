"""
🔧 Web Research Tools — Agent tool-use loop এ ব্যবহৃত হবে
============================================================

Cohere-এর tool-use API-তে এই functions invoke করা হবে যখন agent
unfamiliar UI pattern দেখে — সে web search করে docs থেকে শিখবে।

Tools:
  • web_search(query)  → DuckDuckGo HTML (no API key required)
  • fetch_url(url)     → URL fetch + HTML strip (plain text)

সব tool JSON-serializable dict return করে — Cohere tool message-এ
directly pass করা যাবে।
"""

import re
import json
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional


# ─── HTML → text converter (no external dep) ─────────────────
class _HTMLTextExtractor(HTMLParser):
    """
    Minimal HTML→text converter — script/style/nav বাদ দিয়ে readable text বের করে।
    Cohere tool result-এ plain text দরকার।
    """

    SKIP_TAGS = frozenset({
        "script", "style", "noscript", "iframe", "svg", "canvas",
        "header", "footer", "nav", "aside", "form",
    })
    BLOCK_TAGS = frozenset({
        "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3",
        "h4", "h5", "h6", "tr", "td", "section", "article",
    })

    def __init__(self):
        super().__init__()
        self._text: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag in self.BLOCK_TAGS:
            self._text.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in self.BLOCK_TAGS:
            self._text.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._text.append(data)

    @property
    def text(self) -> str:
        out = "".join(self._text)
        # Collapse whitespace
        out = re.sub(r"[ \t]+", " ", out)
        out = re.sub(r"\n[ \t]+", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.text


# ─── Web search (DuckDuckGo HTML — no API key) ─────────────────
def web_search(query: str, max_results: int = 5,
               timeout: int = 10) -> Dict[str, Any]:
    """
    DuckDuckGo HTML search — returns list of {title, url, snippet}.

    Returns:
        {
            "query": str,
            "results": [{title, url, snippet}],
            "count": int
        }
    """
    try:
        encoded = urllib.parse.urlencode({"q": query})
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return {"query": query, "error": f"search failed: {e}", "results": [], "count": 0}

    # Extract results — DDG HTML uses .result class for each item
    results: List[Dict[str, str]] = []
    # Match result blocks (title + URL + snippet)
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        url_href, title_html, snippet_html = match.groups()
        # Strip HTML tags
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
        # DDG wraps URLs in a redirect — extract real URL
        if "uddg=" in url_href:
            from urllib.parse import parse_qs
            qs = parse_qs(url_href.split("?", 1)[-1])
            url_href = qs.get("uddg", [url_href])[0]
        results.append({
            "title": title[:200],
            "url": url_href,
            "snippet": snippet[:300],
        })
        if len(results) >= max_results:
            break

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }


# ─── URL fetch (plain HTML read + strip) ───────────────────────
def fetch_url(url: str, max_chars: int = 3000,
              timeout: int = 10) -> Dict[str, Any]:
    """
    URL fetch করে plain text content return করে।
    HTML tags strip করে, script/style বাদ দিয়ে।

    Returns:
        {
            "url": str,
            "title": str,
            "text": str (truncated to max_chars),
            "truncated": bool,
            "error": str | None
        }
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml,text/plain",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            # Detect charset
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ct, re.IGNORECASE)
            if m:
                charset = m.group(1)
            html = raw.decode(charset, errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return {"url": url, "error": f"fetch failed: {e}", "text": "", "title": ""}

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""

    # Convert to text
    text = _html_to_text(html)
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "\n\n... [truncated]"

    return {
        "url": url,
        "title": title[:200],
        "text": text,
        "truncated": truncated,
    }


# ─── Tool definitions for Cohere tool-use API ─────────────────
# Cohere v2 tool definitions — passed to client.chat(tools=[...])
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for documentation, UI patterns, button "
                "labels, or any information about an unfamiliar interface. "
                "Use when you don't recognize a UI element (e.g. arrow-only "
                "button, hidden submit, custom widget). Returns top 5 results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Fetch a specific URL and return its plain-text content. "
                "Use after web_search to read a specific page that looks "
                "relevant — e.g. official docs for Veo 3, Google Docs "
                "editor, YouTube Studio, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters to return (default 3000)",
                        "default": 3000,
                    },
                },
                "required": ["url"],
            },
        },
    },
]


def invoke_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool name + arguments দিয়ে actual tool execute করে।
    Cohere tool_calls থেকে আসা name + parsed args pass হবে।
    """
    if name == "web_search":
        return web_search(
            query=arguments.get("query", ""),
            max_results=arguments.get("max_results", 5),
        )
    if name == "fetch_url":
        return fetch_url(
            url=arguments.get("url", ""),
            max_chars=arguments.get("max_chars", 3000),
        )
    return {"error": f"unknown tool: {name}"}


# ─── Standalone test ──────────────────────────────────────────
if __name__ == "__main__":
    print("🔧 Web Tools — standalone test\n")
    print("→ web_search('Veo 3.1 Fast model')...")
    r = web_search("Veo 3.1 Fast", max_results=3)
    print(json.dumps(r, indent=2, ensure_ascii=False)[:600])
    print("\n→ fetch_url('https://example.com')...")
    r = fetch_url("https://example.com", max_chars=300)
    print(json.dumps(r, indent=2, ensure_ascii=False)[:600])