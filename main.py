from fastapi import FastAPI, Request, Header, HTTPException
import requests
import os
from dotenv import load_dotenv
import openai
import hmac
import hashlib

# Load environment variables from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

openai.api_key = OPENAI_API_KEY
app = FastAPI()

# Verify GitHub webhook signature
def verify_signature(payload_body, signature_header):
    if signature_header is None:
        return False
    sha_name, signature = signature_header.split('=')
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

# Function to call OpenAI API for code review
def run_ai_review(diff):
    prompt = f"""
    You are a senior software engineer performing a code review.
    
    Analyze this diff for:
    - Security vulnerabilities
    - Performance issues
    - Scalability problems
    - Code readability and style

    Provide actionable suggestions as bullet points.
    Diff:
    {diff}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful and thorough code reviewer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    review_text = response['choices'][0]['message']['content']
    return review_text

# Function to post a comment on a GitHub PR
def post_comment(repo, pr_number, review):
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    data = {"body": f"## 🤖 AI Code Review\n\n{review}"}
    response = requests.post(url, json=data, headers=headers)
    print("GitHub response:", response.status_code, response.text)


# Webhook endpoint
@app.post("/webhook")
async def webhook(request: Request, x_hub_signature_256: str = Header(None)):
    payload_body = await request.body()

    # Verify signature
    if not verify_signature(payload_body, x_hub_signature_256):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    action = payload.get("action")
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored"}

    if "pull_request" not in payload:
        return {"status": "not a PR event"}

    pr = payload["pull_request"]
    repo = payload["repository"]["full_name"]
    pr_number = pr["number"]

    print(f"Processing PR #{pr_number} in {repo}")

    # Fetch PR diff
    diff_url = pr["diff_url"]
    diff = requests.get(diff_url).text
    print(f"Fetched diff of length {len(diff)}")

    # Run AI review
    review = run_ai_review(diff)

    # Post comment to GitHub
    post_comment(repo, pr_number, review)

    return {"status": "review posted"}
