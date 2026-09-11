"""Servihabitat (servihabitat.com).

Servicer inmobiliario (CaixaBank/Lone Star) con cartera de adjudicados. Las
fichas se sirven renderizadas en servidor e incluyen JSON-LD schema.org, así que
se lee el dato estructurado y sólo se recurre al texto para lo que no publica
(parcela, sobre todo).

Se recorre provincia -> comarca -> municipio, que es como el portal particiona
su listado público (cada página muestra 20 fichas).
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import parse
from ..models import Inmueble
from .base import Fuente

BASE = "https://www.servihabitat.com"
# 'vivienda-casa' es la tipología casa/chalet del portal (excluye pisos).
LISTADO = BASE + "/es/venta/vivienda-casa/barcelona"

RE_FICHA = re.compile(r"^/es/venta/vivienda-casa/[a-z0-9\-]+/\d+$")
RE_ZONA = re.compile(r"^/es/venta/vivienda-casa/barcelona(-[a-z0-9]+){1,2}$")


class Servihabitat(Fuente):
    nombre = "Servihabitat"
    url_base = BASE

    def recoge(self):
        zonas = [LISTADO]
        vistas: set[str] = set()
        fichas: set[str] = set()

        # Descubrimiento por niveles: provincia -> comarcas -> municipios.
        for nivel in range(3):
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
                    if RE_FICHA.match(href):
                        fichas.add(urljoin(BASE, href))
                    elif RE_ZONA.match(href) and urljoin(BASE, href) not in vistas:
                        nuevas.append(urljoin(BASE, href))
            zonas = nuevas
            self.log.info("Servihabitat nivel %s → %s zonas nuevas, %s fichas acumuladas",
                          nivel, len(nuevas), len(fichas))
            if not nuevas:
                break

        self.log.info("Servihabitat: %s fichas a leer", len(fichas))
        for url in sorted(fichas):
            inm = self._ficha(url)
            if inm:
                yield inm

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
        texto = soup.get_text(" ", strip=True)

        if not prop:
            return None
        direccion = prop.get("address", {}) or {}
        precio = None
        oferta = prop.get("offers") or {}
        if isinstance(oferta, dict):
            precio = parse.a_numero(str(oferta.get("price", "")))
        superficie = None
        fs = prop.get("floorSize") or {}
        if isinstance(fs, dict):
            superficie = parse.a_numero(str(fs.get("value", "")))

        descripcion = prop.get("description", "") or ""
        # La parcela no está en el JSON-LD; se busca en el texto de la ficha.
        terreno = parse.extrae_terreno(descripcion) or parse.extrae_terreno(texto)

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
                f"{prop.get('accommodationCategory','')} {prop.get('name','')}"),
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
        """Extrae el nodo del inmueble del grafo JSON-LD."""
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
