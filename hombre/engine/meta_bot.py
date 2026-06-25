"""
engine/meta_bot.py — Facebook & Instagram Graph API poller.
"""

import threading, time

try:
    import requests
except ImportError:
    requests = None


class MetaBot:
    GRAPH = "https://graph.facebook.com/v19.0"

    def __init__(self, secrets: dict, settings: dict, on_message):
        self.secrets    = secrets
        self.settings   = settings
        self.on_message = on_message
        self._running   = False
        self._seen      = set()

    def start(self):
        if self._running or not requests:
            return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                if self.settings.get("fb_bot_on"):
                    self._poll_fb()
                if self.settings.get("ig_bot_on"):
                    self._poll_ig()
            except Exception as ex:
                self.on_message(None, f"[Meta bot error] {ex}", "system")
            time.sleep(int(self.settings.get("interval", 60)))

    def _poll_fb(self):
        s     = self.secrets
        token = s.get("fb_page_token", "")
        pid   = s.get("fb_page_id", "")
        if not token or not pid:
            return
        r = requests.get(
            f"{self.GRAPH}/{pid}/conversations",
            params={"access_token": token, "fields": "messages{message,from}"},
        )
        for convo in r.json().get("data", []):
            for msg in convo.get("messages", {}).get("data", []):
                mid = msg.get("id", "")
                if mid in self._seen:
                    continue
                self._seen.add(mid)
                sender = msg.get("from", {}).get("name", "Facebook User")
                text   = msg.get("message", "")
                if text:
                    self.on_message({
                        "sender": sender, "body": text,
                        "source": "Facebook", "mid": mid,
                        "token": token, "pid": pid,
                    }, None, "meta")

    def _poll_ig(self):
        s     = self.secrets
        token = s.get("fb_page_token", "")
        ig_id = s.get("ig_user_id", "")
        if not token or not ig_id:
            return
        r = requests.get(
            f"{self.GRAPH}/{ig_id}/conversations",
            params={"access_token": token,
                    "fields": "messages{message,from}",
                    "platform": "instagram"},
        )
        for convo in r.json().get("data", []):
            for msg in convo.get("messages", {}).get("data", []):
                mid = msg.get("id", "")
                if mid in self._seen:
                    continue
                self._seen.add(mid)
                sender = msg.get("from", {}).get("name", "Instagram User")
                text   = msg.get("message", "")
                if text:
                    self.on_message({
                        "sender": sender, "body": text,
                        "source": "Instagram", "mid": mid,
                        "token": token, "ig_id": ig_id,
                    }, None, "meta")

    def send_reply(self, msg_data: dict, reply_text: str):
        if not requests:
            return
        token = msg_data.get("token", "")
        if msg_data.get("source") == "Facebook":
            requests.post(
                f"{self.GRAPH}/{msg_data['pid']}/messages",
                params={"access_token": token},
                json={"recipient": {"id": msg_data["mid"]},
                      "message": {"text": reply_text}},
            )
        else:
            requests.post(
                f"{self.GRAPH}/{msg_data['ig_id']}/messages",
                params={"access_token": token},
                json={"recipient": {"comment_id": msg_data["mid"]},
                      "message": {"text": reply_text}},
            )
