from monitor.criteria import evalua
from monitor.models import Inmueble


def inmueble(**kw):
    base = dict(fuente="Test", url="https://ejemplo.test/1", tipo="casa",
                dormitorios=3, superficie_m2=120, terreno_m2=500, distancia_km=20)
    base.update(kw)
    return Inmueble(**base)


def test_cumple_todo():
    assert evalua(inmueble())[0] == "total"


def test_descarta_piso():
    assert evalua(inmueble(tipo="no_casa"))[0] == "descartado"


def test_descarta_por_umbrales():
    assert evalua(inmueble(superficie_m2=60))[0] == "descartado"
    assert evalua(inmueble(terreno_m2=250))[0] == "descartado"
    assert evalua(inmueble(dormitorios=1))[0] == "descartado"
    assert evalua(inmueble(distancia_km=55))[0] == "descartado"


def test_datos_incompletos_quedan_como_parcial():
    estado, faltan = evalua(inmueble(terreno_m2=None, dormitorios=None))
    assert estado == "parcial"
    assert set(faltan) == {"terreno", "dormitorios"}


def test_limites_exactos_se_aceptan():
    assert evalua(inmueble(superficie_m2=80, terreno_m2=300, dormitorios=2,
                           distancia_km=40))[0] == "total"
