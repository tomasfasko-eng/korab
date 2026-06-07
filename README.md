# Koráb 🚢🏔️

Webová prezentace turistických tras na **Koráb** — horu, rozhlednu a chatu nad
Kdyní. Z GPX souborů (export z Mapy.cz) vygeneruje statický web s přehledem
tras, interaktivní mapou, výškovým profilem a statistikami.

## Trasy

| Trasa | Délka | Stoupání | Odhad času | Obtížnost |
|---|---|---|---|---|
| Malý okruh | 10,5 km | ↑156 m | 2 h 36 min | Střední |
| Střední okruh | 23,6 km | ↑446 m | ~6 h | Náročná |
| Velký okruh | 39,5 km | ↑841 m | ~10 h | Expediční |
| Expediční okruh | 102,8 km | ↑2457 m | ~27 h | Expediční |

## Jak to funguje

`build.py` přečte GPX soubory ze složky projektu, spočítá statistiky
(délka přes haversine, převýšení s vyhlazením šumu, odhad času Naismithovým
pravidlem, obtížnost) a vygeneruje statický web do složky `site/`:

```
site/
  index.html            # přehled všech tras + „story" o Korábu
  trasa-maly.html       # detail trasy: mapa + profil + statistiky
  trasa-stredni.html
  trasa-velky.html
  trasa-expedicni.html
  assets/
    style.css
    trasa.js
    foto/                 # fotky do bannerů
    gpx/                  # GPX ke stažení (maly.gpx, stredni.gpx, …)
```

Web je **samostatný** — mapa (Leaflet + OpenStreetMap), graf (Chart.js) a QR
kód (qrcode-generator) se načítají z CDN, data tras jsou vložená přímo ve
stránkách. Žádný server běžet nemusí.

Každá trasa má **QR kód a tlačítko ke stažení GPX**. QR se generuje v
prohlížeči z aktuální adresy stránky, takže funguje lokálně i po nasazení
(automaticky odkazuje na správnou doménu) bez jakýchkoli úprav.

## Generování

```bash
python3 build.py
```

Žádné závislosti — jen Python 3.12 (standardní knihovna).

### Přidání / úprava trasy

1. Ulož nový GPX do složky projektu.
2. Přidej záznam do seznamu `TRASY_DEF` v `build.py` (soubor, slug, název,
   barva, popis).
3. Spusť `python3 build.py`.

### Fotky do banneru trasy

Fotky míst, kudy trasa vede, se zobrazí v banneru detailu (první jako pozadí
hlavičky, ostatní v pásku náhledů).

1. Ulož fotky do zdrojové složky `foto/` (build je sám zkopíruje do
   `site/assets/foto/`). Doporučené pojmenování: `<slug>-<misto>.jpg`.
2. K dané trase v `TRASY_DEF` přidej klíč `fotky` se seznamem:
   ```python
   "fotky": [
       {"soubor": "expedicni-cerchov.jpg", "popisek": "Čerchov (1042 m)",
        "autor": "Jan Macura", "licence": "CC BY-SA 4.0"},
       ...
   ],
   ```
3. Spusť `python3 build.py`.

> **Licence:** používej jen volně licencované fotky (ideálně z Wikimedia
> Commons — CC0 / CC BY / CC BY-SA). Autor a licence se automaticky vypíšou
> pod páskem fotek. Fotky z náhodných webů nebo Mapy.cz jsou autorsky chráněné
> a na publikovaný web nepatří.

## Lokální náhled

```bash
cd site
python3 -m http.server 8099
# → otevři http://localhost:8099
```

## Nasazení na PythonAnywhere

Web obsluhuje malá Flask appka (`flask_app.py`), která servíruje složku
`site/`. Nasazení přes ZIP + Bash konzoli (nejrychlejší):

1. **Vytvoř balíček** lokálně:
   ```bash
   python3 build.py
   zip -rq korab-deploy.zip site flask_app.py -x "*.DS_Store"
   ```
2. **Nahraj ZIP** na PythonAnywhere (záložka *Files*) do domovské složky.
3. **Bash konzole** (*Consoles → Bash*):
   ```bash
   unzip -o korab-deploy.zip -d ~/korab
   pip install --user flask        # pokud Flask chybí
   ```
4. **Web app** (*Web → Add a new web app → Manual configuration → Python 3.x*).
5. **WSGI soubor** (odkaz v *Web*) — smaž obsah a vlož:
   ```python
   import sys
   cesta = "/home/UZIVATEL/korab"          # uprav UZIVATEL
   if cesta not in sys.path:
       sys.path.insert(0, cesta)
   from flask_app import app as application
   ```
6. **Reload** web app. Hotovo → `https://UZIVATEL.pythonanywhere.com`.

### Aktualizace webu

Po změně tras/fotek znovu `python3 build.py`, vytvoř nový ZIP, nahraj,
v Bash konzoli `unzip -o korab-deploy.zip -d ~/korab` a **Reload** web app.

> QR kódy se generují z adresy stránky, takže po nasazení automaticky míří na
> `…pythonanywhere.com` a fungují odkudkoliv — žádná úprava není potřeba.

## Zdroje dat

- Trasy: export GPX z [Mapy.cz](https://mapy.cz)
- Mapové podklady: © OpenStreetMap přispěvatelé
- Informace o Korábu: [Wikipedie](https://cs.wikipedia.org/wiki/Rozhledna_Kor%C3%A1b),
  [chatakorab.cz](https://www.chatakorab.cz/)
