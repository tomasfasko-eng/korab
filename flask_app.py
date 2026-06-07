# -*- coding: utf-8 -*-
"""
Koráb — minimální Flask appka pro PythonAnywhere.

Obsluhuje statický web vygenerovaný do složky ``site/`` (viz build.py).
Hlavní stránka je na ``/``, ostatní soubory (trasy, CSS, JS, fotky, GPX)
se servírují podle cesty.

Na PythonAnywhere ve WSGI souboru stačí:
    import sys
    cesta = "/home/UZIVATEL/korab"        # uprav podle svého
    if cesta not in sys.path:
        sys.path.insert(0, cesta)
    from flask_app import app as application
"""

import os

from flask import Flask, abort, send_from_directory

ZAKLAD = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ZAKLAD, "site")

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(SITE, "index.html")


@app.route("/<path:cesta>")
def soubor(cesta):
    plna = os.path.normpath(os.path.join(SITE, cesta))
    # Zůstaň uvnitř složky site/ (ochrana proti ../).
    if not plna.startswith(SITE) or not os.path.isfile(plna):
        abort(404)
    return send_from_directory(SITE, cesta)


if __name__ == "__main__":
    # Lokální spuštění pro test: python flask_app.py → http://localhost:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
