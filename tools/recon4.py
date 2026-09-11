import json, re, itertools
import requests
from bs4 import BeautifulSoup
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
S=requests.Session(); S.headers.update({"User-Agent":UA,"Accept-Language":"es-ES,es;q=0.9"})
def sec(t): print("\n"+"="*92+f"\n### {t}\n"+"="*92, flush=True)
def get(u,**k):
    try:
        r=S.get(u,timeout=45,**k); print(f"  [{r.status_code}] {r.url[:150]} ({len(r.content)}B)",flush=True); return r
    except Exception as e: print(f"  ERROR {u}: {e}",flush=True); return None

sec("BOE: desplegable.js (¿qué vale campo[4]?)")
r=get("https://subastas.boe.es/lib/js/desplegable.js")
if r and r.ok:
    for m in re.finditer(r"campo\[?4\]?[^\n]{0,140}", r.text): print("   ", m.group(0)[:160])
    print("   BIEN.* citados:", sorted(set(re.findall(r"BIEN\.[A-Z_]+", r.text))))

sec("BOE: variantes de payload hasta que funcione")
base=get("https://subastas.boe.es/subastas_ava.php")
soup=BeautifulSoup(base.text,"lxml")
form=soup.find("form", action=re.compile("subastas_ava"))
def payload_base():
    p={}
    for i in form.find_all("input"):
        n,t=i.get("name"),(i.get("type") or "").lower()
        if n and t in ("hidden","text","date"): p[n]=i.get("value") or ""
    for s in form.find_all("select"):
        if s.get("name"): p[s["name"]]=""
    p["page_hits"]="50"; p["sort_field[0]"]="SUBASTA.FECHA_FIN"; p["sort_order[0]"]="asc"
    p["accion"]="Buscar"
    return p
variantes={
 "A_sin_subtipo": {"dato[2]":"EJ","dato[3]":"I","dato[8]":"08"},
 "B_campo4_SUBTIPO": {"dato[2]":"EJ","dato[3]":"I","dato[4]":"501","campo[4]":"BIEN.SUBTIPO","dato[8]":"08"},
 "C_campo4_COD_SUBTIPO": {"dato[2]":"EJ","dato[3]":"I","dato[4]":"501","campo[4]":"BIEN.COD_SUBTIPO","dato[8]":"08"},
 "D_solo_provincia": {"dato[8]":"08"},
}
ok_payload=None
for nombre,extra in variantes.items():
    p=payload_base(); p.update(extra)
    rr=S.post("https://subastas.boe.es/subastas_ava.php",data=p,timeout=45,
              headers={"Referer":"https://subastas.boe.es/subastas_ava.php"})
    so=BeautifulSoup(rr.text,"lxml")
    err="Se ha producido un error" in rr.text
    n=len(so.select("div.resultado-busqueda")) or len([a for a in so.find_all('a',href=True) if 'detalleSubasta' in a['href']])
    print(f"  {nombre}: status={rr.status_code} bytes={len(rr.content)} error={err} enlaces_detalle={n}")
    if not err and n and ok_payload is None:
        ok_payload=(nombre,p,rr)
if ok_payload:
    nombre,p,rr=ok_payload
    print("  PAYLOAD OK:", nombre)
    so=BeautifulSoup(rr.text,"lxml")
    c=so.find("div",id="contenido") or so
    print("  RESUMEN:", re.sub(r"\s+"," ",c.get_text(" | ",strip=True))[:1200])
    blo=so.select("div.resultado-busqueda") or so.select("div.bloque")
    print(f"  BLOQUES={len(blo)}")
    if blo: print("  BLOQUE0:", str(blo[0])[:2500])
    else:
        a=[x for x in so.find_all('a',href=True) if 'detalleSubasta' in x['href']]
        print("  CONTEXTO DE UN ENLACE:", str(a[0].find_parent(['li','div','tr','p']))[:2500] if a else "")
    pag=[a['href'] for a in so.find_all('a',href=True) if 'dato' in a['href'] and 'page' in a['href'].lower()]
    print("  PAGINACION:", json.dumps(pag[:8],ensure_ascii=False)[:600])
    det=[a['href'] for a in so.find_all('a',href=True) if 'detalleSubasta' in a['href']]
    if det:
        u=det[0] if det[0].startswith("http") else "https://subastas.boe.es/"+det[0].lstrip("/")
        rr2=get(u); s2=BeautifulSoup(rr2.text,"lxml")
        c2=s2.find("div",id="contenido") or s2
        print("  FICHA TEXTO:", re.sub(r"\s+"," ",c2.get_text(" | ",strip=True))[:2200])
        print("  FICHA TABLAS:", str(c2.find("table"))[:1800])
        tabs=[a['href'] for a in s2.find_all('a',href=True) if re.search(r'idBus|ver=|Bienes|Lotes', a['href'], re.I)]
        print("  PESTAÑAS:", json.dumps(sorted(set(tabs))[:12],ensure_ascii=False)[:900])

sec("SERVIHABITAT: comarcas y paginación")
r=get("https://www.servihabitat.com/es/venta/vivienda-casa/barcelona")
if r and r.ok:
    so=BeautifulSoup(r.text,"lxml")
    zonas=sorted({a['href'] for a in so.find_all('a',href=True)
                  if re.match(r'^/es/venta/vivienda-casa/barcelona-[a-z]+$', a['href'])})
    print(f"  COMARCAS({len(zonas)}):", json.dumps(zonas,ensure_ascii=False)[:1200])
    print("  'ver mas'/paginacion en js:", json.dumps(sorted(set(re.findall(r"[\w/]*(?:paginacion|verMas|loadMore|nextPage)[\w/]*", r.text)))[:10]))
    m=re.search(r"(\d[\d\.]*)\s*(?:inmuebles|resultados|viviendas)", so.get_text(" ",strip=True), re.I)
    print("  TOTAL declarado:", m.group(0) if m else "n/d")
    for prueba in ["https://www.servihabitat.com/es/venta/vivienda-casa/barcelona?p=2",
                   "https://www.servihabitat.com/es/venta/vivienda-casa/barcelona/2"]:
        rr=get(prueba)
        if rr and rr.ok:
            s2=BeautifulSoup(rr.text,"lxml")
            f=sorted({a['href'] for a in s2.find_all('a',href=True) if re.search(r'/vivienda-casa/[^/]+/\d+$',a['href'])})
            print(f"   {prueba} -> fichas={len(f)} primera={f[0] if f else None}")

sec("SERVIHABITAT: JSON-LD completo de una ficha")
r=get("https://www.servihabitat.com/es/venta/vivienda-casa/barcelona-altpenedes-mediona/60470589")
if r and r.ok:
    so=BeautifulSoup(r.text,"lxml")
    for x in so.find_all("script",type="application/ld+json"):
        t=x.string or ""
        if "mainEntity" in t or "Residence" in t or "Product" in t or "offers" in t:
            print("   ", re.sub(r"\s+"," ",t)[1200:4000])

sec("ALISEDA: ¿ficha con SSR?")
r=get("https://www.alisedainmobiliaria.com/sitemap-inmuebles-aliseda-es-0.xml")
if r and r.ok:
    locs=re.findall(r"<loc>(.*?)</loc>", r.text)
    print(f"  URLs={len(locs)} muestra={json.dumps(locs[:4],ensure_ascii=False)}")
    cas=[l for l in locs if re.search(r"casa|chalet|barcelona", l, re.I)][:3]
    print("  CANDIDATAS:", json.dumps(cas,ensure_ascii=False))
    if cas:
        rr=get(cas[0])
        if rr and rr.ok:
            s2=BeautifulSoup(rr.text,"lxml")
            print("  SSR-TEXTO:", re.sub(r"\s+"," ",s2.get_text(" | ",strip=True))[:900])
