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
    """Prints an informational message."""
    print(f"[INFO] {message}")

def log_success(message):
    """Prints a success message."""
    print(f"\033[92m[SUCCESS]\033[0m {message}")

def log_error(message):
    """Prints an error message and exits."""
    print(f"\033[91m[ERROR]\033[0m {message}")
    sys.exit(1)

def generate_filename(title):
    """Creates a URL-friendly filename from a post title."""
    s = title.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    s = s.strip('-')
    return f"{s}.md"

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
            log_info(f"Research indicates {cve_id} is a known vulnerability. Categorizing as 'hot-attacks'.")
            return 'hot-attacks'
            
    except Exception as e:
        log_error(f"Could not perform Google Search for CVE: {e}")

def get_ai_generated_post(topic, category):
    """
    Uses a single, powerful prompt to generate the entire formatted post, including a creative title.
    """
    log_info("Sending topic to AI for full article generation...")
    
    # This is a "few-shot" prompt. We give it a perfect example to copy.
    prompt = f"""
    You are an autonomous cybersecurity blog writer for 'Zero Day Briefing'. Your output MUST be a single, complete markdown file with YAML frontmatter, followed by the article content in 1500-2000 words.
    
    DO NOT include any commentary, conversation, or explanations before or after the markdown file content. Your entire response must be ONLY the markdown file content and nothing else.

    HERE IS A PERFECT EXAMPLE OF THE REQUIRED OUTPUT FORMAT:
    ---
    title: "Critical RCE Flaw in Apache Flink Threatens Data Centers"
    date: 2025-07-27
    category: hot-attacks
    excerpt: "A critical remote code execution vulnerability in Apache Flink allows unauthenticated attackers to take over servers, posing a severe risk to data processing infrastructure worldwide."
    ---
    Vulnerability Overview
    Security researchers have disclosed a critical remote code execution (RCE) vulnerability affecting Apache Flink, a popular open-source framework for stream processing. The flaw allows an attacker to execute arbitrary code on the server, potentially leading to a full system compromise.
    
        Affected Versions:</strong> All versions prior to 1.18.0
        Severity:</strong> Critical (CVSS 9.8)
        
   Impact
   Successful exploitation of this vulnerability could allow attackers to steal sensitive data, deploy ransomware, or use the compromised server as a pivot point to attack other systems within the network.

    **NOW, GENERATE A COMPLETE MARKDOWN FILE IN THE EXACT SAME FORMAT FOR THE FOLLOWING TOPIC:**
    "{topic}"
    
    **USE THE FOLLOWING CATEGORY IN THE FRONTMATTER:**
    "{category}"
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        # The AI will return the full text, including the frontmatter.
        full_content = response.text.strip()
        
        # Extract the title from the generated frontmatter for the filename
        title_match = re.search(r'title:\s*["\']?(.*?)["\']?$', full_content, re.MULTILINE)
        if not title_match:
            log_error("AI failed to generate a title in the frontmatter.")
        
        creative_title = title_match.group(1).strip()
        
        log_success(f"AI generated article with title: '{creative_title}'")
        return creative_title, full_content
        
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
            log_info(f"File '{filename}' already exists. Overwriting.")
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
    if len(sys.argv) < 2:
        original_topic = get_latest_cybersecurity_topic()
    else:
        original_topic = sys.argv[1]
    
    # --- New Simplified Workflow ---
    # 1. Research the topic to determine the category
    post_category = research_cve_status(original_topic)
    
    # 2. Generate the title and full content in one step
    creative_title, full_content = get_ai_generated_post(original_topic, post_category)
    
    # 3. Generate a filename from the new title
    new_filename = generate_filename(creative_title)
    
    # 4. Push the new file to GitHub
    push_to_github(new_filename, full_content)
    
    log_success("Automation complete. Your new post should be live in ~60 seconds.")
