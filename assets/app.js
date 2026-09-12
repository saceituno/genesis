/* Monitor de subastas — listado.
 *
 * Los datos no se piden con fetch() a propósito: al abrir la página desde el
 * disco (file://) el navegador bloquea esas peticiones por CORS y el listado
 * aparecía vacío. Un <script> inyectado bajo demanda no tiene esa limitación,
 * y de paso es lo que activa el botón «Generar búsquedas». */
(() => {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const eur = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const num = new Intl.NumberFormat("es-ES");
  const FUENTE_DATOS = "data/listings.js";

  const boton = $("#buscar"), estado = $("#estado"), grid = $("#grid"), pie = $("#pie");

  boton.addEventListener("click", buscar);

  function buscar() {
    boton.disabled = true;
    boton.textContent = "Buscando…";
    estado.className = "estado trabajando";
    estado.textContent = "Cargando los resultados de la última recogida…";
    grid.innerHTML = "";
    pie.hidden = true;

    const script = document.createElement("script");
    script.src = `${FUENTE_DATOS}?v=${Date.now()}`;   // sin caché: siempre lo último
    script.onload = () => { listo(); pinta(window.SUBASTAS); };
    script.onerror = () => { listo(); falla(); };
    document.head.appendChild(script);
  }

  function listo() {
    boton.disabled = false;
    boton.textContent = "Actualizar búsqueda";
  }

  function falla() {
    estado.className = "estado error";
    estado.innerHTML = `No se encuentra <code>${FUENTE_DATOS}</code>. ` +
      "Ejecuta el monitor (<code>python -m monitor.run</code>) para generarlo.";
  }

  function pinta(datos) {
    const casas = (datos && datos.inmuebles) || [];
    if (!casas.length) {
      estado.className = "estado vacio";
      estado.textContent = "Ahora mismo no hay ninguna vivienda con proceso abierto que cumpla los criterios.";
      return;
    }
    estado.className = "estado ok";
    estado.innerHTML = `<b>${casas.length}</b> viviendas en proceso abierto · ` +
      `${plataformas(casas)} · datos del ${fecha(datos.generado)}`;
    grid.innerHTML = casas.map(tarjeta).join("");
    pie.hidden = false;
  }

  const plataformas = (casas) => {
    const n = new Set(casas.map((c) => c.fuente)).size;
    return `${n} plataforma${n === 1 ? "" : "s"}`;
  };

  const fecha = (iso) => iso
    ? new Date(iso).toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
    : "fecha desconocida";

  function tarjeta(d) {
    const dato = (valor, texto, falta) => valor
      ? `<span class="dato">${texto}</span>`
      : `<span class="dato falta">${falta}</span>`;
    return `
    <a class="card" href="${esc(d.url)}" target="_blank" rel="noopener">
      <div class="foto">
        <div class="sinfoto"><span>⌂</span>${esc(d.municipio || "Sin imagen")}</div>
        ${d.imagen
          /* El marcador va debajo: si la foto del portal no carga, queda a la vista. */
          ? `<img loading="lazy" alt="" src="${esc(d.imagen)}" onerror="this.remove()">`
          : ""}
        <span class="badge">${esc(d.fuente)}</span>
      </div>
      <div class="cuerpo">
        <p class="precio">${d.precio != null ? eur.format(d.precio) : "Precio n/d"}
          <small>${esc(d.estado || "")}</small></p>
        <p class="titulo">${esc(d.titulo || d.direccion || "Inmueble")}</p>
        <p class="ubi">${esc(d.municipio || d.provincia || "Ubicación n/d")}${
          d.distancia_km != null ? ` · a ${d.distancia_km} km` : ""}</p>
        <p class="datos">
          ${dato(d.superficie_m2, `${num.format(d.superficie_m2 || 0)} m² const.`, "sup. n/d")}
          ${dato(d.terreno_m2, `${num.format(d.terreno_m2 || 0)} m² parcela`, "parcela n/d")}
          ${dato(d.dormitorios, `${d.dormitorios} dorm.`, "dorm. n/d")}
        </p>
        ${d.fecha_fin ? `<p class="plazo">Cierra el ${fecha(d.fecha_fin)}</p>` : ""}
      </div>
    </a>`;
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
})();
