"""Geolocalización de municipios y distancia al centro de Barcelona.

Se usa Nominatim (OpenStreetMap) con caché persistente en disco: las coordenadas
no se inventan, se consultan una vez por municipio y se reutilizan siempre.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import requests

from .config import BARCELONA, USER_AGENT

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocache.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
_ultima_peticion = 0.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * 6371.0088 * math.asin(math.sqrt(h)), 2)


class Geocodificador:
    def __init__(self, cache_path: Path = CACHE_PATH, offline: bool = False):
        self.cache_path = Path(cache_path)
        self.offline = offline
        self.cache: dict[str, dict | None] = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text("utf-8"))
            except json.JSONDecodeError:
                self.cache = {}
        self.nuevas = 0

    # -- API pública ---------------------------------------------------------
    def coords(self, municipio: str | None, provincia: str | None = None) -> tuple[float, float] | None:
        if not municipio:
            return None
        clave = self._clave(municipio, provincia)
        if clave in self.cache:
            v = self.cache[clave]
            return (v["lat"], v["lon"]) if v else None
        if self.offline:
            return None
        v = self._consulta(municipio, provincia)
        self.cache[clave] = v
        self.nuevas += 1
        return (v["lat"], v["lon"]) if v else None

    def nombre_canonico(self, municipio: str | None, provincia: str | None = None) -> str | None:
        """Nombre oficial del municipio según OpenStreetMap, si se pudo geocodificar."""
        if not municipio:
            return None
        self.coords(municipio, provincia)
        entrada = self.cache.get(self._clave(municipio, provincia))
        if not entrada:
            return None
        return (entrada.get("nombre") or "").split(",")[0].strip() or None

    def distancia_a_barcelona(self, municipio: str | None, provincia: str | None = None) -> float | None:
        c = self.coords(municipio, provincia)
        return haversine_km(BARCELONA, c) if c else None

    def guarda(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=1, sort_keys=True), "utf-8"
        )

    # -- interno -------------------------------------------------------------
    @staticmethod
    def _clave(municipio: str, provincia: str | None) -> str:
        return f"{municipio.strip().lower()}|{(provincia or '').strip().lower()}"

    def _consulta(self, municipio: str, provincia: str | None) -> dict | None:
        global _ultima_peticion
        consulta = municipio if not provincia else f"{municipio}, {provincia}"
        espera = 1.1 - (time.time() - _ultima_peticion)
        if espera > 0:
            time.sleep(espera)
        try:
            r = requests.get(
                NOMINATIM,
                params={"q": f"{consulta}, España", "format": "json", "limit": 1,
                        "countrycodes": "es", "addressdetails": 1},
                headers={"User-Agent": USER_AGENT, "Accept-Language": "es"},
                timeout=30,
            )
            _ultima_peticion = time.time()
            if r.status_code != 200:
                return None
            datos = r.json()
            if not datos:
                return None
            d = datos[0]
            return {"lat": float(d["lat"]), "lon": float(d["lon"]),
                    "nombre": d.get("display_name", "")[:120]}
        except Exception:
            _ultima_peticion = time.time()
            return None
