"""Contrato común de las fuentes."""
from __future__ import annotations

import logging
from typing import Iterable

from ..http import Cliente
from ..models import Inmueble

log = logging.getLogger("monitor.fuente")


class Fuente:
    nombre: str = "genérica"
    url_base: str = ""

    def __init__(self, cliente: Cliente | None = None, limite_paginas: int = 20):
        self.cliente = cliente or Cliente()
        self.limite_paginas = limite_paginas
        self.log = logging.getLogger(f"monitor.{self.nombre}")

    def recoge(self) -> Iterable[Inmueble]:
        raise NotImplementedError
