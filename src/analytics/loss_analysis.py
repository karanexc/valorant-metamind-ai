from __future__ import annotations

import pandas as pd

from src.analytics.player_analysis import prepare_player_stats


def explain_match_loss(
    df: pd.DataFrame,
    match_id: str | int,
    losing_team: str | None = None,
    form_window: int = 5,
) -> dict:
    prepared = prepare_player_stats(df)
    prepared["match_id"] = prepared["match_id"].astype(str)
    match_id = str(match_id)
    match_df = prepared[prepared["match_id"] == match_id].copy()

    if match_df.empty:
        return {"error": f"No rows found for match_id={match_id}"}

    team_scores = _team_match_scores(match_df)
    losing_team = losing_team or _infer_losing_team(team_scores)
    if losing_team not in set(match_df["team"].dropna()):
        return {"error": f"Team {losing_team} was not found in match_id={match_id}"}

    winner_team = _opponent_for(match_df, losing_team)
    baseline_df = prepared[prepared["match_id"] != match_id]

    player_signals = _player_underperformance(match_df, baseline_df, losing_team)
    form_signal = _team_form_signal(baseline_df, losing_team, form_window=form_window)
    map_signals = _map_weakness_signals(match_df, baseline_df, losing_team)
    ranking_signal = _ranking_ambiguity_signal(baseline_df, losing_team, winner_team)
    factors = _rank_loss_factors(player_signals, form_signal, map_signals, ranking_signal)

    return {
        "match_id": match_id,
        "losing_team": losing_team,
        "winner_team": winner_team,
        "match_team_scores": team_scores.to_dict("records"),
        "top_factors": factors,
        "player_underperformance": player_signals,
        "team_form": form_signal,
        "map_weakness": map_signals,
        "ranking_ambiguity": ranking_signal,
        "summary": _build_loss_summary(losing_team, winner_team, factors),
    }


def _team_match_scores(match_df: pd.DataFrame) -> pd.DataFrame:
    return (
        match_df.groupby("team", dropna=True)
        .agg(
            kills=("kills", "sum"),
            deaths=("deaths", "sum"),
            assists=("assists", "sum"),
            avg_acs=("acs", "mean"),
            avg_kda=("kda", "mean"),
            kill_diff=("kill_diff", "sum"),
        )
        .round(2)
        .sort_values(["kill_diff", "avg_acs"], ascending=False)
        .reset_index()
    )


def _infer_losing_team(team_scores: pd.DataFrame) -> str:
    if team_scores.empty:
        return ""
    return str(team_scores.sort_values(["kill_diff", "avg_acs"]).iloc[0]["team"])


def _opponent_for(match_df: pd.DataFrame, losing_team: str) -> str | None:
    teams = [team for team in match_df["team"].dropna().unique() if team != losing_team]
    return str(teams[0]) if teams else None


def _player_underperformance(match_df: pd.DataFrame, baseline_df: pd.DataFrame, losing_team: str) -> list[dict]:
    losing_players = match_df[match_df["team"] == losing_team]
    signals = []

    for _, row in losing_players.iterrows():
        player = row["player"]
        baseline = baseline_df[baseline_df["player"].str.lower() == str(player).lower()]
        if baseline.empty:
            expected_acs = float(baseline_df["acs"].mean()) if not baseline_df.empty else float(row["acs"])
            sample_size = 0
        else:
            expected_acs = float(baseline["acs"].mean())
            sample_size = int(len(baseline))

        acs_delta = float(row["acs"] - expected_acs)
        severity = min(max(abs(acs_delta) / max(expected_acs, 1), 0), 1)

        signals.append(
            {
                "player": row["player"],
                "agent": row.get("agent", "Unknown"),
                "map": row.get("map", "Unknown"),
                "actual_acs": float(row["acs"]),
                "expected_acs": round(expected_acs, 1),
                "acs_delta": round(acs_delta, 1),
                "kill_diff": int(row["kill_diff"]),
                "baseline_maps": sample_size,
                "severity": round(severity, 3),
                "underperformed": bool(acs_delta < -20 or row["kill_diff"] < -3),
            }
        )

    return sorted(signals, key=lambda item: (item["underperformed"], item["severity"]), reverse=True)


def _team_form_signal(baseline_df: pd.DataFrame, team: str, form_window: int) -> dict:
    team_df = baseline_df[baseline_df["team"] == team].copy()
    if team_df.empty:
        return {
            "team": team,
            "sample_matches": 0,
            "recent_avg_kill_diff": None,
            "overall_avg_kill_diff": None,
            "status": "unknown",
            "severity": 0.4,
        }

    per_match = (
        team_df.groupby("match_id", dropna=True)
        .agg(avg_kill_diff=("kill_diff", "mean"), avg_acs=("acs", "mean"))
        .reset_index()
    )
    recent = per_match.tail(form_window)
    recent_kd = float(recent["avg_kill_diff"].mean())
    overall_kd = float(per_match["avg_kill_diff"].mean())
    status = "bad form" if recent_kd < overall_kd - 1 or recent_kd < -1 else "stable form"
    severity = min(max(abs(min(recent_kd, 0)) / 5, 0), 1)

    return {
        "team": team,
        "sample_matches": int(len(per_match)),
        "recent_avg_kill_diff": round(recent_kd, 2),
        "overall_avg_kill_diff": round(overall_kd, 2),
        "status": status,
        "severity": round(severity, 3),
    }


def _map_weakness_signals(match_df: pd.DataFrame, baseline_df: pd.DataFrame, losing_team: str) -> list[dict]:
    signals = []
    for map_name in match_df["map"].dropna().unique():
        current = match_df[(match_df["team"] == losing_team) & (match_df["map"] == map_name)]
        historical = baseline_df[(baseline_df["team"] == losing_team) & (baseline_df["map"] == map_name)]

        if historical.empty:
            expected_acs = float(baseline_df[baseline_df["team"] == losing_team]["acs"].mean()) if not baseline_df.empty else None
            sample_size = 0
        else:
            expected_acs = float(historical["acs"].mean())
            sample_size = int(len(historical))

        actual_acs = float(current["acs"].mean()) if not current.empty else 0
        delta = actual_acs - expected_acs if expected_acs else 0
        signals.append(
            {
                "map": map_name,
                "actual_avg_acs": round(actual_acs, 1),
                "expected_avg_acs": round(expected_acs, 1) if expected_acs else None,
                "acs_delta": round(delta, 1),
                "historical_rows": sample_size,
                "severity": round(min(max(abs(min(delta, 0)) / max(expected_acs or 1, 1), 0), 1), 3),
                "weakness": bool(delta < -20),
            }
        )

    return sorted(signals, key=lambda item: item["severity"], reverse=True)


def _ranking_ambiguity_signal(baseline_df: pd.DataFrame, losing_team: str, winner_team: str | None) -> dict:
    if winner_team is None or baseline_df.empty:
        return {"status": "unknown", "severity": 0.4, "reason": "Not enough historical data."}

    team_table = (
        baseline_df.groupby("team", dropna=True)
        .agg(avg_acs=("acs", "mean"), avg_kda=("kda", "mean"), maps=("map", "count"))
        .reset_index()
    )
    losing = team_table[team_table["team"] == losing_team]
    winner = team_table[team_table["team"] == winner_team]

    if losing.empty or winner.empty:
        return {"status": "unknown", "severity": 0.4, "reason": "One team has no baseline sample."}

    acs_gap = float(abs(losing.iloc[0]["avg_acs"] - winner.iloc[0]["avg_acs"]))
    small_sample = int(min(losing.iloc[0]["maps"], winner.iloc[0]["maps"])) < 10
    ambiguous = acs_gap < 10 or small_sample

    return {
        "status": "ambiguous" if ambiguous else "clear baseline gap",
        "severity": 0.7 if ambiguous else 0.2,
        "acs_gap": round(acs_gap, 1),
        "small_sample": small_sample,
        "reason": "Teams are close in baseline ACS or the sample is too small." if ambiguous else "Historical team averages are meaningfully separated.",
    }


def _rank_loss_factors(
    player_signals: list[dict],
    form_signal: dict,
    map_signals: list[dict],
    ranking_signal: dict,
) -> list[dict]:
    factors = []
    worst_players = [item for item in player_signals if item["underperformed"]][:3]
    if worst_players:
        severity = max(item["severity"] for item in worst_players)
        factors.append(
            {
                "factor": "player_underperformance",
                "severity": round(severity, 3),
                "evidence": ", ".join(
                    f"{item['player']} ({item['acs_delta']} ACS, {item['kill_diff']} KD)"
                    for item in worst_players
                ),
            }
        )

    if form_signal.get("status") == "bad form":
        factors.append(
            {
                "factor": "bad_team_form",
                "severity": form_signal["severity"],
                "evidence": f"Recent average kill diff is {form_signal['recent_avg_kill_diff']}.",
            }
        )

    weak_maps = [item for item in map_signals if item["weakness"]]
    if weak_maps:
        factors.append(
            {
                "factor": "map_weakness",
                "severity": max(item["severity"] for item in weak_maps),
                "evidence": ", ".join(f"{item['map']} ({item['acs_delta']} ACS)" for item in weak_maps[:3]),
            }
        )

    if ranking_signal.get("status") in {"ambiguous", "unknown"}:
        factors.append(
            {
                "factor": "ranking_or_sample_ambiguity",
                "severity": ranking_signal["severity"],
                "evidence": ranking_signal["reason"],
            }
        )

    return sorted(factors, key=lambda item: item["severity"], reverse=True)


def _build_loss_summary(losing_team: str, winner_team: str | None, factors: list[dict]) -> str:
    opponent_text = f" against {winner_team}" if winner_team else ""
    if not factors:
        return f"{losing_team}'s loss{opponent_text} is not strongly explained by the current dataset."

    main = factors[0]
    return (
        f"{losing_team}'s loss{opponent_text} is most strongly linked to "
        f"{main['factor'].replace('_', ' ')}. Evidence: {main['evidence']}"
    )
