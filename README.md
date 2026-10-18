# Pokehub price site

Static Pokémon TCG price site: https://tzahmar.github.io/pokehub/

`site.py` builds `public/` (home with top 10 + full searchable table, one page per set, sitemap) from
the daily snapshot in `data/prices/` (TCGplayer market prices via pokemontcg.io, see `ptcg.py`).
`.github/workflows/site.yml` refreshes prices, rebuilds and deploys to GitHub Pages every day.
Companion of the Facebook page bot (private repo tzahmar/pokemon-hub-poster).
