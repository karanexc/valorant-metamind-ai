from __future__ import annotations

from src.api.vlr_client import get_event_matches


def scrape_event_matches(event_url: str) -> list[str]:
    """Backward-compatible helper used by the early test scripts."""

    matches = get_event_matches(event_url)
    return [match["match_id"] for match in matches]
