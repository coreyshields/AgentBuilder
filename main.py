# main.py
from fastapi import FastAPI, Request, Header
import requests
import os
from dotenv import load_dotenv
import hmac
import hashlib
from openai import OpenAI

# Load environment variables from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

print("OPENAI_API_KEY loaded:", bool(OPENAI_API_KEY))
print("GITHUB_TOKEN loaded:", bool(GITHUB_TOKEN))

app = FastAPI()

# Initialize OpenAI client
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)


# Verify GitHub webhook signature (optional, skip if no secret)
def verify_signature(payload_body, signature_header):
    if not WEBHOOK_SECRET:
        return True
    if signature_header is None:
        return False
    try:
        sha_name, signature = signature_header.split("=")
        mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception:
        return False


# AI review function using new OpenAI API
def run_ai_review(diff: str) -> str:
    if not client:
        print("⚠️ No OpenAI API key set. Returning placeholder review.")
        return "⚠️ AI review not run: OPENAI_API_KEY not set."
    try:
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
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful and thorough code reviewer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print("❌ Error in run_ai_review:", e)
        return f"⚠️ AI review failed: {e}"


# Post comment to GitHub PR
def post_comment(repo: str, pr_number: int, review: str):
    if not GITHUB_TOKEN:
        print("⚠️ No GitHub token set. Skipping comment.")
        return
    try:
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        data = {"body": f"## 🤖 AI Code Review\n\n{review}"}
        response = requests.post(url, json=data, headers=headers)
        print("GitHub response:", response.status_code, response.text)
    except Exception as e:
        print("❌ Error posting GitHub comment:", e)


@app.post("/webhook")
async def webhook(request: Request, x_hub_signature_256: str = Header(None)):
    try:
        payload_body = await request.body()

        # Verify signature
        if not verify_signature(payload_body, x_hub_signature_256):
            return {"status": "ignored", "reason": "invalid signature"}

        payload = await request.json()
        action = payload.get("action")
        print("Webhook action:", action)

        # Only handle PR opened or updated
        if action not in ["opened", "synchronize"]:
            return {"status": "ignored", "reason": "not a PR event"}

        if "pull_request" not in payload or "repository" not in payload:
            return {"status": "ignored", "reason": "missing PR or repo"}

        pr = payload["pull_request"]
        repo = payload["repository"]["full_name"]
        pr_number = pr.get("number")
        diff_url = pr.get("diff_url")

        print(f"Processing PR #{pr_number} in repo {repo}")

        # Fetch PR diff safely
        diff = ""
        if diff_url:
            try:
                diff = requests.get(diff_url).text
                print(f"Fetched diff of length {len(diff)}")
            except Exception as e:
                print("❌ Error fetching diff:", e)
        else:
            print("⚠️ No diff URL available")

        # Run AI review
        review = run_ai_review(diff)

        # Post comment to GitHub
        post_comment(repo, pr_number, review)

        return {"status": "ok", "pr_number": pr_number}

    except Exception as e:
        print("❌ Unexpected error in webhook:", e)
        return {"status": "error", "message": str(e)}