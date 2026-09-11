from monitor.config import BARCELONA
from monitor.geo import Geocodificador, haversine_km


def test_distancias_conocidas():
    assert 17 < haversine_km(BARCELONA, (41.5497, 2.1050)) < 21      # Sabadell
    assert 80 < haversine_km(BARCELONA, (41.9794, 2.8214)) < 92      # Girona
    assert haversine_km(BARCELONA, BARCELONA) == 0


def test_cache_evita_consultas(tmp_path):
    cache = tmp_path / "geocache.json"
    cache.write_text('{"sabadell|barcelona": {"lat": 41.5497, "lon": 2.105}}', "utf-8")
    g = Geocodificador(cache, offline=True)
    assert g.coords("Sabadell", "Barcelona") == (41.5497, 2.105)
    assert g.distancia_a_barcelona("Sabadell", "Barcelona") < 21
    assert g.coords("Villa Inexistente", "Barcelona") is None        # offline: no consulta
