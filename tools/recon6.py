"""Ronda 6: URL estable de ficha BOE, foto de fachada del Catastro y cabeceras Servihabitat."""
import re, requests
from bs4 import BeautifulSoup
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
def sec(t): print("\n"+"="*92+f"\n### {t}\n"+"="*92, flush=True)

sec("BOE: ¿funciona detalleSubasta.php?idSub=... sin idBus?")
S=requests.Session(); S.headers.update({"User-Agent":UA,"Accept-Language":"es-ES,es;q=0.9"})
base=S.get("https://subastas.boe.es/subastas_ava.php",timeout=40)
soup=BeautifulSoup(base.text,"lxml"); form=soup.find("form",action=re.compile("subastas_ava"))
p={}
for i in form.find_all("input"):
    n,t=i.get("name"),(i.get("type") or "").lower()
    if n and t in ("hidden","text","date"): p[n]=i.get("value") or ""
for s in form.find_all("select"):
    if s.get("name"): p[s["name"]]=""
p.update({"dato[2]":"EJ","dato[3]":"I","dato[8]":"08","page_hits":"50","accion":"Buscar"})
r=S.post("https://subastas.boe.es/subastas_ava.php",data=p,timeout=40,
         headers={"Referer":"https://subastas.boe.es/subastas_ava.php"})
so=BeautifulSoup(r.text,"lxml")
ids=[h3.get_text(strip=True).replace("SUBASTA","").strip() for h3 in so.select("li.resultado-busqueda h3")][:3]
print("  ids:", ids)
refs=[]
for idsub in ids:
    for ver in ("", "&ver=3"):
        u=f"https://subastas.boe.es/detalleSubasta.php?idSub={idsub}{ver}"
        rr=S.get(u,timeout=40)
        ok = "Datos de la subasta" in rr.text or "Datos del bien" in rr.text
        print(f"   [{rr.status_code}] {'ficha OK' if ok else 'SIN DATOS'} :: {u}")
        if ver and ok:
            s3=BeautifulSoup(rr.text,"lxml")
            cab=[h.get_text(' ',strip=True) for h in s3.find_all(['h2','h3','h4'])]
            print("      cabeceras:", cab[:6])
            print("      etiqueta bien:", [c for c in cab if c.lower().startswith('bien')])
            for tr in s3.find_all("tr"):
                th,td=tr.find("th"),tr.find("td")
                if th and td and "atastral" in th.get_text():
                    refs.append(td.get_text(strip=True)); print("      ref catastral:", td.get_text(strip=True))

sec("CATASTRO: foto de fachada por referencia catastral")
for ref in (refs or ["7634253CF9773S0001DE"]):
    u=("https://ovc.catastro.meh.es/OVCServWeb/OVCWcfLibres/OVCFotoFachada.svc/"
       f"RecuperarFotoFachadaGet?ReferenciaCatastral={ref}")
    try:
        rr=requests.get(u,timeout=30,headers={"User-Agent":UA})
        print(f"   [{rr.status_code}] {rr.headers.get('content-type')} {len(rr.content)}B ref={ref}")
        print("      cuerpo:", rr.content[:60])
    except Exception as e:
        print("   ERROR", e)

sec("SERVIHABITAT: qué cabeceras pasan el WAF")
perfiles = {
  "navegador_completo": {"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
      "Accept-Language":"es-ES,es;q=0.9","Sec-Fetch-Dest":"document","Sec-Fetch-Mode":"navigate",
      "Sec-Fetch-Site":"none","Upgrade-Insecure-Requests":"1"},
  "monitor_simple": {"User-Agent":"SubastasBCNMonitor/1.0 (+https://github.com/saceituno/genesis)"},
  "monitor_con_accept": {"User-Agent":"SubastasBCNMonitor/1.0 (+https://github.com/saceituno/genesis)",
      "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language":"es-ES,es;q=0.9,ca;q=0.8"},
  "chrome_minimo": {"User-Agent":UA},
}
for nombre,h in perfiles.items():
    try:
        rr=requests.get("https://www.servihabitat.com/es/venta/vivienda-casa/barcelona",headers=h,timeout=40)
        n=len(re.findall(r'/es/venta/vivienda-casa/[a-z0-9\-]+/\d+"', rr.text))
        print(f"   {nombre}: {rr.status_code} bytes={len(rr.content)} fichas≈{n}")
    except Exception as e:
        print(f"   {nombre}: ERROR {e}")
