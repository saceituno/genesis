import json

from monitor import store
from monitor.models import Inmueble


def casa(ref="A", fuente="BOE · Judicial", **kw):
    return Inmueble(fuente=fuente, url=f"https://ejemplo.test/{ref}", referencia=ref,
                    tipo="casa", superficie_m2=100, terreno_m2=400, dormitorios=3, **kw)


def test_alta_actualizacion_y_baja(tmp_path):
    ruta = tmp_path / "listings.json"
    estado, cambios = store.fusiona(store.carga(ruta), [casa("A"), casa("B")], ["BOE · Judicial"])
    store.guarda(estado, ruta)
    assert cambios["altas"] == 2 and cambios["activos"] == 2

    # Segunda pasada: A sigue, B desaparece.
    estado2, cambios2 = store.fusiona(json.loads(ruta.read_text()), [casa("A")],
                                      ["BOE · Judicial"])
    assert cambios2["altas"] == 0
    assert cambios2["bajas"] == 1
    bajas = [i for i in estado2["inmuebles"] if not i["activo"]]
    assert bajas[0]["referencia"] == "B"


def test_conserva_first_seen_y_datos_previos(tmp_path):
    ruta = tmp_path / "listings.json"
    estado, _ = store.fusiona(store.carga(ruta), [casa("A", imagen="https://img/1.jpg")], ["BOE · Judicial"])
    primero = estado["inmuebles"][0]["first_seen"]

    sin_imagen = casa("A")
    estado2, _ = store.fusiona(estado, [sin_imagen], ["BOE · Judicial"])
    guardado = estado2["inmuebles"][0]
    assert guardado["first_seen"] == primero
    assert guardado["imagen"] == "https://img/1.jpg"   # no se pisa con un vacío


def test_no_da_de_baja_fuentes_que_no_respondieron(tmp_path):
    estado, _ = store.fusiona({"inmuebles": []}, [casa("A"), casa("S", fuente="Servihabitat")],
                              ["BOE · Judicial", "Servihabitat"])
    # Pasada en la que Servihabitat falla: no aparece en fuentes_ok.
    estado2, cambios = store.fusiona(estado, [casa("A")], ["BOE · Judicial"])
    assert cambios["bajas"] == 0
    assert all(i["activo"] for i in estado2["inmuebles"])
