from monitor.sources.servihabitat import RE_FICHA, RE_ZONA, Servihabitat


def test_reconoce_fichas_y_zonas():
    assert RE_FICHA.match("/es/venta/vivienda-casa/barcelona-garraf-cubelles/60444602")
    assert RE_ZONA.match("/es/venta/vivienda-casa/barcelona-garraf")
    assert not RE_FICHA.match("/es/venta/vivienda/barcelona")          # pisos, no casas


def test_usa_la_tipologia_declarada_por_el_portal():
    assert Servihabitat._tipo({"accommodationCategory": "Casa"}, "") == "casa"
    assert Servihabitat._tipo({"accommodationCategory": "Piso"}, "") == "no_casa"
    # Sin categoría se recurre al texto.
    assert Servihabitat._tipo({}, "Vivienda unifamiliar con jardín") == "casa"


def test_prefiltro_por_distancia():
    class GeoFalso:
        def distancia_a_barcelona(self, nombre, provincia=None):
            return {"Cubelles": 38.0, "Berga": 90.0}.get(nombre)

    s = Servihabitat(geo=GeoFalso())
    s._anota_nombre("barcelona-garraf-cubelles", "Viviendas en venta en Cubelles")
    s._anota_nombre("barcelona-bergueda-berga", "Viviendas en venta en Berga")
    assert s._cerca("barcelona-garraf-cubelles") is True
    assert s._cerca("barcelona-bergueda-berga") is False
    # Municipio sin nombre conocido: ante la duda, se descarga.
    assert s._cerca("barcelona-osona-desconocido") is True
    # Una comarca entera nunca se descarta por este prefiltro.
    assert s._cerca("barcelona-bergueda") is True
