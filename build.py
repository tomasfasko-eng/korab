#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Koráb — generátor webové prezentace tras.

Přečte GPX soubory (z mapy.com) ve složce projektu, spočítá statistiky
a vygeneruje statický web (složka ``site/``) s přehledem tras a detailem
každé z nich. Web je samostatný (HTML + CSS + JS), takže jde rovnou nahrát
na PythonAnywhere jako statické soubory.

Spuštění:
    python3 build.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt

# --- Konfigurace -----------------------------------------------------------

ZAKLAD = os.path.dirname(os.path.abspath(__file__))
VYSTUP = os.path.join(ZAKLAD, "site")
GPX_NS = {"g": "http://www.topografix.com/GPX/1/1"}

# Vrchol Korábu (GPS z Wikipedie) — společný cíl všech okruhů.
KORAB_LAT = 49.39542
KORAB_LON = 13.07524
KORAB_VRCHOL_M = 772

# Definice tras: soubor -> metadata. Pořadí = pořadí na úvodní stránce.
TRASY_DEF = [
    {
        "soubor": "Malý okruh.gpx",
        "slug": "maly",
        "nazev": "Malý okruh",
        "barva": "#2e9e5b",
        "popis": "Krátká vycházka v okolí vrcholu — ideální na rychlé "
                 "protažení nebo s dětmi. Start i cíl přímo u rozhledny.",
        "fotky": [
            {"soubor": "maly-korab.jpg", "popisek": "Rozhledna Koráb",
             "autor": "Stanislav Dusík", "licence": "CC BY-SA 4.0"},
            {"soubor": "maly-kaple.jpg",
             "popisek": "Kaple bl. Karla Rakouského",
             "autor": "RomanM82", "licence": "CC BY-SA 4.0"},
            {"soubor": "maly-modlin.jpg", "popisek": "Modlín",
             "autor": "Hvezdar71", "licence": "CC BY 3.0"},
        ],
    },
    {
        "soubor": "Střední okruh.gpx",
        "slug": "stredni",
        "nazev": "Střední okruh",
        "barva": "#2f7fd6",
        "popis": "Vyvážená půldenní trasa lesy Chudenické vrchoviny "
                 "s návratem k rozhledně a chatě Koráb.",
        "fotky": [
            {"soubor": "stredni-korab.jpg", "popisek": "Rozhledna Koráb",
             "autor": "Stanislav Dusík", "licence": "CC BY-SA 4.0"},
            {"soubor": "stredni-modlin.jpg", "popisek": "Modlín",
             "autor": "Hvezdar71", "licence": "CC BY 3.0"},
            {"soubor": "stredni-herstejn.jpg", "popisek": "Hrad Nový Herštejn",
             "autor": "Jik jik", "licence": "CC BY-SA 3.0"},
            {"soubor": "stredni-mezholezy.jpg", "popisek": "Mezholezy",
             "autor": "StanislavNedele18", "licence": "CC BY-SA 4.0"},
        ],
    },
    {
        "soubor": "Velký okruh.gpx",
        "slug": "velky",
        "nazev": "Velký okruh",
        "barva": "#d6332f",
        "popis": "Celodenní okruh pro zdatnější turisty — delší hřebenové "
                 "úseky a větší převýšení.",
        "fotky": [
            {"soubor": "velky-herstejn.jpg", "popisek": "Nový Herštejn",
             "autor": "Jik jik", "licence": "CC BY-SA 3.0"},
            {"soubor": "velky-loucim.jpg", "popisek": "Židovský hřbitov u Loučim",
             "autor": "Hvezdar71", "licence": "CC BY 3.0"},
            {"soubor": "velky-ryzmberk.jpg", "popisek": "Hrad Rýzmberk",
             "autor": "Stanislav Dusík", "licence": "CC BY-SA 4.0"},
        ],
    },
    {
        "soubor": "Expedicni okruh.gpx",
        "slug": "expedicni",
        "nazev": "Expediční okruh",
        "barva": "#1f1f1f",
        "popis": "Náročná expedice až k Čerchovu (nejvyšší vrchol Českého "
                 "lesa, 1042 m) a zpět na Koráb. Pro vytrvalce na celý den.",
        "fotky": [
            {"soubor": "expedicni-cerchov.jpg", "popisek": "Čerchov (1042 m)",
             "autor": "Jan Macura", "licence": "CC BY-SA 4.0"},
            {"soubor": "expedicni-kurzova.jpg", "popisek": "Kurzova věž",
             "autor": "Wikimedia Commons", "licence": "CC0"},
            {"soubor": "expedicni-hohenbogen.jpg", "popisek": "Hohenbogen – věže",
             "autor": "Rosa-Maria Rinkl", "licence": "CC BY-SA 4.0"},
            {"soubor": "expedicni-schonblick.jpg", "popisek": "Chata Schönblick",
             "autor": "Stoisuacha", "licence": "CC BY-SA 3.0"},
            {"soubor": "expedicni-medvedi.jpg", "popisek": "Medvědí kaple",
             "autor": "Krabat77", "licence": "CC BY-SA 3.0"},
        ],
    },
]

# Informace o cíli — společná „story" o Korábu (zdroje: Wikipedie, chatakorab.cz).
KORAB_INFO = {
    "vyska_vrchol": "775 m n. m.",
    "vyska_rozhledna": "50 m",
    "plosina": "29 m nad zemí",
    "schodu": 144,
    "rok_puvodni": 1938,
    "rok_soucasna": 1992,
    "vyhled": "Šumava, Český les, Brdy, za jasného počasí i Alpy",
}


# --- Výpočty ---------------------------------------------------------------


@dataclass
class Trasa:
    """Jedna trasa včetně spočítaných statistik a dat pro graf/mapu."""

    slug: str
    nazev: str
    barva: str
    popis: str
    body: list = field(default_factory=list)        # [(lat, lon, ele), ...]
    delka_km: float = 0.0
    nastoupano_m: int = 0
    naklesano_m: int = 0
    ele_min: int = 0
    ele_max: int = 0
    cas_min: int = 0                                 # odhad v minutách
    profil: list = field(default_factory=list)       # [(km, ele), ...]
    obtiznost: str = ""
    fotky: list = field(default_factory=list)        # [{soubor, popisek, autor, licence}]
    mapy_url: str = ""                               # odkaz na trasu v Mapy.cz

    @property
    def stred(self) -> tuple:
        lats = [b[0] for b in self.body]
        lons = [b[1] for b in self.body]
        return (sum(lats) / len(lats), sum(lons) / len(lons))


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Vzdálenost dvou GPS bodů v metrech."""
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def vyhlad_vysky(eles, okno=5):
    """Klouzavý průměr — potlačí šum ve výškách z GPX."""
    if len(eles) < okno:
        return eles[:]
    out = []
    h = okno // 2
    for i in range(len(eles)):
        a = max(0, i - h)
        b = min(len(eles), i + h + 1)
        out.append(sum(eles[a:b]) / (b - a))
    return out


def nacti_trasu(definice) -> Trasa:
    """Načte GPX a spočítá všechny statistiky."""
    cesta = os.path.join(ZAKLAD, definice["soubor"])
    strom = ET.parse(cesta)
    body_xml = strom.findall(".//g:trkpt", GPX_NS)

    body = []
    for p in body_xml:
        lat = float(p.get("lat"))
        lon = float(p.get("lon"))
        ele_el = p.find("g:ele", GPX_NS)
        ele = float(ele_el.text) if ele_el is not None else 0.0
        body.append((lat, lon, ele))

    t = Trasa(
        slug=definice["slug"],
        nazev=definice["nazev"],
        barva=definice["barva"],
        popis=definice["popis"],
        body=body,
        fotky=definice.get("fotky", []),
        mapy_url=definice.get("mapy_url", ""),
    )

    # Kumulativní vzdálenost + profil + převýšení.
    eles = [b[2] for b in body]
    eles_hl = vyhlad_vysky(eles)

    delka = 0.0
    profil = [(0.0, round(eles_hl[0]))]
    nast = 0.0
    nakl = 0.0
    prah = 1.0  # m — práh proti šumu

    for i in range(1, len(body)):
        d = haversine(body[i - 1][0], body[i - 1][1], body[i][0], body[i][1])
        delka += d
        rozdil = eles_hl[i] - eles_hl[i - 1]
        if rozdil > prah:
            nast += rozdil
        elif rozdil < -prah:
            nakl += -rozdil
        # Vzorkujeme profil (ať není zbytečně hustý).
        if i % max(1, len(body) // 300) == 0 or i == len(body) - 1:
            profil.append((round(delka / 1000.0, 2), round(eles_hl[i])))

    t.delka_km = round(delka / 1000.0, 1)
    t.nastoupano_m = int(round(nast))
    t.naklesano_m = int(round(nakl))
    t.ele_min = int(round(min(eles)))
    t.ele_max = int(round(max(eles)))
    t.profil = profil

    # Odhad času — Naismithovo pravidlo: 4,5 km/h + 10 min na 100 m stoupání.
    minuty = (t.delka_km / 4.5) * 60 + (t.nastoupano_m / 100) * 10
    t.cas_min = int(round(minuty))

    # Obtížnost dle délky a převýšení.
    skore = t.delka_km + t.nastoupano_m / 100
    if skore < 8:
        t.obtiznost = "Lehká"
    elif skore < 18:
        t.obtiznost = "Střední"
    elif skore < 60:
        t.obtiznost = "Náročná"
    else:
        t.obtiznost = "Expediční"

    return t


def hex_rgb(h: str) -> tuple:
    """#rrggbb -> (r, g, b)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def cas_text(minuty: int) -> str:
    h, m = divmod(minuty, 60)
    if h and m:
        return f"{h} h {m} min"
    if h:
        return f"{h} h"
    return f"{m} min"


# --- Generování HTML -------------------------------------------------------


def html_hlava(titulek: str, korenova: bool) -> str:
    css = "assets/style.css" if korenova else "assets/style.css"
    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulek}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="{css}">
</head>
<body>
"""


def napis_index(trasy):
    karty = []
    for t in trasy:
        karty.append(f"""
      <a class="karta" href="trasa-{t.slug}.html" style="--barva:{t.barva}">
        <div class="karta-pas"></div>
        <div class="karta-telo">
          <h3>{t.nazev}</h3>
          <p class="karta-popis">{t.popis}</p>
          <ul class="karta-staty">
            <li><span>{t.delka_km}</span> km</li>
            <li><span>{t.nastoupano_m}</span> m ↑</li>
            <li class="obt obt-{t.obtiznost.lower()[:4]}">{t.obtiznost}</li>
          </ul>
        </div>
      </a>""")

    info = KORAB_INFO
    obsah = f"""{html_hlava("Koráb — trasy na vrchol a rozhlednu", True)}
  <header class="hero">
    <div class="hero-obsah">
      <p class="hero-nadtitul">Chudenická vrchovina · {info['vyska_vrchol']}</p>
      <h1>Koráb</h1>
      <p class="hero-podtitul">Hora, rozhledna a horská chata nad Kdyní.<br>
         Čtyři okruhy s cílem na vrcholu — vyber si podle nálady a kondice.</p>
    </div>
  </header>

  <main class="obsah">
    <section class="sekce">
      <h2>Trasy</h2>
      <div class="karty">{''.join(karty)}
      </div>
    </section>

    <section class="sekce story">
      <h2>O Korábu</h2>
      <div class="story-mrizka">
        <div class="story-text">
          <p><strong>Koráb</strong> je nejvyšším vrcholem Chudenické vrchoviny
             ({info['vyska_vrchol']}) a tyčí se nad městem Kdyně na Domažlicku.
             Na vrcholu stojí nezaměnitelná <strong>ocelová rozhledna</strong>
             vysoká {info['vyska_rozhledna']} — plechem opláštěný tubus, uvnitř
             {info['schodu']} schodů na vyhlídkovou plošinu
             ({info['plosina']}).</p>
          <p>Z ochozu je za dobré viditelnosti vidět
             <strong>{info['vyhled']}</strong>. První dřevěná rozhledna tu stála
             od roku {info['rok_puvodni']}, dnešní ocelová ji nahradila
             v roce {info['rok_soucasna']}.</p>
          <p>Pod rozhlednou najdeš <strong>horskou chatu Koráb</strong>
             s restaurací a celoročním ubytováním — od roku 2025 nově
             zrekonstruovanou. Příjemné zázemí na začátku i konci túry.</p>
        </div>
        <ul class="story-fakta">
          <li><span class="fakt-cislo">{info['vyska_vrchol']}</span> nadmořská výška</li>
          <li><span class="fakt-cislo">{info['vyska_rozhledna']}</span> výška rozhledny</li>
          <li><span class="fakt-cislo">{info['schodu']}</span> schodů na ochoz</li>
          <li><span class="fakt-cislo">{info['rok_puvodni']}</span> první rozhledna</li>
        </ul>
      </div>
    </section>
  </main>

  <footer class="pata">
    <p>Trasy z <a href="https://mapy.com" target="_blank" rel="noopener">Mapy.cz</a>
       · Mapové podklady © OpenStreetMap přispěvatelé · Projekt Koráb 🚢</p>
  </footer>
</body>
</html>"""
    with open(os.path.join(VYSTUP, "index.html"), "w", encoding="utf-8") as f:
        f.write(obsah)


def napis_detail(t, trasy):
    # Data pro mapu a graf vložíme přímo do stránky (žádný server netřeba).
    coords = [[round(b[0], 6), round(b[1], 6)] for b in t.body]
    data = {
        "nazev": t.nazev,
        "barva": t.barva,
        "coords": coords,
        "profil": t.profil,
        "korab": [KORAB_LAT, KORAB_LON],
    }
    data_json = json.dumps(data, ensure_ascii=False)

    # QR karta Mapy.cz (hotový obrázek qr/<slug>.png).
    qr_img = os.path.join(ZAKLAD, "qr", t.slug + ".png")
    qr_karty = ""
    if os.path.isfile(qr_img):
        qr_karty += f"""
        <figure class="qr-karta">
          <div class="qr"><img src="assets/qr/{t.slug}.png" alt="QR Mapy.cz"></div>
          <figcaption><strong>Mapy.cz</strong><span>otevři trasu</span></figcaption>
        </figure>"""

    # Odkazy na ostatní trasy.
    ostatni = []
    for o in trasy:
        aktiv = " aktivni" if o.slug == t.slug else ""
        ostatni.append(
            f'<a class="prepinac{aktiv}" href="trasa-{o.slug}.html" '
            f'style="--barva:{o.barva}">{o.nazev}</a>'
        )

    # Banner: pokud má trasa fotky, dáme první jako pozadí hlavičky
    # a pod ní pásek náhledů ostatních míst.
    if t.fotky:
        r, g, b = hex_rgb(t.barva)
        hero = t.fotky[0]["soubor"]
        hlava_styl = (
            f"--barva:{t.barva};"
            f"background-image:linear-gradient(150deg,"
            f"rgba({r},{g},{b},.86) 0%,rgba({r},{g},{b},.55) 100%),"
            f"url('assets/foto/{hero}');"
        )
        hlava_trida = "detail-hlava detail-hlava--foto"

        karty = []
        for foto in t.fotky:
            karty.append(f"""
        <figure class="foto-karta">
          <img src="assets/foto/{foto['soubor']}" alt="{foto['popisek']}" loading="lazy">
          <figcaption>{foto['popisek']}</figcaption>
        </figure>""")
        kredity = " · ".join(
            f"{foto['popisek']}: {foto['autor']} ({foto['licence']})"
            for foto in t.fotky
        )
        fotostrip = f"""
  <section class="fotostrip">
    <div class="fotostrip-vnitrek">{''.join(karty)}
    </div>
    <p class="fotokredit">Foto © {kredity} — via Wikimedia Commons</p>
  </section>"""
    else:
        hlava_styl = f"--barva:{t.barva}"
        hlava_trida = "detail-hlava"
        fotostrip = ""

    obsah = f"""{html_hlava(f"{t.nazev} — Koráb", False)}
  <header class="{hlava_trida}" style="{hlava_styl}">
    <div class="detail-hlava-obsah">
      <a class="zpet" href="index.html">← Všechny trasy</a>
      <h1>{t.nazev}</h1>
      <p class="detail-popis">{t.popis}</p>
    </div>
  </header>
{fotostrip}
  <nav class="prepinace">{''.join(ostatni)}</nav>

  <main class="detail">
    <section class="staty-pas">
      <div class="stat"><span class="stat-cislo">{t.delka_km} km</span><span class="stat-popis">délka</span></div>
      <div class="stat"><span class="stat-cislo">{t.nastoupano_m} m</span><span class="stat-popis">stoupání</span></div>
      <div class="stat"><span class="stat-cislo">{t.ele_max} m</span><span class="stat-popis">max. výška</span></div>
      <div class="stat"><span class="stat-cislo">{t.obtiznost}</span><span class="stat-popis">obtížnost</span></div>
    </section>

    <section class="share-blok" style="--barva:{t.barva}">
      <div class="share-karta">
        <div class="share-text">
          <h2>Vezmi si trasu do mobilu</h2>
          <p>Naskenuj QR kód telefonem 📱</p>
        </div>
        <div class="share-qr">{qr_karty}
        </div>
      </div>
    </section>

    <section class="mapa-blok">
      <div id="mapa"></div>
    </section>

    <section class="profil-blok">
      <h2>Výškový profil</h2>
      <div class="profil-plocha"><canvas id="profil"></canvas></div>
    </section>
  </main>

  <footer class="pata">
    <p>Trasa z <a href="https://mapy.com" target="_blank" rel="noopener">Mapy.cz</a>
       · Mapové podklady © OpenStreetMap přispěvatelé · Projekt Koráb 🚢</p>
  </footer>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script>window.TRASA = {data_json};</script>
  <script src="assets/trasa.js"></script>
</body>
</html>"""
    with open(os.path.join(VYSTUP, f"trasa-{t.slug}.html"), "w", encoding="utf-8") as f:
        f.write(obsah)


# --- Statické assety (CSS + JS) -------------------------------------------

CSS = """
:root{
  --tmava:#1b2a23; --text:#22302a; --seda:#6b7b73; --pozadi:#f4f1ea;
  --bila:#ffffff; --linka:#e3ddd1;
  font-size:16px;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--text);background:var(--pozadi);line-height:1.6;}
a{color:inherit;}
h1,h2,h3{line-height:1.2;font-weight:700;letter-spacing:-0.01em;}

/* HERO */
.hero{background:linear-gradient(160deg,#1b3a2b 0%,#2e5a40 60%,#3f6e4e 100%);
  color:#fff;padding:5rem 1.5rem 4.5rem;text-align:center;position:relative;overflow:hidden;}
.hero::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:80px;
  background:radial-gradient(120% 80px at 50% 100%,var(--pozadi) 0,transparent 70%);}
.hero-obsah{max-width:760px;margin:0 auto;position:relative;z-index:1;}
.hero-nadtitul{text-transform:uppercase;letter-spacing:0.18em;font-size:.82rem;
  opacity:.85;margin-bottom:.6rem;}
.hero h1{font-size:clamp(3rem,9vw,5.5rem);margin-bottom:1rem;}
.hero-podtitul{font-size:1.15rem;opacity:.92;}

.obsah{max-width:1080px;margin:0 auto;padding:0 1.5rem;}
.sekce{padding:3.5rem 0;}
.sekce h2{font-size:1.8rem;margin-bottom:1.6rem;}

/* KARTY */
.karty{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1.4rem;}
.karta{background:var(--bila);border-radius:16px;overflow:hidden;text-decoration:none;
  box-shadow:0 2px 14px rgba(20,40,30,.06);transition:transform .18s ease,box-shadow .18s ease;
  display:flex;flex-direction:column;border:1px solid var(--linka);}
.karta:hover{transform:translateY(-4px);box-shadow:0 10px 28px rgba(20,40,30,.14);}
.karta-pas{height:8px;background:var(--barva);}
.karta-telo{padding:1.4rem;display:flex;flex-direction:column;gap:.7rem;flex:1;}
.karta h3{font-size:1.35rem;}
.karta-popis{color:var(--seda);font-size:.95rem;flex:1;}
.karta-staty{list-style:none;display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;
  border-top:1px solid var(--linka);padding-top:.8rem;font-size:.9rem;color:var(--seda);}
.karta-staty span{font-weight:700;color:var(--text);}
.obt{margin-left:auto;font-weight:600;padding:.2rem .6rem;border-radius:999px;font-size:.8rem;color:#fff;}
.obt-lehk{background:#2e9e5b;}.obt-stre{background:#2f7fd6;}
.obt-naro{background:#e8842b;}.obt-expe{background:#9b3fc4;}

/* STORY */
.story{border-top:1px solid var(--linka);}
.story-mrizka{display:grid;grid-template-columns:1.6fr 1fr;gap:2.5rem;align-items:start;}
.story-text p{margin-bottom:1rem;}
.story-fakta{list-style:none;background:var(--bila);border:1px solid var(--linka);
  border-radius:16px;padding:1.4rem;display:flex;flex-direction:column;gap:1rem;}
.story-fakta li{display:flex;flex-direction:column;font-size:.9rem;color:var(--seda);}
.fakt-cislo{font-size:1.5rem;font-weight:700;color:var(--tmava);}

/* DETAIL */
.detail-hlava{background:var(--barva);color:#fff;padding:2.8rem 1.5rem 2.4rem;}
.detail-hlava-obsah{max-width:1080px;margin:0 auto;}
.zpet{text-decoration:none;opacity:.9;font-size:.95rem;display:inline-block;margin-bottom:1rem;}
.zpet:hover{opacity:1;}
.detail-hlava h1{font-size:clamp(2rem,5vw,3rem);}
.detail-popis{margin-top:.6rem;max-width:640px;opacity:.95;}

/* BANNER S FOTKOU */
.detail-hlava--foto{background-size:cover;background-position:center;
  padding:4.5rem 1.5rem 4rem;text-shadow:0 1px 12px rgba(0,0,0,.35);}
.fotostrip{max-width:1080px;margin:0 auto;padding:1.4rem 1.5rem 0;}
.fotostrip-vnitrek{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;}
.foto-karta{margin:0;border-radius:12px;overflow:hidden;background:var(--bila);
  border:1px solid var(--linka);box-shadow:0 2px 10px rgba(20,40,30,.06);}
.foto-karta img{width:100%;height:120px;object-fit:cover;display:block;
  transition:transform .25s ease;}
.foto-karta:hover img{transform:scale(1.05);}
.foto-karta figcaption{padding:.5rem .6rem;font-size:.82rem;color:var(--text);
  font-weight:600;text-align:center;}
.fotokredit{margin-top:.7rem;font-size:.7rem;color:var(--seda);line-height:1.4;}

.prepinace{max-width:1080px;margin:1.2rem auto 0;padding:0 1.5rem;display:flex;flex-wrap:wrap;gap:.6rem;}
.prepinac{text-decoration:none;padding:.45rem .9rem;border-radius:999px;background:var(--bila);
  border:1px solid var(--linka);font-size:.9rem;color:var(--seda);transition:.15s;}
.prepinac:hover{border-color:var(--barva);color:var(--text);}
.prepinac.aktivni{background:var(--barva);color:#fff;border-color:var(--barva);}

.detail{max-width:1080px;margin:0 auto;padding:1.5rem;}
.staty-pas{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:.8rem;margin:1.4rem 0;}
.stat{background:var(--bila);border:1px solid var(--linka);border-radius:14px;padding:1rem;text-align:center;}
.stat-cislo{display:block;font-size:1.5rem;font-weight:700;}
.stat-popis{font-size:.82rem;color:var(--seda);}

/* QR DO MOBILU */
.share-blok{margin:1.6rem 0;}
.share-karta{display:flex;gap:1.6rem;align-items:center;justify-content:space-between;
  flex-wrap:wrap;background:var(--barva);color:#fff;border-radius:16px;
  padding:1.6rem 1.8rem;box-shadow:0 2px 14px rgba(20,40,30,.1);}
.share-text h2{font-size:1.5rem;margin-bottom:.2rem;}
.share-text p{opacity:.92;font-size:1rem;}
.share-qr{display:flex;gap:1.2rem;}
.qr-karta{margin:0;background:#fff;border-radius:14px;padding:.7rem .7rem .5rem;
  display:flex;flex-direction:column;align-items:center;width:150px;}
.qr{width:130px;height:130px;display:flex;align-items:center;justify-content:center;}
.qr svg,.qr img{width:130px;height:130px;display:block;}
.qr-karta figcaption{margin-top:.4rem;text-align:center;color:var(--text);line-height:1.25;}
.qr-karta figcaption strong{display:block;font-size:1rem;}
.qr-karta figcaption span{font-size:.78rem;color:var(--seda);}
@media(max-width:560px){.share-karta{flex-direction:column;text-align:center;}
  .share-qr{justify-content:center;}}

.mapa-blok{margin:1.6rem 0;}
#mapa{height:520px;border-radius:16px;border:1px solid var(--linka);box-shadow:0 2px 14px rgba(20,40,30,.06);}
.profil-blok{margin:2rem 0 3rem;}
.profil-blok h2{font-size:1.4rem;margin-bottom:1rem;}
.profil-plocha{background:var(--bila);border:1px solid var(--linka);border-radius:16px;
  padding:1rem;height:280px;}

/* PATA */
.pata{border-top:1px solid var(--linka);padding:2rem 1.5rem;text-align:center;
  color:var(--seda);font-size:.85rem;}
.pata a{color:var(--seda);}

@media(max-width:720px){
  .story-mrizka{grid-template-columns:1fr;}
  #mapa{height:380px;}
}
"""

JS = """
// Vykreslení mapy + výškového profilu pro jednu trasu.
(function(){
  const d = window.TRASA;
  if(!d) return;

  // --- Mapa (Leaflet + OSM dlaždice) ---
  const map = L.map('mapa', {scrollWheelZoom:false});
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap'
  }).addTo(map);

  const cara = L.polyline(d.coords, {color:d.barva, weight:5, opacity:.9}).addTo(map);
  map.fitBounds(cara.getBounds(), {padding:[30,30]});

  // Start/cíl.
  const start = d.coords[0];
  const cil = d.coords[d.coords.length-1];
  L.circleMarker(start, {radius:7, color:'#fff', weight:2, fillColor:d.barva, fillOpacity:1})
    .addTo(map).bindPopup('Start');
  L.circleMarker(cil, {radius:7, color:'#fff', weight:2, fillColor:'#1b2a23', fillOpacity:1})
    .addTo(map).bindPopup('Cíl');

  // Vrchol Koráb s rozhlednou.
  const ikona = L.divIcon({className:'korab-ikona', html:'🗼',
    iconSize:[28,28], iconAnchor:[14,14]});
  L.marker(d.korab, {icon:ikona}).addTo(map)
    .bindPopup('<b>Rozhledna Koráb</b><br>772 m n. m.');

  // Po načtení dorovnat velikost.
  setTimeout(()=>map.invalidateSize(), 200);

  // --- Výškový profil (Chart.js) ---
  const ctx = document.getElementById('profil');
  new Chart(ctx, {
    type:'line',
    data:{
      labels: d.profil.map(p=>p[0]),
      datasets:[{
        data: d.profil.map(p=>p[1]),
        borderColor: d.barva,
        backgroundColor: d.barva+'22',
        fill:true, tension:.3, pointRadius:0, borderWidth:2
      }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{
          title:(it)=>it[0].label+' km',
          label:(it)=>it.formattedValue+' m n. m.'
        }}},
      scales:{
        x:{title:{display:true,text:'vzdálenost (km)'},
           ticks:{maxTicksLimit:10}},
        y:{title:{display:true,text:'nadm. výška (m)'}}
      }
    }
  });
})();
"""


# --- Hlavní běh ------------------------------------------------------------


def main():
    os.makedirs(os.path.join(VYSTUP, "assets"), exist_ok=True)

    # Zkopírujeme fotky ze zdrojové složky foto/ do site/assets/foto/.
    zdroj_foto = os.path.join(ZAKLAD, "foto")
    cil_foto = os.path.join(VYSTUP, "assets", "foto")
    if os.path.isdir(zdroj_foto):
        os.makedirs(cil_foto, exist_ok=True)
        for jmeno in os.listdir(zdroj_foto):
            if jmeno.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                shutil.copy2(os.path.join(zdroj_foto, jmeno),
                             os.path.join(cil_foto, jmeno))

    # Zkopírujeme hotové QR obrázky (Mapy.cz), pokud existují.
    zdroj_qr = os.path.join(ZAKLAD, "qr")
    if os.path.isdir(zdroj_qr):
        cil_qr = os.path.join(VYSTUP, "assets", "qr")
        os.makedirs(cil_qr, exist_ok=True)
        for jmeno in os.listdir(zdroj_qr):
            if jmeno.lower().endswith(".png"):
                shutil.copy2(os.path.join(zdroj_qr, jmeno),
                             os.path.join(cil_qr, jmeno))

    trasy = [nacti_trasu(d) for d in TRASY_DEF]

    napis_index(trasy)
    for t in trasy:
        napis_detail(t, trasy)

    with open(os.path.join(VYSTUP, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    with open(os.path.join(VYSTUP, "assets", "trasa.js"), "w", encoding="utf-8") as f:
        f.write(JS)

    print("Hotovo. Vygenerováno do složky 'site/':")
    print(f"  - index.html (přehled {len(trasy)} tras)")
    for t in trasy:
        print(f"  - trasa-{t.slug}.html  |  {t.nazev}: "
              f"{t.delka_km} km, ↑{t.nastoupano_m} m, "
              f"{cas_text(t.cas_min)}, {t.obtiznost}")


if __name__ == "__main__":
    main()
