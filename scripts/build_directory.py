#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Postaví kompletní adresář VŠECH restaurací v pilotní zóně (Vinohrady/Žižkov):
- vstup: data/research/candidates.json (OSM zóna + menicka match) + data/overrides.json
- pro každou restauraci vyřeší: správný web (override > OSM-živý > slug-guess),
  URL poledního menu, platformu (menicka / choiceqr / generic-link / web / none)
- výstup: data/directory.json  (kurátorovaný, commitne se; menu se pak stahuje denně)
"""
import os, sys, json, re, unicodedata
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import fetch, find_choiceqr, find_menu_url  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
RES = os.path.join(DATA, "research")
LUNCH = {"restaurant", "pub", "fast_food", "food_court"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " ").replace(" and ", " ")
    return re.sub(r"[^a-z0-9]+", "", s)


def slug_urls(name):
    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"\b(restaurace|restaurant|pizzerie|pizzeria|cafe|kavarna|bar|pub|bistro|hostinec)\b", "", base)
    s1 = re.sub(r"[^a-z0-9]+", "", base)
    s2 = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    out = []
    for s in [s1, s2]:
        if 3 <= len(s) <= 30:
            out += [f"https://{s}.cz", f"https://www.{s}.cz", f"https://{s}.com"]
    seen, ded = set(), []
    for u in out:
        if u not in seen:
            seen.add(u); ded.append(u)
    return ded[:4]


def name_present(html, name):
    n = norm(name)[:10]
    return bool(n) and n in norm(re.sub(r"<[^>]+>", " ", html or ""))[:30000]


_PARKED = re.compile(
    r"(dom[ée]na?[^<]{0,30}na prodej|this domain (is )?for sale|buy this domain|"
    r"koupit dom[ée]nu|je na prodej|sedoparking|domain[- ]?parking|parkov[aá]n[oa]|"
    r"forsale|domain for sale|w[eé]b[^<]{0,20}p[řr]ipravujeme)", re.I)


def is_parked(html):
    if not html or len(html) < 400:
        return True
    return bool(_PARKED.search(html[:6000]))


_FOOD = re.compile(
    r"(restaurac|menu|j[íi]deln|kuchyn|poledn|ob[ěe]d|pizza|rezervac|restaurant|"
    r"lunch|kitchen|n[áa]poj|pivo|bistro|k[áa]v[ae]|jídl|burger|sushi|ku[řr]e)", re.I)


def looks_restaurant(html):
    return bool(_FOOD.search(re.sub(r"<[^>]+>", " ", html or "")[:9000]))


def resolve(r, overrides):
    name = r["name"]
    ov = overrides.get(norm(name))
    website = (ov or {}).get("website") or r.get("website")
    menu_url = (ov or {}).get("menu_url")
    platform = (ov or {}).get("platform")
    if platform and menu_url:
        return {"website": website, "menu_url": menu_url, "platform": platform, "resolved_by": "override"}

    html = fetch(website) if website else None
    by = "osm" if html else None
    if html and is_parked(html):            # OSM web parkovaný / mrtvý → zahodit
        html, website, by = None, None, None
    if not html:                            # slug-guess s přísnou validací
        for g in slug_urls(name):
            h = fetch(g)
            if h and not is_parked(h) and name_present(h, name) and looks_restaurant(h):
                website, html, by = g, h, "slug-guess"
                break

    if not html:
        return {"website": website, "menu_url": None, "platform": "none", "resolved_by": by}

    cq = find_choiceqr(website, html)
    if cq:
        return {"website": website, "menu_url": cq, "platform": "choiceqr", "resolved_by": by}
    mu = find_menu_url(website, html)
    if mu:
        return {"website": website, "menu_url": mu, "platform": "generic", "resolved_by": by}
    return {"website": website, "menu_url": website, "platform": "web", "resolved_by": by}


def main():
    cands = json.load(open(os.path.join(RES, "candidates.json"), encoding="utf-8"))["candidates"]
    overrides = {norm(k): v for k, v in json.load(open(os.path.join(DATA, "overrides.json"), encoding="utf-8")).items() if not k.startswith("_")}
    zone = [c for c in cands if c.get("lat") and c["amenity"] in LUNCH]
    print(f"zóna lunch-type: {len(zone)} restaurací, řeším weby…")

    def work(c):
        res = resolve(c, overrides)
        return {
            "name": c["name"], "lat": c["lat"], "lng": c["lng"], "amenity": c["amenity"],
            "d_kancelar": c["d_kancelar"], "d_byt": c["d_byt"],
            "on_menicka": bool(c.get("menicka_url")), "menicka_url": c.get("menicka_url"),
            "website": res["website"], "menu_url": res["menu_url"],
            "platform": "menicka" if c.get("menicka_url") else res["platform"],
            "resolved_by": res["resolved_by"],
        }

    out = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        out = list(ex.map(work, zone))

    json.dump({"zone": "Vinohrady/Zizkov", "count": len(out), "restaurants": out},
              open(os.path.join(DATA, "directory.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("platform rozpad:", dict(Counter(o["platform"] for o in out)))
    print("resolved_by:", dict(Counter(o["resolved_by"] for o in out)))
    print(f"menu_url k dispozici: {sum(1 for o in out if o['menu_url'])}/{len(out)}")
    print("\nukázka choiceqr:")
    for o in out:
        if o["platform"] == "choiceqr":
            print(f"   {o['name'][:26]:26} {o['menu_url']}")


if __name__ == "__main__":
    main()
