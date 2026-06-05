#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Složí výsledky agentní extrakce (data/research/results_link/*.json) do data/extra.json.
Pro každou restauraci s nalezeným dnešním menu vytvoří/aktualizuje záznam v kurátorované vrstvě."""
import json, os, re, glob, unicodedata
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
RES = os.path.join(DATA, "research")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " ").replace(" and ", " ")
    return re.sub(r"[^a-z0-9]+", "", s)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "web-" + re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    directory = {norm(d["name"]): d for d in json.load(open(os.path.join(DATA, "directory.json"), encoding="utf-8"))["restaurants"]}
    extra = json.load(open(os.path.join(DATA, "extra.json"), encoding="utf-8"))
    by = {norm(e["name"]): e for e in extra["restaurants"]}

    results = []
    for f in glob.glob(os.path.join(RES, "results_link", "batch_*.json")):
        try:
            results += json.load(open(f, encoding="utf-8"))
        except Exception as ex:  # noqa: BLE001
            print("skip", f, ex)

    added = updated = 0
    for r in results:
        if not r.get("found") or not r.get("menu"):
            continue
        menu = [{"text": (m.get("text") or "").strip(), "price": (m.get("price") or None)}
                for m in r["menu"] if (m.get("text") or "").strip()]
        if not menu:
            continue
        nk = norm(r["name"])
        d = directory.get(nk, {})
        entry = {
            "id": slug(r["name"]), "name": r["name"],
            "lat": d.get("lat"), "lng": d.get("lng"), "amenity": d.get("amenity"),
            "source": "web", "website": d.get("website"),
            "source_url": r.get("source_url") or d.get("menu_url") or d.get("website"),
            "menu": menu, "time_from": r.get("time_from"), "time_to": r.get("time_to"),
            "menu_date": today, "web_confirmed": True,
            "on_menicka": bool(d.get("on_menicka")), "menicka_url": d.get("menicka_url"),
        }
        if entry["lat"] is None:
            continue
        if nk in by:
            by[nk].update(entry); updated += 1
        else:
            by[nk] = entry; added += 1

    extra["restaurants"] = list(by.values())
    extra["generated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(extra, open(os.path.join(DATA, "extra.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"extra.json: +{added} nových, {updated} aktualizováno, celkem {len(by)} (s menu z webů)")


if __name__ == "__main__":
    main()
