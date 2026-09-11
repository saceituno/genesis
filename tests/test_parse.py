from monitor import parse


def test_superficie_construida_y_parcela():
    t = ("URBANA. Vivienda unifamiliar aislada con superficie construida de 152,45 m2 "
         "sobre una parcela de 1.200 m2.")
    assert parse.extrae_superficie(t) == 152.45
    assert parse.extrae_terreno(t) == 1200.0


def test_superficie_unica_sin_parcela():
    assert parse.extrae_superficie("Casa de 95 m2 en el centro") == 95.0


def test_no_confunde_parcela_con_construida():
    t = "Solar de 800 m2"
    assert parse.extrae_superficie(t) is None
    assert parse.extrae_terreno(t) == 800.0


def test_dormitorios():
    assert parse.extrae_dormitorios("Casa con tres dormitorios y 2 baños") == 3
    assert parse.extrae_dormitorios("4 hab. 2 baños") == 4
    assert parse.extrae_dormitorios("Habitaciones: 5") == 5
    assert parse.extrae_dormitorios("Local comercial diáfano") is None


def test_clasifica_tipo():
    assert parse.clasifica_tipo("CHALET ADOSADO CON JARDÍN") == "casa"
    assert parse.clasifica_tipo("Vivienda unifamiliar") == "casa"
    assert parse.clasifica_tipo("Piso en planta 3ª puerta 2ª") == "no_casa"
    assert parse.clasifica_tipo("Plaza de garaje número 5") == "no_casa"
    assert parse.clasifica_tipo("Finca registral 1234") == "desconocido"


def test_numeros_en_formato_espanol():
    assert parse.a_numero("1.234,56") == 1234.56
    assert parse.a_numero("185.000,00 €") == 185000.0
    assert parse.a_numero("1.200") == 1200.0
    assert parse.a_numero("") is None


def test_precio_y_municipio():
    assert parse.extrae_precio("Valor de subasta: 185.000,00 €") == 185000.0
    assert parse.extrae_municipio("Calle Mayor 3, 08290 Cerdanyola del Vallès (Barcelona)") \
        == "Cerdanyola del Vallès"
