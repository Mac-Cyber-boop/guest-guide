import os
import sys
import requests
import datetime
import base64
import re
import google.generativeai as genai
from googleapiclient.discovery import build

# --- CONFIGURATION ---
GITHUB_OWNER = "mac-cyber-boop"
GITHUB_REPO = "guest-guide"
POSTS_DIRECTORY = "_posts"

# --- SETUP: API KEYS ---
try:
    GITHUB_TOKEN = os.environ["GH_TOKEN"]
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    SEARCH_ENGINE_ID = os.environ["SEARCH_ENGINE_ID"]
except KeyError as e:
    print(f"ERROR: Missing environment variable: {e}.")
    sys.exit(1)

# Configure the Gemini API client
genai.configure(api_key=GEMINI_API_KEY)

def log_info(message):
    print(f"[INFO] {message}")

def log_success(message):
    print(f"\033[92m[SUCCESS]\033[0m {message}")

def log_error(message):
    print(f"\033[91m[ERROR]\033[0m {message}")
    sys.exit(1)

def generate_filename(title):
    s = title.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    s = s.strip('-')
    return f"{s}.md"

def get_latest_cybersecurity_topic():
    """
    Uses AI to find the single most important cybersecurity news story or vulnerability
    disclosed in the last 24 hours.
    """
    log_info("Asking AI to research the latest cybersecurity topic...")
    prompt = """
    You are a world-class cybersecurity threat intelligence analyst.
    Your task is to identify the single most important, impactful, or widely discussed cybersecurity news story,
    vulnerability disclosure, major threat actor campaign, Zero-Day vulnerabilities, Latest Cybersecurity tools and tricks, Hacking tools, Hacking tricks that has emerged in the last 24 hours.

    Return only the specific, descriptive topic name. For example:
    - "Critical RCE Vulnerability in Apache Flink"
    - "BlackCat Ransomware Targets Healthcare Sector"
    - "Analysis of the new 'Sandman' APT Espionage Campaign"

    Provide only the topic.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        topic = response.text.strip()
        log_success(f"AI identified the latest topic: {topic}")
        return topic
    except Exception as e:
        log_error(f"Could not get the latest topic from AI: {e}")

def get_creative_title(topic):
    """Uses AI to generate a compelling title."""
    log_info("Asking AI to generate a creative title...")
    prompt = f"""
    You are a marketing expert and copywriter for a top-tier cybersecurity blog called 'Zero Day Briefing'.
    Your task is to take a technical topic and create a short, compelling, and 'hooked' blog post title.
    The title should be interesting and make people want to click.
    
    TOPIC: "{topic}"
    
    Generate one title.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        creative_title = response.text.strip().replace('"', '').replace('*', '')
        log_success(f"Generated Title: {creative_title}")
        return creative_title
    except Exception as e:
        log_error(f"Could not generate title from AI: {e}")

def research_cve_status(topic):
    """Researches a CVE to determine if it's a zero-day."""
    cve_match = re.search(r'(CVE-\d{4}-\d{4,7})', topic, re.IGNORECASE)
    if not cve_match:
        log_info("No CVE found in topic, defaulting category to 'hot-attacks'.")
        return 'hot-attacks'
        
    cve_id = cve_match.group(0).upper()
    log_info(f"CVE detected: {cve_id}. Researching its current status...")
    
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=f'"{cve_id}" patch status exploit', cx=SEARCH_ENGINE_ID, num=5).execute()
        
        snippets = " ".join([item['snippet'] for item in res.get('items', [])]).lower()
        
        is_unpatched = "unpatched" in snippets or "no patch" in snippets or "patch is not available" in snippets
        is_exploited = "actively exploited" in snippets or "in the wild" in snippets
        
        if is_unpatched and is_exploited:
            log_success(f"Research indicates {cve_id} is an active zero-day.")
            return 'zero-day'
        else:
            log_info(f"Research indicates {cve_id} is a known vulnerability, not a zero-day. Categorizing as 'hot-attacks'.")
            return 'hot-attacks'
            
    except Exception as e:
        log_error(f"Could not perform Google Search for CVE: {e}")

def get_ai_generated_post(title, topic, category):
    log_info(f"Sending final request to AI with title '{title}' and category '{category}'...")
    prompt = f"""
    You are a world-class cybersecurity analyst and writer for the 'Zero Day Briefing' blog. Your tone is technical, engaging, and authoritative.
    
    Write a detailed, in-depth blog post about the following original topic: "{topic}".

    The post MUST be formatted in markdown and MUST include a YAML frontmatter block at the very top.
    The frontmatter block must be enclosed in '---' and contain these exact fields and values:
    - title: "{title}"
    - date: {datetime.date.today().isoformat()}
    - category: {category}
    - excerpt: A compelling, one-sentence summary of the article, no more than 50 words.

  The main content of the article MUST be written in clean, readable format.
    
    **HTML Formatting and Readability Rules:**
    - The content MUST begin immediately after the final '---' of the frontmatter.
    - Use Bullet for Bullet points.
    - Ensure the Bullet Points are used where needed.
    - Make the content more read friendly.
    - Ensure proper paragraph breaks to avoid large walls of text.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        log_success("AI has generated the full article.")
        return response.text
    except Exception as e:
        log_error(f"Could not generate content from AI: {e}")

def push_to_github(filename, content):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{POSTS_DIRECTORY}/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    sha = None
    try:
        get_response = requests.get(url, headers=headers)
        if get_response.status_code == 200:
            sha = get_response.json()['sha']
            log_info(f"File '{filename}' already exists. This is unusual for an autonomous script. Overwriting.")
    except requests.exceptions.RequestException:
        pass

    data = {
        "message": f"[AI PUBLISH] Create post: {filename}",
        "content": encoded_content,
        "committer": {"name": "ZDB AI Publisher", "email": "ai@zerodaybriefing.com"}
    }
    if sha:
        data["sha"] = sha

    log_info(f"Pushing '{filename}' to GitHub repository...")
    try:
        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()
        log_success(f"Successfully pushed '{filename}' to GitHub.")
    except requests.exceptions.RequestException as e:
        log_error(f"Failed to push to GitHub: {e}. Response: {response.text}")

if __name__ == "__main__":
    # --- Fully Autonomous Workflow ---
    # 1. Get the latest topic from the AI
    original_topic = get_latest_cybersecurity_topic()
    
    # 2. The rest of the process is the same as before
    creative_title = get_creative_title(original_topic)
    post_category = research_cve_status(original_topic)
    markdown_content = get_ai_generated_post(creative_title, original_topic, post_category)
    new_filename = generate_filename(creative_title)
    push_to_github(new_filename, markdown_content)
    
    log_success("Automation complete. A new post should be live in ~60 seconds.")
