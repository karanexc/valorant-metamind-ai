from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.reporting.executive_report import generate_executive_match_report
from src.storage.database import load_player_stats_from_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a dark executive HTML match report")
    parser.add_argument("--db", default="data/valorant_metamind.sqlite", help="SQLite database path")
    parser.add_argument("--match-id", required=True, help="VLR match ID")
    parser.add_argument("--losing-team", help="Optional losing team abbreviation")
    parser.add_argument("--output", help="Output HTML path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = load_player_stats_from_db(args.db)
    output = generate_executive_match_report(
        df,
        match_id=args.match_id,
        losing_team=args.losing_team,
        output_path=args.output,
    )
    print(f"Report generated: {output}")


if __name__ == "__main__":
    main()
