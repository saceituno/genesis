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


def test_lenguaje_registral_no_confunde_piso_con_casa():
    # "la casa número 23" es el edificio, no una vivienda unifamiliar.
    assert parse.clasifica_tipo(
        "PISO TERCERO PUERTA PRIMERA, EN LA TERCERA PLANTA ALTA DE LA CASA "
        "SEÑALADA CON EL NÚMERO VEINTITRÉS") == "no_casa"
    assert parse.clasifica_tipo(
        "Elemento número quince.- Piso Segundo, Puerta Tercera, vivienda de la "
        "casa número 75") == "no_casa"
    assert parse.clasifica_tipo("ALMACEN SITO EN LA PLANTA BAJA DE LA CASA NÚMERO 110") == "no_casa"
    assert parse.clasifica_tipo("RÚSTICA. PIEZA DE TIERRA CAMPO") == "no_casa"
    assert parse.clasifica_tipo("Finca urbana en Calle Monturiol 117, 2º, 1º") == "no_casa"
    assert parse.clasifica_tipo("Vivienda unifamiliar de planta baja en Sant Quirze") == "casa"
    assert parse.clasifica_tipo("MASIA CON TERRENO") == "casa"


def test_numeros_escritos_en_letra():
    assert parse.numero_en_letras("ciento veinte") == 120
    assert parse.numero_en_letras("catorce mil quinientos") == 14500
    assert parse.numero_en_letras("noventa y cinco") == 95
    assert parse.numero_en_letras("no es un numero") is None
    assert parse.extrae_superficie(
        "TIENE UNA SUPERFICIE DE CIENTO VEINTE METROS CUADRADOS") == 120
    assert parse.extrae_terreno(
        "sobre una parcela de mil doscientos metros cuadrados") == 1200


def test_titulo_lugar():
    assert parse.titulo_lugar("SANTA COLOMA DE GRAMENET") == "Santa Coloma de Gramenet"
    assert parse.titulo_lugar("EL PRAT DE LLOBREGAT") == "El Prat de Llobregat"
    assert parse.titulo_lugar("Sant Cugat del Vallès") == "Sant Cugat del Vallès"
    assert parse.titulo_lugar(None) is None
