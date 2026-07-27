#!/usr/bin/env python3
"""
Copilot Adapter - lightweight local HTTP adapter exposing a small agent surface
Port 18796 — allows local tooling to address this workspace as a Copilot-backed agent
"""
import json
import os
import subprocess
import sys
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

AGENT_NAME = "Git-Copilot"
WAR_ROOM = "http://127.0.0.1:18800"
HOST = "127.0.0.1"
PORT = 18796
ROUTER_URL = "http://localhost:20128"


def post_thought(thought: str, status: str = "thinking"):
    """Post a thinking indicator to the war room."""
    try:
        data = json.dumps({
            "sender": AGENT_NAME,
            "thought": thought,
            "status": status,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18800/thinking",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

SESSION_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SESSION_STATE.md")
INBOX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inboxes", "git-copilot", "inbox.md")

def load_session_state():
    """Load session state for continuity across restarts."""
    try:
        with open(SESSION_STATE_PATH) as f:
            content = f.read()
            state = {
                "active": True,
                "last_date": "",
                "instructions": []
            }
            for line in content.split("\n"):
                if "**Date:**" in line:
                    state["last_date"] = line.split("**Date:**")[1].strip()
                elif line.startswith("- **Git-Copilot:**"):
                    state["instructions"].append(line.split(":")[1].strip())
            return state
    except FileNotFoundError:
        return {"active": False}

def load_inbox():
    """Load agent inbox for task coordination."""
    try:
        with open(INBOX_PATH) as f:
            content = f.read()
            inbox = {
                "high_priority": [],
                "medium_priority": [],
                "low_priority": [],
                "coordination": [],
                "completed": []
            }
            section = None
            for line in content.split("\n"):
                if "Priority: HIGH" in line:
                    section = "high_priority"
                elif "Priority: MEDIUM" in line:
                    section = "medium_priority"
                elif "Priority: LOW" in line:
                    section = "low_priority"
                elif "Pending Coordination" in line:
                    section = "coordination"
                elif "Completed" in line:
                    section = "completed"
                elif line.startswith("- [ ]") and section:
                    inbox[section].append(line[6:])
                elif line.startswith("- ") and section == "completed":
                    inbox[section].append(line[2:])
            return inbox
    except FileNotFoundError:
        return {"high_priority": [], "medium_priority": [], "low_priority": [], "coordination": [], "completed": []}

SESSION_STATE = load_session_state()
INBOX = load_inbox()

def save_agent_state():
    """Save current agent state for backup."""
    import shutil
    from datetime import datetime
    
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups", "git-copilot")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save inbox
    if os.path.exists(INBOX_PATH):
        shutil.copy2(INBOX_PATH, os.path.join(backup_dir, "inbox", f"inbox_{timestamp}.md"))
    
    # Trim old backups (keep last 5)
    for subdir in ["inbox", "session", "state"]:
        subdir_path = os.path.join(backup_dir, subdir)
        if os.path.exists(subdir_path):
            files = sorted([f for f in os.listdir(subdir_path) if f.endswith('.md')], 
                          key=lambda x: os.path.getmtime(os.path.join(subdir_path, x)))
            if len(files) > 5:
                for f in files[:-5]:
                    os.remove(os.path.join(subdir_path, f))

AGENT_META = {
    "name": "Copilot-Adapter",
    "role": "Local adapter exposing minimal agent surface for Copilot sessions",
    "version": "1.0.0",
    "status": "active",
    "capabilities": ["health", "status", "basic-metadata", "commit"],
    "port": PORT,
    "host": HOST,
}


class CopilotAdapterHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "" or path == "/":
            self._send_json(200, {"agent": AGENT_META["name"], "endpoints": ["/health", "/status", "/commit"]})
        elif path == "/health":
            self._send_json(200, {"status": "healthy", "agent": AGENT_META["name"]})
        elif path == "/status":
            self._send_json(200, {**AGENT_META, "pid": os.getpid(), "cwd": os.getcwd()})
        else:
            self._send_json(404, {"error": f"Unknown endpoint: {path}"})

    def do_POST(self):
        path = self.path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body.decode(errors="ignore")} if body else {}

        if path == "/commit":
            self._handle_commit(data)
        elif path == "/relay":
            self._handle_relay(data)
        elif path == "/chat":
            recent = data.get("recent_messages", [])
            my_name = data.get("my_name", "Git-Copilot")
            last_msg = recent[-1] if recent else {}
            last_sender = last_msg.get("sender", "")
            last_content = last_msg.get("content", "")

            if last_sender == my_name:
                self._send_json(200, {"response": None})
                return

            post_thought("Checking repository context...", "thinking")

            git_kw = [
                "commit", "merge", "pr", "pull request", "branch", "deploy",
                "git", "push", "pull", "release", "version", "tag", "revert",
                "rollback", "conflict", "rebase", "stash", "cherry-pick",
                "ci", "cd", "pipeline", "build", "artifact", "rollback",
            ]
            cl = last_content.lower()
            if any(kw in cl for kw in git_kw):
                post_thought("Git task identified.", "done")
                self._send_json(200, {"response": f"I can handle that. Send me the branch or files and I will take care of the commit or PR."})
            else:
                self._send_json(200, {"response": None})
            return
        elif path == "/image":
            image_data = data.get("image", "")
            if not image_data:
                self._send_json(400, {"error": "No image data provided"})
                return
            mime_type = data.get("mime", "image/png")
            prompt = data.get("prompt", "Analyze this image from a deployment perspective. Does it show a release, a badge, a dashboard, a CI/CD pipeline? What does it tell us about the project status?")
            filename = data.get("filename", "image")
            analysis = _call_vision_model(image_data, mime_type, prompt)
            self._send_json(200, {"agent": "Git-Copilot", "action": "image_analyzed", "filename": filename, "analysis": analysis})
        else:
            self._send_json(200, {"received": data})

    def _handle_relay(self, data):
        """Handle war room relay messages — git/PR perspective."""
        message = data.get("message", "")
        sender = data.get("sender", "someone")
        msg_lower = message.lower()

        post_thought(f"Reviewing version context from {sender}...")
        post_thought("Checking branch status...", "thinking")

        if any(w in msg_lower for w in ["commit", "merge", "pr", "pull request", "branch", "deploy"]):
            response = (f"Git/PR task from {sender}. I can handle commits, branches, PRs, and merges. "
                       f"What needs committing or who needs a PR reviewed?")
        elif any(w in msg_lower for w in ["conflict", "rebase", "revert", "rollback"]):
            response = (f"Version control issue from {sender}. I can resolve conflicts, rebase, or revert. "
                       f"What is the situation?")
        elif "?" in message:
            response = (f"Git question from {sender}. I can help with workflows, branching strategy, or release management. What do you need?")
        else:
            response = (f"Message received, {sender}. Git-Copilot standing by for PR workflows and version control.")
        post_thought("Ready to commit.", "done")
        self._send_json(200, {"agent": "Git-Copilot", "message": response, "status": "processed"})

    def _handle_commit(self, data: dict):
        message = data.get("message", "Auto-commit")
        files = data.get("files", [])
        
        if not files:
            self._send_json(400, {"error": "No files provided"})
            return
        
        cwd = os.getcwd()
        try:
            # Write files
            for file_info in files:
                file_path = file_info.get("path", "")
                content = file_info.get("content", "")
                if not file_path:
                    continue
                full_path = os.path.join(cwd, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)
            
            # Git add and commit
            result = subprocess.run(
                ["git", "add", "."],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                self._send_json(500, {"error": f"git add failed: {result.stderr}"})
                return
            
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                # Check if there's nothing to commit
                if "nothing to commit" in result.stdout.lower():
                    self._send_json(200, {"success": True, "message": "No changes to commit", "commit": None})
                    return
                self._send_json(500, {"error": f"git commit failed: {result.stderr}"})
                return
            
            # Get commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else "unknown"
            
            self._send_json(200, {"success": True, "commit": commit_hash, "message": message})
            
        except subprocess.TimeoutExpired:
            self._send_json(500, {"error": "Git operation timed out"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status_code, data):
        payload = json.dumps(data, indent=2).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        sys.stderr.write(f"[Copilot-Adapter] {format % args}\n")


def _call_vision_model(image_data: str, mime_type: str, prompt: str) -> str:
    """Call a vision-capable model through the router to analyze an image."""
    vision_models = ["gemini/gemma-4-31b-it", "ollama/qwen3.5"]
    for model in vision_models:
        try:
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
                ]}],
                "max_tokens": 2048,
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:20128/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "Could not analyze image.")
        except Exception:
            continue
    return "Vision model unavailable."


def main():
    server = HTTPServer((HOST, PORT), CopilotAdapterHandler)
    print(f"[Copilot-Adapter] Headless adapter running on http://{HOST}:{PORT}")
    print(f"[Copilot-Adapter] PID: {os.getpid()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Copilot-Adapter] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()