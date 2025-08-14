# publish_openai.py
# Drop-in replacement for publish.py that uses OpenAI instead of Gemini.
# Requirements:
#   pip install openai google-api-python-client pytz jsonschema
#
# Env vars required:
#   GH_TOKEN                -> GitHub personal access token (repo scope)
#   OPENAI_API_KEY         -> OpenAI API key
#   OPENAI_MODEL           -> (optional) default: gpt-4.1
#   GOOGLE_API_KEY         -> (optional) for Google Custom Search
#   SEARCH_ENGINE_ID       -> (optional) Google CSE ID
#
# Usage:
#   python publish_openai.py
#
import os
import sys
import json
import base64
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

try:
    from jsonschema import validate, Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except Exception:
    JSONSCHEMA_AVAILABLE = False

# Optional: Google Custom Search for fresh inputs
try:
    from googleapiclient.discovery import build as google_build
    GSEARCH_AVAILABLE = True
except Exception:
    GSEARCH_AVAILABLE = False

# OpenAI client (new SDK style)
try:
    from openai import OpenAI
    OPENAI_SDK_V2 = True
except Exception:
    OPENAI_SDK_V2 = False

# ---------------- Configuration ----------------
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "mac-cyber-boop")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "guest-guide")
POSTS_DIRECTORY = os.getenv("POSTS_DIRECTORY", "_posts")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

# ---------------- Helpers ----------------
def log(msg, level="INFO"):
    print(f"[{level}] {msg}", flush=True)

def now_ist_date():
    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")

def slugify(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s or "post"

def github_api(url_path: str, method="GET", json_body=None, raw_body=None):
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("Missing GH token: set GITHUB_TOKEN or GH_TOKEN")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"https://api.github.com{url_path}"
    if method == "GET":
        r = requests.get(url, headers=headers)
    elif method == "PUT":
        r = requests.put(url, headers=headers, json=json_body, data=raw_body)
    else:
        r = requests.request(method, url, headers=headers, json=json_body, data=raw_body)
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub API error {r.status_code}: {r.text}")
    return r.json() if r.text else {}

def push_to_github(filename: str, markdown: str):
    path = f"{POSTS_DIRECTORY}/{filename}"
    log(f"Pushing to GitHub: {path}")
    content_b64 = base64.b64encode(markdown.encode("utf-8")).decode("utf-8")
    json_body = {
        "message": f"autopublish: {filename}",
        "content": content_b64,
    }
    return github_api(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}", method="PUT", json_body=json_body)

# ---------------- Search Inputs ----------------
def google_cse_search(q: str, num=6):
    if not (GOOGLE_API_KEY and SEARCH_ENGINE_ID and GSEARCH_AVAILABLE):
        log("Google CSE not configured; skipping search.", "WARN")
        return []
    service = google_build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    res = service.cse().list(q=q, cx=SEARCH_ENGINE_ID, num=num).execute()
    items = res.get("items", []) or []
    out = []
    for it in items:
        out.append({
            "title": it.get("title"),
            "url": it.get("link"),
            "snippet": it.get("snippet"),
            "published": None  # CSE doesn't always provide dates
        })
    return out

# ---------------- System Prompt ----------------
SYSTEM_PROMPT = r'''You are ZDB Autonomous Publisher, the AI operator for the “Zero Day Briefing” site.

Mission:
- From provided fresh web search snippets (and any structured inputs), pick ONE most-impactful, recent cybersecurity topic.
- Produce a publish-ready Markdown article with YAML front matter.
- Strictly avoid unsupported claims; only use provided inputs.

Allowed categories (choose exactly one): zero-day | hot-attacks | tools | tricks

Output contract (JSON only — no prose):
{
  "topic": "concise topic name from inputs",
  "title": "headline",
  "category": "zero-day | hot-attacks | tools | tricks",
  "excerpt": "≤ 50 words",
  "filename_suggestion": "slug-from-title.md",
  "sources": [{"title":"...", "url":"..."}],
  "markdown": "---\\nYAML front matter\\n---\\n\\nBody in Markdown"
}

YAML front matter required fields:
- title: same as JSON title
- date: <YYYY-MM-DD> (use provided now_ist_date)
- category: one of zero-day | hot-attacks | tools | tricks
- excerpt: ≤ 50 words

Writing guidance:
- Be technical, precise, readable.
- Use sections like Overview, Impact, Affected, Exploitation Status, Detection & Mitigation (as applicable).
- Include actionable bullet points when possible.
- Include optional sections when relevant:
  - IOCs: bullet list (IPs/domains/hashes)
  - Detections: placeholders for Sigma/YARA (no fake rules; outline detection ideas instead).
- If inputs are too weak to publish, return topic="NO-PUBLISH" and a two-sentence explanation in markdown explaining why.

Category rubric:
- zero-day: actively exploited & unpatched.
- hot-attacks: current campaigns/incidents/breaches.
- tools: new or updated offensive/defensive tools.
- tricks: methods, PoCs, bypasses, TTPs without a single news event.
'''

# JSON Schema for validation
JSON_SCHEMA = {
    "type": "object",
    "required": ["topic", "title", "category", "excerpt", "filename_suggestion", "sources", "markdown"],
    "properties": {
        "topic": {"type": "string", "minLength": 3},
        "title": {"type": "string", "minLength": 5},
        "category": {"type": "string", "enum": ["zero-day","hot-attacks","tools","tricks"]},
        "excerpt": {"type": "string", "minLength": 5, "maxLength": 400},
        "filename_suggestion": {"type": "string", "pattern": "^[a-z0-9-]+\\.md$"},
        "sources": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["title","url"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"}
                }
            }
        },
        "markdown": {"type": "string", "minLength": 50}
    }
}

# ---------------- OpenAI Call ----------------
def openai_generate(now_ist_date_str: str, search_items: list):
    user_payload = {
        "now_ist_date": now_ist_date_str,
        "search": search_items
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
    ]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    if OPENAI_SDK_V2:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            response_format={"type":"json_object"}
        )
        content = resp.choices[0].message.content
    else:
        # Legacy fallback using requests
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "response_format": {"type":"json_object"}
        }
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=120)
        if r.status_code >= 300:
            raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")
        content = r.json()["choices"][0]["message"]["content"]

    # Parse JSON
    try:
        data = json.loads(content)
    except Exception as e:
        # Try to extract the first JSON block with a regex
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise
        data = json.loads(m.group(0))

    # Validate schema
    if JSONSCHEMA_AVAILABLE:
        v = Draft7Validator(JSON_SCHEMA)
        errors = sorted(v.iter_errors(data), key=lambda e: e.path)
        if errors:
            msgs = "; ".join([f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors])
            raise RuntimeError(f"Model output failed schema validation: {msgs}")
    else:
        # Basic sanity checks
        if data.get("category") not in ["zero-day","hot-attacks","tools","tricks"]:
            raise RuntimeError("Invalid category in model output.")
        if not data.get("markdown","").startswith("---"):
            raise RuntimeError("Markdown must start with YAML front matter.")

    return data

# ---------------- Main ----------------
def main():
    log("Starting ZDB OpenAI publisher…")
    # Construct search inputs (tweak the query if you want a different niche)
    search_items = google_cse_search("cybersecurity critical vulnerability exploit CVE PoC breach malware campaign site:blog.vendor.com OR site:security.googleblog.com OR site:cert.gov OR site:github.com")
    now_date = now_ist_date()

    data = openai_generate(now_date, search_items)
    if data.get("topic") == "NO-PUBLISH":
        log("Model indicated NO-PUBLISH. Skipping commit.", "WARN")
        print(data.get("markdown",""))
        return

    title = data["title"]
    category = data["category"]
    excerpt = data["excerpt"]
    filename = data.get("filename_suggestion") or f"{slugify(title)}.md"
    if not re.match(r"^[a-z0-9-]+\\.md$", filename):
        filename = f"{slugify(title)}.md"

    markdown = data["markdown"]

    # Ensure YAML front matter contains the exact title/date/category/excerpt
    # If not, prepend/repair.
    if not markdown.strip().startswith("---"):
        front = f"---\\ntitle: \"{title}\"\\ndate: {now_date}\\ncategory: {category}\\nexcerpt: \"{excerpt}\"\\n---\\n\\n"
        markdown = front + markdown
    else:
        # Patch date/category/excerpt if missing
        # (Simple patching approach; assumes small front matter)
        def ensure_field(text, key, value, quote=False):
            pattern = re.compile(rf"^({key}):\\s*(.*)$", re.M)
            if not pattern.search(text):
                insert_point = text.find("---", 3)
                if insert_point != -1:
                    repl_val = f'"{value}"' if quote else value
                    text = text[:insert_point] + f"{key}: {repl_val}\\n" + text[insert_point:]
            return text
        fm_end = markdown.find("\n---", 3)
        if fm_end != -1:
            markdown = ensure_field(markdown, "title", title, quote=True)
            markdown = ensure_field(markdown, "date", now_date, quote=False)
            markdown = ensure_field(markdown, "category", category, quote=False)
            markdown = ensure_field(markdown, "excerpt", excerpt, quote=True)

    push_to_github(filename, markdown)
    log(f"Published: {filename}", "SUCCESS")

if __name__ == "__main__":
    main()