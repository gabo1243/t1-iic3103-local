import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
URL = os.getenv("URL")
CLIENT_ID = os.getenv("CLIENT_ID")
GITHUB_LOGIN_URL = os.getenv("GITHUB_LOGIN_URL")
GITHUB_TOKEN_URL = os.getenv("GITHUB_TOKEN_URL","")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    response = requests.post(url, json={
        "chat_id": chat_id,
        "text": text
    })

    print("Status:", response.status_code)
    print("Response:", response.json())
    return response.json().get("result", {}).get("message_id")

def login(user_id, repo):
    state = str(user_id)+"/"+repo
    url = f"{GITHUB_LOGIN_URL}?client_id={CLIENT_ID}&redirect_uri={URL}/callback&state={state}&scope=repo"
    return url

def does_repo_exist(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    print(token)
    response = requests.get(url, headers={"Authorization": f"token {token}"})
    print("Checking if repo exists. Status:", response.status_code)
    return response.status_code == 200

def star_repo(owner, repo, token):
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    response = requests.put(url, headers={"Authorization": f"token {token}"})
    print("Starring repo. Status:", response.status_code)
    print("Response:", response)
    return response.status_code == 204

def remove_star_repo(owner, repo, token):
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    response = requests.delete(url, headers={"Authorization": f"token {token}"})
    print("Removing star from repo. Status:", response.status_code)
    return response.status_code == 204

def get_pull_requests(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    response = requests.get(url, headers={"Authorization": f"token {token}"})
    print("Getting pull requests. Status:", response.status_code)
    if response.status_code == 200:
        return response.json()
    return None

def get_weekly_contributors(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/contributors"
    response = requests.get(url, headers={"Authorization": f"token {token}"})
    print("Getting weekly contributors. Status:", response.status_code)
    if response.status_code == 200:
        list_response = response.json()
        data = []
        for contributor in list_response:
            if contributor["author"] is None:
                continue
            data.append({
                "name": contributor["author"]["login"],
                "total": contributor["total"],
                "last_week": contributor["weeks"][-1] if contributor["weeks"] else {"w": None, "a": 0, "d": 0, "c": 0}
            })
        return data
    return None

def get_issues(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    response = requests.get(url, headers={"Authorization": f"token {token}"})
    print("Getting issues. Status:", response.status_code)
    if response.status_code == 200:
        return response.json()
    return None

def get_particular_commits(owner, repo, token, keyword):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    response = requests.get(url, headers={"Authorization": f"token {token}"}, params={"q": keyword})
    print("Getting commits with keyword. Status:", response.status_code)
    if response.status_code == 200:
        final_response = []
        for commit in response.json():
            if ((keyword.lower() in commit.get("commit", {}).get("message", "").lower()) or (keyword.lower() in commit.get("commit", {}).get("author", {}).get("name", "").lower()) or
                (keyword.lower() in commit.get("commit", {}).get("author", {}).get("email", "").lower()) or (keyword.lower() in commit.get("html_url", "").lower())
                or (keyword.lower() in commit.get("commit", {}).get("author", {}).get("date", "").lower())):
                final_response.append(commit)
        return final_response
    return None

def get_token(code):
    url = GITHUB_TOKEN_URL
    
    response = requests.post(url, json={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code
    }, headers={"Accept": "application/json"})
    print("Status TOKEN:", response.status_code)
    print("Response:", response.json())
    return response.json().get("access_token")

def check_user_connected(bdd, chat_id):
    user_id = bdd.get("user_id", None)
    token = bdd.get("token", None)
    if user_id is None or token is None:
        send_message(chat_id, "Please connect your GitHub account first!")
        return False
    return True

def create_web_hook(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/hooks"
    response = requests.post(url, headers={"Authorization": f"token {token}"}, json={
        "name": "web",
        "active": True,
        "events": ["issues"],
        "config": {
            "url": f"{URL}/notification",
            "content_type": "json",
            "secret": CLIENT_SECRET
        }
    })
    print("Creating webhook. Status:", response.status_code)
    print("Response:", response.json())
    hook_id = response.json().get("id")
    return hook_id

def delete_web_hook(owner, repo, token, hook_id):
    url = f"https://api.github.com/repos/{owner}/{repo}/hooks/{hook_id}"
    response = requests.delete(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
    print("HOOK ID:", hook_id)
    print("Deleting webhook:", response)
    print("Deleting webhook. Status:", response.status_code)
    return response.status_code == 204

def is_repo_starred(owner, repo, token):
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    response = requests.get(url, headers={"Authorization": f"token {token}", })
    print("Checking if repo is starred. Status:", response.status_code)
    return response.status_code == 204

def get_hook(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/hooks"
    response = requests.get(url, headers={"Authorization": f"token {token}"})
    print("Checking if there is a hook. Status:", response.status_code)
    if response.status_code == 200:
        print("Response:", response.json())
        hooks = response.json()
        for hook in hooks:
            if hook["config"].get("url") == f"{URL}/notification":
                return hook["id"]
    return None