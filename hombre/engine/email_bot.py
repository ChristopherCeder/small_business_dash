"""
engine/email_bot.py — Gmail IMAP poller and SMTP sender.
- Persistent IMAP connection (reconnects only on error)
- Only fires on_message when a real filtered email lands
- Rate limit: 1 AI reply per sender per 10 minutes
- Default poll interval: 5 minutes (configurable in settings)
"""

import imaplib, email, email.utils, email.message, smtplib
import threading, time, logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


class EmailBot:
    DEFAULT_INTERVAL = 300   # 5 minutes

    def __init__(self, secrets: dict, settings: dict, on_message):
        self.secrets      = secrets
        self.settings     = settings
        self.on_message   = on_message
        self._running     = False
        self._thread      = None
        self._mail        = None           # persistent IMAP connection
        self._seen_uids   = set()          # dedup guard across restarts
        self._last_reply  = {}             # sender → datetime, rate limiting

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._disconnect()

    def _loop(self):
        while self._running:
            try:
                self._check()
            except Exception as ex:
                log.warning(f"Email bot error: {ex}")
                self._disconnect()   # force reconnect next cycle
            interval = int(self.settings.get("interval", self.DEFAULT_INTERVAL))
            time.sleep(max(interval, 60))   # never poll faster than 60s

    # ── IMAP connection (persistent) ──────────────────────────────────────────

    def _connect(self):
        s = self.secrets
        if not s.get("email") or not s.get("app_password"):
            raise RuntimeError("Email credentials not configured.")
        self._mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self._mail.login(s["email"], s["app_password"])
        self._mail.select("inbox")

    def _disconnect(self):
        try:
            if self._mail:
                self._mail.logout()
        except Exception:
            pass
        self._mail = None

    def _ensure_connected(self):
        if self._mail is None:
            self._connect()
        else:
            # NOOP keeps the connection alive and raises if it dropped
            try:
                self._mail.noop()
            except Exception:
                self._disconnect()
                self._connect()

    # ── Check for new emails ──────────────────────────────────────────────────

    def _check(self):
        self._ensure_connected()

        filt   = self.settings.get("subject_filter", "")
        search = f'(UNSEEN SUBJECT "{filt}")' if filt else "(UNSEEN)"
        _, data = self._mail.search(None, search)
        ids    = [uid for uid in data[0].split() if uid not in self._seen_uids]

        if not ids:
            return   # nothing new — do NOT call AI

        for uid in ids:
            self._seen_uids.add(uid)
            try:
                _, raw = self._mail.fetch(uid, "(RFC822)")
                msg    = email.message_from_bytes(raw[0][1])
                sender = email.utils.parseaddr(msg["From"])[1].lower().strip()
                subj   = msg.get("Subject", "")
                body   = self._extract_body(msg)

                if not body.strip():
                    continue   # empty message, skip entirely

                # Rate limit: skip if we already replied to this sender recently
                if self._is_rate_limited(sender):
                    log.info(f"Rate limited: {sender}")
                    continue

                self._mail.store(uid, "+FLAGS", "\\Seen")
                self.on_message({
                    "sender":      sender,
                    "subject":     subj,
                    "body":        body,
                    "source":      "Email",
                    "uid":         uid.decode(),
                    "message_id":  msg.get("Message-ID", ""),
                    "in_reply_to": msg.get("In-Reply-To", ""),
                }, None, "email")

            except Exception as ex:
                log.warning(f"Error processing email UID {uid}: {ex}")

    @staticmethod
    def _extract_body(msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        return part.get_payload(decode=True).decode(errors="replace")
                    except Exception:
                        pass
            return ""
        try:
            return msg.get_payload(decode=True).decode(errors="replace")
        except Exception:
            return ""

    # ── Rate limiting ─────────────────────────────────────────────────────────

    def _is_rate_limited(self, sender: str, window_minutes: int = 10) -> bool:
        last = self._last_reply.get(sender)
        if last and datetime.now() - last < timedelta(minutes=window_minutes):
            return True
        return False

    def record_reply(self, sender: str):
        """Call this after a reply is successfully sent."""
        self._last_reply[sender] = datetime.now()

    # ── Send ──────────────────────────────────────────────────────────────────

    def send_reply(self, to_addr: str, subject: str, body: str,
                   in_reply_to: str = "") -> str:
        """Send reply via SMTP. Returns Message-ID of sent message."""
        s   = self.secrets
        msg = email.message.EmailMessage()
        msg["From"]    = s["email"]
        msg["To"]      = to_addr
        msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"]  = in_reply_to
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(s["email"], s["app_password"])
            smtp.send_message(msg)
        sent_id = msg.get("Message-ID", "")

        # Forward copy to owner
        fwd_to = s.get("forward_to", "")
        if fwd_to and fwd_to != to_addr:
            try:
                fwd = email.message.EmailMessage()
                fwd["From"]    = s["email"]
                fwd["To"]      = fwd_to
                fwd["Subject"] = f"[FWD copy] Re: {subject}"
                fwd.set_content(f"Reply sent to {to_addr}:\n\n{body}")
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                    smtp.login(s["email"], s["app_password"])
                    smtp.send_message(fwd)
            except Exception as ex:
                log.warning(f"Forward copy failed: {ex}")

        self.record_reply(to_addr.lower())
        return sent_id

    def send_owner_alert(self, subject: str, body: str):
        """Send an alert email to the forward_to address."""
        s = self.secrets
        fwd_to = s.get("forward_to", "")
        if not fwd_to:
            return
        msg = email.message.EmailMessage()
        msg["From"]    = s["email"]
        msg["To"]      = fwd_to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(s["email"], s["app_password"])
            smtp.send_message(msg)

    def check_owner_approvals(self) -> list:
        """
        Scan inbox for owner replies containing exactly 'Approved' or 'approved'.
        Returns list of subjects that matched.
        """
        s      = self.secrets
        fwd_to = s.get("forward_to", "")
        if not fwd_to:
            return []
        approved = []
        try:
            self._ensure_connected()
            _, data = self._mail.search(
                None, f'(UNSEEN FROM "{fwd_to}")')
            for uid in data[0].split():
                _, raw = self._mail.fetch(uid, "(RFC822)")
                msg    = email.message_from_bytes(raw[0][1])
                body   = self._extract_body(msg).strip()
                if body in ("Approved", "approved"):
                    approved.append(msg.get("Subject", ""))
                    self._mail.store(uid, "+FLAGS", "\\Seen")
        except Exception as ex:
            log.warning(f"Approval check error: {ex}")
        return approved
