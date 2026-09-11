"""Ronda 5: pestaña Bienes del BOE y por qué Servihabitat devuelve 0."""
import json, re
import requests
from bs4 import BeautifulSoup
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
S=requests.Session(); S.headers.update({"User-Agent":UA,"Accept-Language":"es-ES,es;q=0.9"})
def sec(t): print("\n"+"="*92+f"\n### {t}\n"+"="*92, flush=True)
def get(u,**k):
    try:
        r=S.get(u,timeout=45,**k); print(f"  [{r.status_code}] {r.url[:140]} ({len(r.content)}B)",flush=True); return r
    except Exception as e: print(f"  ERROR {u}: {e}",flush=True); return None

sec("BOE: localizar una subasta y volcar TODAS sus pestañas")
base=get("https://subastas.boe.es/subastas_ava.php")
soup=BeautifulSoup(base.text,"lxml")
form=soup.find("form",action=re.compile("subastas_ava"))
p={}
for i in form.find_all("input"):
    n,t=i.get("name"),(i.get("type") or "").lower()
    if n and t in ("hidden","text","date"): p[n]=i.get("value") or ""
for s in form.find_all("select"):
    if s.get("name"): p[s["name"]]=""
p.update({"dato[2]":"EJ","dato[3]":"I","dato[8]":"08","page_hits":"50",
          "sort_field[0]":"SUBASTA.FECHA_FIN","sort_order[0]":"asc","accion":"Buscar"})
r=S.post("https://subastas.boe.es/subastas_ava.php",data=p,timeout=45,
         headers={"Referer":"https://subastas.boe.es/subastas_ava.php"})
so=BeautifulSoup(r.text,"lxml")
enlaces=[a["href"] for a in so.find_all("a",href=True) if "detalleSubasta" in a["href"]]
print("  subastas encontradas:", len(so.select("li.resultado-busqueda")))
u="https://subastas.boe.es/"+enlaces[0].lstrip("./")
r=get(u); s2=BeautifulSoup(r.text,"lxml")
print("  PESTAÑAS (texto -> href):")
for a in s2.select("#idBloqueDatos1 a, .caja a, ul a"):
    txt=a.get_text(" ",strip=True)
    if txt in ("Información general","Autoridad gestora","Bienes","Pujas","Lotes"):
        print(f"    {txt!r} -> {a['href'][:90]}")
for ver in ("3","2","4"):
    uu=re.sub(r"detalleSubasta\.php\?", f"detalleSubasta.php?ver={ver}&", u)
    rr=get(uu)
    if rr and rr.ok:
        s3=BeautifulSoup(rr.text,"lxml")
        c=s3.find("div",id="contenido") or s3
        cab=[h.get_text(" ",strip=True) for h in c.find_all(["h2","h3","h4"])][:6]
        pares=[(tr.find("th").get_text(" ",strip=True), tr.find("td").get_text(" ",strip=True)[:90])
               for tr in c.find_all("tr") if tr.find("th") and tr.find("td")]
        print(f"  --- ver={ver} cabeceras={cab}")
        for k,v in pares[:28]: print(f"      {k}: {v}")
        imgs=[i.get("src") for i in c.find_all("img",src=True)]
        print("      imgs:", json.dumps(imgs[:6],ensure_ascii=False))

sec("SERVIHABITAT: ¿por qué 0 fichas?")
for u in ["https://www.servihabitat.com/es/venta/vivienda-casa/barcelona",
          "https://www.servihabitat.com/es/venta/vivienda-casa/barcelona-vallesoriental"]:
    rr=get(u, headers={"User-Agent":"SubastasBCNMonitor/1.0 (+https://github.com/saceituno/genesis)"})
    if rr:
        s4=BeautifulSoup(rr.text,"lxml")
        fichas=[a["href"] for a in s4.find_all("a",href=True)
                if re.match(r"^/es/venta/vivienda-casa/[a-z0-9\-]+/\d+$", a["href"].split("#")[0])]
        zonas=[a["href"] for a in s4.find_all("a",href=True)
               if re.match(r"^/es/venta/vivienda-casa/barcelona(-[a-z0-9]+){1,2}$", a["href"].split("#")[0])]
        print(f"   UA propio -> fichas={len(fichas)} zonas={len(zonas)} titulo={(s4.title.string or '')[:60]}")
        print("   muestra fichas:", json.dumps(sorted(set(fichas))[:3],ensure_ascii=False))
        print("   muestra zonas:", json.dumps(sorted(set(zonas))[:6],ensure_ascii=False))
