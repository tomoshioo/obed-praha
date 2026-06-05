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

## Zdroje a metody scrapingu (`scripts/sources.py`)

Restaurace v zóně (Vinohrady/Žižkov) jsou objevené přes OSM (`build_directory.py`). Menu se získává v tomto pořadí:

1. **menicka.cz** – primární, strukturované, denně (Praha 1–10).
2. **choiceqr.com** – platforma; menu z `__NEXT_DATA__` JSON, sekce „polední menu", ceny ÷100.
3. **kurátorovaná vrstva** `data/extra.json` – ručně/agenty ověřená menu (date-guard).
4. **LLM extraktor** (volitelný) – pro heterogenní weby; vytáhne dnešní menu z textu stránky.
5. **odkaz** – když menu nestáhneme, karta dá tlačítko na web restaurace; bez webu odkaz na Google.

Stavy v UI: `scraped` (barva dle ceny) / `link` (modrá, odkaz na menu) / `none` (šedá, hledání na Googlu).
Ruční opravy URL menu: `data/overrides.json`.

### Zapnutí LLM extrakce (zvýší účinnost dlouhého ocasu)

Bez klíče běží menicka + choiceqr. S OpenAI-compatible klíčem se denně stahuje i zbytek:
v repo **Settings → Secrets and variables → Actions** přidej:

- `OBED_LLM_KEY` – API klíč (např. free [Groq](https://console.groq.com), nebo vlastní endpoint).
- `OBED_LLM_URL` – (volitelně) chat endpoint, default Groq.
- `OBED_LLM_MODEL` – (volitelně) model, default `llama-3.3-70b-versatile`.

## Aktualizace

GitHub Action **`refresh.yml` běží každý den v ~10:00** (08:00 UTC) + ručně přes „Run workflow".

## Data & atribuce

- Polední menu: **[Menicka.cz](https://www.menicka.cz)**, **choiceqr.com**, weby restaurací.
- Objevování restaurací: **OpenStreetMap / Overpass**. Dlaždice © OpenStreetMap, © CARTO. Geokódování: Nominatim.

Projekt je osobní/nekomerční. Menu jsou orientační – závazné je vždy menu přímo v restauraci.

---
Součást [tomaskalivoda.cz](https://tomaskalivoda.cz). Údržba: automatická (GitHub Actions).
