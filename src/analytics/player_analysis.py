from __future__ import annotations

import pandas as pd


def _rounded(value: float, digits: int = 2) -> float:
    return float(round(value, digits))


def prepare_player_stats(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    required = {"kills", "deaths", "assists", "acs"}
    missing = required.difference(prepared.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    prepared["deaths_safe"] = prepared["deaths"].replace(0, 1)
    prepared["kda"] = (prepared["kills"] + prepared["assists"]) / prepared["deaths_safe"]
    prepared["kill_diff"] = prepared["kills"] - prepared["deaths"]
    return prepared


def analyze_player(df: pd.DataFrame, player: str) -> dict | str:
    prepared = prepare_player_stats(df)
    player_df = prepared[prepared["player"].str.lower() == player.lower()]

    if player_df.empty:
        return "No data found"

    map_stats = player_df.groupby("map", dropna=True)["kda"].mean()
    agent_stats = player_df.groupby("agent", dropna=True)["acs"].mean().sort_values(ascending=False)

    return {
        "matches": int(player_df["match_id"].nunique()),
        "maps_played": int(len(player_df)),
        "avg_kda": _rounded(player_df["kda"].mean(), 2),
        "avg_acs": _rounded(player_df["acs"].mean(), 1),
        "avg_kills": _rounded(player_df["kills"].mean(), 1),
        "avg_deaths": _rounded(player_df["deaths"].mean(), 1),
        "avg_assists": _rounded(player_df["assists"].mean(), 1),
        "avg_kill_diff": _rounded(player_df["kill_diff"].mean(), 1),
        "best_map": map_stats.idxmax() if not map_stats.empty else "Unknown",
        "worst_map": map_stats.idxmin() if not map_stats.empty else "Unknown",
        "best_agent": agent_stats.index[0] if not agent_stats.empty else "Unknown",
    }


def compare_players(df: pd.DataFrame, player_one: str, player_two: str) -> dict:
    return {
        player_one: analyze_player(df, player_one),
        player_two: analyze_player(df, player_two),
    }


def team_summary(df: pd.DataFrame) -> pd.DataFrame:
    prepared = prepare_player_stats(df)
    return (
        prepared.groupby("team", dropna=True)
        .agg(
            maps=("map", "count"),
            avg_acs=("acs", "mean"),
            avg_kda=("kda", "mean"),
            avg_kill_diff=("kill_diff", "mean"),
        )
        .round(2)
        .sort_values("avg_acs", ascending=False)
        .reset_index()
    )


def generate_report(df: pd.DataFrame, player: str) -> str:
    stats = analyze_player(df, player)

    if isinstance(stats, str):
        return stats

    return f"""Player: {player}

Maps played: {stats['maps_played']}
Average KDA: {stats['avg_kda']}
Average ACS: {stats['avg_acs']}
Average kill diff: {stats['avg_kill_diff']}

Best map: {stats['best_map']}
Worst map: {stats['worst_map']}
Best agent by ACS: {stats['best_agent']}
"""
