# Monitor de subastas de casas · 40 km de Barcelona

Sistema ligero que revisa de forma recurrente los portales de subastas y de
servicers inmobiliarios, se queda sólo con las **casas en proceso abierto** que
cumplen los criterios de búsqueda y mantiene un listado con el enlace a cada
ficha original y la plataforma de la que procede.

**Listado:** `index.html` — un botón, *Generar búsquedas*, carga los resultados.
Funciona igual abriéndolo con doble clic que servido por HTTP.
**Datos:** `data/listings.json` (estado completo) y `data/listings.js` (lo que lee
la página).

---

## Criterios de búsqueda

| Criterio | Valor |
|---|---|
| Tipología | Casa / chalet / unifamiliar / adosado / masía (excluye pisos, locales, garajes) |
| Dormitorios | ≥ 2 |
| Superficie construida | ≥ 80 m² |
| Parcela / terreno | ≥ 300 m² |
| Distancia | ≤ 40 km de Plaça de Catalunya (distancia ortodrómica) |

Se ajustan en `monitor/config.py`.

### Sólo procesos abiertos

Un listado de oportunidades sólo sirve si lo que muestra se puede pujar o comprar
hoy, así que se descarta todo lo que tenga alguna señal de estar cerrado:

- un estado que lo diga (cancelada, desierta, adjudicada, vendido, reservado…),
- una fecha de conclusión ya pasada,
- una convocatoria de un año anterior,
- un anuncio que se declare fuera de plazo o no disponible.

La comprobación se hace dos veces: al recoger, para no gastar peticiones en lo
que ya está cerrado, y al guardar, para que un plazo que venció ayer salga del
listado aunque el portal todavía no lo haya retirado.

Ante la falta de información se conserva: muchas fichas no publican fechas y
retirarlas por silencio vaciaría el listado.

### Total, parcial y descartado

Muchos anuncios de subasta —sobre todo los judiciales— no publican dormitorios
ni superficie de parcela. Descartar por silencio dejaría fuera oportunidades
reales, así que cada inmueble se clasifica en:

- **total**: todos los criterios confirmados con dato explícito.
- **parcial**: ningún criterio incumple, pero falta algún dato por verificar en
  la ficha original. Aparece marcado en la interfaz con el aviso de qué falta.
- **descartado**: algún criterio se incumple con dato explícito. No se guarda.

La interfaz marca cada ficha con lo que falta por verificar.

---

## Plataformas

| Plataforma | Qué aporta | Cómo se lee |
|---|---|---|
| **BOE · Judicial** | Subastas de juzgados | Portal de Subastas (`subastas.boe.es`), formulario de búsqueda avanzada |
| **BOE · Agencia Tributaria** | Embargos de la AEAT | ídem |
| **BOE · Seguridad Social** | Embargos de la TGSS | ídem (se detecta por la autoridad gestora) |
| **BOE · Notarial** | Subastas notariales | ídem |
| **BOE · otras administraciones** | Resto de subastas administrativas | ídem |
| **Servihabitat** | Cartera de adjudicados en venta directa | Fichas con JSON-LD schema.org |

El Portal de Subastas del BOE es la fuente oficial única de las subastas
públicas españolas: los cinco orígenes anteriores se publican ahí, de modo que
una sola pasada cubre juzgados, AEAT, Seguridad Social y notarías. El origen
concreto de cada anuncio se guarda en el campo `fuente` y la autoridad gestora
(juzgado, unidad de recaudación, TGSS…) en `organismo`.

Qué orígenes aparecen cada día depende de lo que haya publicado en ese momento y
supere los criterios: una pasada puede traer sólo judiciales y la siguiente
incluir AEAT o Seguridad Social. El monitor consulta siempre los cinco; que una
etiqueta no aparezca en el listado significa que ese día no había casas suyas
dentro del radio, no que la fuente esté desactivada.

Portales descartados en el reconocimiento previo, con el motivo:

- **Haya Real Estate** — el dominio responde 522 (servicio caído).
- **Sareb** — protegido con Imperva/Incapsula, no sirve HTML.
- **Solvia y Altamira** — aplicaciones Angular/Vite sin renderizado en servidor;
  su `robots.txt` prohíbe además las rutas de resultados (`/api/`, `/ajax/`,
  `/resultados`). Habría que usar navegador headless contra endpoints vetados.
- **Aliseda** — su sitemap publica 5.542 fichas sin tipología ni provincia en la
  URL; recorrerlas todas cada día no compensa para el alcance de este monitor.

Añadir una plataforma nueva es escribir un módulo en `monitor/sources/` que
devuelva objetos `Inmueble` y registrarlo en `monitor/sources/__init__.py`.

---

## Uso

```bash
pip install -r requirements.txt
python -m monitor.run -v            # pasada completa
python -m monitor.run --fuente BOE  # sólo una plataforma
python -m monitor.run --sin-red     # re-evalúa el JSON ya guardado
python tools/qa.py                  # comprueba que el listado es publicable
python -m pytest tests -q           # pruebas del parseo y del almacén
```

Para ver la interfaz basta con abrir `index.html` en el navegador y pulsar
**Generar búsquedas**; no hace falta servidor. Los datos se cargan inyectando
`data/listings.js`, porque al abrir la página desde el disco el navegador
bloquea `fetch()` por CORS y el listado aparecía vacío.

### Ejecución automática

`.github/workflows/monitor.yml` ejecuta una pasada diaria (07:17 hora
peninsular), pasa el QA y hace commit de `data/` sólo si hay cambios. También se
puede lanzar a mano desde la pestaña **Actions → monitor-subastas → Run
workflow**.

---

## Cómo se mantiene el listado

`data/listings.json` es el estado completo, no una foto de la última pasada:

- Un inmueble nuevo se da de **alta** con `first_seen`.
- Si vuelve a aparecer, se actualiza `last_seen` y se completan los campos que
  antes faltaban (un dato ya conocido nunca se pisa con un vacío).
- Si desaparece de su portal, se marca `activo: false` con `baja_detectada` en
  vez de borrarse, para conservar el histórico. Sólo se dan de baja inmuebles de
  plataformas que respondieron en esa pasada, de modo que una caída del portal
  no vacía el listado.

La interfaz muestra los vigentes y destaca como **NUEVO** lo detectado en los
últimos 7 días.

---

## Geolocalización

Los portales dan municipio, no coordenadas. Se geocodifica una vez por municipio
contra **Nominatim (OpenStreetMap)**, respetando su límite de una petición por
segundo, y el resultado se guarda en `data/geocache.json`. Ningún dato de
ubicación es inventado: si un municipio no se puede geocodificar, el inmueble se
conserva con `distancia_km: null` y queda marcado como pendiente de ubicar.

La búsqueda en el BOE se limita a la provincia de Barcelona porque el radio de
40 km no alcanza ningún municipio de Girona ni de Tarragona.

---

## Cortesía y robots.txt

El cliente HTTP se identifica con un User-Agent propio y espera 1,2 s entre
peticiones al mismo host, con reintentos y espera exponencial ante 429/5xx.

**A tener en cuenta:** el `robots.txt` de `subastas.boe.es` contiene
`Disallow: /` (el portal no quiere ser indexado por buscadores, dado que cada
búsqueda genera URLs distintas). Este monitor hace unas pocas decenas de
peticiones al día, muy por debajo de un rastreo, pero la decisión de consultarlo
es tuya: ejecutando con `--robots` (o `RESPETAR_ROBOTS=1`) el monitor obedece el
`robots.txt` de cada portal y, en ese modo, el BOE queda fuera y el listado se
alimenta sólo del resto de plataformas.

---

## Estructura

```
monitor/
  config.py      criterios, radio y ritmo de peticiones
  http.py        sesión con reintentos, ritmo por host y robots.txt
  parse.py       extracción de m², dormitorios, precio y tipología del texto
  criteria.py    total / parcial / descartado
  geo.py         haversine + geocodificación cacheada
  models.py      el objeto Inmueble
  store.py       fusión incremental del listado
  run.py         orquestador
  sources/       boe.py, servihabitat.py
tools/
  qa.py          control de calidad del listado
  qa_ui.py       QA de la interfaz con navegador real (file:// y http://)
  recon*.py      reconocimiento de los portales (histórico de la investigación)
tests/           pruebas del parseo, criterios, almacén y distancias
  vigencia.py    ¿sigue el proceso abierto?
index.html       interfaz: un botón y el listado
assets/          estilos y lógica del listado (sin dependencias)
data/            listings.json (estado) · listings.js (lo que lee la web) · geocache.json
```
