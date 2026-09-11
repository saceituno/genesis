"""Configuración central del monitor.

Todos los umbrales del encargo viven aquí para poder ajustarlos sin tocar los parsers.
"""
from dataclasses import dataclass, field

# Centro de referencia: Plaça de Catalunya, Barcelona.
BARCELONA = (41.3870, 2.1701)
RADIO_KM = 40.0


@dataclass(frozen=True)
class Criterios:
    tipo_vivienda: str = "casa"          # casa / chalet / unifamiliar / adosado / masía
    dormitorios_min: int = 2
    superficie_min_m2: float = 80.0      # superficie construida
    terreno_min_m2: float = 300.0        # parcela / solar
    radio_km: float = RADIO_KM
    centro: tuple = BARCELONA


CRITERIOS = Criterios()

# Provincias/comarcas cuyo territorio puede caer dentro del radio de 40 km.
# Se usa como pre-filtro barato antes de geocodificar.
PROVINCIAS_OBJETIVO = {"barcelona", "girona", "tarragona"}

USER_AGENT = (
    "SubastasBCNMonitor/1.0 (+https://github.com/saceituno/genesis; "
    "monitorización personal de subastas inmobiliarias)"
)

# Segundos de espera entre peticiones al mismo host (cortesía / rate-limit).
DELAY_POR_HOST = 1.2
TIMEOUT = 40
REINTENTOS = 3
