from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd

from src.analytics.loss_analysis import explain_match_loss
from src.analytics.player_analysis import prepare_player_stats


def generate_executive_match_report(
    df: pd.DataFrame,
    match_id: str,
    losing_team: str | None = None,
    output_path: str | Path | None = None,
) -> Path:
    prepared = prepare_player_stats(df)
    prepared["match_id"] = prepared["match_id"].astype(str)
    match_id = str(match_id)
    match_df = prepared[prepared["match_id"] == match_id].copy()

    if match_df.empty:
        raise ValueError(f"No match data found for match_id={match_id}")

    explanation = explain_match_loss(prepared, match_id, losing_team=losing_team)
    if "error" in explanation:
        raise ValueError(explanation["error"])

    title = _match_title(match_df)
    output_path = Path(output_path or f"output/report_{match_id}.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html = _render_report(prepared, match_df, explanation, title)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _match_title(match_df: pd.DataFrame) -> str:
    title = str(match_df["match_title"].dropna().iloc[0]) if "match_title" in match_df and not match_df["match_title"].dropna().empty else ""
    return title.replace(" | Valorant match | VLR.gg", "") or f"Match {match_df['match_id'].iloc[0]}"


def _render_report(df: pd.DataFrame, match_df: pd.DataFrame, explanation: dict, title: str) -> str:
    losing_team = explanation["losing_team"]
    winner_team = explanation.get("winner_team") or "Opponent"
    event = str(match_df["event"].dropna().iloc[0]) if "event" in match_df and not match_df["event"].dropna().empty else "Unknown event"
    tier = str(match_df["tier"].dropna().iloc[0]) if "tier" in match_df and not match_df["tier"].dropna().empty else "Unknown"
    maps = ", ".join(sorted(str(value) for value in match_df["map"].dropna().unique()))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    key_stats = _key_stats(match_df, explanation)
    player_table = _player_rows(match_df)
    map_table = pd.DataFrame(explanation["map_weakness"])
    factors = pd.DataFrame(explanation["top_factors"])
    team_scores = pd.DataFrame(explanation["match_team_scores"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} | Valorant Executive Match Report</title>
  <style>
    :root {{
      --bg: #071120;
      --panel: #101d31;
      --panel-2: #13233a;
      --line: #243a58;
      --text: #e8f2ff;
      --muted: #91a5bd;
      --cyan: #55d8ff;
      --gold: #f5ca55;
      --danger: #ff6b7a;
      --good: #6fe6a6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at 20% 0%, #10223b 0, var(--bg) 38%, #050b14 100%);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    main {{ width: min(1540px, calc(100vw - 48px)); margin: 28px auto 64px; }}
    .hero, .section {{
      background: linear-gradient(135deg, rgba(30, 49, 78, .92), rgba(12, 25, 43, .95));
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 18px 48px rgba(0,0,0,.28);
    }}
    .hero {{ padding: 28px 32px; margin-bottom: 18px; }}
    h1 {{ margin: 0 0 10px; font-size: 34px; }}
    .subtitle {{ color: var(--muted); margin-bottom: 20px; font-size: 16px; }}
    .chips {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .chip {{ background: #19314f; color: #ccecff; padding: 8px 13px; border-radius: 999px; font-weight: 700; font-size: 13px; }}
    .tabs {{ position: sticky; top: 0; z-index: 5; display: flex; gap: 8px; padding: 10px; margin: 18px 0; width: fit-content; background: rgba(8, 17, 31, .9); border: 1px solid var(--line); border-radius: 999px; backdrop-filter: blur(10px); }}
    .tabs a {{ color: var(--muted); text-decoration: none; padding: 10px 16px; border-radius: 999px; font-weight: 700; }}
    .tabs a:hover, .tabs a.active {{ color: var(--text); background: #26364f; }}
    .section {{ margin-top: 18px; overflow: hidden; }}
    .section h2 {{ margin: 0; padding: 20px; color: var(--cyan); font-size: 18px; text-transform: uppercase; letter-spacing: .08em; border-bottom: 1px solid var(--line); }}
    .section-body {{ padding: 20px; }}
    .callout {{ border: 1px solid var(--line); border-left: 5px solid var(--cyan); border-radius: 8px; padding: 22px; color: #d8e9ff; font-size: 18px; line-height: 1.55; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; background: rgba(11, 24, 42, .72); padding: 18px; min-height: 100px; }}
    .metric {{ font-size: 28px; font-weight: 800; color: #dff8ff; }}
    .label {{ margin-top: 8px; color: var(--muted); font-size: 12px; text-transform: uppercase; font-weight: 800; }}
    h3 {{ color: var(--gold); margin: 22px 0 10px; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 8px; border: 1px solid var(--line); }}
    th {{ text-align: left; background: #203652; color: #eaf7ff; font-size: 13px; text-transform: uppercase; padding: 13px 14px; }}
    td {{ padding: 12px 14px; border-top: 1px solid var(--line); color: #dcecff; }}
    tr:nth-child(even) td {{ background: rgba(255,255,255,.03); }}
    .bars {{ display: grid; gap: 12px; }}
    .bar-row {{ display: grid; grid-template-columns: 130px 1fr 70px; align-items: center; gap: 12px; }}
    .bar-track {{ height: 18px; background: #0a1526; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }}
    .bar {{ height: 100%; background: linear-gradient(90deg, var(--cyan), #7fe7bc); }}
    .note {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    @media (max-width: 900px) {{ main {{ width: calc(100vw - 24px); }} .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Valorant Executive Match Report</h1>
      <div class="subtitle">{escape(title)}</div>
      <div class="chips">
        <span class="chip">Tier: {escape(tier)}</span>
        <span class="chip">Event: {escape(event)}</span>
        <span class="chip">Generated: {escape(generated)}</span>
        <span class="chip">Question: Why did {escape(losing_team)} lose?</span>
      </div>
    </section>

    <nav class="tabs">
      <a class="active" href="#analysis">Analysis</a>
      <a href="#key-stats">Key Stats</a>
      <a href="#data">Data</a>
      <a href="#visualizations">Visualizations</a>
    </nav>

    <section class="section" id="analysis">
      <h2>Analysis</h2>
      <div class="section-body">
        <div class="callout">{escape(explanation["summary"])}</div>
        <h3>Top explanatory factors</h3>
        {_table(factors)}
      </div>
    </section>

    <section class="section" id="key-stats">
      <h2>Key Stats</h2>
      <div class="section-body">
        <div class="grid">{''.join(_metric_card(label, value) for label, value in key_stats)}</div>
      </div>
    </section>

    <section class="section" id="data">
      <h2>Data</h2>
      <div class="section-body">
        <h3>Team comparison</h3>
        {_table(team_scores)}
        <h3>Players ({escape(losing_team)} and {escape(winner_team)})</h3>
        {_table(player_table)}
        <h3>Map weakness signals</h3>
        {_table(map_table)}
      </div>
    </section>

    <section class="section" id="visualizations">
      <h2>Visualizations</h2>
      <div class="section-body">
        <h3>Average ACS by team</h3>
        {_bar_chart(team_scores, "team", "avg_acs")}
        <h3>Player ACS</h3>
        {_bar_chart(player_table, "player", "acs")}
        <p class="note">Round-level post-plant tables, opening-kill minimaps, and site-position heatmaps require event-log or VOD-derived coordinate data. This report is ready to receive those features once that data source is added.</p>
      </div>
    </section>
  </main>
</body>
</html>"""


def _key_stats(match_df: pd.DataFrame, explanation: dict) -> list[tuple[str, str]]:
    losing_team = explanation["losing_team"]
    losing_rows = match_df[match_df["team"] == losing_team]
    factors = explanation["top_factors"]
    top_factor = factors[0]["factor"].replace("_", " ").title() if factors else "No dominant factor"
    return [
        ("Losing team", losing_team),
        ("Winner", explanation.get("winner_team") or "Unknown"),
        ("Maps", str(match_df["map"].nunique())),
        ("Players", str(match_df["player"].nunique())),
        ("Avg ACS", f"{losing_rows['acs'].mean():.1f}"),
        ("Avg KDA", f"{losing_rows['kda'].mean():.2f}"),
        ("Kill diff", f"{int(losing_rows['kill_diff'].sum())}"),
        ("Main factor", top_factor),
    ]


def _player_rows(match_df: pd.DataFrame) -> pd.DataFrame:
    return (
        match_df.groupby(["player", "team", "agent"], dropna=True)
        .agg(
            maps=("map", "nunique"),
            kills=("kills", "sum"),
            deaths=("deaths", "sum"),
            assists=("assists", "sum"),
            acs=("acs", "mean"),
            kda=("kda", "mean"),
            kill_diff=("kill_diff", "sum"),
        )
        .round({"acs": 1, "kda": 2})
        .sort_values("acs", ascending=False)
        .reset_index()
    )


def _metric_card(label: str, value: str) -> str:
    return f'<div class="card"><div class="metric">{escape(value)}</div><div class="label">{escape(label)}</div></div>'


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return '<p class="note">No rows available.</p>'
    columns = list(df.columns)
    head = "".join(f"<th>{escape(str(col).replace('_', ' '))}</th>" for col in columns)
    rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{escape(str(row[col]))}</td>" for col in columns)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _bar_chart(df: pd.DataFrame, label_col: str, value_col: str) -> str:
    if df.empty or value_col not in df:
        return '<p class="note">No chart data available.</p>'
    chart_df = df[[label_col, value_col]].dropna().copy()
    chart_df[value_col] = pd.to_numeric(chart_df[value_col], errors="coerce").fillna(0)
    chart_df = chart_df.sort_values(value_col, ascending=False).head(12)
    max_value = max(float(chart_df[value_col].max()), 1)
    rows = []
    for _, row in chart_df.iterrows():
        value = float(row[value_col])
        width = min(max(value / max_value * 100, 2), 100)
        rows.append(
            f'<div class="bar-row"><strong>{escape(str(row[label_col]))}</strong>'
            f'<div class="bar-track"><div class="bar" style="width:{width:.1f}%"></div></div>'
            f'<span>{value:.1f}</span></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>'
