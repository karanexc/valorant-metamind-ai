from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.ingestion.pipeline import build_multi_event_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect player-map stats from multiple VLR event pages")
    parser.add_argument("--event-pages", type=int, default=1, help="Number of VLR event index pages to scan")
    parser.add_argument("--event-limit", type=int, default=5, help="Number of events to scrape")
    parser.add_argument("--match-limit-per-event", type=int, default=5, help="Number of matches per event")
    parser.add_argument("--tiers", default="", help="Optional comma-separated tiers such as vct,vcl")
    parser.add_argument("--output", default="data/vlr_player_stats.csv", help="CSV or parquet output path")
    parser.add_argument("--cache-dir", default="data/raw/vlr_html", help="Raw HTML cache directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tiers = [tier.strip().lower() for tier in args.tiers.split(",") if tier.strip()] or None
    df = build_multi_event_dataset(
        event_pages=args.event_pages,
        event_limit=args.event_limit,
        match_limit_per_event=args.match_limit_per_event,
        output_path=args.output,
        cache_dir=args.cache_dir,
        tiers=tiers,
    )
    print(f"Collected {len(df)} player-map rows")
    print(f"Unique matches: {df['match_id'].nunique() if not df.empty else 0}")
    print(f"Unique players: {df['player'].nunique() if not df.empty else 0}")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
