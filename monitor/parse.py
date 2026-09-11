"""Extracción de datos estructurados a partir de texto libre en castellano/catalán.

Los anuncios de subasta (sobre todo los del BOE) describen el inmueble en prosa.
Aquí se normaliza todo a números para poder aplicar los criterios de búsqueda.
"""
from __future__ import annotations

import re
import unicodedata

__all__ = [
    "normaliza", "a_numero", "numero_en_letras", "extrae_superficie", "extrae_terreno",
    "extrae_dormitorios", "clasifica_tipo", "extrae_precio", "extrae_municipio",
    "titulo_lugar",
]

# --- utilidades -------------------------------------------------------------


def normaliza(texto: str | None) -> str:
    """Minúsculas, sin acentos y con espacios colapsados."""
    if not texto:
        return ""
    txt = unicodedata.normalize("NFKD", str(texto))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().lower()


def a_numero(valor: str | None) -> float | None:
    """Convierte '1.234,56' o '1234.56' o '120' a float."""
    if valor is None:
        return None
    txt = str(valor).strip()
    txt = re.sub(r"[^\d.,-]", "", txt)
    if not txt:
        return None
    if "," in txt and "." in txt:
        # formato español: el punto es millar
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        entero, _, dec = txt.partition(",")
        txt = f"{entero}.{dec}" if len(dec) <= 2 else entero + dec
    elif txt.count(".") == 1:
        entero, _, dec = txt.partition(".")
        if len(dec) == 3 and len(entero) <= 3:   # 1.234 -> millar
            txt = entero + dec
    else:
        txt = txt.replace(".", "")
    try:
        return float(txt)
    except ValueError:
        return None


# --- números escritos en letra ---------------------------------------------
# El BOE publica muchas superficies en letra ("superficie de ciento veinte
# metros cuadrados"). Se convierten a cifra para poder aplicar los criterios.

_LETRAS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30,
    "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
}
_IGNORAR = {"y", "de", "con"}


def numero_en_letras(texto: str) -> float | None:
    """Convierte 'ciento veinte' -> 120.0. Devuelve None si no reconoce nada."""
    total = parcial = 0
    visto = False
    for palabra in normaliza(texto).replace("-", " ").split():
        if palabra in _IGNORAR:
            continue
        if palabra == "mil":
            parcial = (parcial or 1) * 1000
            total += parcial
            parcial = 0
            visto = True
        elif palabra in ("millon", "millones"):
            total = (total + parcial or 1) * 1_000_000
            parcial = 0
            visto = True
        elif palabra in _LETRAS:
            parcial += _LETRAS[palabra]
            visto = True
        else:
            break
    return float(total + parcial) if visto else None


# --- superficies ------------------------------------------------------------

_UNIDAD = r"(?:m2|m²|metros? cuadrados?|mts?2|m\.?\s?c\.?)"
_NUM = r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)"

_RE_CONSTRUIDA = [
    re.compile(rf"superficie\s+(?:util|construida|total)?\s*(?:de\s+)?{_NUM}\s*{_UNIDAD}"),
    re.compile(rf"(?:construida|edificada|habitable)\s*(?:de\s+)?{_NUM}\s*{_UNIDAD}"),
    re.compile(rf"{_NUM}\s*{_UNIDAD}\s*(?:construidos?|utiles?|de vivienda)"),
]
_RE_TERRENO = [
    re.compile(rf"(?:parcela|solar|terreno|finca|jardin|patio)\s*(?:de\s+)?{_NUM}\s*{_UNIDAD}"),
    re.compile(rf"{_NUM}\s*{_UNIDAD}\s*de\s*(?:parcela|solar|terreno|jardin)"),
    re.compile(rf"superficie\s+de\s+(?:la\s+)?(?:parcela|solar|terreno)\s*(?:de\s+)?{_NUM}\s*{_UNIDAD}"),
]
_RE_GENERICA = re.compile(rf"{_NUM}\s*{_UNIDAD}")

_RE_LETRAS_CONSTRUIDA = re.compile(
    r"superficie(?:\s+(?:util|construida|total|edificada|de))*\s+"
    r"((?:[a-z]+\s+){1,8}?)(?:metros?\s+cuadrados?|m2)")
_RE_LETRAS_TERRENO = re.compile(
    r"(?:parcela|solar|terreno|finca|patio|jardin)\s+(?:de\s+)?"
    r"((?:[a-z]+\s+){1,8}?)(?:metros?\s+cuadrados?|m2)")



def _primero(patrones, texto: str) -> float | None:
    for pat in patrones:
        m = pat.search(texto)
        if m:
            val = a_numero(m.group(1))
            if val and 1 <= val <= 100_000:
                return val
    return None


def extrae_superficie(texto: str) -> float | None:
    """Superficie construida/útil en m²."""
    t = normaliza(texto)
    val = _primero(_RE_CONSTRUIDA, t)
    if val:
        return val
    val = _en_letras(_RE_LETRAS_CONSTRUIDA, t)
    if val:
        return val
    # Si sólo hay una cifra de superficie en todo el texto y no habla de parcela,
    # se asume construida.
    todas = _RE_GENERICA.findall(t)
    if len(todas) == 1 and not re.search(r"parcela|solar|terreno", t):
        return a_numero(todas[0])
    return None


def extrae_terreno(texto: str) -> float | None:
    """Superficie de parcela/terreno en m²."""
    t = normaliza(texto)
    return _primero(_RE_TERRENO, t) or _en_letras(_RE_LETRAS_TERRENO, t)


def _en_letras(patron, texto: str) -> float | None:
    for m in patron.finditer(texto):
        val = numero_en_letras(m.group(1))
        if val and 1 <= val <= 100_000:
            return val
    return None


# --- dormitorios ------------------------------------------------------------

_PALABRA_NUM = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
_RE_DORM = re.compile(
    r"(\d{1,2}|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*"
    r"(?:dormitorios?|habitaciones?|hab\.?\b|dorm\.?\b|estancias? dormitorio)"
)
_RE_DORM_INV = re.compile(r"(?:dormitorios?|habitaciones?)\s*[:\-]?\s*(\d{1,2})")


def extrae_dormitorios(texto: str) -> int | None:
    t = normaliza(texto)
    for m in (_RE_DORM.search(t), _RE_DORM_INV.search(t)):
        if not m:
            continue
        bruto = m.group(1)
        valor = _PALABRA_NUM.get(bruto, None)
        if valor is None:
            try:
                valor = int(bruto)
            except ValueError:
                continue
        if 0 < valor <= 20:
            return valor
    return None


# --- tipología --------------------------------------------------------------
# El lenguaje registral es traicionero: "piso tercero de LA CASA número 23"
# describe un piso, no una casa ("la casa" es el edificio). Por eso sólo cuentan
# como casa las expresiones inequívocas, y "casa" a secas no basta.

_CASA = (
    r"vivienda\s+unifamiliar", r"casa\s+unifamiliar", r"\bunifamiliar\b",
    r"chalet", r"chale\b", r"xalet", r"adosad", r"paread", r"\bmasia\b",
    r"bungalow", r"\bvilla\b", r"casa\s+de\s+pueblo", r"casa\s+rural",
    r"casa\s+de\s+campo", r"casa\s+de\s+labor", r"caseri", r"cortijo",
    r"casa\s+aislada", r"vivienda\s+aislada", r"casa\s+con\s+(?:jardin|terreno|patio|huerto)",
    r"casa\s+y\s+(?:corral|huerto)",
)
_NO_CASA = (
    r"\bpiso\b", r"apartamento", r"\batico\b", r"duplex", r"\bestudio\b", r"\bloft\b",
    r"plaza\s+de\s+(?:aparcamiento|garaje)", r"\bgaraje\b", r"\bparking\b",
    r"\baparcamiento\b", r"\btrastero\b", r"\balmacen\b", r"local\s+comercial",
    r"\blocal\b", r"nave\s+industrial", r"\boficina\b", r"\bdespacho\b",
    r"participacion\s+indivisa", r"cuota\s+indivisa", r"participacion\s+indivia",
    r"pieza\s+de\s+tierra", r"\bsolar\b", r"suelo\s+urbanizable",
    # "70, 2º 1ª" -> planta y puerta (normaliza() convierte º/ª en o/a)
    r"\d+\s*[ºªoa]\s*[,\-\s]\s*\d+\s*[ºªoa]\b",
    # Vocabulario de propiedad horizontal: describe elementos de un edificio.
    r"\bpuerta\s+(?:primera|segunda|tercera|cuarta|quinta|sexta|septima|octava|"
    r"novena|decima|\d+|[a-d]\b)",
    r"planta\s+(?:segunda|tercera|cuarta|quinta|sexta|septima|octava|novena|decima|"
    r"\d{1,2}\s*[ªº]?)\b",
    r"\bdepartamento\s+(?:numero\s+)?\w+", r"entidad\s+numero", r"elemento\s+numero",
    r"escalera\s+numero", r"parte\s+indivisa", r"\bcuota\b.{0,20}\bindivis",
)


def clasifica_tipo(texto: str) -> str:
    """Devuelve 'casa', 'no_casa' o 'desconocido'."""
    t = normaliza(texto)
    if any(re.search(p, t) for p in _CASA):
        return "casa"
    if any(re.search(p, t) for p in _NO_CASA):
        return "no_casa"
    return "desconocido"


# --- precio -----------------------------------------------------------------

_RE_PRECIO = re.compile(rf"{_NUM}\s*(?:€|euros?|eur\b)")


def extrae_precio(texto: str) -> float | None:
    t = normaliza(texto)
    m = _RE_PRECIO.search(t)
    if m:
        return a_numero(m.group(1))
    return None


# --- municipio --------------------------------------------------------------

_MINUSCULAS = {"de", "del", "la", "las", "los", "el", "i", "y", "d'", "de la", "dels"}


def titulo_lugar(nombre: str | None) -> str | None:
    """'SANTA COLOMA DE GRAMENET' -> 'Santa Coloma de Gramenet'."""
    if not nombre:
        return None
    nombre = " ".join(nombre.split())
    if not nombre.isupper() and not nombre.islower():
        return nombre                      # ya viene con mayúsculas razonables
    palabras = []
    for i, palabra in enumerate(nombre.lower().split()):
        palabras.append(palabra if i and palabra in _MINUSCULAS else palabra.capitalize())
    return " ".join(palabras)

_RE_MUNI = re.compile(r"\b\d{5}\s+([A-ZÁÉÍÓÚÑÇ][\wÀ-ÿ'’\.\- ]{2,40})")


def extrae_municipio(texto: str) -> str | None:
    """Intenta aislar el municipio de una dirección postal española."""
    if not texto:
        return None
    m = _RE_MUNI.search(texto)
    if m:
        return m.group(1).strip(" .,-")
    partes = [p.strip() for p in re.split(r"[,()]", texto) if p.strip()]
    if partes:
        cand = partes[-1]
        cand = re.sub(r"^\d{5}\s*", "", cand).strip()
        if 2 < len(cand) < 45 and not cand.isdigit():
            return cand
    return None
