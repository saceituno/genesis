"""Extracción de datos estructurados a partir de texto libre en castellano/catalán.

Los anuncios de subasta (sobre todo los del BOE) describen el inmueble en prosa.
Aquí se normaliza todo a números para poder aplicar los criterios de búsqueda.
"""
from __future__ import annotations

import re
import unicodedata

__all__ = [
    "normaliza", "a_numero", "extrae_superficie", "extrae_terreno",
    "extrae_dormitorios", "clasifica_tipo", "extrae_precio", "extrae_municipio",
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
    # Si sólo hay una cifra de superficie en todo el texto y no habla de parcela,
    # se asume construida.
    todas = _RE_GENERICA.findall(t)
    if len(todas) == 1 and not re.search(r"parcela|solar|terreno", t):
        return a_numero(todas[0])
    return None


def extrae_terreno(texto: str) -> float | None:
    """Superficie de parcela/terreno en m²."""
    return _primero(_RE_TERRENO, normaliza(texto))


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

_CASA = (
    "casa", "chalet", "chalé", "xalet", "unifamiliar", "adosad", "paread",
    "masia", "masía", "torre", "villa", "bungalow", "caseri", "casa de pueblo",
    "vivienda aislada", "casa rural", "cortijo", "finca con vivienda", "mas ",
)
_NO_CASA = (
    "piso", "apartamento", "atico", "duplex", "estudio", "loft", "local comercial",
    "plaza de garaje", "plaza de aparcamiento", "trastero", "nave industrial",
    "oficina", "solar sin edificar", "suelo urbanizable", "finca rustica sin",
    "participacion indivisa", "garaje", "parking",
)


def clasifica_tipo(texto: str) -> str:
    """Devuelve 'casa', 'no_casa' o 'desconocido'."""
    t = normaliza(texto)
    if any(p in t for p in _CASA):
        # 'casa' puede aparecer dentro de otras palabras; se prioriza casa salvo
        # que el texto declare explícitamente un piso/apartamento como objeto.
        if re.search(r"\b(piso|apartamento|atico)\b", t) and not re.search(
            r"\b(casa|chalet|xalet|unifamiliar|adosad|paread|masia|torre|villa)\b", t
        ):
            return "no_casa"
        return "casa"
    if any(p in t for p in _NO_CASA):
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
