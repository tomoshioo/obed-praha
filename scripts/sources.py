#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adaptéry pro stahování poledního menu z různých zdrojů (kromě menicka.cz).

- choiceqr.com  – platforma (Next.js), menu v __NEXT_DATA__, ceny v setinách (÷100)
- generic       – best-effort: najdi stránku s denním menu + zkus vytáhnout dnešní jídla;
                  když nejde rozparsovat, vrať aspoň URL menu (pro odkaz / link_only)

Pouze Python stdlib (kvůli GitHub Actions).
"""
import urllib.request
import re
import json
import ssl
from urllib.parse import urljoin
from datetime import datetime

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

CZ_DAYS = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]


def fetch(url, timeout=25):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=_CTX).read()
        for enc in ("utf-8", "windows-1250"):
            try:
                return raw.decode(enc)
            except Exception:
                pass
        return raw.decode("utf-8", "replace")
    except Exception:
        return None


def _clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


# ---------------- choiceqr ----------------
_MODIFIER = re.compile(r"(pol[ée]vk|^s\s+poledn|^bez\s+poledn|nápoj|^příloh|extra\s)", re.I)


_LUNCH_SEC = re.compile(r"poledn|ob[ěe]dov|denn[íi]\s*menu|lunch|menu\s*dne", re.I)


def _cq_item(it):
    nm = it.get("name")
    p = it.get("price")
    if isinstance(nm, str) and isinstance(p, (int, float)) and p >= 1000 and it.get("available") is not False:
        nm = nm.strip()
        if not _MODIFIER.search(nm):
            return {"text": nm, "price": f"{int(round(p / 100))} Kč"}
    return None


def scrape_choiceqr(url):
    """Vrátí list [{text, price}] poledního menu z choiceqr, nebo None (= nemá denní menu → odkaz)."""
    h = fetch(url)
    if not h:
        return None
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        return None
    try:
        app = json.loads(m.group(1)).get("props", {}).get("app", {})
    except Exception:
        return None
    menu = app.get("menu") or []
    sections = app.get("sections") or []
    lunch_ids = {s.get("_id") for s in sections if _LUNCH_SEC.search(s.get("name") or "")}

    def collect(filt):
        out, seen = [], set()
        for it in menu:
            if filt and it.get("section") not in lunch_ids:
                continue
            r = _cq_item(it)
            if r and r["text"] not in seen:
                seen.add(r["text"])
                out.append(r)
        return out

    if lunch_ids:                       # má sekci „Polední menu"
        return collect(True) or None
    allit = collect(False)
    if len(allit) <= 10:                # malý lístek = celý je polední nabídka
        return allit or None
    return None                         # velký à-la-carte bez denní sekce → odkaz


_CQ_BAD = re.compile(r"(cdn|client|booking|embed|static|media|asset|widget|^api$|^img$|^www$|^app$)", re.I)


def find_choiceqr(base, html):
    """Vrátí choiceqr URL restaurace (subdoména-restaurace.choiceqr.com), ne infra/CDN. Jinak None."""
    if base:
        mb = re.match(r"https?://([\w-]+)\.choiceqr\.com", base)
        if mb and not _CQ_BAD.search(mb.group(1)):
            return f"https://{mb.group(1)}.choiceqr.com/section:poledni-menu"
    for sub in re.findall(r"https?://([\w-]+)\.choiceqr\.com", html or ""):
        if not _CQ_BAD.search(sub):
            return f"https://{sub}.choiceqr.com/section:poledni-menu"
    return None


# ---------------- generic web ----------------
_MENU_LINK = re.compile(r"(denni-?menu|poledni-?menu|denni-?nabidka|poledni-?nabidka|"
                        r"obedove-?menu|denninabidka|jidelni-?listek|/lunch|/obed)", re.I)
_PRICE = re.compile(r"(\d{2,3})\s*(?:,-|,–|\s?Kč|\s?kc)", re.I)


def find_menu_url(base, html):
    cands = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', html):
        if _MENU_LINK.search(href) and not re.search(r"\.(webp|jpg|png|pdf|css|js)$", href, re.I):
            cands.append(urljoin(base, href))
    # preferuj poledni/denni-menu pred obecnym menu
    cands.sort(key=lambda u: (0 if re.search(r"poledn|denni", u, re.I) else 1, len(u)))
    return cands[0] if cands else None


def _today_present(text):
    d = datetime.now()
    wd = CZ_DAYS[d.weekday()]
    pats = [wd, f"{d.day}.{d.month}.", f"{d.day}. {d.month}.", f"{d.day}.\\s?{d.month}\\."]
    low = text.lower()
    return any(re.search(p, low) for p in pats)


def extract_dishes(html):
    """Best-effort: jídla + ceny z HTML. Vrátí list nebo []."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    # rozbij na řádky podle blokových tagů
    rows = re.split(r"</(?:li|p|tr|div|h\d|td)>", text)
    out = []
    for r in rows:
        line = _clean(r)
        if not line or len(line) < 6:
            continue
        pm = _PRICE.search(line)
        if not pm:
            continue
        name = _clean(line[:pm.start()])
        name = re.sub(r"^\d+[\).]\s*", "", name)  # poradi
        if 5 <= len(name) <= 90 and not re.search(r"@|www\.|http", name):
            out.append({"text": name, "price": pm.group(1) + " Kč"})
    # dedup
    seen, ded = set(), []
    for it in out:
        k = it["text"].lower()
        if k not in seen:
            seen.add(k)
            ded.append(it)
    return ded[:12]


def scrape_generic(website):
    """Vrátí (menu_list_or_None, menu_url_or_None, status).
    status: 'scraped' | 'link' | 'none'"""
    h = fetch(website)
    if not h:
        return None, None, "none"
    menu_url = find_menu_url(website, h)
    target = menu_url or website
    mh = h if target == website else (fetch(target) or h)
    dishes = extract_dishes(mh)
    if dishes and _today_present(mh):
        return dishes, target, "scraped"
    if menu_url:
        return None, menu_url, "link"
    # homepage sama vypadá jako menu?
    if dishes and _today_present(mh):
        return dishes, website, "scraped"
    return None, None, "none"


if __name__ == "__main__":
    import sys
    tests = sys.argv[1:] or [
        "https://chilliandlime.choiceqr.com/section:poledni-menu",
        "https://letsmeat.choiceqr.com/section:poledni-menu",
        "https://modryzub.choiceqr.com/",
    ]
    for u in tests:
        if "choiceqr" in u:
            r = scrape_choiceqr(u)
            print(f"\n[choiceqr] {u}\n  -> {len(r) if r else 0} jídel")
            for it in (r or [])[:8]:
                print("   ", it["text"][:50], "|", it["price"])
        else:
            d, mu, st = scrape_generic(u)
            print(f"\n[generic] {u}\n  -> status={st} url={mu} jídel={len(d) if d else 0}")
            for it in (d or [])[:6]:
                print("   ", it["text"][:50], "|", it["price"])
