import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.api.vlr_client import get_events
from src.ingestion.scraper import scrape_event_matches

events = get_events()

event = events[0]

print("Testing event:", event["title"])

matches = scrape_event_matches(event["url_path"])

print("Matches found:", len(matches))
print("Sample match IDs:", matches[:5])
