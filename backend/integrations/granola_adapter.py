import httpx
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Map meeting-note content to existing signal types so Granola corroborates the
# other sources (the coordinator needs >=2 distinct types to surface).
CHURN_KW = ["cancel", "churn", "unhappy", "switching", "competitor", "too expensive", "refund"]
INVESTOR_KW = ["investor", "funding", "raise", "term sheet", "valuation", "board"]
CONFLICT_KW = ["blocked", "escalate", "conflict", "urgent", "at risk", "slipping", "behind schedule"]
ACTION_KW = ["decision", "decided", "action item", "follow up", "deadline", "next steps", "we should"]


ALL_KW = CHURN_KW + INVESTOR_KW + CONFLICT_KW + ACTION_KW


def classify_note(text: str):
    """Best-fit signal type for a meeting note, or None if it's not decision-worthy."""
    t = (text or "").lower()
    if any(k in t for k in CHURN_KW):
        return "churn_signal"
    if any(k in t for k in INVESTOR_KW):
        return "investor_contact"
    if any(k in t for k in CONFLICT_KW):
        return "team_conflict"
    if any(k in t for k in ACTION_KW):
        return "meeting_action"
    return None


def matching_line(transcript) -> str:
    """First transcript line that mentions a trigger keyword — the quote to show."""
    for entry in transcript or []:
        line = entry.get("text", "")
        if any(k in line.lower() for k in ALL_KW):
            return line.strip()
    return ""


class GranolaAdapter:
    """Adapter for Granola meeting notes (REST API, Bearer grn_ key).

    Docs: https://docs.granola.ai — GET /notes?created_after=<ISO>.
    """

    def __init__(self, api_key: str, base_url: str = "https://public-api.granola.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def scan_recent_notes(self, lookback_hours: int = 24) -> list:
        """Return decision-worthy meeting notes as signal dicts. Raises on API
        error so the caller marks the integration sync failed."""
        since = (datetime.utcnow() - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = httpx.get(
            f"{self.base_url}/notes",
            headers={"Authorization": f"Bearer {self.api_key}"},
            params={"created_after": since},
            timeout=20,
        )
        resp.raise_for_status()
        notes = resp.json().get("notes", [])

        signals = []
        for n in notes:
            text = f"{n.get('title', '')} {n.get('summary', '')}"
            kind = classify_note(text)
            if not kind:
                continue
            note_id = n.get("id")
            signals.append({
                "kind": kind,
                "title": n.get("title", "Meeting note"),
                "snippet": (n.get("summary") or "")[:240],
                # ponytail: one extra GET per signal-worthy note (already filtered, so few)
                "quote": self.fetch_transcript_quote(note_id) if note_id else "",
                "note_id": note_id,
                "timestamp": datetime.utcnow(),
            })
        return signals

    def fetch_transcript_quote(self, note_id: str) -> str:
        """Best-effort: the exact transcript line that triggered the signal.
        Failures are swallowed — the alert still works without the quote."""
        try:
            resp = httpx.get(
                f"{self.base_url}/notes/{note_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"include": "transcript"},
                timeout=20,
            )
            resp.raise_for_status()
            return matching_line(resp.json().get("transcript", []))
        except Exception as e:
            logger.warning(f"Granola transcript fetch failed for {note_id}: {e}")
            return ""


if __name__ == "__main__":
    # ponytail: one runnable check for the classifier (the only non-trivial logic).
    assert classify_note("Customer threatening to cancel, too expensive") == "churn_signal"
    assert classify_note("Investor wants an updated deck before the board meeting") == "investor_contact"
    assert classify_note("Project is blocked and slipping behind schedule") == "team_conflict"
    assert classify_note("We decided to ship Friday; action item: email the team") == "meeting_action"
    assert classify_note("Nice chat about the weekend") is None
    assert matching_line([{"text": "just saying hi"}, {"text": "we should cancel the contract"}]) == "we should cancel the contract"
    assert matching_line([{"text": "small talk only"}]) == ""
    print("classify_note + matching_line: all checks passed")
