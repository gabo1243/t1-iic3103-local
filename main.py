from flask import Flask, request
from utils import (send_message, login, get_token, check_user_connected, does_repo_exist, star_repo, remove_star_repo,
                    get_pull_requests, get_weekly_contributors, get_issues, create_web_hook, delete_web_hook,
                    is_repo_starred, get_hook, get_particular_commits)
from datetime import date


app = Flask(__name__)

class RepoInfo:
    def __init__(self, owner, repo, date_connected, status, starred, hook_id=None):
        self.owner = owner
        self.repo = repo
        self.date_connected = date_connected
        self.status = status
        self.starred = starred
        self.hook_id = hook_id
        self.installation_token = None

bdd: dict = {
    "user_id": None,
    "token": None,
    "chat_id": None,
    "repos": [],
    "msgs": dict()
}

def add_repo(owner, repo, token):
    if repo is not None and does_repo_exist(owner, repo, token):
        if any(r.owner == owner and r.repo == repo for r in bdd["repos"]):
            send_message(bdd["chat_id"], f"You are already connected to the repository: {owner}/{repo}")
            return
        is_starred = is_repo_starred(owner, repo, token)
        hook_id = get_hook(owner, repo, token)
        bdd["repos"].append(RepoInfo(owner, repo, date.today().isoformat(), "subscribed" if hook_id is not None else "not subscribed",
                                      "starred" if is_starred else "not starred", hook_id))
        send_message(bdd["chat_id"], f"Connected to repository: {owner}/{repo}")
    else:
        send_message(bdd["chat_id"], f"Connected to GitHub account successfully, but the repository {owner}/{repo} does not exist or is not accessible with the provided token.")

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/notification", methods=["POST"])
def notification():
    data = request.get_json()
    print("Received notification:", data)
    if bdd["chat_id"] is not None and "issue" in data:
        msg = (f"Received notification for repository: {data.get('repository', {}).get('full_name', 'unknown')}\n" +
                f"Event: {data.get('action', 'unknown')}\n" +
                f"Issue URL: {data.get('issue', {}).get('html_url', 'N/A')}\n" +
                f"Issue Title: {data.get('issue', {}).get('title', 'N/A')}\n" +
                f"User: {data.get('sender', {}).get('login', 'unknown')}\n")
        send_message(bdd["chat_id"], msg)
    return "Notification received!"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state", "//")
    items = state.split("/")
    user_id = items[0]
    owner = items[1]
    repo = items[2] if len(items) > 2 else None

    token = get_token(code)
    print("Received token:", token)
    bdd["user_id"] = user_id
    bdd["token"] = token
    

    add_repo(owner, repo, token)
    print(bdd)
    print("Received code:", code)
    return "Callback received!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    text = data.get("message", {}).get("text", "")
    is_reaction = "message_reaction" in data
    chat_id = data.get("message", {}).get("chat", {}).get("id") if not is_reaction else data.get("message_reaction", {}).get("chat", {}).get("id")
    
    if bdd["chat_id"] is None:
        bdd["chat_id"] = chat_id
    print("Received data:", data)
    print("Message text:", text)

    if text.startswith("/send"):
        response_text = text[len("/send "):]
        send_message(chat_id, response_text)
        
    elif text.startswith("/connect"):

        next_text = text[len("/connect "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /connect. For example: /connect owner/repo")
            return "OK"
        user_id = data.get("message", {}).get("from", {}).get("id")
        print(bdd["token"])
        if bdd["token"] is not None:
            add_repo(next_text.split("/")[0], next_text.split("/")[1], bdd["token"])
            return "OK"
        login_url = login(user_id, next_text)
        send_message(chat_id, f"Please click the following link to connect your GitHub account: {login_url}")

    elif text.startswith("/disconnect"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/disconnect "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /disconnect. For example: /disconnect owner/repo")
            return "OK"
        repo_to_disconnect = next_text.strip()
        bdd["repos"] = [repo for repo in bdd["repos"] if not (repo.owner == repo_to_disconnect.split("/")[0] and repo.repo == repo_to_disconnect.split("/")[1])]
        send_message(chat_id, f"Disconnected from repository: {repo_to_disconnect}")

    elif text.startswith("/repos"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        len_repos = len(bdd["repos"])
        if len_repos == 0:
            send_message(chat_id, "You have no connected repositories.")
            return "OK"
        send_message(chat_id, f"Your connected repositories ({len_repos}):")
        for repo in bdd["repos"]:
            msg = f"Connected repository: {repo.owner}/{repo.repo} (connected on {repo.date_connected}) - Status: {repo.status} - Starred: {repo.starred}.\n"
            msg += "React with a ❤ to star this repository." if repo.starred == "not starred" else "React with a 💔 to remove the star from this repository."
            msg_id = send_message(chat_id, msg)
            bdd["msgs"][msg_id] = repo

    elif text.startswith("/subscribe"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/subscribe "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /subscribe. For example: /subscribe owner/repo")
            return "OK"
        repo_to_subscribe = next_text.strip()
        for repo in bdd["repos"]:
            if repo.owner == repo_to_subscribe.split("/")[0] and repo.repo == repo_to_subscribe.split("/")[1]:
                if repo.status == "not subscribed":
                    hook_id = create_web_hook(repo.owner, repo.repo, bdd["token"])
                    repo.hook_id = hook_id
                    repo.status = "subscribed"
                    send_message(chat_id, f"Subscribed to repository: {repo_to_subscribe}")
                else:
                    send_message(chat_id, f"You are already subscribed to the repository: {repo_to_subscribe}")
                return "OK"
        send_message(chat_id, f"You are not connected to the repository: {repo_to_subscribe}")
        
    

    elif text.startswith("/unsubscribe"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/unsubscribe "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /unsubscribe. For example: /unsubscribe owner/repo")
            return "OK"
        repo_to_unsubscribe = next_text.strip()
        for repo in bdd["repos"]:
            if repo.owner == repo_to_unsubscribe.split("/")[0] and repo.repo == repo_to_unsubscribe.split("/")[1]:
                if repo.status == "subscribed":
                    delete_web_hook(repo.owner, repo.repo, bdd["token"], repo.hook_id)
                    repo.status = "not subscribed"
                    repo.hook_id = None
                    send_message(chat_id, f"Unsubscribed from repository: {repo_to_unsubscribe}")
                else:
                    send_message(chat_id, f"You are not subscribed to the repository: {repo_to_unsubscribe}")
                return "OK"
        send_message(chat_id, f"You are not connected to the repository: {repo_to_unsubscribe}")
                

    elif text.startswith("/stats"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/stats "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /stats. For example: /stats owner/repo")
            return "OK"
        repo = next_text.strip()
        response = get_weekly_contributors(repo.split("/")[0], repo.split("/")[1], bdd["token"])
        if response is not None:
            print(response)
            total_contributors = len(response)
            weekly_contributors = sorted(response, key=lambda x: x["last_week"]["c"], reverse=True)[:3]
            weekly_contributors = [f"{contributor['name']} (commits last week: {contributor['last_week']['c']})" for contributor in weekly_contributors]
            msg = f"Repository: {repo}\nTotal Contributors: {total_contributors}\nTop 3 Weekly Contributors: {weekly_contributors}"
            send_message(chat_id, msg)
        
        return "OK"

    elif text.startswith("/prs"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/prs "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /prs. For example: /prs owner/repo")
            return "OK"
        repo = next_text.strip()
        response = get_pull_requests(repo.split("/")[0], repo.split("/")[1], bdd["token"])
        if response is not None:
            total_prs = len(response)
            formatted_prs = []
            for pr in response:
                formatted_prs.append({
                    "title": pr.get("title"),
                    "url": pr.get("html_url"),
                    "state": pr.get("state"),
                    "created_at": pr.get("created_at"),
                    "user": pr.get("user", {}).get("login")
                })
            msg = f"Repository: {repo}\nTotal Open Pull Requests: {total_prs}\nPull Requests Details: {formatted_prs}"
            send_message(chat_id, msg)
        return "OK"
        

    elif text.startswith("/search"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/search "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /search. For example: /search owner/repo keyword")
            return "OK"
        parts = next_text.strip().split(" ")
        if len(parts) < 2:
            send_message(chat_id, "Please provide both the repository and the keyword. For example: /search owner/repo keyword")
            return "OK"
        repo = parts[0]
        keyword = " ".join(parts[1:])
        response = get_particular_commits(repo.split("/")[0], repo.split("/")[1], bdd["token"], keyword)
        if response is not None:
            total_commits = len(response)
            formatted_commits = []
            for commit in response:
                formatted_commits.append({
                    "message": commit.get("commit", {}).get("message"),
                    "url": commit.get("html_url"),
                    "author": commit.get("commit", {}).get("author", {}).get("name"),
                    "date": commit.get("commit", {}).get("author", {}).get("date")
                })
            msg = f"Repository: {repo}\nTotal Commits Found: {total_commits}\nCommits Details: {formatted_commits}"
            send_message(chat_id, msg)

    elif text.startswith("/issues"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        next_text = text[len("/issues "):]
        if len(next_text) == 0 or "/" not in next_text:
            send_message(chat_id, "Please provide a valid command after /issues. For example: /issues owner/repo")
            return "OK"
        repo = next_text.strip()
        response = get_issues(repo.split("/")[0], repo.split("/")[1], bdd["token"])
        if response is not None:
            total_issues = len(response)
            formatted_issues = []
            for issue in response:
                formatted_issues.append({
                    "title": issue.get("title"),
                    "url": issue.get("html_url"),
                    "state": issue.get("state"),
                    "created_at": issue.get("created_at"),
                    "user": issue.get("user", {}).get("login")
                })
            msg = f"Repository: {repo}\nTotal Open Issues: {total_issues}\nIssues Details: {formatted_issues}"
            send_message(chat_id, msg)
        return "OK"

    elif text.startswith("/info"):
        if not check_user_connected(bdd, chat_id):
            return "OK"
        msg = (
            "USER ID: " + str(bdd["user_id"]) + "\n" +
            "AUTH TOKEN: " + str(bdd["token"]) + "\n"
        )
        send_message(chat_id, msg)

    elif text.startswith("/help"):
        help_message = (
            "Author: gabo1243\n"
            "Github T1: https://github.com/IIC3103-2026-01/tarea-1-gabo1243\n"
            "Available commands:\n"
            "/send <message> - Send a message back to the chat.\n"
            "/connect <owner/repo> - Connect your GitHub account and specify a repository.\n"
            "/disconnect <owner/repo> - Disconnect from a specific repository.\n"
            "/repos - List your connected repositories.\n"
            "/subscribe <owner/repo> - Subscribe to notifications for the connected repository.\n"
            "/unsubscribe <owner/repo> - Unsubscribe from notifications for the connected repository.\n"
            "/stats <owner/repo> - Show statistics for the connected repository.\n"
            "/prs <owner/repo> - List pull requests for the connected repository.\n"
            "/search <owner/repo> - Search for issues or pull requests in the connected repository.\n"
            "/issues <owner/repo> - List issues for the connected repository.\n"
            "/help - Show this help message."
        )
        send_message(chat_id, help_message)
    
    elif is_reaction:
        reaction_emote_list = data.get("message_reaction", {}).get("new_reaction", {})
        reaction_emote = reaction_emote_list[0].get("emoji") if reaction_emote_list else "unknown"
        print("Received a message reaction:", reaction_emote)
        message_id = data.get("message_reaction", {}).get("message_id")
        repo_prev_msg = bdd["msgs"].get(message_id, None)
        if reaction_emote == "❤":
            print("Received a ❤ reaction for message ID:", message_id)
            if repo_prev_msg is not None:
                for i, repo in enumerate(bdd["repos"]):
                    print("Checking repo:", repo.owner + "/" + repo.repo, "against", repo_prev_msg)
                    if repo.owner + "/" + repo.repo == repo_prev_msg.owner + "/" + repo_prev_msg.repo and repo.starred == "not starred":
                        repo.starred = "starred"
                        star_repo(repo.owner, repo.repo, bdd["token"])
                        send_message(chat_id, f"Starred repository: {repo.owner}/{repo.repo}")
        elif reaction_emote == "💔":
            if repo_prev_msg is not None:
                for i, repo in enumerate(bdd["repos"]):
                    print("Checking repo:", repo.owner + "/" + repo.repo, "against", repo_prev_msg)
                    if repo.owner + "/" + repo.repo == repo_prev_msg.owner + "/" + repo_prev_msg.repo and repo.starred == "starred":
                        repo.starred = "not starred"
                        remove_star_repo(repo.owner, repo.repo, bdd["token"])
                        send_message(chat_id, f"Unstarred repository: {repo.owner}/{repo.repo}")

    else:
        send_message(chat_id, "Unknown command. Type /help for a list of available commands.")
        

    return "OK"
