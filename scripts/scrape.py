#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper polednich menu z menicka.cz pro Prahu (mestske casti 1-10).

- Stahne listing stranky praha-1..praha-10 -> dnesni menu kazde restaurace.
- Pro restaurace bez ulozenych souradnic stahne detail stranku -> GPS + adresa.
  Souradnice se cachuji do data/places.json (stahuji se jen jednou per restaurace).
- Vystup: data/restaurants.json (menu + souradnice) = jediny soubor, ktery cte frontend.

Zavislosti: pouze Python stdlib (kvuli GitHub Actions bez pip installu).
Spusteni: python scripts/scrape.py
"""
import urllib.request
import re
import json
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

BASE = "https://www.menicka.cz"
DISTRICTS = [f"praha-{i}" for i in range(1, 11)]
UA = "Mozilla/5.0 (compatible; ObedPrahaBot/1.0; +https://obed.tomaskalivoda.cz)"

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))

CZ_DAYS = ["pondeli", "utery", "streda", "ctvrtek", "patek", "sobota", "nedele"]
CZ_DAYS_DIA = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]


def fetch(url, tries=3):
    """Stahne URL a dekoduje z windows-1250. Vrati str nebo None."""
    for t in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Language": "cs"}
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("windows-1250", "replace")
        except Exception as e:  # noqa: BLE001
            if t == tries - 1:
                sys.stderr.write(f"  ! fetch fail {url}: {e}\n")
                return None
            time.sleep(1.0 * (t + 1))
    return None


def clean(s):
    """Odstrani HTML tagy, sjednoti bile znaky."""
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_addr(s):
    if not s:
        return None
    s = clean(s)
    s = re.sub(r"\s+,", ",", s)        # mezera pred carkou
    s = re.sub(r",\s*,", ",", s)       # prazdne casti
    s = re.sub(r"\s{2,}", " ", s)
    # PSC "11000" -> "110 00"
    s = re.sub(r"\b(\d{3})(\d{2})\b", r"\1 \2", s)
    return s.strip(" ,")


def parse_listing(html, district):
    """Z listing stranky vytahne restaurace + dnesni menu."""
    out = []
    blocks = re.split(r"<div class='menicka_detail'>", html)[1:]
    for b in blocks:
        rid = re.search(r"menicka\.cz/(\d+)-([^.'\"/]+)\.html", b)
        if not rid:
            continue
        nm = re.search(r"class='nazev'>\s*<a[^>]*>(.*?)</a>", b, re.S)
        # menu items jen z kontejneru .menicka (ne z hlavicky)
        mc = re.search(r"<div class='menicka'>(.*?)(?=<div class='menicka_detail'>|$)", b, re.S)
        scope = mc.group(1) if mc else b
        items = []
        for mm in re.finditer(
            r"class='(nabidka_\d)[^']*'>(.*?)</div>\s*<div class='cena'>(.*?)</div>",
            scope, re.S
        ):
            text = clean(mm.group(2))
            price = clean(mm.group(3))
            if not text:
                continue
            items.append({
                "text": text,
                "price": price or None,
                "kind": "soup" if mm.group(1) == "nabidka_1" else "main",
            })
        out.append({
            "id": rid.group(1),
            "slug": rid.group(2),
            "name": clean(nm.group(1)) if nm else rid.group(2),
            "district": district,
            "menu": items,
        })
    return out


def parse_detail(html):
    """Z detail stranky vytahne GPS + adresu."""
    if not html:
        return None
    c = re.search(r"LatLng\(\s*(5[01]\.\d{3,})\s*,\s*(1[345]\.\d{3,})", html)
    if not c:
        c = re.search(r"(5[01]\.\d{4,})\s*,\s*(1[345]\.\d{4,})", html)
    if not c:
        return None
    lat, lng = float(c.group(1)), float(c.group(2))
    # sanity: Praha bbox
    if not (49.9 < lat < 50.25 and 14.15 < lng < 14.8):
        return None
    a = re.search(r"class='adresa'>(?:<a[^>]*>)?(.*?)</a>", html, re.S)
    return {"lat": lat, "lng": lng, "address": norm_addr(a.group(1)) if a else None}


def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return default
    return default


def main():
    os.makedirs(DATA, exist_ok=True)
    places_path = os.path.join(DATA, "places.json")
    places = load_json(places_path, {})

    all_rest = []
    menu_date = None
    for d in DISTRICTS:
        html = fetch(f"{BASE}/{d}.html")
        if not html:
            continue
        if menu_date is None:
            md = re.search(r"class='date'>(.*?)<", html)
            if md:
                menu_date = clean(md.group(1))
        recs = parse_listing(html, d)
        all_rest += recs
        print(f"  {d}: {len(recs)} restauraci")
        time.sleep(0.3)

    # restaurace bez ulozenych souradnic -> dostahnout detail
    missing = [r for r in all_rest if r["id"] not in places]
    print(f"  seeding souradnic: {len(missing)} novych restauraci (detail stranky)")

    def seed(r):
        time.sleep(0.2)
        det = parse_detail(fetch(f"{BASE}/{r['id']}-{r['slug']}.html"))
        return r["id"], det

    if missing:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for rid, det in ex.map(seed, missing):
                if det:
                    places[rid] = det
        json.dump(places, open(places_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)

    # sestav restaurants.json (jen ty s menu i souradnicemi)
    feats = []
    seen = set()
    for r in all_rest:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        p = places.get(r["id"])
        if not p or not r["menu"]:
            continue
        feats.append({
            "id": r["id"],
            "name": r["name"],
            "district": r["district"],
            "address": p.get("address"),
            "lat": p["lat"],
            "lng": p["lng"],
            "url": f"{BASE}/{r['id']}-{r['slug']}.html",
            "menu": r["menu"],
        })

    if menu_date is None:
        now_local = datetime.now()
        menu_date = f"{CZ_DAYS_DIA[now_local.weekday()]} {now_local.day}. {now_local.month}. {now_local.year}"

    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "menu_date": menu_date,
        "count": len(feats),
        "restaurants": feats,
    }
    out_path = os.path.join(DATA, "restaurants.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"HOTOVO: {len(all_rest)} restauraci parsovano, "
          f"{len(feats)} s menu+souradnicemi -> {out_path}")
    print(f"        places cache: {len(places)} restauraci, menu_date='{menu_date}'")


if __name__ == "__main__":
    main()
