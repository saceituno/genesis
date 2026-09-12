from datetime import date

from monitor.models import Inmueble
from monitor.vigencia import fecha_de, revisa

HOY = date(2026, 9, 12)


def inm(**kw):
    base = dict(fuente="Test", url="https://ejemplo.test/1", estado="Celebrándose")
    base.update(kw)
    return Inmueble(**base)


def test_lee_las_dos_formas_de_fecha():
    assert fecha_de("2026-09-14T18:00:00+02:00") == date(2026, 9, 14)
    assert fecha_de("14-09-2026") == date(2026, 9, 14)
    assert fecha_de("sin fecha") is None
    assert fecha_de(None) is None


def test_conserva_lo_que_sigue_abierto():
    assert revisa(inm(fecha_fin="2026-09-30T18:00:00+02:00"), HOY)[0]
    assert revisa(inm(estado="Próxima apertura"), HOY)[0]
    assert revisa(inm(estado="En venta", fecha_fin=None), HOY)[0]


def test_descarta_plazos_vencidos():
    vale, motivo = revisa(inm(fecha_fin="2026-09-11T18:00:00+02:00"), HOY)
    assert not vale and "plazo" in motivo


def test_descarta_convocatorias_de_años_anteriores():
    vale, motivo = revisa(inm(fecha_fin="2025-12-01T18:00:00+02:00"), HOY)
    assert not vale and "2025" in motivo


def test_descarta_estados_cerrados():
    for estado in ("Cancelada", "Desierta", "Vendido", "Concluida en Portal de Subastas"):
        vale, motivo = revisa(inm(estado=estado), HOY)
        assert not vale, estado


def test_descarta_por_el_texto_del_anuncio():
    vale, _ = revisa(inm(estado="", descripcion="El inmueble vendido en 2024 …"), HOY)
    assert not vale


def test_una_historia_registral_no_cierra_una_subasta_abierta():
    # 'vendido' aparece en la descripción, pero el estado dice que está abierta.
    assert revisa(inm(estado="Celebrándose",
                      descripcion="finca vendida por los anteriores titulares en 1998"), HOY)[0]
