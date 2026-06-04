# 🍽️ Oběd na mapě – polední menu v Praze

Webová mapa pražských restaurací (městské části Praha 1–10) s **dnešním poledním menu**.
Najedeš myší na restauraci ve svém okolí (kde bydlíš nebo pracuješ) a hned vidíš, co dnes vaří.
Na mobilu klepneš na špendlík.

**Live:** https://obed.tomaskalivoda.cz

## Jak to funguje

```
menicka.cz  ──scrape──>  data/restaurants.json  ──>  Leaflet mapa (statický web)
   (zdroj menu)          (denně přes GitHub Action)     (GitHub Pages)
```

- **`scripts/scrape.py`** – stáhne listing stránky `praha-1..praha-10` z [menicka.cz](https://www.menicka.cz),
  vytáhne dnešní menu každé restaurace. Souřadnice (GPS) bere z detail stránek a cachuje je do
  `data/places.json` (stahují se jen jednou per restaurace). Výstup: `data/restaurants.json`.
  Závislosti: **pouze Python stdlib**.
- **`index.html` + `app.js` + `styles.css`** – statický frontend. [Leaflet](https://leafletjs.com) +
  marker clustering, dlaždice CARTO/OSM. Geolokace uživatele, vyhledání místa (Nominatim),
  filtr podle jídla/názvu, hover/klik = polední menu.
- **`.github/workflows/refresh.yml`** – GitHub Action každý všední den ráno (~8:20) a dopoledne (~10:30)
  znovu spustí scraper a commitne čerstvá data → GitHub Pages je publikuje.

## Lokální spuštění

```bash
python scripts/scrape.py        # vygeneruje data/restaurants.json
python -m http.server 8000      # http://localhost:8000
```

## Data & atribuce

- Polední menu: **[Menicka.cz](https://www.menicka.cz)** (zdroj dat).
- Mapové dlaždice: © OpenStreetMap, © CARTO.
- Geokódování míst: Nominatim / OpenStreetMap.

Projekt je osobní/nekomerční. Menu jsou orientační – závazné je vždy menu přímo v restauraci.

---
Součást [tomaskalivoda.cz](https://tomaskalivoda.cz). Údržba: automatická (GitHub Actions).
