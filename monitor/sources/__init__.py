"""Fuentes de datos. Cada módulo expone una clase con .nombre y .recoge()."""
from .base import Fuente

def todas():
    from .boe import FuentesBOE
    from .servihabitat import Servihabitat
    return [*FuentesBOE(), Servihabitat()]
