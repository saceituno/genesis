"""Reconocimiento de portales de subastas: descubre estructura real antes de escribir parsers."""
import json, re, sys, urllib.parse
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})

TARGETS = [
    ("BOE", "https://subastas.boe.es/"),
    ("BOE_AVA", "https://subastas.boe.es/subastas_ava.php"),
    ("SERVIHABITAT", "https://www.servihabitat.com/"),
    ("HAYA", "https://www.haya.es/"),
    ("ALTAMIRA", "https://www.altamirainmuebles.com/"),
    ("SOLVIA", "https://www.solvia.es/"),
    ("ALISEDA", "https://www.aliseda.es/"),
    ("SAREB", "https://www.sareb.es/"),
    ("DIGLO", "https://www.diglo.com/"),
    ("SUBASTAS_AEAT", "https://www.agenciatributaria.gob.es/AEAT.sede/procedimientoini/ZZ09.shtml"),
]

def head(txt, n=400):
    return re.sub(r"\s+", " ", txt)[:n]

def probe(name, url):
    print("=" * 90)
    print(f"### {name} -> {url}")
    try:
        r = S.get(url, timeout=40, allow_redirects=True)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return
    print(f"  status={r.status_code} final={r.url} ctype={r.headers.get('content-type')} bytes={len(r.content)}")
    if "html" not in (r.headers.get("content-type") or ""):
        print("  body:", head(r.text))
        return
    soup = BeautifulSoup(r.text, "lxml")
    print("  title:", head(soup.title.get_text() if soup.title else "", 120))
    # forms
    for f in soup.find_all("form")[:6]:
        names = [i.get("name") for i in f.find_all(["input", "select"]) if i.get("name")]
        print(f"  FORM action={f.get('action')} method={f.get('method')} inputs={names[:25]}")
    # SPA markers / api hints
    for marker in ("__NEXT_DATA__", "window.__NUXT__", "ng-version", "data-reactroot"):
        if marker in r.text:
            print(f"  MARKER: {marker}")
    apis = sorted(set(re.findall(r"https?://[a-z0-9.\-]+/[A-Za-z0-9/_\-.]*(?:api|search|buscador|rest|graphql)[A-Za-z0-9/_\-.]*", r.text)))[:15]
    if apis:
        print("  API-HINTS:", json.dumps(apis, ensure_ascii=False))
    scripts = [s.get("src") for s in soup.find_all("script", src=True)][:12]
    print("  SCRIPTS:", json.dumps(scripts, ensure_ascii=False)[:600])
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    interesting = [l for l in links if re.search(r"(subast|inmueb|vivienda|propert|buscador|search|venta|casa|chalet)", l, re.I)][:20]
    print("  LINKS:", json.dumps(interesting, ensure_ascii=False)[:900])

def robots(host):
    try:
        r = S.get(f"https://{host}/robots.txt", timeout=25)
        print(f"--- robots {host} [{r.status_code}]:")
        print("\n".join(r.text.splitlines()[:40]))
    except Exception as e:
        print(f"--- robots {host}: ERROR {e}")

if __name__ == "__main__":
    for name, url in TARGETS:
        probe(name, url)
    print("#" * 90)
    for h in ["subastas.boe.es", "www.servihabitat.com", "www.haya.es", "www.altamirainmuebles.com",
              "www.solvia.es", "www.aliseda.es", "www.sareb.es", "www.diglo.com"]:
        robots(h)
