"""
Builds the Pokehub price site (static HTML) into public/.

  index.html            hero stats, top 10, full searchable/sortable table
  sets/<slug>.html      one page per set ("<Set> card prices"), for search traffic
  cards/<slug>.html     one page per card ("<Card> <Set> #num price"): the long-tail
                        searches collectors type every day, plus a buy link
  sitemap.xml, robots.txt

Data: today's snapshot from ptcg.py (TCGplayer market prices via
pokemontcg.io), 7-day change from the snapshot a week earlier when present.
Run daily by .github/workflows/site.yml, which deploys public/ to Pages.
"""

import datetime as dt
import html
import json
import re
import shutil
from pathlib import Path

import ptcg

ROOT = Path(__file__).parent
OUT = ROOT / "public"
BASE_URL = "https://tzahmar.github.io/pokehub"
FB_URL = "https://www.facebook.com/pokehubtcg"
# IndexNow (Bing, Yandex, Seznam...): the key file proves we own the site.
# Google Search Console HTML-tag verification token (content="..."); empty = no tag.
GOOGLE_VERIFY = ""
INDEXNOW_KEY = "8de9360f1c559c36332b9d1157148c40"
E = html.escape


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def money(p: float) -> str:
    return f"${p:,.0f}" if p >= 100 else f"${p:,.2f}"


def card_path(c: dict) -> str:
    # The pokemontcg.io id ("swsh7-215") keeps the URL stable and unique; older
    # snapshots have no card number, so the number can't be the key.
    return f"cards/{slug(c['n'] + ' ' + c['s'] + ' ' + c['id'])}.html"


def history() -> dict:
    """{card_id: [(date, price), ...]} from every saved daily snapshot."""
    out = {}
    for f in sorted(ptcg.PRICES.glob("*.json")):
        day = f.stem
        for cid, c in json.loads(f.read_text(encoding="utf8")).items():
            out.setdefault(cid, []).append((day, c["p"]))
    return out


def sparkline(points: list) -> str:
    """Inline SVG price line; empty until there are two days of data."""
    if len(points) < 2:
        return ""
    w, h, ps = 640, 160, [p for _, p in points]
    lo, hi = min(ps), max(ps)
    span = (hi - lo) or 1
    xy = [(i * w / (len(ps) - 1), h - 12 - (p - lo) / span * (h - 24)) for i, p in enumerate(ps)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    return (f'<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:640px;background:var(--card);'
            f'border:1px solid var(--line);border-radius:14px"><polyline fill="none" stroke="#ffcb05" '
            f'stroke-width="3" points="{path}"/></svg>')


def load():
    day, snap = ptcg.latest_snapshot()
    if snap is None:
        raise SystemExit("no price snapshot yet")
    before = ptcg.load_snapshot(day - dt.timedelta(days=7)) or {}
    cards = []
    for cid, c in snap.items():
        old = (before.get(cid) or {}).get("p")
        cards.append({**c, "id": cid, "chg": ((c["p"] - old) / old * 100) if old else None})
    cards.sort(key=lambda c: c["p"], reverse=True)
    return day, cards, bool(before)


CSS = """
:root{--bg:#0c1430;--bg2:#1c1240;--card:#16204a;--line:#2a356b;--y:#ffcb05;--t:#fff;--m:#b8c2e0;--up:#5be08a;--dn:#ff7a7a}
*{box-sizing:border-box}html{background:var(--bg2)}body{margin:0;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--t);
background:linear-gradient(180deg,var(--bg) 0,var(--bg2) 1200px,var(--bg2));min-height:100vh}a{color:var(--y)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
header{padding:28px 0 8px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.logo{font-weight:900;font-size:30px;color:var(--y);text-decoration:none;letter-spacing:.5px}
.fb{background:#1877f2;color:#fff;text-decoration:none;font-weight:700;padding:10px 16px;border-radius:999px;font-size:14px}
h1{font-size:clamp(28px,5vw,44px);margin:18px 0 4px}h2{margin:36px 0 12px;font-size:24px}
.sub{color:var(--m);margin:0 0 20px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px}
.stat b{display:block;color:var(--y);font-size:28px}.stat span{color:var(--m);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px;text-align:center;text-decoration:none;color:var(--t)}
.tile img{width:100%;border-radius:8px;aspect-ratio:.716;object-fit:cover;background:#0003}
.tile .p{color:var(--y);font-weight:900;font-size:20px;margin-top:6px}.tile .n{font-size:13px;color:var(--m)}
.rank{position:relative}.rank i{position:absolute;top:-6px;left:-6px;background:var(--y);color:#141428;font:900 14px system-ui;
border-radius:999px;width:28px;height:28px;display:grid;place-items:center;font-style:normal}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.tools input,.tools select{background:var(--card);color:var(--t);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:15px}
.tools input{flex:1;min-width:200px}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:14px}
table{width:100%;border-collapse:collapse;background:var(--card)}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:14px;white-space:nowrap}
th{position:sticky;top:0;background:#1d2858;cursor:pointer;user-select:none}th:hover{color:var(--y)}
td img{width:36px;border-radius:4px;vertical-align:middle}
td.price{color:var(--y);font-weight:800}.up{color:var(--up)}.dn{color:var(--dn)}
.sets{display:flex;flex-wrap:wrap;gap:8px}.sets a{background:var(--card);border:1px solid var(--line);border-radius:999px;
padding:6px 12px;text-decoration:none;color:var(--t);font-size:14px}.sets a:hover{border-color:var(--y)}
.cta{margin:40px 0;background:var(--card);border:1px solid var(--y);border-radius:18px;padding:22px;text-align:center}
footer{color:var(--m);font-size:13px;padding:30px 0 50px}
@media(max-width:600px){td.hide,th.hide{display:none}.cardtop{grid-template-columns:1fr!important}.cardtop>img{max-width:240px;margin:0 auto;display:block}}
"""

JS = """
const rows=[...document.querySelectorAll('#t tbody tr')],q=document.getElementById('q'),s=document.getElementById('s');
function f(){const v=q.value.toLowerCase(),set=s?s.value:'';rows.forEach(r=>{const ok=r.dataset.k.includes(v)&&(!set||r.dataset.s===set);r.style.display=ok?'':'none'})}
q&&q.addEventListener('input',f);s&&s.addEventListener('change',f);
document.querySelectorAll('#t th[data-c]').forEach(th=>th.onclick=()=>{const c=th.dataset.c,d=th.dataset.d=th.dataset.d==='1'?'-1':'1',
tb=document.querySelector('#t tbody');rows.sort((a,b)=>{const x=a.dataset[c],y=b.dataset[c];const nx=parseFloat(x),ny=parseFloat(y);
return (isNaN(nx)||isNaN(ny)?x.localeCompare(y):nx-ny)*d});rows.forEach(r=>tb.appendChild(r))});
"""


def page(title: str, desc: str, path: str, body: str) -> str:
    gv = f'<meta name="google-site-verification" content="{E(GOOGLE_VERIFY)}">' if GOOGLE_VERIFY else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="{BASE_URL}/{path}">{gv}
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{BASE_URL}/{path}">
<style>{CSS}</style></head><body><div class="wrap">
<header><a class="logo" href="{BASE_URL}/">POKEHUB</a>
<a class="fb" href="{FB_URL}" rel="noopener">Follow on Facebook</a></header>
{body}
<div class="cta"><b>Daily card prices, Top 10s, news and Reels.</b><br>
<a class="fb" style="display:inline-block;margin-top:12px" href="{FB_URL}" rel="noopener">Follow Pokehub on Facebook</a></div>
<footer>Prices are TCGplayer market prices for ungraded cards (via pokemontcg.io), updated daily. For reference only.
Pokehub is a fan site, not affiliated with Nintendo, The Pokémon Company or TCGplayer. Card images © their owners.</footer>
</div><script>{JS}</script></body></html>"""


def table(cards: list, with_set_filter: bool, has_change: bool) -> str:
    sets = sorted({c["s"] for c in cards})
    tools = '<div class="tools"><input id="q" placeholder="Search a card, e.g. Charizard" autocomplete="off">'
    if with_set_filter:
        tools += '<select id="s"><option value="">All sets</option>' + "".join(
            f'<option>{E(s)}</option>' for s in sets) + "</select>"
    tools += "</div>"
    head = ('<tr><th></th><th data-c="n">Card</th><th class="hide" data-c="s">Set</th>'
            '<th class="hide" data-c="r">Rarity</th><th data-c="p">Price</th>'
            + ('<th data-c="c">7d</th>' if has_change else "") + "</tr>")
    rows = []
    for c in cards:
        chg = c["chg"]
        chg_td = ""
        if has_change:
            chg_td = (f'<td class="{"up" if chg > 0 else "dn" if chg < 0 else ""}">{chg:+.0f}%</td>'
                      if chg is not None else "<td>–</td>")
        name = E(c["n"]) + (f' <span style="color:var(--m)">#{E(c["num"])}</span>' if c.get("num") else "")
        link = f'<a href="{BASE_URL}/{card_path(c)}">{name}</a>'
        rows.append(
            f'<tr data-k="{E((c["n"] + " " + c["s"]).lower())}" data-s="{E(c["s"])}" data-n="{E(c["n"])}" '
            f'data-r="{E(c["r"])}" data-p="{c["p"]}" data-c="{chg if chg is not None else -999}">'
            f'<td><img loading="lazy" src="{E(c.get("sm") or c["img"])}" alt=""></td><td>{link}</td>'
            f'<td class="hide">{E(c["s"])}</td><td class="hide">{E(c["r"])}</td>'
            f'<td class="price">{money(c["p"])}</td>{chg_td}</tr>')
    return f'{tools}<div class="tbl"><table id="t"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def tiles(cards: list) -> str:
    return '<div class="grid">' + "".join(
        f'<a class="tile rank" href="{BASE_URL}/{card_path(c)}"><i>{i}</i>'
        f'<img loading="lazy" src="{E(c.get("sm") or c["img"])}" alt="{E(c["n"])}">'
        f'<div class="p">{money(c["p"])}</div><div class="n">{E(c["n"])}<br>{E(c["s"])}</div></a>'
        for i, c in enumerate(cards, 1)) + "</div>"


def build() -> None:
    day, cards, has_change = load()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "sets").mkdir(parents=True)
    (OUT / "cards").mkdir()
    try:
        date = day.strftime("%B %-d, %Y")
    except ValueError:                       # Windows strftime has no %-d
        date = day.strftime("%B %d, %Y").replace(" 0", " ")

    by_set = {}
    for c in cards:
        by_set.setdefault(c["s"], []).append(c)
    gainers = sorted([c for c in cards if c["chg"] is not None and c["p"] >= 15], key=lambda c: -c["chg"])
    top = cards[0]
    stats = (f'<div class="stats"><div class="stat"><span>Most valuable card</span><b>{money(top["p"])}</b>'
             f'<span>{E(top["n"])} · {E(top["s"])}</span></div>'
             f'<div class="stat"><span>Cards tracked</span><b>{len(cards)}</b><span>across {len(by_set)} sets</span></div>')
    if gainers:
        g = gainers[0]
        stats += (f'<div class="stat"><span>Biggest 7-day gainer</span><b class="up">+{g["chg"]:.0f}%</b>'
                  f'<span>{E(g["n"])} · {money(g["p"])}</span></div>')
    stats += "</div>"
    set_links = '<div class="sets">' + "".join(
        f'<a href="{BASE_URL}/sets/{slug(s)}.html">{E(s)}</a>'
        for s in sorted(by_set, key=lambda s: -max(c["p"] for c in by_set[s]))) + "</div>"

    body = (f'<h1>Pokémon card prices today</h1><p class="sub">Market prices for {len(cards)} cards, updated {date}.</p>'
            f'{stats}<h2>Top 10 most valuable right now</h2>{tiles(cards[:10])}'
            + (f'<h2>Biggest gainers this week</h2>{tiles(gainers[:10])}' if len(gainers) >= 5 else "")
            + f'<h2>Prices by set</h2>{set_links}<h2>All card prices</h2>{table(cards, True, has_change)}')
    (OUT / "index.html").write_text(page(
        "Pokémon Card Prices Today: Top 10 & Full Price List | Pokehub",
        f"Today's Pokémon TCG market prices for {len(cards)} cards across {len(by_set)} sets. "
        f"Top 10 most valuable cards, weekly gainers and a searchable price list, updated daily.",
        "", body), encoding="utf8")

    for s, cs in by_set.items():
        total = sum(c["p"] for c in cs[:10])
        body = (f'<p class="sub"><a href="{BASE_URL}/">← All sets</a></p><h1>{E(s)} card prices</h1>'
                f'<p class="sub">Market prices for {len(cs)} {E(s)} cards worth $5 or more, updated {date}. '
                f'The top 10 are worth {money(total)} together.</p>'
                f'<h2>Most valuable {E(s)} cards</h2>{tiles(cs[:10])}<h2>Full {E(s)} price list</h2>{table(cs, False, has_change)}')
        (OUT / "sets" / f"{slug(s)}.html").write_text(page(
            f"{s} Card Prices: Most Valuable Cards Today | Pokehub",
            f"{s} Pokémon card prices today: the most valuable cards, led by {cs[0]['n']} at {money(cs[0]['p'])}. "
            f"Updated daily.", f"sets/{slug(s)}.html", body), encoding="utf8")

    hist = history()
    for c in cards:
        cs = by_set[c["s"]]
        rank = cs.index(c) + 1
        pts = hist.get(c["id"], [])
        chg = (f'<span class="{"up" if c["chg"] > 0 else "dn"}">{c["chg"]:+.0f}% in 7 days</span>'
               if c["chg"] else "")
        hist_rows = "".join(f"<tr><td>{d}</td><td class=\"price\">{money(p)}</td></tr>" for d, p in reversed(pts[-30:]))
        num = f" #{E(str(c['num']))}" if c.get("num") else ""
        others = [o for o in cs if o is not c][:10]
        buy = (f'<p><a class="fb" style="display:inline-block;background:#ffcb05;color:#141428" href="{E(c["u"])}" '
               f'rel="nofollow noopener sponsored">See listings on TCGplayer</a></p>' if c.get("u") else "")
        body = (f'<p class="sub"><a href="{BASE_URL}/">All prices</a> › <a href="{BASE_URL}/sets/{slug(c["s"])}.html">{E(c["s"])}</a></p>'
                f'<h1>{E(c["n"])}{num} price</h1>'
                f'<p class="sub">{E(c["s"])} · {E(c["r"])} · #{rank} most valuable card in the set</p>'
                f'<div style="display:grid;grid-template-columns:minmax(0,300px) 1fr;gap:24px;align-items:start" class="cardtop">'
                f'<img src="{E(c["img"])}" alt="{E(c["n"])} {E(c["s"])}{num}" style="width:100%;border-radius:14px">'
                f'<div><div class="stat"><span>Market price today ({date}), ungraded</span><b>{money(c["p"])}</b>{chg}</div>'
                f'{buy}<h2>Price history</h2>{sparkline(pts)}'
                f'<div class="tbl" style="margin-top:12px"><table><thead><tr><th>Date</th><th>Market price</th></tr></thead>'
                f'<tbody>{hist_rows}</tbody></table></div></div></div>'
                f'<h2>More {E(c["s"])} cards</h2>{tiles(others)}')
        (OUT / card_path(c)).write_text(page(
            f"{c['n']} {c['s']}{num and ' #' + str(c['num'])} Price Today | Pokehub",
            f"{c['n']} ({c['s']}{num and ' #' + str(c['num'])}, {c['r']}) is worth {money(c['p'])} today "
            f"(TCGplayer market price, ungraded). Price history, 7-day change and the set's other top cards.",
            card_path(c), body), encoding="utf8")

    urls = [""] + [f"sets/{slug(s)}.html" for s in by_set] + [card_path(c) for c in cards]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{BASE_URL}/{u}</loc><lastmod>{day.isoformat()}</lastmod></url>" for u in urls)
        + "</urlset>", encoding="utf8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf8")
    (OUT / ".nojekyll").write_text("")
    (OUT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY)
    # Google Search Console ownership file (verified 2026-10-18; removing it unverifies the site).
    (OUT / "googlecbe4c6e43a9d807b.html").write_text("google-site-verification: googlecbe4c6e43a9d807b.html")
    (OUT / "urls.txt").write_text("\n".join(f"{BASE_URL}/{u}" for u in urls), encoding="utf8")
    print(f"built {len(urls)} pages, {len(cards)} cards")


if __name__ == "__main__":
    build()
