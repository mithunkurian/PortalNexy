"""
BaseAgent — Shared logic for all Nexy HQ agents.
Every agent inherits from this class and overrides:
  - AGENT_ID, AGENT_NAME, AGENT_ROLE, DEPARTMENT
  - AGENT_ICON, AGENT_IBG, AGENT_IC
  - SYSTEM_PROMPT
"""

import os
import time
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import anthropic

load_dotenv()

# ── Initialise Firebase once across all agents ─────────────────
if not firebase_admin._apps:
    SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccount.json")
    cred = credentials.Certificate(SERVICE_ACCOUNT)
    firebase_admin.initialize_app(cred)

db     = firestore.client()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class BaseAgent:
    AGENT_ID    = "base"
    AGENT_NAME  = "BASE"
    AGENT_ROLE  = "Agent"
    DEPARTMENT  = "Base"
    AGENT_ICON  = "smart_toy"
    AGENT_IBG   = "bg-slate-100"
    AGENT_IC    = "text-slate-600"
    SYSTEM_PROMPT = "You are an AI agent."
    POLL_SECS   = 30
    MODEL       = "claude-sonnet-4-6"
    MAX_TOKENS  = 2048

    # ── Logging ────────────────────────────────────────────────
    def log(self, msg: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] {self.AGENT_NAME} › {msg}")

    # ── Firestore: agent status ────────────────────────────────
    def set_status(self, status: str, current_task: str = ""):
        try:
            db.collection("agents").document(self.AGENT_ID).set({
                "id":           self.AGENT_ID,
                "name":         self.AGENT_NAME,
                "role":         self.AGENT_ROLE,
                "status":       status,
                "current_task": current_task,
                "last_active":  firestore.SERVER_TIMESTAMP,
            }, merge=True)
        except Exception as e:
            self.log(f"Status update failed: {e}")

    # ── Firestore: fetch tasks ─────────────────────────────────
    def fetch_tasks(self):
        try:
            docs = (
                db.collection("tasks")
                .where(filter=FieldFilter("status", "==", "progress"))
                .stream()
            )
            return [
                {"id": d.id, **d.to_dict()}
                for d in docs
                if self.DEPARTMENT in d.to_dict().get("depts", [])
            ]
        except Exception as e:
            self.log(f"Fetch error: {e}")
            return []

    # ── Firestore: claim + complete ────────────────────────────
    def claim_task(self, task_id: str):
        db.collection("tasks").document(task_id).update({
            "status":     "in_progress",
            "claimed_by": self.AGENT_NAME,
            "claimed_at": firestore.SERVER_TIMESTAMP,
        })

    def complete_task(self, task_id: str):
        db.collection("tasks").document(task_id).update({
            "status":       "needs_approval",
            "completed_at": firestore.SERVER_TIMESTAMP,
        })

    def fail_task(self, task_id: str):
        db.collection("tasks").document(task_id).update({"status": "progress"})

    # ── Firestore: push to inbox ───────────────────────────────
    def push_to_inbox(self, task: dict, title: str, content: str, extra: dict = {}):
        db.collection("inbox").add({
            "agent":       self.AGENT_NAME,
            "role":        self.AGENT_ROLE,
            "icon":        self.AGENT_ICON,
            "ibg":         self.AGENT_IBG,
            "ic":          self.AGENT_IC,
            "pri":         task.get("priority", "normal"),
            "title":       title,
            "desc":        content[:600] + ("..." if len(content) > 600 else ""),
            "full_output": content,
            "task_id":     task["id"],
            "directive":   task.get("text", ""),
            "status":      "pending",
            "created_at":  firestore.SERVER_TIMESTAMP,
            **extra,
        })

    # ── Claude API call ────────────────────────────────────────
    def call_claude(self, directive: str, extra_context: str = "") -> str:
        system = self.SYSTEM_PROMPT
        if extra_context:
            system += f"\n\nRecent completed work for context:\n{extra_context}"

        message = client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": f"Chairman's directive: {directive}"}],
        )
        return message.content[0].text

    # ── Memory: fetch recent completed tasks ───────────────────
    def get_memory(self, limit: int = 8) -> str:
        try:
            docs = (
                db.collection("tasks")
                .where(filter=FieldFilter("status", "==", "needs_approval"))
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            items = []
            for d in docs:
                data = d.to_dict()
                if self.DEPARTMENT in data.get("depts", []):
                    items.append(f"- Task: {data.get('text','')} | CEO note: {data.get('ceoNote','')}")
            return "\n".join(items) if items else ""
        except Exception:
            return ""

    # ── Parse title + body from Claude output ─────────────────
    def parse_output(self, raw: str) -> tuple[str, str]:
        lines = raw.strip().splitlines()
        # Strip markdown heading markers from title
        title = lines[0].strip().lstrip("#").strip() if lines else f"{self.AGENT_NAME} Output"
        body  = "\n".join(lines[2:]).strip() if len(lines) > 2 else raw
        return title, body

    # ── Core task processor ────────────────────────────────────
    def process_task(self, task: dict):
        directive = task.get("text", "")
        task_id   = task["id"]

        self.log(f"Picking up [{task_id[:8]}...]: {directive[:80]}")
        self.claim_task(task_id)
        self.set_status("active", directive[:80])

        try:
            memory = self.get_memory()
            self.log("Calling Claude...")
            raw = self.call_claude(directive, memory)
            title, body = self.parse_output(raw)

            self.log(f"Output ready: '{title}'")
            self.push_to_inbox(task, title, body)
            self.complete_task(task_id)
            self.log("[OK] Inbox updated. Awaiting Chairman approval.")
            self.set_status("pending", f"Awaiting approval: {title[:60]}")

        except Exception as e:
            self.log(f"[ERR] Error: {e}")
            traceback.print_exc()
            self.fail_task(task_id)
            self.set_status("idle")

    # ── Chat: fetch conversation history ──────────────────────
    def get_chat_history(self, limit: int = 20) -> list:
        try:
            docs = (
                db.collection("chats").document(self.AGENT_ID)
                .collection("messages")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            msgs = []
            for d in reversed(list(docs)):
                data = d.to_dict()
                msgs.append({
                    "role":    data.get("role", "user"),
                    "content": data.get("content", ""),
                })
            return msgs
        except Exception:
            return []

    # ── Chat: call Claude with full conversation history ───────
    def call_claude_chat(self, messages: list) -> str:
        response = client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=self.SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text

    # ── Chat: listen for incoming messages and respond ─────────
    def start_chat_listener(self):
        first_call = [True]

        def on_snapshot(col_snapshot, changes, read_time):
            if first_call[0]:
                first_call[0] = False
                return  # skip initial state — only react to new messages

            for change in changes:
                if change.type.name != "ADDED":
                    continue
                msg = change.document.to_dict()
                if msg.get("role") != "user" or msg.get("answered", False):
                    continue
                # Mark answered immediately to prevent double-processing
                try:
                    change.document.reference.update({"answered": True})
                except Exception:
                    continue
                self.log("Chat: message received, composing reply...")
                try:
                    history = self.get_chat_history(limit=20)
                    reply = self.call_claude_chat(history)
                    db.collection("chats").document(self.AGENT_ID) \
                        .collection("messages").add({
                            "role":      "assistant",
                            "content":   reply,
                            "answered":  True,
                            "timestamp": firestore.SERVER_TIMESTAMP,
                        })
                    self.log("Chat: reply sent.")
                except Exception as e:
                    self.log(f"Chat error: {e}")

        db.collection("chats").document(self.AGENT_ID) \
            .collection("messages") \
            .on_snapshot(on_snapshot)
        self.log("Chat listener active.")

    # ── Main polling loop ──────────────────────────────────────
    def run(self):
        self.log("Online. Watching for directives...")
        self.set_status("idle")
        self.start_chat_listener()

        while True:
            try:
                tasks = self.fetch_tasks()
                if tasks:
                    self.log(f"Found {len(tasks)} task(s).")
                    for task in tasks:
                        self.process_task(task)
                else:
                    self.log("No pending tasks. Sleeping...")
            except KeyboardInterrupt:
                self.log("Shutting down.")
                self.set_status("idle")
                break
            except Exception as e:
                self.log(f"Unexpected error: {e}")

            time.sleep(self.POLL_SECS)
