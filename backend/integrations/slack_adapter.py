from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class SlackAdapter:
    """Adapter for Slack integration."""

    def __init__(self, token: str):
        self.client = WebClient(token=token)
        self.escalation_keywords = ["urgent", "blocked", "stuck", "critical", "asap", "emergency", "help"]
        self.conflict_keywords = ["disagree", "conflict", "issue", "problem", "angry", "upset", "frustrated"]

    def post_message(self, channel: str, text: str) -> bool:
        """Post a plain text message (used by the chief-of-staff Slack bot)."""
        try:
            self.client.chat_postMessage(channel=channel, text=text)
            return True
        except SlackApiError as e:
            logger.error(f"Slack post_message error: {e}")
            return False

    def post_alert(self, channel: str, alert_payload: dict) -> bool:
        """Post a formatted alert to Slack."""
        try:
            blocks = self._format_alert_blocks(alert_payload)
            response = self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text="Decision Alert"
            )
            logger.info(f"Alert posted to Slack: {response['ts']}")
            return True
        except SlackApiError as e:
            logger.error(f"Slack API error: {e}")
            return False

    def _format_alert_blocks(self, alert: dict) -> list:
        """Format alert as Slack Block Kit message."""
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 {alert.get('title', 'Alert')}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*What Happened:*\n{alert.get('what_happened', '')}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Why It Matters:*\n{alert.get('why_it_matters', '')}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*What To Do Next:*\n{alert.get('what_to_do_next', '')}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Decide"},
                        "value": f"decide_{alert.get('id')}",
                        "action_id": f"decide_{alert.get('id')}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Delegate"},
                        "value": f"delegate_{alert.get('id')}",
                        "action_id": f"delegate_{alert.get('id')}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Dismiss"},
                        "value": f"dismiss_{alert.get('id')}",
                        "action_id": f"dismiss_{alert.get('id')}"
                    }
                ]
            }
        ]

    def scan_channels_for_escalations(self, channels: list = None) -> list:
        """Scan Slack channels for escalation/conflict signals."""
        escalations = []
        try:
            # Get list of channels if not provided
            if not channels:
                conversations = self.client.conversations_list(limit=100)
                channels = [c["id"] for c in conversations["channels"]]

            for channel_id in channels:
                try:
                    # Get recent messages
                    messages = self.client.conversations_history(
                        channel=channel_id,
                        limit=50
                    )

                    for msg in messages.get("messages", []):
                        text = msg.get("text", "").lower()
                        timestamp = datetime.fromtimestamp(float(msg["ts"]))

                        # Check for escalation keywords
                        is_escalation = any(kw in text for kw in self.escalation_keywords)
                        is_conflict = any(kw in text for kw in self.conflict_keywords)

                        # Check for caps (indicates urgency)
                        has_caps = sum(1 for c in text if c.isupper()) > len(text) * 0.5
                        exclamation_count = text.count("!")

                        if is_escalation or is_conflict or has_caps or exclamation_count > 2:
                            escalations.append({
                                "channel_id": channel_id,
                                "message": msg.get("text", ""),
                                "user": msg.get("user", "unknown"),
                                "timestamp": timestamp,
                                "severity": "high" if has_caps or exclamation_count > 2 else "medium"
                            })

                except Exception as e:
                    logger.warning(f"Failed to scan channel {channel_id}: {e}")

            return escalations

        except SlackApiError as e:
            logger.error(f"Slack API error scanning channels: {e}")
            return []

    def get_user_info(self, user_id: str) -> dict:
        """Fetch user info for context."""
        try:
            response = self.client.users_info(user=user_id)
            user = response["user"]
            return {
                "id": user["id"],
                "name": user["name"],
                "email": user.get("profile", {}).get("email", "")
            }
        except SlackApiError as e:
            logger.error(f"Failed to get user info: {e}")
            return {}
