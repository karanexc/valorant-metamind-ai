from __future__ import annotations

import pandas as pd

from src.analytics.player_analysis import analyze_player, prepare_player_stats


def generate_player_insight(df: pd.DataFrame, player: str) -> str:
    """Generate a deterministic AI-style insight.

    This is intentionally local and explainable for the dissertation prototype.
    A hosted LLM can later rewrite this evidence pack into richer prose.
    """

    stats = analyze_player(df, player)
    if isinstance(stats, str):
        return stats

    prepared = prepare_player_stats(df)
    player_df = prepared[prepared["player"].str.lower() == player.lower()]
    field_avg_acs = prepared["acs"].mean()
    field_avg_kda = prepared["kda"].mean()

    acs_delta = stats["avg_acs"] - field_avg_acs
    kda_delta = stats["avg_kda"] - field_avg_kda

    form = "above the dataset average" if acs_delta >= 0 else "below the dataset average"
    survivability = "healthy" if kda_delta >= 0 else "an area to improve"

    return (
        f"{player} is performing {form} on ACS, averaging {stats['avg_acs']} ACS "
        f"across {stats['maps_played']} maps. Their KDA profile is {survivability} "
        f"at {stats['avg_kda']}, with an average kill differential of "
        f"{stats['avg_kill_diff']} per map. The strongest map signal is "
        f"{stats['best_map']}, while {stats['worst_map']} is the weakest map in "
        "the current sample. For tactical review, prioritise agent comfort, map "
        "consistency, and whether low-ACS maps also coincide with higher deaths."
    )


def build_llm_context(df: pd.DataFrame, player: str) -> dict:
    stats = analyze_player(df, player)
    if isinstance(stats, str):
        return {"player": player, "error": stats}

    return {
        "task": "Explain Valorant player performance using only the supplied statistics.",
        "player": player,
        "statistics": stats,
        "instruction": (
            "Write a concise scouting insight. Mention strengths, weaknesses, "
            "map tendencies, and one coaching recommendation."
        ),
    }
