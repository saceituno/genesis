"""QA del listado generado: comprueba que el resultado es usable, no sólo que no peta.

Se ejecuta después de cada pasada del monitor y falla si el listado no cumple
las condiciones mínimas para poder publicarse.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "data" / "listings.json"


def main() -> int:
    if not RUTA.exists():
        print("QA ✗ no existe data/listings.json")
        return 1
    datos = json.loads(RUTA.read_text("utf-8"))
    inmuebles = datos.get("inmuebles", [])
    activos = [i for i in inmuebles if i.get("activo", True)]
    fallos: list[str] = []
    avisos: list[str] = []

    print(f"Generado: {datos.get('generado')}")
    print(f"Inmuebles en el fichero: {len(inmuebles)} (vigentes: {len(activos)})")

    if not activos:
        fallos.append("el listado no tiene ningún inmueble vigente")

    fuentes = Counter(i.get("fuente") for i in activos)
    print("Por plataforma:", dict(fuentes))
    if len(fuentes) < 2:
        avisos.append(f"sólo hay {len(fuentes)} plataforma(s) con resultados")

    sin_url = [i for i in activos if not i.get("url", "").startswith("http")]
    if sin_url:
        fallos.append(f"{len(sin_url)} inmuebles sin enlace válido")

    sin_fuente = [i for i in activos if not i.get("fuente")]
    if sin_fuente:
        fallos.append(f"{len(sin_fuente)} inmuebles sin plataforma de origen")

    ids = [i.get("id") for i in inmuebles]
    if len(ids) != len(set(ids)):
        fallos.append("hay identificadores duplicados")

    radio = (datos.get("criterios") or {}).get("radio_km", 40)
    lejos = [i for i in activos if (i.get("distancia_km") or 0) > radio]
    if lejos:
        fallos.append(f"{len(lejos)} inmuebles fuera del radio de {radio} km")

    # La distancia es el criterio que no se puede verificar a ojo en la ficha:
    # si falla la geolocalización, el listado deja de estar acotado a los 40 km.
    sin_ubicar = [i for i in activos if i.get("distancia_km") is None]
    if len(sin_ubicar) > len(activos) * 0.4:
        fallos.append(f"{len(sin_ubicar)} de {len(activos)} inmuebles sin geolocalizar: "
                      "el radio no se está aplicando")
    elif sin_ubicar:
        avisos.append(f"{len(sin_ubicar)} inmuebles sin geolocalizar")

    for campo, minimo in (("superficie_m2", 80), ("terreno_m2", 300), ("dormitorios", 2)):
        malos = [i for i in activos if i.get(campo) is not None and i[campo] < minimo]
        if malos:
            fallos.append(f"{len(malos)} inmuebles incumplen {campo} >= {minimo}")

    completos = [i for i in activos if i.get("cumple") == "total"]
    con_imagen = [i for i in activos if i.get("imagen")]
    con_precio = [i for i in activos if i.get("precio") is not None]
    print(f"Criterios completos: {len(completos)} · con imagen: {len(con_imagen)} · "
          f"con precio: {len(con_precio)}")
    municipios = Counter(i.get("municipio") for i in activos)
    print("Municipios top:", municipios.most_common(8))

    for a in avisos:
        print(f"QA ⚠ {a}")
    for f in fallos:
        print(f"QA ✗ {f}")
    if fallos:
        return 1
    print("QA ✓ listado operativo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
