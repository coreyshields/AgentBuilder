from fastapi import FastAPI, Request
import requests
import os

app = FastAPI()

GITHUB_TOKEN = ''#token goes here


@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()

        print("🔥 Webhook received!")

        action = payload.get("action")
        print("Action:", action)

        # Only act on PR events
        if "pull_request" not in payload:
            return {"status": "not a PR event"}

        pr = payload["pull_request"]
        repo = payload["repository"]["full_name"]
        pr_number = pr["number"]

        print(f"Repo: {repo}, PR: {pr_number}")

        # Get diff
        diff_url = pr["diff_url"]
        diff = requests.get(diff_url).text

        print("Diff fetched (length):", len(diff))

        # TEMP: fake review (so nothing crashes)
        review = "✅ AI review placeholder: looks good overall, but this is a test."

        # Post comment to PR
        post_comment(repo, pr_number, review)

        return {"status": "success"}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {"error": str(e)}


def post_comment(repo, pr_number, review):
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    data = {
        "body": f"## 🤖 AI Code Review\n\n{review}"
    }

    response = requests.post(url, json=data, headers=headers)

    print("GitHub response:", response.status_code, response.text)