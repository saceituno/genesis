"""Portal de Subastas del BOE (subastas.boe.es).

Fuente oficial de las subastas públicas españolas. Agrupa cinco orígenes:
judicial, notarial, Agencia Tributaria, otras administraciones tributarias y
subastas administrativas generales (entre ellas las de la Tesorería General de
la Seguridad Social).

El portal no ofrece API: se replica el formulario de búsqueda avanzada
(subastas_ava.php) tal y como lo enviaría un navegador. De cada subasta se lee
la pestaña «Bienes», que es la que trae los datos estructurados del inmueble
(tipo, dirección, localidad, referencia catastral), y se emite un registro por
bien, porque una misma subasta puede sacar varias fincas a la vez.
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
FOTO_CATASTRO = ("https://ovc.catastro.meh.es/OVCServWeb/OVCWcfLibres/OVCFotoFachada.svc/"
                 "RecuperarFotoFachadaGet?ReferenciaCatastral=")

ESTADOS = {"EJ": "Celebrándose", "PU": "Próxima apertura"}
PROVINCIA_BARCELONA = "08"

# Subtipos del portal que pueden contener una casa. El resto (garaje, trastero,
# local, nave, solar) se descarta en origen para no gastar peticiones.
SUBTIPOS_VIVIENDA = {"vivienda"}
SUBTIPOS_POSIBLES = {"finca rustica", "otros", "otro", ""}

RE_BIEN = re.compile(r"^(?:bien|lote)\s+(\d+)\s*[-–]\s*([^(]+?)\s*(?:\(([^)]*)\))?$", re.I)


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
        self.url_estable: bool | None = None   # se comprueba con la primera ficha

    # ------------------------------------------------------------------ API
    def recoge(self):
        plantilla = self._plantilla_formulario()
        if plantilla is None:
            self.log.error("No se ha podido leer el formulario de búsqueda del BOE")
            return
        vistos: set[str] = set()
        for estado in ESTADOS:
            for enlace, resumen in self._resultados(plantilla, estado):
                if resumen["referencia"] in vistos:
                    continue
                vistos.add(resumen["referencia"])
                yield from self._inmuebles(enlace, resumen)

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
                h3, h4 = li.find("h3"), li.find("h4")
                parrafos = [p.get_text(" ", strip=True) for p in li.find_all("p")]
                yield urljoin(BASE, a["href"]), {
                    "referencia": (h3.get_text(strip=True).replace("SUBASTA", "").strip()
                                   if h3 else ""),
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
            texto = parse.normaliza(a.get_text(" ", strip=True))
            titulo = parse.normaliza(a.get("title") or "")
            if "siguiente" in texto or "siguiente" in titulo:
                return a["href"]
        return None

    # ------------------------------------------------------------- fichas
    def _inmuebles(self, enlace_busqueda: str, resumen: dict):
        ref = resumen["referencia"]
        # URL estable (sin el testigo de búsqueda), que es la que verá el usuario.
        estable = f"{BASE}detalleSubasta.php?idSub={ref}" if ref else enlace_busqueda

        if self.url_estable is False:
            estable = enlace_busqueda
        r = self.cliente.get(estable)
        valida = bool(r and r.status_code == 200 and "Datos de la subasta" in r.text)
        if self.url_estable is None and estable != enlace_busqueda:
            self.url_estable = valida
            if not valida:
                self.log.warning("El BOE no acepta la URL sin testigo de búsqueda; "
                                 "se usarán los enlaces del listado")
        if not valida:
            estable = enlace_busqueda
            r = self.cliente.get(enlace_busqueda)
            if not r or r.status_code != 200:
                return
        general = self._tabla(BeautifulSoup(r.text, "lxml"))

        url_bienes = (f"{estable}&ver=3" if "idSub=" in estable and "ver=" not in estable
                      else self._pestana(BeautifulSoup(r.text, "lxml"), "bienes"))
        rb = self.cliente.get(urljoin(BASE, url_bienes)) if url_bienes else None
        bienes = self._bienes(BeautifulSoup(rb.text, "lxml")) if rb and rb.status_code == 200 else []
        if not bienes:
            self.log.debug("Subasta %s sin datos de bienes legibles", ref)
            return

        tipo_subasta = general.get("Tipo de subasta", "")
        fuente = _fuente_desde_tipo(tipo_subasta, resumen.get("organismo", ""))

        for bien in bienes:
            inm = self._a_inmueble(bien, general, resumen, fuente, estable, len(bienes))
            if inm:
                yield inm

    def _a_inmueble(self, bien: dict, general: dict, resumen: dict, fuente: str,
                    url: str, total_bienes: int) -> Inmueble | None:
        campos = bien["campos"]
        subtipo = parse.normaliza(bien.get("subtipo"))
        descripcion = " ".join(filter(None, [
            campos.get("Descripción", ""),
            campos.get("Información adicional", ""),
            campos.get("Dirección", ""),
        ])) or resumen.get("descripcion", "")
        tipo = parse.clasifica_tipo(descripcion)

        if subtipo and subtipo not in SUBTIPOS_VIVIENDA:
            if subtipo not in SUBTIPOS_POSIBLES or tipo != "casa":
                return None      # garaje, local, trastero, nave, solar sin casa…

        catastro = campos.get("Referencia catastral", "").strip()
        sufijo = f"-b{bien['orden']}" if total_bienes > 1 else ""
        direccion = " ".join((campos.get("Dirección") or "").split())

        return Inmueble(
            fuente=fuente,
            url=f"{url}&ver=3" if "ver=" not in url else url,
            referencia=f"{resumen['referencia']}{sufijo}",
            titulo=(campos.get("Descripción") or direccion or
                    resumen.get("descripcion", "Subasta BOE"))[:180],
            municipio=(campos.get("Localidad") or
                       parse.extrae_municipio(direccion) or None),
            provincia=campos.get("Provincia") or "Barcelona",
            direccion=", ".join(filter(None, [direccion, campos.get("Código Postal")])) or None,
            tipo=tipo,
            superficie_m2=parse.extrae_superficie(descripcion),
            terreno_m2=parse.extrae_terreno(descripcion),
            dormitorios=parse.extrae_dormitorios(descripcion),
            precio=(parse.a_numero(general.get("Valor subasta")) or
                    parse.a_numero(general.get("Puja mínima"))),
            valor_tasacion=parse.a_numero(general.get("Tasación")),
            deposito=parse.a_numero(general.get("Importe del depósito")),
            estado=self._estado(resumen.get("estado_txt", "")),
            fecha_fin=self._fecha(general.get("Fecha de conclusión", "")),
            organismo=resumen.get("organismo") or None,
            imagen=self._foto_catastro(catastro),
            descripcion=descripcion.strip(),
        )

    # ----------------------------------------------------------- utilidades
    def _bienes(self, soup: BeautifulSoup) -> list[dict]:
        """Un diccionario por bien subastado, con su subtipo y su tabla de datos."""
        bienes: list[dict] = []
        for cabecera in soup.find_all(re.compile(r"^h[2-6]$")):
            m = RE_BIEN.match(cabecera.get_text(" ", strip=True))
            if not m:
                continue
            tabla = cabecera.find_next("table")
            if tabla is None:
                continue
            bienes.append({
                "orden": int(m.group(1)),
                "clase": m.group(2).strip(),
                "subtipo": (m.group(3) or "").strip(),
                "campos": self._tabla(tabla),
            })
        if not bienes:
            campos = self._tabla(soup)
            if campos.get("Descripción"):
                bienes.append({"orden": 1, "clase": "Inmueble", "subtipo": "", "campos": campos})
        return bienes

    @staticmethod
    def _tabla(nodo) -> dict[str, str]:
        datos: dict[str, str] = {}
        for tr in nodo.find_all("tr"):
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

    def _foto_catastro(self, referencia: str) -> str | None:
        """Foto de fachada del Catastro, sólo si ese inmueble tiene una publicada.

        El servicio responde 200 con cuerpo vacío cuando no hay foto (solares,
        fincas rústicas), así que se comprueba antes de guardar el enlace.
        """
        if not referencia or len(referencia) < 14:
            return None
        url = FOTO_CATASTRO + referencia
        r = self.cliente.get(url)
        if (r and r.status_code == 200 and len(r.content) > 1024
                and "image" in (r.headers.get("content-type") or "")):
            return url
        return None

    @staticmethod
    def _estado(texto: str) -> str | None:
        """'Estado: Celebrándose - [Conclusión prevista: …]' -> 'Celebrándose'."""
        limpio = texto.replace("Estado:", "").split(" - [")[0].strip()
        return limpio or None

    @staticmethod
    def _fecha(texto: str) -> str | None:
        m = re.search(r"ISO:\s*([0-9T:\-+]+)", texto)
        if m:
            return m.group(1)
        m = re.search(r"(\d{2}-\d{2}-\d{4})", texto)
        return m.group(1) if m else None


def FuentesBOE(**kw):
    """El portal es único; se devuelve como una sola fuente que ya etiqueta el origen."""
    return [SubastasBOE(**kw)]
