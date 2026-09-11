"""Ronda 3: réplica exacta del formulario BOE + estructura de fichas."""
import json, re
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
def sec(t): print("\n" + "=" * 92 + f"\n### {t}\n" + "=" * 92, flush=True)
def get(u, **k):
    try:
        r = S.get(u, timeout=45, **k); print(f"  [{r.status_code}] {r.url[:160]} ({len(r.content)}B)", flush=True); return r
    except Exception as e:
        print(f"  ERROR {u}: {e}", flush=True); return None

sec("BOE: etiquetas de radios y provincias")
r = get("https://subastas.boe.es/subastas_ava.php")
soup = BeautifulSoup(r.text, "lxml")
for grupo in ("dato[0]", "dato[2]", "dato[3]", "dato[4]"):
    out = []
    for i in soup.find_all("input", attrs={"name": grupo}):
        lab = soup.find("label", attrs={"for": i.get("id")})
        out.append((i.get("value"), (lab.get_text(" ", strip=True) if lab else "")[:34]))
    print(f"  {grupo}: {json.dumps(out, ensure_ascii=False)}")
for s in soup.find_all("select"):
    opts = [(o.get('value'), o.get_text(strip=True)) for o in s.find_all('option')]
    bcn = [o for o in opts if 'arcelona' in (o[1] or '')]
    print(f"  SELECT {s.get('name')} ({len(opts)} opts) barcelona={bcn} primeras={opts[:4]}")

sec("BOE: búsqueda replicando el formulario (POST)")
form = soup.find("form", action=re.compile("subastas_ava"))
payload = {}
for i in form.find_all("input"):
    n, t = i.get("name"), (i.get("type") or "").lower()
    if not n: continue
    if t in ("hidden", "text", "date"): payload[n] = i.get("value") or ""
for s in form.find_all("select"):
    if s.get("name"): payload[s["name"]] = ""
payload.update({"dato[0]": "", "dato[2]": "EJ", "dato[3]": "I", "dato[4]": "501",
                "dato[8]": "08", "accion": "Buscar", "page_hits": "50",
                "sort_field[0]": "SUBASTA.FECHA_FIN_INICIO", "sort_order[0]": "desc"})
print("  payload:", json.dumps(payload, ensure_ascii=False)[:900])
r = S.post("https://subastas.boe.es/subastas_ava.php", data=payload, timeout=45)
print(f"  [{r.status_code}] {len(r.content)}B")
so = BeautifulSoup(r.text, "lxml")
cont = so.find("div", id="contenido") or so
txt = cont.get_text(" ", strip=True)
print("  TEXTO:", txt[:900])
print("  --- primeros bloques de resultado:")
for sel in ["div.result", "div.resultado-busqueda", "div#listaSubastas", "table", "div.bloque"]:
    n = so.select(sel)
    if n: print(f"   sel={sel} n={len(n)} :: {str(n[0])[:1800]}")
det = sorted({a['href'] for a in so.find_all('a', href=True) if 'detalleSubasta' in a['href']})
print("  ENLACES DETALLE:", json.dumps(det[:10], ensure_ascii=False))

if det:
    sec("BOE: ficha de subasta + pestaña de bienes")
    u = det[0] if det[0].startswith("http") else "https://subastas.boe.es/" + det[0].lstrip("/")
    rr = get(u)
    ss = BeautifulSoup(rr.text, "lxml")
    c = ss.find("div", id="contenido") or ss
    print("  FICHA-TEXTO:", re.sub(r"\s+", " ", c.get_text(" | ", strip=True))[:2500])
    print("  FICHA-HTML:", str(c)[:2500])
    tabs = sorted({a['href'] for a in ss.find_all('a', href=True) if 'idBus' in a['href'] or 'ver=' in a['href']})
    print("  PESTAÑAS:", json.dumps(tabs[:10], ensure_ascii=False))

sec("SERVIHABITAT: tarjeta, paginación y ficha")
r = get("https://www.servihabitat.com/es/venta/vivienda-casa/barcelona")
if r and r.ok:
    so = BeautifulSoup(r.text, "lxml")
    for sel in ["div.property-item", "div.card-property", "article", "div[class*=result-item]", "div[class*=inmueble]"]:
        n = so.select(sel)
        if n: print(f"  sel={sel} n={len(n)} :: {str(n[0])[:2200]}"); break
    print("  TOTAL-TEXTO:", re.sub(r"\s+"," ", so.get_text(" ", strip=True))[:400])
    pag = sorted({a['href'] for a in so.find_all('a', href=True) if re.search(r'pagina|page|/p\d|\?p=', a['href'])})
    print("  PAGINACION:", json.dumps(pag[:15], ensure_ascii=False)[:800])
    fichas = sorted({a['href'] for a in so.find_all('a', href=True) if re.search(r'/es/venta/vivienda-casa/[^/]+/\d+$', a['href'])})
    print(f"  FICHAS({len(fichas)}):", json.dumps(fichas[:6], ensure_ascii=False))
    if fichas:
        rr = get("https://www.servihabitat.com" + fichas[0])
        s2 = BeautifulSoup(rr.text, "lxml")
        ld = [x.string for x in s2.find_all("script", type="application/ld+json")]
        print("  FICHA JSON-LD:", json.dumps(ld, ensure_ascii=False)[:2500])
        print("  FICHA TEXTO:", re.sub(r"\s+"," ", s2.get_text(" | ", strip=True))[:1800])
        og = {m.get("property") or m.get("name"): m.get("content") for m in s2.find_all("meta")}
        print("  METAS:", json.dumps({k: v for k, v in og.items() if k and ("og:" in k or "descri" in k.lower())}, ensure_ascii=False)[:800])

sec("ALTAMIRA: sitemap + ficha")
r = get("https://www.altamirainmuebles.com/sitemap-venta-pisos-y-casas.xml")
if r and r.ok:
    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    print(f"  URLs={len(locs)} muestra={json.dumps(locs[:8], ensure_ascii=False)}")
    bcn = [l for l in locs if re.search(r"barcelona|/08\d|cataluna", l, re.I)][:5]
    print("  BCN:", json.dumps(bcn, ensure_ascii=False))
    if locs:
        rr = get(bcn[0] if bcn else locs[0])
        if rr and rr.ok:
            s2 = BeautifulSoup(rr.text, "lxml")
            print("  SSR-TEXTO:", re.sub(r"\s+"," ", s2.get_text(" | ", strip=True))[:1200])
            ld = [x.string for x in s2.find_all("script", type="application/ld+json")]
            print("  JSON-LD:", json.dumps(ld, ensure_ascii=False)[:1200])

sec("ALISEDA: sitemap + ficha")
r = get("https://www.alisedainmobiliaria.com/sitemap-index-aliseda.xml")
if r and r.ok:
    print("  ", re.sub(r"\s+", " ", r.text)[:800])
