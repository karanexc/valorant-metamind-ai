from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.api.vlr_client import VLRClient, get_event_matches, get_event_pages, get_match_details


PLAYER_STAT_COLUMNS = [
    "event_id",
    "event",
    "tier",
    "match_id",
    "match_title",
    "map",
    "player",
    "team",
    "agent",
    "kills",
    "deaths",
    "assists",
    "acs",
    "rating",
    "kda",
]


def extract_match_stats(match: dict | str, event: dict, client: VLRClient | None = None) -> list[dict]:
    match_id = match["match_id"] if isinstance(match, dict) else str(match)
    match_url = match.get("url", match_id) if isinstance(match, dict) else match_id
    details = get_match_details(match_url, client=client)
    rows: list[dict] = []

    for map_data in details.get("maps", []):
        for player in map_data.get("players", []):
            deaths = int(player.get("deaths") or 0)
            kills = int(player.get("kills") or 0)
            assists = int(player.get("assists") or 0)

            rows.append(
                {
                    "event_id": event.get("event_id"),
                    "event": event.get("title"),
                    "tier": event.get("tier"),
                    "match_id": match_id,
                    "match_title": details.get("title"),
                    "map": map_data.get("map"),
                    "player": player.get("player"),
                    "team": player.get("team"),
                    "agent": player.get("agent"),
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "acs": int(player.get("acs") or 0),
                    "rating": float(player.get("rating") or 0),
                    "kda": round((kills + assists) / max(deaths, 1), 3),
                }
            )

    return rows


def build_event_dataset(
    event: dict,
    output_path: str | Path | None = None,
    match_limit: int | None = None,
    client: VLRClient | None = None,
) -> pd.DataFrame:
    client = client or VLRClient()
    matches = get_event_matches(event["url_path"], client=client)

    if match_limit:
        matches = matches[:match_limit]

    rows: list[dict] = []
    for match in matches:
        rows.extend(extract_match_stats(match, event, client=client))

    df = pd.DataFrame(rows, columns=PLAYER_STAT_COLUMNS)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix == ".parquet":
            df.to_parquet(output_path, index=False)
        else:
            df.to_csv(output_path, index=False)

    return df


def build_multi_event_dataset(
    event_pages: int = 1,
    event_limit: int | None = None,
    match_limit_per_event: int | None = 5,
    output_path: str | Path | None = None,
    cache_dir: str | Path | None = "data/raw/vlr_html",
    tiers: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    client = VLRClient(cache_dir=Path(cache_dir) if cache_dir else None)
    selected_tiers = list(tiers or [None])
    events: list[dict] = []

    for tier in selected_tiers:
        events.extend(get_event_pages(pages=event_pages, client=client, tier=tier))

    if event_limit:
        events = events[:event_limit]

    frames = []
    for event in events:
        df = build_event_dataset(event, match_limit=match_limit_per_event, client=client)
        if not df.empty:
            frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PLAYER_STAT_COLUMNS)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix == ".parquet":
            combined.to_parquet(output_path, index=False)
        else:
            combined.to_csv(output_path, index=False)

    return combined


def load_player_stats(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)
