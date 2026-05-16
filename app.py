from pathlib import Path

import pandas as pd
import streamlit as st

from src.ai.insights import build_llm_context, generate_player_insight
from src.analytics.loss_analysis import explain_match_loss
from src.analytics.player_analysis import analyze_player, compare_players, generate_report, prepare_player_stats, team_summary
from src.reporting.executive_report import generate_executive_match_report
from src.storage.database import load_player_stats_from_db

DEFAULT_DATA_PATH = Path("data/vlr_player_stats.csv")
SAMPLE_DATA_PATH = Path("notebooks/event_2667_player_stats.csv")
DEFAULT_DB_PATH = Path("data/valorant_metamind.sqlite")


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    if path.suffix in {".sqlite", ".db"}:
        df = load_player_stats_from_db(path)
        return prepare_player_stats(df)

    df = pd.read_csv(path)
    return prepare_player_stats(df)


def match_label(row: pd.Series) -> str:
    title = str(row.get("match_title") or "").replace(" | Valorant match | VLR.gg", "")
    title = title.split(" | ")[0] if title else "Unknown match"
    maps = int(row.get("maps") or 0)
    return f"{title} ({row['match_id']}, {maps} maps)"


def event_label(event: str, event_df: pd.DataFrame) -> str:
    matches = event_df["match_id"].astype(str).nunique()
    return f"{event} ({matches} matches)"


st.set_page_config(page_title="Valorant MetaMind AI", layout="wide")
st.title("Valorant MetaMind AI")

initial_path = DEFAULT_DB_PATH if DEFAULT_DB_PATH.exists() else DEFAULT_DATA_PATH if DEFAULT_DATA_PATH.exists() else SAMPLE_DATA_PATH
data_path = Path(st.sidebar.text_input("Dataset path", value=str(initial_path)))

if not data_path.exists():
    st.error(f"Dataset not found: {data_path}")
    st.stop()

df = load_data(data_path)

option = st.sidebar.selectbox(
    "Choose feature",
    [
        "Player Analysis",
        "Compare Players",
        "Team Overview",
        "Match Loss Explanation",
        "Dataset Overview",
        "AI Insight Context",
    ],
)

if option == "Player Analysis":
    st.header("Player Analysis")
    player = st.selectbox("Player", sorted(df["player"].dropna().unique()))

    if player:
        st.text(generate_report(df, player))
        st.subheader("AI insight")
        st.write(generate_player_insight(df, player))

elif option == "Compare Players":
    st.header("Compare Players")
    players = sorted(df["player"].dropna().unique())
    p1 = st.selectbox("Player 1", players, index=0)
    p2 = st.selectbox("Player 2", players, index=min(1, len(players) - 1))

    comparison = compare_players(df, p1, p2)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(p1)
        st.json(comparison[p1])

    with col2:
        st.subheader(p2)
        st.json(comparison[p2])

elif option == "Team Overview":
    st.header("Team Overview")
    st.dataframe(team_summary(df), use_container_width=True)

elif option == "Match Loss Explanation":
    st.header("Match Loss Explanation")

    available_tiers = sorted([tier for tier in df.get("tier", pd.Series(dtype=str)).dropna().unique()])
    if available_tiers:
        tier = st.selectbox("Tier", available_tiers)
        tier_df = df[df["tier"] == tier]
    else:
        st.info("This dataset does not include a tier column, so all matches are shown together.")
        tier = None
        tier_df = df

    events = sorted(tier_df["event"].dropna().unique()) if "event" in tier_df.columns else []
    if not events:
        st.warning("No events found for the selected tier.")
        st.stop()

    event_options = {event_label(event, tier_df[tier_df["event"] == event]): event for event in events}
    selected_event_label = st.selectbox("Event", list(event_options.keys()))
    selected_event = event_options[selected_event_label]
    event_df = tier_df[tier_df["event"] == selected_event]

    match_options_df = (
        event_df.groupby("match_id", dropna=True)
        .agg(
            match_title=("match_title", "first"),
            maps=("map", "nunique"),
            teams=("team", lambda values: " vs ".join(sorted(set(str(value) for value in values if pd.notna(value))))),
        )
        .reset_index()
        .sort_values("match_title")
    )
    match_options = {match_label(row): str(row["match_id"]) for _, row in match_options_df.iterrows()}
    selected_match_label = st.selectbox("Match", list(match_options.keys()))
    match_id = match_options[selected_match_label]

    match_df = df[df["match_id"].astype(str) == str(match_id)]
    teams = sorted(match_df["team"].dropna().unique())
    losing_team = st.selectbox("Losing team", ["Infer automatically"] + teams)
    losing_team_value = None if losing_team == "Infer automatically" else losing_team

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tier", tier or "All")
    c2.metric("Event matches", event_df["match_id"].astype(str).nunique())
    c3.metric("Match maps", match_df["map"].nunique())
    c4.metric("Teams", match_df["team"].nunique())

    explanation = explain_match_loss(df, match_id, losing_team=losing_team_value)
    if "error" in explanation:
        st.error(explanation["error"])
    else:
        st.subheader("Summary")
        st.write(explanation["summary"])

        st.subheader("Top factors")
        st.dataframe(pd.DataFrame(explanation["top_factors"]), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Player underperformance")
            st.dataframe(pd.DataFrame(explanation["player_underperformance"]), use_container_width=True)

        with col2:
            st.subheader("Map weakness")
            st.dataframe(pd.DataFrame(explanation["map_weakness"]), use_container_width=True)

        st.subheader("Team form and ambiguity")
        st.json(
            {
                "team_form": explanation["team_form"],
                "ranking_ambiguity": explanation["ranking_ambiguity"],
            }
        )

        if st.button("Generate executive HTML report"):
            output_path = generate_executive_match_report(
                df,
                match_id=match_id,
                losing_team=explanation["losing_team"],
                output_path=Path("output") / f"match_report_{match_id}.html",
            )
            st.success(f"Report generated: {output_path}")

elif option == "Dataset Overview":
    st.header("Dataset Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", len(df))
    c2.metric("Players", df["player"].nunique())
    c3.metric("Teams", df["team"].nunique())
    c4.metric("Maps", df["map"].nunique())

    st.subheader("Sample Data")
    st.dataframe(df.head(20), use_container_width=True)

    st.subheader("ACS by player")
    chart_data = df.groupby("player")["acs"].mean().sort_values(ascending=False)
    st.bar_chart(chart_data)

else:
    st.header("AI Insight Context")
    player = st.selectbox("Player", sorted(df["player"].dropna().unique()))
    st.json(build_llm_context(df, player))
