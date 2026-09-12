"""QA de la interfaz con navegador real.

Comprueba las dos formas de abrir la página —desde el disco (file://) y desde un
servidor (http://)— porque el fallo que dejaba el listado vacío sólo aparecía en
la primera: el navegador bloquea fetch() en file:// por CORS.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
fallos: list[str] = []


def comprueba(condicion: bool, mensaje: str) -> None:
    print(("  ✓ " if condicion else "  ✗ ") + mensaje)
    if not condicion:
        fallos.append(mensaje)


def _chromium() -> str | None:
    for patron in ("chromium*/chrome-linux/chrome", "chromium*/chrome-linux64/chrome"):
        for ruta in sorted(Path("/opt/pw-browsers").glob(patron), reverse=True):
            if ruta.is_file():
                return str(ruta)
    return None


def servidor():
    """Sirve el proyecto en un puerto libre y devuelve (servidor, puerto)."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(RAIZ), **kw)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def revisa_pagina(nav, url, etiqueta, esperadas, capturas=None):
    print(f"\n— {etiqueta} —")
    pag = nav.new_page(viewport={"width": 1280, "height": 900})
    errores: list[str] = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(url)

    comprueba(pag.locator("#buscar").is_visible(), "el botón «Generar búsquedas» está a la vista")
    comprueba(pag.locator(".card").count() == 0, "antes de pulsar no se pinta nada")

    pag.click("#buscar")
    pag.wait_for_selector(".card", timeout=15000)
    tarjetas = pag.locator(".card").count()
    comprueba(tarjetas == esperadas, f"al pulsar aparecen las {esperadas} viviendas (salen {tarjetas})")
    comprueba("viviendas en proceso abierto" in pag.inner_text("#estado"),
              f"el estado resume el resultado: «{pag.inner_text('#estado')[:70]}»")
    comprueba(pag.locator("#buscar").inner_text() == "Actualizar búsqueda",
              "el botón pasa a «Actualizar búsqueda»")

    enlaces = pag.locator(".card").evaluate_all("els => els.map(e => e.href)")
    comprueba(all(u.startswith("http") for u in enlaces), "cada ficha enlaza a su anuncio original")
    plataformas = set(pag.locator(".card .badge").all_inner_texts())
    comprueba(len(plataformas) > 0, f"cada ficha indica su plataforma: {sorted(plataformas)}")
    comprueba(pag.locator("#pie").is_visible(), "el pie con los criterios aparece con los datos")
    # Sin conexión las fotos de los portales no cargan: debe verse el marcador,
    # no un hueco gris.
    huecos = pag.locator(".foto:not(:has(img)):not(:has(.sinfoto))").count()
    comprueba(huecos == 0, f"ninguna ficha queda sin imagen ni marcador ({huecos} huecos)")

    pag.click("#buscar")                       # segunda pulsación: recarga
    pag.wait_for_timeout(600)
    comprueba(pag.locator(".card").count() == esperadas, "volver a pulsar recarga sin duplicar")
    comprueba(not errores, f"sin errores de JavaScript {errores[:2]}")

    if capturas:
        pag.screenshot(path=str(capturas / "escritorio.png"))
    pag.close()


def main() -> int:
    datos = json.loads((RAIZ / "data" / "listings.json").read_text("utf-8"))
    esperadas = len([i for i in datos["inmuebles"] if i.get("activo", True)])
    print(f"Datos: {esperadas} viviendas vigentes")
    comprueba((RAIZ / "data" / "listings.js").exists(), "existe data/listings.js (carga sin CORS)")

    httpd, puerto = servidor()
    salida = RAIZ / "data" / "qa"
    salida.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=_chromium())
        # El caso que fallaba: abrir el fichero con doble clic.
        revisa_pagina(nav, f"file://{RAIZ}/index.html", "Abierto desde el disco (file://)", esperadas)
        revisa_pagina(nav, f"http://127.0.0.1:{puerto}/index.html", "Servido por HTTP",
                      esperadas, capturas=salida)

        print("\n— Móvil —")
        movil = nav.new_page(viewport={"width": 390, "height": 844})
        movil.goto(f"http://127.0.0.1:{puerto}/index.html")
        movil.click("#buscar")
        movil.wait_for_selector(".card", timeout=15000)
        desborde = movil.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        comprueba(desborde <= 0, f"sin desbordamiento horizontal ({desborde}px)")
        movil.screenshot(path=str(salida / "movil.png"))
        nav.close()

    httpd.shutdown()
    print("\n" + (f"QA UI ✗ {len(fallos)} fallos" if fallos else "QA UI ✓ interfaz operativa"))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
