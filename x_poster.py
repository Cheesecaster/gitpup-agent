#!/usr/bin/env python3
"""Post queued X/Twitter updates. Called from agent.py main loop."""
import os, json

ROOT = os.path.dirname(os.path.abspath(__file__))
X_QUEUE = os.path.join(ROOT, "data", "x_queue.jsonl")
X_POSTED = os.path.join(ROOT, "data", "x_posted.jsonl")

def _log(msg):
    with open(os.path.join(ROOT, "evolve.log"), "a") as f:
        f.write("[X_POSTER] {}\n".format(msg))

def process_x_queue():
    """Read x_queue, generate tweets, write to x_posted.
    Since we don't have xurl CLI on VPS, we queue posts for Hermes to pick up."""
    if not os.path.exists(X_QUEUE):
        return []
    posts = []
    with open(X_QUEUE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
                repo = post.get("repo", "")
                event = post.get("event", "")
                details = post.get("details", "")
                # Generate tweet text
                if event == "pr_created":
                    text = "Just contributed to {repo}! I studied the codebase in depth and found some docs improvements.\n\nWatch me live: https://gitpup.fun".format(repo=repo)
                elif event == "project_pushed":
                    text = "Just built and shipped a new project! {repo}\n\nI learned from studying 30+ GitHub repos and put it all together.\n\nCheck my journey: https://gitpup.fun/story".format(repo=repo)
                elif event == "repo_studied":
                    text = "Studied {repo} today and added it to my knowledge base. Always learning from the best open-source projects.\n\ngitpup.fun".format(repo=repo)
                else:
                    text = "Update from Goldie: {event} on {repo}".format(event=event, repo=repo)
                posts.append({"text": text, "repo": repo, "event": event, "timestamp": post.get("timestamp", 0)})
            except Exception:
                continue
    if posts:
        # Move to posted
        with open(X_POSTED, "a") as f:
            for p in posts:
                f.write(json.dumps(p) + "\n")
        # Clear queue
        open(X_QUEUE, "w").close()
        _log("Processed {} X posts".format(len(posts)))
    return posts
