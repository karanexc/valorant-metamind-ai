from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from time import sleep
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.vlr.gg"
TIER_CODES = {
    "vct": "60",
    "vcl": "61",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


@dataclass(frozen=True)
class VLRClient:
    base_url: str = BASE_URL
    delay_seconds: float = 0.5
    timeout_seconds: int = 30
    retries: int = 2
    cache_dir: Path | None = None

    def get_soup(self, path_or_url: str) -> BeautifulSoup:
        return BeautifulSoup(self.get_html(path_or_url), "html.parser")

    def get_html(self, path_or_url: str) -> str:
        url = self._normalise_url(path_or_url)
        cache_path = self._cache_path(url)
        if cache_path and cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                res = requests.get(url, headers=HEADERS, timeout=self.timeout_seconds)
                res.raise_for_status()
                html = res.text
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(html, encoding="utf-8")
                sleep(self.delay_seconds)
                return html
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                sleep(self.delay_seconds * (attempt + 1))

        raise RuntimeError(f"Failed to fetch {url}") from last_error

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        key = sha1(url.encode("utf-8")).hexdigest()
        return Path(self.cache_dir) / f"{key}.html"

    def _normalise_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http"):
            return path_or_url
        return urljoin(self.base_url, path_or_url)


def get_event_pages(
    pages: int = 1,
    client: VLRClient | None = None,
    tier: str | None = None,
) -> list[dict]:
    client = client or VLRClient()
    events: list[dict] = []
    for page in range(1, pages + 1):
        events.extend(get_events(page=page, client=client, tier=tier))
    return _unique_by_id(events, "event_id")


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _id_from_href(href: str, resource: str) -> str | None:
    match = re.search(rf"/{resource}/(\d+)", href)
    return match.group(1) if match else None


def _unique_by_id(items: Iterable[dict], key: str) -> list[dict]:
    unique: dict[str, dict] = {}
    for item in items:
        item_id = item.get(key)
        if item_id:
            unique[item_id] = item
    return list(unique.values())


def get_events(page: int = 1, client: VLRClient | None = None, tier: str | None = None) -> list[dict]:
    """Return VLR events from the events index.

    VLR is not an official API, so this parser prefers stable URL patterns over
    fragile CSS selectors. Extra metadata is kept when the page exposes it.
    """

    client = client or VLRClient()
    query = _events_query(page=page, tier=tier)
    path = f"/events{query}"
    soup = client.get_soup(path)
    events: list[dict] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        event_id = _id_from_href(href, "event")
        if not event_id:
            continue

        title = _clean_text(link.select_one(".event-item-title").get_text(" ") if link.select_one(".event-item-title") else link.get_text(" "))
        title = re.sub(r"\b(ongoing|upcoming|completed) Status\b.*$", "", title).strip()

        if title:
            events.append(
                {
                    "event_id": event_id,
                    "title": title,
                    "tier": tier.upper() if tier else None,
                    "url": urljoin(BASE_URL, href),
                    "url_path": urljoin(BASE_URL, href),
                }
            )

    return _unique_by_id(events, "event_id")


def _events_query(page: int, tier: str | None) -> str:
    params = []
    if tier:
        tier_code = TIER_CODES.get(tier.lower(), tier)
        params.append(f"tier={tier_code}")
    if page > 1:
        params.append(f"page={page}")
    return f"/?{'&'.join(params)}" if params else ""


def get_event_matches(event_id_or_url: str, client: VLRClient | None = None) -> list[dict]:
    """Return match IDs and labels for a VLR event page."""

    client = client or VLRClient()
    path = event_id_or_url if str(event_id_or_url).startswith("http") else f"/event/{event_id_or_url}"
    soup = client.get_soup(path)
    matches: list[dict] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        match_id = _id_from_href(href, "match") or re.match(r"^/(\d{5,})/", href)
        match_id = match_id.group(1) if hasattr(match_id, "group") else match_id
        if not match_id:
            continue

        label = _clean_text(link.get_text(" "))
        matches.append(
            {
                "match_id": str(match_id),
                "label": label,
                "url": urljoin(BASE_URL, href),
            }
        )

    return _unique_by_id(matches, "match_id")


def get_match_details(match_id_or_url: str, client: VLRClient | None = None) -> dict:
    """Scrape core match metadata and per-map player rows from a VLR match page."""

    client = client or VLRClient()
    path = match_id_or_url if str(match_id_or_url).startswith("http") else f"/{match_id_or_url}"
    soup = client.get_soup(path)
    match_id_match = re.search(r"/(\d{5,})(?:/|$)", str(match_id_or_url))
    match_id = match_id_match.group(1) if match_id_match else str(match_id_or_url).strip("/")

    title = _clean_text(soup.select_one("h1").get_text(" ") if soup.select_one("h1") else soup.title.get_text(" "))
    teams = [_clean_text(team.get_text(" ")) for team in soup.select(".match-header-link-name")]
    score_text = _clean_text(soup.select_one(".match-header-vs-score").get_text(" ") if soup.select_one(".match-header-vs-score") else "")

    return {
        "match_id": match_id,
        "title": title,
        "teams": teams,
        "score": score_text,
        "maps": _parse_player_stat_tables(soup),
    }


def _parse_player_stat_tables(soup: BeautifulSoup) -> list[dict]:
    maps: list[dict] = []
    stat_blocks = soup.select(".vm-stats-game")

    for block in stat_blocks:
        if block.get("data-game-id") == "all":
            continue

        map_name = _clean_text(block.select_one(".map").get_text(" ") if block.select_one(".map") else "")
        if not map_name:
            map_name = _clean_text(block.get("data-game-id", "all_maps"))
        map_name = re.sub(r"\s+PICK\b.*$", "", map_name).strip()

        rows = []
        for row in block.select("tr"):
            player_cell = row.select_one("td.mod-player")
            player_link = player_cell.select_one("a[href*='/player/']") if player_cell else None
            if not player_link:
                continue

            player_name = _clean_text(player_link.select_one(".text-of").get_text(" ") if player_link.select_one(".text-of") else player_link.get_text(" "))
            team = _clean_text(player_link.select_one(".ge-text-light").get_text(" ") if player_link.select_one(".ge-text-light") else "")
            agent_img = row.select_one("img[alt]")
            agent = agent_img.get("alt", "") if agent_img else ""
            stat_cells = row.select("td.mod-stat")

            if len(stat_cells) < 5:
                continue

            rows.append(
                {
                    "player": player_name,
                    "team": team,
                    "agent": agent,
                    "rating": _stat_float(stat_cells[0]),
                    "acs": _stat_int(stat_cells[1]),
                    "kills": _stat_int(row.select_one("td.mod-vlr-kills")),
                    "deaths": _stat_int(row.select_one("td.mod-vlr-deaths")),
                    "assists": _stat_int(row.select_one("td.mod-vlr-assists")),
                }
            )

        if rows:
            maps.append({"map": map_name, "players": rows})

    return maps


def _stat_text(cell) -> str:
    if cell is None:
        return "0"
    value = cell.select_one(".mod-both")
    return _clean_text(value.get_text(" ") if value else cell.get_text(" "))


def _stat_float(cell) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", _stat_text(cell))
    return float(match.group(0)) if match else 0.0


def _stat_int(cell) -> int:
    return int(round(_stat_float(cell)))
