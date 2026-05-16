from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.api.vlr_client import get_events
from src.ingestion.pipeline import build_event_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Valorant player stats dataset from VLR.gg")
    parser.add_argument("--event-id", help="Specific VLR event ID to scrape")
    parser.add_argument("--event-index", type=int, default=0, help="Index from the events page when event ID is omitted")
    parser.add_argument("--match-limit", type=int, default=3, help="Limit matches for quick dissertation experiments")
    parser.add_argument("--output", default="data/player_stats.csv", help="CSV or parquet output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = get_events()

    if args.event_id:
        event = next((item for item in events if item["event_id"] == args.event_id), None)
        if event is None:
            raise SystemExit(f"Event ID {args.event_id} was not found on the VLR events page.")
    else:
        event = events[args.event_index]

    df = build_event_dataset(event, output_path=Path(args.output), match_limit=args.match_limit)
    print(f"Built {len(df)} player-map rows for {event['title']}")
    print(f"Saved dataset to {args.output}")


if __name__ == "__main__":
    main()
