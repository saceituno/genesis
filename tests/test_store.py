import json

from monitor import store
from monitor.models import Inmueble


def casa(ref="A", fuente="BOE · Judicial", origen="BOE", **kw):
    return Inmueble(fuente=fuente, origen=origen, url=f"https://ejemplo.test/{ref}",
                    referencia=ref, tipo="casa", superficie_m2=100, terreno_m2=400,
                    dormitorios=3, **kw)


def test_alta_actualizacion_y_baja(tmp_path):
    ruta = tmp_path / "listings.json"
    estado, cambios = store.fusiona(store.carga(ruta), [casa("A"), casa("B")], ["BOE"])
    store.guarda(estado, ruta)
    assert cambios["altas"] == 2 and cambios["activos"] == 2

    # Segunda pasada: A sigue, B desaparece.
    estado2, cambios2 = store.fusiona(json.loads(ruta.read_text()), [casa("A")], ["BOE"])
    assert cambios2["altas"] == 0
    assert cambios2["bajas"] == 1
    bajas = [i for i in estado2["inmuebles"] if not i["activo"]]
    assert bajas[0]["referencia"] == "B"


def test_baja_aunque_cambie_la_etiqueta_de_la_plataforma(tmp_path):
    """Una subasta de la AEAT desaparecida se da de baja aunque esa pasada sólo
    haya traído subastas judiciales: lo que manda es la fuente, no la etiqueta."""
    estado, _ = store.fusiona({"inmuebles": []},
                              [casa("AEAT1", fuente="BOE · Agencia Tributaria")], ["BOE"])
    estado2, cambios = store.fusiona(estado, [casa("JUD1", fuente="BOE · Judicial")], ["BOE"])
    assert cambios["bajas"] == 1
    bajas = [i for i in estado2["inmuebles"] if not i["activo"]]
    assert bajas[0]["referencia"] == "AEAT1"


def test_conserva_first_seen_y_datos_previos(tmp_path):
    ruta = tmp_path / "listings.json"
    estado, _ = store.fusiona(store.carga(ruta), [casa("A", imagen="https://img/1.jpg")], ["BOE"])
    primero = estado["inmuebles"][0]["first_seen"]

    estado2, _ = store.fusiona(estado, [casa("A")], ["BOE"])
    guardado = estado2["inmuebles"][0]
    assert guardado["first_seen"] == primero
    assert guardado["imagen"] == "https://img/1.jpg"   # no se pisa con un vacío


def test_no_da_de_baja_fuentes_que_no_respondieron(tmp_path):
    estado, _ = store.fusiona({"inmuebles": []},
                              [casa("A"), casa("S", fuente="Servihabitat", origen="Servihabitat")],
                              ["BOE", "Servihabitat"])
    # Pasada en la que Servihabitat falla: no aparece en los orígenes que respondieron.
    estado2, cambios = store.fusiona(estado, [casa("A")], ["BOE"])
    assert cambios["bajas"] == 0
    assert all(i["activo"] for i in estado2["inmuebles"])
