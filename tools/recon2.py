"""Segunda ronda: estructura concreta de búsqueda/resultado/ficha por portal."""
import json, re, sys
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})

def get(url, **kw):
    try:
        r = S.get(url, timeout=45, **kw)
        print(f"  [{r.status_code}] {r.url} ({len(r.content)}B, {r.headers.get('content-type')})")
        return r
    except Exception as e:
        print(f"  ERROR {url}: {type(e).__name__}: {e}")
        return None

def sec(t): print("\n" + "=" * 95 + f"\n### {t}\n" + "=" * 95)

# ---------------------------------------------------------------- BOE formulario
sec("BOE: campos del formulario avanzado")
r = get("https://subastas.boe.es/subastas_ava.php")
if r:
    soup = BeautifulSoup(r.text, "lxml")
    for s in soup.find_all("select"):
        opts = [(o.get("value"), (o.get_text() or "").strip()[:38]) for o in s.find_all("option")]
        print(f"  SELECT name={s.get('name')} id={s.get('id')} n={len(opts)}")
        print("     ", json.dumps(opts[:70], ensure_ascii=False)[:2200])
    for i in soup.find_all("input"):
        print(f"  INPUT name={i.get('name')} type={i.get('type')} value={str(i.get('value'))[:45]} id={i.get('id')}")

sec("BOE: ¿datos abiertos / sindicación?")
for u in ["https://subastas.boe.es/sindicacion.php",
          "https://subastas.boe.es/rss.php",
          "https://subastas.boe.es/sitemap.xml",
          "https://www.boe.es/datosabiertos/",
          "https://www.boe.es/robots.txt"]:
    rr = get(u)
    if rr is not None and rr.status_code == 200:
        print("   ", re.sub(r"\s+", " ", rr.text)[:700])

sec("BOE: búsqueda GET (provincia Barcelona, bienes inmuebles)")
params = {
    "campo[0]": "SUBASTA.ESTADO", "dato[0]": "EJ",
    "campo[1]": "BIEN.TIPO", "dato[1]": "I",
    "campo[2]": "BIEN.PROVINCIA", "dato[2]": "8",
    "page_hits": "50", "sort_field[0]": "SUBASTA.FECHA_FIN_INICIO", "sort_order[0]": "desc",
    "accion": "Buscar",
}
r = get("https://subastas.boe.es/subastas_ava.php", params=params)
if r:
    soup = BeautifulSoup(r.text, "lxml")
    main = soup.find("div", id="main") or soup.find("div", class_="contenido") or soup
    print("  RESULT-HTML-EXCERPT:")
    print(re.sub(r"\n\s*\n", "\n", main.get_text("|", strip=True))[:1500])
    print("  --- estructura:")
    print(str(main)[:4000])

sec("SERVIHABITAT: listado de casas en Barcelona")
for u in ["https://www.servihabitat.com/es/venta/vivienda/barcelona",
          "https://www.servihabitat.com/es/venta/casa/barcelona"]:
    rr = get(u)
    if rr and rr.status_code == 200:
        so = BeautifulSoup(rr.text, "lxml")
        arts = so.select("article, .card, .inmueble, [class*=resultado], [class*=property]")
        print(f"   bloques candidatos={len(arts)}")
        if arts:
            print("   PRIMER BLOQUE:", str(arts[0])[:2500])
        jsonld = [s.string for s in so.find_all("script", type="application/ld+json")]
        print("   JSON-LD:", json.dumps(jsonld, ensure_ascii=False)[:900])
        links = sorted({a["href"] for a in so.find_all("a", href=True) if "/inmueble" in a["href"] or "/es/venta/" in a["href"]})
        print("   LINKS:", json.dumps(links[:25], ensure_ascii=False)[:1200])
        pag = so.select("[class*=pagin] a, [class*=Pagin] a")
        print("   PAGINACION:", json.dumps([a.get("href") for a in pag][:12], ensure_ascii=False)[:600])
        break

sec("ALTAMIRA / SOLVIA / ALISEDA / DIGLO: sitemaps y portada")
for u in ["https://www.altamirainmuebles.com/sitemap.xml",
          "https://www.solvia.es/sitemap.xml",
          "https://www.alisedainmobiliaria.com/robots.txt",
          "https://www.alisedainmobiliaria.com/",
          "https://www.diglo.es/robots.txt",
          "https://www.diglo.es/"]:
    rr = get(u)
    if rr is not None and rr.status_code == 200:
        print("   ", re.sub(r"\s+", " ", rr.text)[:900])
