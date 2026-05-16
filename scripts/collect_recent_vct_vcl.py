from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.api.vlr_client import VLRClient, get_event_matches, get_event_pages
from src.ingestion.pipeline import extract_match_stats
from src.storage.database import (
    connect,
    database_summary,
    delete_player_stats_for_match,
    init_db,
    upsert_event,
    upsert_match,
    upsert_player_stats,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect recent VCT and VCL data from VLR.gg into SQLite")
    parser.add_argument("--db", default="data/valorant_metamind.sqlite", help="SQLite database path")
    parser.add_argument("--event-pages", type=int, default=1, help="Number of recent event pages per tier")
    parser.add_argument("--event-limit-per-tier", type=int, default=8, help="Events to collect for each tier")
    parser.add_argument("--match-limit-per-event", type=int, default=8, help="Matches to collect per event")
    parser.add_argument("--tiers", default="vct,vcl", help="Comma-separated tiers. Use vct,vcl for this dissertation dataset")
    parser.add_argument("--cache-dir", default="data/raw/vlr_html", help="Raw HTML cache directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tiers = [tier.strip().lower() for tier in args.tiers.split(",") if tier.strip()]
    client = VLRClient(cache_dir=Path(args.cache_dir), delay_seconds=0.8, retries=2)

    init_db(args.db)
    total_rows = 0

    with connect(args.db) as conn:
        for tier in tiers:
            events = get_event_pages(pages=args.event_pages, client=client, tier=tier)
            events = events[: args.event_limit_per_tier]
            print(f"{tier.upper()}: collecting {len(events)} events")

            for event in events:
                event["tier"] = tier.upper()
                upsert_event(conn, event)
                matches = get_event_matches(event["url_path"], client=client)
                matches = matches[: args.match_limit_per_event]
                print(f"  {event['title']} -> {len(matches)} matches")

                for match in matches:
                    rows = extract_match_stats(match, event, client=client)
                    match_title = rows[0].get("match_title") if rows else None
                    upsert_match(conn, match, event_id=event["event_id"], title=match_title)
                    delete_player_stats_for_match(conn, match["match_id"])
                    upsert_player_stats(conn, rows)
                    total_rows += len(rows)

            conn.commit()

    print(f"Inserted/updated {total_rows} player-map rows")
    print(database_summary(args.db))


if __name__ == "__main__":
    main()
