"""Validación de las respuestas de Nominatim, sin tocar la red."""
import monitor.geo as geo
from monitor.geo import Geocodificador


def _con_respuesta(monkeypatch, respuesta):
    monkeypatch.setattr(geo.Geocodificador, "_pide", staticmethod(lambda params: respuesta))
    return Geocodificador.__new__(Geocodificador)


MUNICIPIO = {"lat": "41.5497", "lon": "2.1050", "category": "place", "name": "Sabadell",
             "address": {"city": "Sabadell"}, "display_name": "Sabadell, Vallès Occidental"}
NEGOCIO = {"lat": "41.4", "lon": "2.2", "category": "office", "name": "Artica Viajes Bcn",
           "address": {}, "display_name": "Artica Viajes Bcn, Barcelona"}
# El formato antiguo usa 'class' en lugar de 'category'.
MUNICIPIO_FORMATO_ANTIGUO = {**MUNICIPIO, "class": "place"}
MUNICIPIO_FORMATO_ANTIGUO.pop("category")


def test_acepta_un_municipio(monkeypatch):
    g = _con_respuesta(monkeypatch, MUNICIPIO)
    assert Geocodificador._consulta(g, "Sabadell", "Barcelona") == {
        "lat": 41.5497, "lon": 2.105, "nombre": "Sabadell"}


def test_acepta_tambien_el_formato_con_class(monkeypatch):
    """jsonv2 llama 'category' a lo que 'json' llama 'class'; valen los dos."""
    g = _con_respuesta(monkeypatch, MUNICIPIO_FORMATO_ANTIGUO)
    assert Geocodificador._consulta(g, "Sabadell", "Barcelona") is not None


def test_rechaza_un_negocio_con_nombre_parecido(monkeypatch):
    g = _con_respuesta(monkeypatch, NEGOCIO)
    assert Geocodificador._consulta(g, "Bcn-Nou Barris", "Barcelona") is None


def test_sin_respuesta_no_inventa_coordenadas(monkeypatch):
    g = _con_respuesta(monkeypatch, None)
    assert Geocodificador._consulta(g, "Municipio Inexistente", "Barcelona") is None
