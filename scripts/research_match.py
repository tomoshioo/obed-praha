#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spoji OSM discovery (data/research/discover.json) s menicka.cz daty pro pilotni
zonu (Vinohrady/Zizkov), spocita vzdalenosti ke kotvam a oznaci prekryv.
Vystup: data/research/candidates.json + tisk statistik a pilot setu."""
import json, re, os, math, unicodedata, urllib.request, time
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "data", "research")
PLACES = os.path.join(HERE, "..", "data", "places.json")
UA = {"User-Agent": "ObedPrahaResearch/1.0 (tomaskalivoda.cz)"}
BASE = "https://www.menicka.cz"

ANCHORS = {"kancelar": (50.0839647, 14.4559908), "byt": (50.0791467, 14.4460314)}
BBOX = (50.0751, 14.4400, 50.0880, 14.4620)  # S,W,N,E


def hav(a, b):
    R = 6371000
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return int(2*R*math.asin(math.sqrt(d)))


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(restaurace|restaurant|pizzerie|pizzeria|cafe|kavarna|bar|pub|bistro|hostinec|praha)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def fetch(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode("windows-1250", "replace")
    except Exception as e:
        print("  fetch fail", url, e); return ""


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).replace("&nbsp;", " ").strip()


def parse_menicka(html, district):
    out = {}
    for b in re.split(r"<div class='menicka_detail'>", html)[1:]:
        rid = re.search(r"menicka\.cz/(\d+)-([^.'\"/]+)\.html", b)
        if not rid:
            continue
        nm = re.search(r"class='nazev'>\s*<a[^>]*>(.*?)</a>", b, re.S)
        mc = re.search(r"<div class='menicka'>(.*?)(?=<div class='menicka_detail'>|$)", b, re.S)
        scope = mc.group(1) if mc else b
        items = []
        for mm in re.finditer(r"class='(nabidka_\d)[^']*'>(.*?)</div>\s*<div class='cena'>(.*?)</div>", scope, re.S):
            t = clean(mm.group(2)); p = clean(mm.group(3))
            if t:
                items.append({"text": t, "price": p or None})
        out[rid.group(1)] = {"id": rid.group(1), "slug": rid.group(2),
                             "name": clean(nm.group(1)) if nm else rid.group(2),
                             "menu": items, "url": f"{BASE}/{rid.group(1)}-{rid.group(2)}.html",
                             "district": district}
    return out


def main():
    disc = json.load(open(os.path.join(RES, "discover.json"), encoding="utf-8"))
    osm = disc["restaurants"]
    places = json.load(open(PLACES, encoding="utf-8")) if os.path.exists(PLACES) else {}

    # menicka dnes pro P2+P3
    men = {}
    for d in ["praha-2", "praha-3"]:
        men.update(parse_menicka(fetch(f"{BASE}/{d}.html"), d))
        time.sleep(0.3)
    # pripoj souradnice z places cache
    for mid, m in men.items():
        p = places.get(mid)
        m["lat"], m["lng"] = (p["lat"], p["lng"]) if p else (None, None)
    print(f"menicka P2+P3 dnes: {len(men)} restauraci s dnesnim menu")

    def best_menicka(name, lat, lng):
        bn = norm(name); best = None; bs = 0
        for m in men.values():
            r = SequenceMatcher(None, bn, norm(m["name"])).ratio()
            close = (lat and m["lat"] and hav((lat, lng), (m["lat"], m["lng"])) < 180)
            if r > bs and (r > 0.86 or close):
                bs = r; best = m
        return (best, round(bs, 2)) if bs >= 0.72 else (None, round(bs, 2))

    cands = []
    LUNCH = {"restaurant", "pub", "fast_food", "food_court"}
    for oid, r in osm.items():
        if not r.get("lat"):
            continue
        m, score = best_menicka(r["name"], r["lat"], r["lng"])
        cands.append({
            "osm_id": oid, "name": r["name"], "lat": r["lat"], "lng": r["lng"],
            "amenity": r["amenity"], "website": r["website"], "fb": r.get("fb"),
            "opening_hours": r["opening_hours"], "cuisine": r["cuisine"],
            "lunch_type": r["amenity"] in LUNCH,
            "d_kancelar": hav((r["lat"], r["lng"]), ANCHORS["kancelar"]),
            "d_byt": hav((r["lat"], r["lng"]), ANCHORS["byt"]),
            "menicka_url": m["url"] if m else None,
            "menicka_name": m["name"] if m else None,
            "menicka_menu": m["menu"] if m else None,
            "match_score": score,
        })
    for c in cands:
        c["d_min"] = min(c["d_kancelar"], c["d_byt"])
    cands.sort(key=lambda c: c["d_min"])
    json.dump({"anchors": ANCHORS, "candidates": cands, "menicka_zone": list(men.values())},
              open(os.path.join(RES, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    lunch = [c for c in cands if c["lunch_type"]]
    on_men = [c for c in lunch if c["menicka_url"]]
    web_only = [c for c in lunch if c["website"] and not c["menicka_url"]]
    both = [c for c in lunch if c["website"] and c["menicka_url"]]
    print(f"\n=== PILOT ZONA (lunch-type: restaurant/pub/fast_food) ===")
    print(f"celkem lunch-type: {len(lunch)}")
    print(f"  na menicka (dnes menu): {len(on_men)}")
    print(f"  s vlastnim webem:       {sum(1 for c in lunch if c['website'])}")
    print(f"  na OBOU (web+menicka) = validacni pary: {len(both)}")
    print(f"  jen web (coverage gain, NEjsou na menicka): {len(web_only)}")
    print(f"\n--- 25 nejblizsich lunch podniku ke kotvam ---")
    for c in lunch[:25]:
        tag = "MEN+WEB" if (c["website"] and c["menicka_url"]) else ("MENICKA" if c["menicka_url"] else ("WEB" if c["website"] else "-"))
        print(f"  {c['d_min']:4}m {tag:8} {c['name'][:30]:30} {(c['website'] or '')[:38]}")


if __name__ == "__main__":
    main()
