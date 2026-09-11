"""QA de la interfaz con navegador real: comprueba que el listado es operativo.

Levanta un servidor local, abre index.html con los datos reales y verifica que
se pintan las fichas, que los filtros de ubicación, precio, plataforma y radio
responden, y que la ficha de detalle enlaza al origen. Deja capturas en
data/qa/.
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
PUERTO = 8765
fallos: list[str] = []


def comprueba(condicion: bool, mensaje: str) -> None:
    print(("  ✓ " if condicion else "  ✗ ") + mensaje)
    if not condicion:
        fallos.append(mensaje)


def servidor():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(RAIZ), **kw)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", PUERTO), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> int:
    datos = json.loads((RAIZ / "data" / "listings.json").read_text("utf-8"))
    activos = [i for i in datos["inmuebles"] if i.get("activo", True)]
    print(f"Datos: {len(activos)} inmuebles vigentes")

    httpd = servidor()
    salida = RAIZ / "data" / "qa"
    salida.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path="/opt/pw-browsers/chromium/chrome-linux/chrome")
        pag = nav.new_page(viewport={"width": 1280, "height": 900})
        errores_js: list[str] = []
        pag.on("pageerror", lambda e: errores_js.append(str(e)))
        pag.goto(f"http://127.0.0.1:{PUERTO}/index.html", wait_until="networkidle")
        pag.wait_for_selector(".card", timeout=15000)

        tarjetas = pag.locator(".card").count()
        print("\n1. Pintado inicial")
        comprueba(tarjetas > 0, f"se pintan fichas ({tarjetas})")
        comprueba(tarjetas == len(activos), f"se pintan todas las vigentes ({tarjetas}/{len(activos)})")
        comprueba(not errores_js, f"sin errores de JavaScript {errores_js[:2]}")
        resumen = pag.inner_text("#resumen")
        comprueba("plataformas" in resumen, f"cabecera con resumen: «{resumen[:90]}»")

        print("\n2. Origen visible en cada ficha")
        fuentes_ui = set(pag.locator(".card .badge").all_inner_texts())
        fuentes_datos = {i["fuente"] for i in activos}
        comprueba(fuentes_datos.issubset(fuentes_ui | {"NUEVO", "DATOS PARCIALES"}),
                  f"la plataforma aparece en la tarjeta: {sorted(fuentes_datos)}")

        print("\n3. Filtro de ubicación")
        municipio = next((i["municipio"] for i in activos if i.get("municipio")), None)
        esperado = sum(1 for i in activos if i.get("municipio") == municipio)
        pag.select_option("#f-muni", municipio)
        pag.wait_for_timeout(250)
        n = pag.locator(".card").count()
        comprueba(n == esperado, f"«{municipio}» → {n} fichas (esperadas {esperado})")
        pag.select_option("#f-muni", "")
        pag.wait_for_timeout(200)

        print("\n4. Filtro de precio")
        precios = sorted(i["precio"] for i in activos if i.get("precio") is not None)
        if precios:
            corte = precios[len(precios) // 2]
            esperado = sum(1 for i in activos if (i.get("precio") or -1) <= corte and i.get("precio") is not None)
            pag.fill("#f-pmax", str(int(corte)))
            pag.wait_for_timeout(250)
            n = pag.locator(".card").count()
            comprueba(n == esperado, f"hasta {int(corte)} € → {n} fichas (esperadas {esperado})")
            pag.fill("#f-pmax", "")
            pag.wait_for_timeout(200)
        else:
            comprueba(False, "hay precios con los que filtrar")

        print("\n5. Filtro de plataforma")
        fuente = sorted(fuentes_datos)[0]
        esperado = sum(1 for i in activos if i["fuente"] == fuente)
        pag.click(f'.chip[data-fuente="{fuente}"]')
        pag.wait_for_timeout(250)
        n = pag.locator(".card").count()
        comprueba(n == esperado, f"«{fuente}» → {n} fichas (esperadas {esperado})")
        pag.click(f'.chip[data-fuente="{fuente}"]')
        pag.wait_for_timeout(200)

        print("\n6. Filtro de radio")
        pag.eval_on_selector("#f-dist", "el => { el.value = 15; el.dispatchEvent(new Event('input')); }")
        pag.wait_for_timeout(250)
        esperado = sum(1 for i in activos if (i.get("distancia_km") is None or i["distancia_km"] <= 15))
        n = pag.locator(".card").count()
        comprueba(n == esperado, f"radio 15 km → {n} fichas (esperadas {esperado})")
        pag.click("#f-reset")
        pag.wait_for_timeout(250)
        comprueba(pag.locator(".card").count() == len(activos), "«Limpiar» restaura el listado")

        print("\n7. Ficha de detalle")
        pag.locator(".card").first.click()
        pag.wait_for_timeout(400)
        comprueba(pag.locator("#panel[open]").count() == 1, "se abre el panel de detalle")
        cta = pag.locator(".cta").first
        href = cta.get_attribute("href") or ""
        comprueba(href.startswith("http"), f"enlace al anuncio original: {href[:70]}")
        comprueba("Plataforma" in pag.inner_text("#panel-in"), "la ficha indica la plataforma")
        pag.screenshot(path=str(salida / "detalle.png"))
        pag.keyboard.press("Escape")
        pag.wait_for_timeout(300)

        print("\n8. Capturas")
        pag.screenshot(path=str(salida / "escritorio.png"), full_page=False)
        movil = nav.new_page(viewport={"width": 390, "height": 844})
        movil.goto(f"http://127.0.0.1:{PUERTO}/index.html", wait_until="networkidle")
        movil.wait_for_selector(".card", timeout=15000)
        desbordamiento = movil.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        comprueba(desbordamiento <= 0, f"sin desbordamiento horizontal en móvil ({desbordamiento}px)")
        movil.screenshot(path=str(salida / "movil.png"))
        comprueba(not errores_js, f"sin errores de JavaScript al final {errores_js[:2]}")
        nav.close()

    httpd.shutdown()
    print("\n" + ("QA UI ✗ " + str(len(fallos)) + " fallos" if fallos else "QA UI ✓ interfaz operativa"))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
