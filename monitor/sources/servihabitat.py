"""Servihabitat (servihabitat.com).

Servicer inmobiliario con cartera de adjudicados en venta. Las fichas se sirven
renderizadas en servidor e incluyen JSON-LD schema.org, así que se lee el dato
estructurado y sólo se recurre al texto para lo que no publica (la parcela,
sobre todo).

El portal particiona su listado público por provincia → comarca → municipio y
muestra 20 fichas por página, así que se recorre ese árbol. Para no descargar
cientos de fichas que luego se descartarían, se mira antes el municipio: el
listado da su nombre en el texto del enlace, se geolocaliza (con caché) y sólo
se abren las fichas que caen dentro del radio.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import parse
from ..config import CRITERIOS
from ..models import Inmueble
from .base import Fuente

BASE = "https://www.servihabitat.com"
# 'vivienda-casa' es la tipología casa/chalet del portal (excluye pisos).
LISTADO = BASE + "/es/venta/vivienda-casa/barcelona"

RE_FICHA = re.compile(r"^/es/venta/vivienda-casa/(barcelona(?:-[a-z0-9]+){0,2})/(\d+)$")
RE_ZONA = re.compile(r"^/es/venta/vivienda-casa/(barcelona(?:-[a-z0-9]+){1,2})$")


class Servihabitat(Fuente):
    nombre = "Servihabitat"
    url_base = BASE

    def __init__(self, *a, geo=None, **kw):
        super().__init__(*a, **kw)
        self.geo = geo                      # opcional: permite el prefiltro por distancia
        self.nombres: dict[str, str] = {}   # slug de zona -> nombre legible

    # ------------------------------------------------------------------ API
    def recoge(self):
        zonas, vistas, fichas = [LISTADO], set(), {}

        for nivel in range(3):              # provincia -> comarcas -> municipios
            nuevas: list[str] = []
            for zona in zonas:
                if zona in vistas:
                    continue
                vistas.add(zona)
                html = self._html(zona)
                if html is None:
                    continue
                soup = BeautifulSoup(html, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"].split("#")[0]
                    ficha = RE_FICHA.match(href)
                    if ficha:
                        fichas[urljoin(BASE, href)] = ficha.group(1)
                        continue
                    sub = RE_ZONA.match(href)
                    if sub:
                        self._anota_nombre(sub.group(1), a.get_text(" ", strip=True))
                        destino = urljoin(BASE, href)
                        if destino not in vistas:
                            nuevas.append(destino)
            zonas = nuevas
            self.log.info("Servihabitat nivel %s → %s zonas por visitar, %s fichas localizadas",
                          nivel, len(nuevas), len(fichas))
            if not nuevas:
                break

        candidatas = [u for u, zona in fichas.items() if self._cerca(zona)]
        self.log.info("Servihabitat: %s fichas localizadas, %s dentro del radio",
                      len(fichas), len(candidatas))
        for url in sorted(candidatas):
            inm = self._ficha(url)
            if inm:
                yield inm

    # ------------------------------------------------------- prefiltro zonal
    def _anota_nombre(self, slug: str, texto: str) -> None:
        texto = re.sub(r"^(?:Viviendas?|Casas?)[^A-ZÀ-Ý]*", "", texto).strip(" ·,")
        if texto and 2 < len(texto) < 45 and slug not in self.nombres:
            self.nombres[slug] = texto

    def _cerca(self, slug: str) -> bool:
        """¿Puede este municipio estar dentro del radio? Ante la duda, se acepta."""
        if self.geo is None or slug.count("-") < 2:
            return True
        nombre = self.nombres.get(slug)
        if not nombre:
            return True
        distancia = self.geo.distancia_a_barcelona(nombre, "Barcelona")
        if distancia is None:
            return True
        return distancia <= CRITERIOS.radio_km

    # ------------------------------------------------------------------ util
    def _html(self, url: str) -> str | None:
        r = self.cliente.get(url)
        return r.text if r and r.status_code == 200 else None

    def _ficha(self, url: str) -> Inmueble | None:
        html = self._html(url)
        if html is None:
            return None
        soup = BeautifulSoup(html, "lxml")
        prop = self._propiedad(soup)
        if not prop:
            return None

        direccion = prop.get("address", {}) or {}
        oferta = prop.get("offers") or {}
        precio = parse.a_numero(str(oferta.get("price", ""))) if isinstance(oferta, dict) else None
        medida = prop.get("floorSize") or {}
        superficie = parse.a_numero(str(medida.get("value", ""))) if isinstance(medida, dict) else None

        descripcion = prop.get("description", "") or ""
        # La parcela no viene en el JSON-LD; se busca en el texto de la ficha.
        terreno = parse.extrae_terreno(descripcion) or parse.extrae_terreno(
            soup.get_text(" ", strip=True))

        return Inmueble(
            fuente=self.nombre,
            url=url,
            referencia=str(prop.get("sku") or url.rsplit("/", 1)[-1]),
            titulo=prop.get("name") or "",
            municipio=direccion.get("addressLocality"),
            provincia=direccion.get("addressRegion"),
            direccion=", ".join(filter(None, [direccion.get("streetAddress"),
                                              direccion.get("postalCode")])) or None,
            tipo=parse.clasifica_tipo(
                f"{prop.get('accommodationCategory','')} {prop.get('name','')} {descripcion}"),
            superficie_m2=superficie,
            terreno_m2=terreno,
            dormitorios=self._entero(prop.get("numberOfBedrooms")),
            banos=self._entero(prop.get("numberOfBathroomsTotal")),
            precio=precio,
            estado="En venta",
            imagen=self._imagen(soup, prop),
            descripcion=descripcion.strip(),
        )

    @staticmethod
    def _entero(valor) -> int | None:
        try:
            return int(valor)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _propiedad(soup: BeautifulSoup) -> dict | None:
        """Nodo del inmueble dentro del grafo JSON-LD de la ficha."""
        for etiqueta in soup.find_all("script", type="application/ld+json"):
            try:
                datos = json.loads(etiqueta.string or "{}")
            except json.JSONDecodeError:
                continue
            grafo = datos.get("@graph") if isinstance(datos, dict) else None
            for nodo in (grafo or [datos]):
                if not isinstance(nodo, dict):
                    continue
                tipos = nodo.get("@type")
                tipos = tipos if isinstance(tipos, list) else [tipos]
                if any(t in ("SingleFamilyResidence", "House", "Residence", "Apartment",
                             "Accommodation", "Product") for t in tipos if t):
                    if nodo.get("offers") or nodo.get("floorSize"):
                        return nodo
        return None

    @staticmethod
    def _imagen(soup: BeautifulSoup, prop: dict) -> str | None:
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            return meta["content"]
        img = prop.get("image")
        if isinstance(img, list) and img:
            img = img[0]
        if isinstance(img, dict):
            return img.get("url") or img.get("contentUrl") or (
                img.get("@id", "").split("#")[0] or None)
        return img if isinstance(img, str) else None
