# Valorant MetaMind AI

Valorant MetaMind AI is a dissertation project for collecting competitive Valorant data from VLR.gg, transforming it into structured player/team datasets, and generating explainable AI-assisted performance insights.

## System Goal

The full system has four layers:

1. Data collection: scrape events, tournament matches, match metadata, maps, agents, and player statistics from VLR.gg.
2. Data engineering: convert raw page data into repeatable CSV/parquet datasets.
3. Analytics and modelling: calculate player form, team form, map tendencies, underperformance signals, and later predictive models.
4. AI explanation: turn structured evidence into plain-English scouting and coaching insights.

## Current Vertical Slice

This repository now includes:

- VLR event discovery in `src/api/vlr_client.py`
- Event match discovery from VLR event pages
- Match stat extraction scaffolding from VLR match pages
- SQLite persistence for events, matches, and player-map stats in `src/storage/database.py`
- Dataset building in `src/ingestion/pipeline.py`
- Player, comparison, and team analytics in `src/analytics/player_analysis.py`
- Match-loss explanation in `src/analytics/loss_analysis.py`
- Deterministic AI-style insight generation in `src/ai/insights.py`
- Streamlit dashboard in `app.py`

## Data Source

The data source is [VLR.gg](https://www.vlr.gg/events). VLR is not an official API, so scrapers should be treated as research tooling: use conservative request rates, cache outputs, and expect selectors to need maintenance.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the Dashboard

```bash
streamlit run app.py
```

The app currently loads the sample dataset at:

```text
notebooks/event_2667_player_stats.csv
```

## Build a Dataset

Collect recent VCT and VCL tier data into SQLite:

```bash
python3 scripts/collect_recent_vct_vcl.py --event-pages 1 --event-limit-per-tier 8 --match-limit-per-event 8 --db data/valorant_metamind.sqlite
```

VLR tier filters used by the collector:

- VCT: `https://www.vlr.gg/events/?tier=60`
- VCL: `https://www.vlr.gg/events/?tier=61`

Build a larger multi-event dataset:

```bash
python3 scripts/collect_more_data.py --tiers vct,vcl --event-pages 2 --event-limit 20 --match-limit-per-event 10 --output data/vlr_player_stats.csv
```

The collector caches raw VLR HTML under `data/raw/vlr_html` by default. This makes experiments more reproducible and reduces repeated requests to VLR.

Build a small sample from the first event listed on VLR:

```bash
python3 scripts/build_dataset.py --match-limit 3 --output data/player_stats.csv
```

Build from a specific VLR event ID:

```bash
python3 scripts/build_dataset.py --event-id 2863 --match-limit 10 --output data/vct_emea_stage_1.csv
```

## Dissertation AI Roadmap

Recommended next steps:

1. Add a raw HTML cache so experiments are reproducible.
2. Store normalized tables: events, matches, maps, teams, players, player_map_stats.
3. Add underperformance detection using rolling player baselines.
4. Train a simple match outcome model with explainability using feature importance or SHAP.
5. Add an LLM layer that receives a strict JSON evidence pack and generates scouting reports.
6. Evaluate the AI layer with metrics such as factual consistency, usefulness, and explanation clarity.

## Loss Explanation Logic

The match-loss explanation feature combines four interpretable signals:

1. Player underperformance: compares each losing-side player ACS against their historical baseline.
2. Team form: compares recent team kill differential against the team's overall baseline.
3. Map weakness: checks whether the losing team was below its usual output on the map.
4. Ranking/sample ambiguity: flags when the historical team gap is small or the sample size is weak.

This gives you a defensible evidence pack before using an LLM. The LLM should rewrite the evidence into a report, not invent the evidence.

## Executive Match Report

Generate a standalone dark HTML report:

```bash
python3 scripts/generate_match_report.py --match-id 660384 --losing-team FNC --output output/report_660384.html
```

The Streamlit match-loss page also has a `Generate executive HTML report` button after an analysis is produced.

The report includes analysis, KPI cards, team comparison, player tables, map weakness signals, and bar-chart visualizations. Round-level post-plant analysis and minimap heatmaps require extra round-event or VOD-derived positional data that VLR match pages do not expose.

## Project Structure

```text
src/
  ai/
    insights.py
  analytics/
    player_analysis.py
  api/
    vlr_client.py
  ingestion/
    pipeline.py
scripts/
  build_dataset.py
  collect_more_data.py
  collect_recent_vct_vcl.py
  test_events.py
  test_matches.py
notebooks/
  event_2667_player_stats.csv
app.py
```

## Author

Karan Mhaswadkar
