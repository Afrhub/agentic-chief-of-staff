import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EmailAdapter:
    """Adapter for email (IMAP) integration."""

    def __init__(self, email_address: str, imap_token: str, imap_server: str = "imap.gmail.com"):
        self.email_address = email_address
        self.imap_token = imap_token
        self.imap_server = imap_server
        self.important_senders = set()  # Will populate with known VIPs

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        try:
            imap = imaplib.IMAP4_SSL(self.imap_server)
            imap.authenticate("XOAUTH2", self._generate_oauth2_string())
            return imap
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            return None

    def _generate_oauth2_string(self) -> str:
        """Generate OAuth2 string for Gmail IMAP."""
        auth_string = f"user={self.email_address}\x01auth=Bearer {self.imap_token}\x01\x01"
        return auth_string

    def scan_inbox_for_vips(self, lookback_hours: int = 24) -> list:
        """Scan inbox for emails from key contacts (investors, major customers)."""
        vip_emails = []
        imap = self._connect()

        if not imap:
            return []

        try:
            imap.select("INBOX")

            # Search for recent emails (last 24 hours)
            since_date = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%d-%b-%Y")
            status, messages = imap.search(None, f"SINCE {since_date}")

            if status == "OK":
                for msg_id in messages[0].split():
                    status, msg_data = imap.fetch(msg_id, "(RFC822)")
                    if status == "OK":
                        msg = email.message_from_bytes(msg_data[0][1])

                        from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
                        subject = self._decode_subject(msg.get("Subject", ""))
                        date_str = msg.get("Date", "")

                        # Check if from important sender (VIP list or known investor/customer)
                        if self._is_vip_email(from_addr, subject):
                            vip_emails.append({
                                "from": from_addr,
                                "subject": subject,
                                "date": date_str,
                                "timestamp": datetime.utcnow(),
                                "urgency": "high"
                            })

            imap.close()
            imap.logout()
            return vip_emails

        except Exception as e:
            logger.error(f"Error scanning inbox: {e}")
            return []

    def scan_inbox_for_churn_signals(self, lookback_hours: int = 24) -> list:
        """Scan inbox for angry customer emails or cancellation requests."""
        churn_signals = []
        imap = self._connect()

        if not imap:
            return []

        try:
            imap.select("INBOX")

            since_date = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%d-%b-%Y")
            status, messages = imap.search(None, f"SINCE {since_date}")

            churn_keywords = ["cancel", "angry", "frustrated", "switch", "competitor", "pricing too high", "unhappy"]

            if status == "OK":
                for msg_id in messages[0].split():
                    status, msg_data = imap.fetch(msg_id, "(RFC822)")
                    if status == "OK":
                        msg = email.message_from_bytes(msg_data[0][1])
                        from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
                        subject = self._decode_subject(msg.get("Subject", "")).lower()
                        body = self._get_body(msg).lower()

                        text = f"{subject} {body}"

                        if any(kw in text for kw in churn_keywords):
                            churn_signals.append({
                                "from": from_addr,
                                "subject": self._decode_subject(msg.get("Subject", "")),
                                "snippet": body[:200],
                                "timestamp": datetime.utcnow(),
                                "signal_type": "angry_customer" if "angry" in text or "frustrated" in text else "cancellation"
                            })

            imap.close()
            imap.logout()
            return churn_signals

        except Exception as e:
            logger.error(f"Error scanning for churn signals: {e}")
            return []

    def _decode_subject(self, subject: str) -> str:
        """Decode email subject (handles encoded-word syntax)."""
        decoded_parts = decode_header(subject)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or "utf-8", errors="ignore")
            else:
                result += part
        return result

    def _get_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors="ignore")
        else:
            return msg.get_payload(decode=True).decode(errors="ignore")
        return ""

    def _is_vip_email(self, sender: str, subject: str) -> bool:
        """Check if email is from a VIP (investor, major customer, etc.)."""
        vip_keywords = ["investor", "venture", "series", "funding", "acquisition", "acquisition inquiry"]
        subject_lower = subject.lower()
        return any(kw in subject_lower for kw in vip_keywords) or sender in self.important_senders

    def set_important_senders(self, senders: list):
        """Set list of important email addresses (investors, key customers)."""
        self.important_senders = set(senders)
