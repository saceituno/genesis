"""Portal de Subastas del BOE (subastas.boe.es).

Es la fuente oficial de las subastas públicas españolas y agrupa cinco orígenes:
judicial, notarial, Agencia Tributaria, otras administraciones tributarias y
subastas administrativas generales (donde se publican, entre otras, las de la
Tesorería General de la Seguridad Social).

El portal no ofrece API: se replica el formulario de búsqueda avanzada
(subastas_ava.php) tal y como lo enviaría un navegador y se leen las fichas.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import parse
from ..models import Inmueble
from .base import Fuente

BASE = "https://subastas.boe.es/"
BUSQUEDA = BASE + "subastas_ava.php"

# Estados que interesan: en curso y próximas a abrirse.
ESTADOS = {"EJ": "Celebrándose", "PU": "Próxima apertura"}
PROVINCIA_BARCELONA = "08"


def _fuente_desde_tipo(tipo: str, organismo: str) -> str:
    t = parse.normaliza(tipo)
    org = parse.normaliza(organismo)
    if "seguridad social" in org or "tesoreria general" in org or "seguridad social" in t:
        return "BOE · Seguridad Social"
    if "agencia tributaria" in t or "(aeat)" in org:
        return "BOE · Agencia Tributaria"
    if "judicial" in t:
        return "BOE · Judicial"
    if "notarial" in t:
        return "BOE · Notarial"
    if t:
        return "BOE · " + tipo.strip().capitalize()
    return "BOE · Subastas"


class SubastasBOE(Fuente):
    nombre = "BOE"
    url_base = BASE

    def __init__(self, *a, provincia: str = PROVINCIA_BARCELONA, **kw):
        super().__init__(*a, **kw)
        self.provincia = provincia

    # ------------------------------------------------------------------ API
    def recoge(self):
        plantilla = self._plantilla_formulario()
        if plantilla is None:
            self.log.error("No se ha podido leer el formulario de búsqueda del BOE")
            return
        vistos: set[str] = set()
        for estado in ESTADOS:
            for enlace, resumen in self._resultados(plantilla, estado):
                id_sub = resumen["referencia"]
                if id_sub in vistos:
                    continue
                vistos.add(id_sub)
                inm = self._ficha(enlace, resumen)
                if inm:
                    yield inm

    # ------------------------------------------------------- búsqueda/listado
    def _plantilla_formulario(self) -> dict | None:
        r = self.cliente.get(BUSQUEDA)
        if not r or r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        form = soup.find("form", action=re.compile("subastas_ava"))
        if not form:
            return None
        datos: dict[str, str] = {}
        for i in form.find_all("input"):
            nombre, tipo = i.get("name"), (i.get("type") or "").lower()
            if nombre and tipo in ("hidden", "text", "date"):
                datos[nombre] = i.get("value") or ""
        for s in form.find_all("select"):
            if s.get("name"):
                datos[s["name"]] = ""
        datos.update({
            "dato[3]": "I",                      # BIEN.TIPO = Inmuebles
            "dato[8]": self.provincia,           # BIEN.COD_PROVINCIA
            "page_hits": "500",
            "sort_field[0]": "SUBASTA.FECHA_FIN",
            "sort_order[0]": "asc",
            "accion": "Buscar",
        })
        return datos

    def _resultados(self, plantilla: dict, estado: str):
        datos = dict(plantilla)
        datos["dato[2]"] = estado                # SUBASTA.ESTADO.CODIGO
        url, metodo, envio = BUSQUEDA, "post", datos
        for pagina in range(1, self.limite_paginas + 1):
            r = (self.cliente.post(url, data=envio, headers={"Referer": BUSQUEDA})
                 if metodo == "post" else self.cliente.get(url))
            if not r or r.status_code != 200 or "Se ha producido un error" in r.text:
                self.log.warning("Búsqueda BOE estado=%s página=%s sin resultados", estado, pagina)
                return
            soup = BeautifulSoup(r.text, "lxml")
            bloques = soup.select("li.resultado-busqueda")
            self.log.info("BOE estado=%s página=%s → %s subastas", estado, pagina, len(bloques))
            for li in bloques:
                a = li.find("a", href=re.compile("detalleSubasta"))
                if not a:
                    continue
                h3 = li.find("h3")
                h4 = li.find("h4")
                parrafos = [p.get_text(" ", strip=True) for p in li.find_all("p")]
                ref = (h3.get_text(strip=True).replace("SUBASTA", "").strip() if h3 else "")
                yield urljoin(BASE, a["href"]), {
                    "referencia": ref,
                    "organismo": h4.get_text(" ", strip=True) if h4 else "",
                    "estado_txt": next((p for p in parrafos if p.startswith("Estado")), ""),
                    "descripcion": " ".join(p for p in parrafos if not p.startswith("Estado")),
                }
            siguiente = self._siguiente(soup)
            if not siguiente:
                return
            url, metodo, envio = urljoin(BASE, siguiente), "get", None

    @staticmethod
    def _siguiente(soup: BeautifulSoup) -> str | None:
        for a in soup.find_all("a", href=True):
            txt = parse.normaliza(a.get_text(" ", strip=True))
            titulo = parse.normaliza(a.get("title") or "")
            if "siguiente" in txt or "siguiente" in titulo:
                return a["href"]
        return None

    # ------------------------------------------------------------- ficha
    def _ficha(self, enlace: str, resumen: dict) -> Inmueble | None:
        r = self.cliente.get(enlace)
        if not r or r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        general = self._tabla(soup)

        bienes = {}
        url_bienes = self._pestana(soup, "bienes")
        if url_bienes:
            rb = self.cliente.get(urljoin(BASE, url_bienes))
            if rb and rb.status_code == 200:
                sb = BeautifulSoup(rb.text, "lxml")
                bienes = self._tabla(sb)
                imagen = self._imagen(sb)
            else:
                imagen = None
        else:
            imagen = None

        descripcion = " ".join(filter(None, [
            bienes.get("Descripción", ""), bienes.get("Dirección", ""),
            resumen.get("descripcion", ""),
        ]))
        tipo_subasta = general.get("Tipo de subasta", "")
        municipio = (bienes.get("Localidad") or
                     parse.extrae_municipio(bienes.get("Dirección", "")) or
                     parse.extrae_municipio(resumen.get("descripcion", "")))

        inm = Inmueble(
            fuente=_fuente_desde_tipo(tipo_subasta, resumen.get("organismo", "")),
            url=enlace,
            referencia=resumen["referencia"] or general.get("Identificador", ""),
            titulo=self._titulo(bienes, resumen),
            municipio=municipio,
            provincia=bienes.get("Provincia") or "Barcelona",
            direccion=bienes.get("Dirección"),
            tipo=parse.clasifica_tipo(descripcion),
            superficie_m2=parse.extrae_superficie(descripcion),
            terreno_m2=parse.extrae_terreno(descripcion),
            dormitorios=parse.extrae_dormitorios(descripcion),
            precio=parse.a_numero(general.get("Valor subasta")) or
                   parse.a_numero(general.get("Puja mínima")),
            valor_tasacion=parse.a_numero(general.get("Tasación")),
            deposito=parse.a_numero(general.get("Importe del depósito")),
            estado=resumen.get("estado_txt", "").replace("Estado:", "").strip() or None,
            fecha_fin=self._fecha(general.get("Fecha de conclusión", "")),
            organismo=resumen.get("organismo") or None,
            imagen=imagen,
            descripcion=descripcion.strip(),
        )
        return inm

    # ----------------------------------------------------------- utilidades
    @staticmethod
    def _tabla(soup: BeautifulSoup) -> dict[str, str]:
        datos: dict[str, str] = {}
        for tr in soup.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                clave = th.get_text(" ", strip=True)
                valor = td.get_text(" ", strip=True)
                if clave and valor and clave not in datos:
                    datos[clave] = valor
        return datos

    @staticmethod
    def _pestana(soup: BeautifulSoup, nombre: str) -> str | None:
        for a in soup.find_all("a", href=True):
            if parse.normaliza(a.get_text(strip=True)) == nombre:
                return a["href"]
        return None

    @staticmethod
    def _imagen(soup: BeautifulSoup) -> str | None:
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if re.search(r"(fotos?|imagenes/bienes|adjunto)", src, re.I) and "logo" not in src.lower():
                return urljoin(BASE, src)
        return None

    @staticmethod
    def _fecha(texto: str) -> str | None:
        m = re.search(r"ISO:\s*([0-9T:\-+]+)", texto)
        if m:
            return m.group(1)
        m = re.search(r"(\d{2}-\d{2}-\d{4})", texto)
        return m.group(1) if m else None

    @staticmethod
    def _titulo(bienes: dict, resumen: dict) -> str:
        for clave in ("Descripción", "Dirección"):
            if bienes.get(clave):
                return bienes[clave][:160]
        return (resumen.get("descripcion") or "Subasta BOE")[:160]


def FuentesBOE(**kw):
    """El portal es único; se devuelve como una sola fuente que ya etiqueta origen."""
    return [SubastasBOE(**kw)]
