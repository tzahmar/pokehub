"""
Pokémon TCG card data and market prices, from the public Pokémon TCG API
(api.pokemontcg.io). Prices are TCGplayer market prices for ungraded cards,
refreshed by the API roughly daily.

Known gaps (checked 2026-10-18):
  * the newest sets (me5 Pitch Black, me55 30th Celebration) have no prices yet;
  * the API throws intermittent 500s, so every call retries;
  * there is no graded (PSA/BGS/CGC) data here. Graded sales need a paid
    source (e.g. PriceCharting) and are not scraped from eBay.
"""

import datetime as dt
import json
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger("pokemon_hub.ptcg")

API = "https://api.pokemontcg.io/v2"
DATA = Path(__file__).parent / "data"
PRICES = DATA / "prices"

# Chase sets people still talk about, tracked alongside the newest releases.
CLASSIC_SETS = ["sv3pt5", "swsh7", "sv8pt5", "swsh12pt5", "sv4pt5", "cel25", "swsh45"]
RECENT_SETS = 14          # newest N sets also tracked
MIN_TRACKED_PRICE = 5.0   # snapshot only cards worth something


def _headers() -> dict:
    key = os.environ.get("POKEMONTCG_API_KEY")
    return {"X-Api-Key": key} if key else {}


def _get(path: str, params: dict, tries: int = 4) -> dict:
    last = None
    for i in range(tries):
        try:
            r = requests.get(f"{API}/{path}", params=params, headers=_headers(), timeout=90)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"pokemontcg.io {path} failed after {tries} tries: {last}")


def recent_sets(n: int = RECENT_SETS) -> list:
    data = _get("sets", {"orderBy": "-releaseDate", "pageSize": n,
                         "select": "id,name,series,releaseDate,total,images"})
    return data["data"]


def set_info(set_id: str) -> dict:
    return _get(f"sets/{set_id}", {"select": "id,name,series,releaseDate,total,images"})["data"]


def set_cards(set_id: str) -> list:
    cards, page = [], 1
    while True:
        data = _get("cards", {"q": f"set.id:{set_id}", "page": page, "pageSize": 250,
                              "select": "id,name,number,rarity,set,tcgplayer,cardmarket,images"})
        cards.extend(data["data"])
        if len(cards) >= data.get("totalCount", 0) or not data["data"]:
            return cards
        page += 1


def market_price(card: dict):
    """(price, variant) of the card's most valuable printing, or (0, None)."""
    best = (0.0, None)
    for variant, p in (card.get("tcgplayer") or {}).get("prices", {}).items():
        m = p.get("market") or 0
        if m > best[0]:
            best = (float(m), variant)
    return best


def tracked_set_ids() -> list:
    ids = [s["id"] for s in recent_sets()]
    return ids + [s for s in CLASSIC_SETS if s not in ids]


def snapshot(set_ids: list = None) -> dict:
    """Today's prices for every tracked card above MIN_TRACKED_PRICE.

    {card_id: {"p": price, "n": name, "s": set name, "r": rarity, "img": url}}
    Saved to data/prices/YYYY-MM-DD.json so the bot builds its own history,
    which is what the weekly "biggest movers" post is computed from.
    """
    out = {}
    for sid in set_ids or tracked_set_ids():
        try:
            for c in set_cards(sid):
                price, _ = market_price(c)
                if price >= MIN_TRACKED_PRICE:
                    out[c["id"]] = {"p": round(price, 2), "n": c["name"], "s": c["set"]["name"],
                                    "r": c.get("rarity") or "", "img": c["images"]["large"],
                                    "sm": c["images"].get("small") or c["images"]["large"],
                                    "num": c.get("number", ""), "d": c["set"].get("releaseDate", ""),
                                    "u": (c.get("tcgplayer") or {}).get("url", "")}
        except RuntimeError as e:
            log.warning(f"skipping set {sid}: {e}")
    return out


def save_snapshot(snap: dict, day: dt.date = None) -> Path:
    PRICES.mkdir(parents=True, exist_ok=True)
    path = PRICES / f"{(day or dt.date.today()).isoformat()}.json"
    path.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    return path


def load_snapshot(day: dt.date):
    path = PRICES / f"{day.isoformat()}.json"
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else None


def latest_snapshot():
    files = sorted(PRICES.glob("*.json"))
    if not files:
        return None, None
    f = files[-1]
    return dt.date.fromisoformat(f.stem), json.loads(f.read_text(encoding="utf8"))


def movers(today: dict, before: dict, min_price: float = 15.0, n: int = 10) -> list:
    """Biggest % gainers between two snapshots, ignoring cheap cards (noise)."""
    rows = []
    for cid, now in today.items():
        old = before.get(cid)
        if not old or now["p"] < min_price or old["p"] <= 0:
            continue
        rows.append({**now, "id": cid, "old": old["p"], "pct": (now["p"] - old["p"]) / old["p"] * 100})
    rows.sort(key=lambda r: r["pct"], reverse=True)
    return [r for r in rows if r["pct"] > 0][:n]
