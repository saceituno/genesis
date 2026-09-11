/* Monitor de subastas — capa de presentación. Lee data/listings.json y filtra en cliente. */
(() => {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const eur = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const num = new Intl.NumberFormat("es-ES");

  const estado = {
    datos: [], fuentes: [], generado: null,
    f: { texto: "", muni: "", pmin: null, pmax: null, dist: 40, orden: "distancia",
         fuentes: new Set(), verificados: false, nuevos: false },
  };

  const DIAS_NUEVO = 7;
  const esNuevo = (d) => d.first_seen &&
    (Date.now() - Date.parse(d.first_seen)) / 86400000 <= DIAS_NUEVO;

  // ---------------------------------------------------------------- carga
  async function init() {
    let json;
    try {
      const r = await fetch("data/listings.json", { cache: "no-cache" });
      if (!r.ok) throw new Error(r.status);
      json = await r.json();
    } catch (e) {
      $("#resumen").textContent = "No se ha podido cargar data/listings.json. Ejecuta el monitor para generarlo.";
      return;
    }
    estado.datos = (json.inmuebles || []).filter((d) => d.activo !== false);
    estado.fuentes = json.fuentes && json.fuentes.length
      ? json.fuentes : [...new Set(estado.datos.map((d) => d.fuente))].sort();
    estado.generado = json.generado;
    montaFiltros();
    pinta();
  }

  function montaFiltros() {
    const munis = [...new Set(estado.datos.map((d) => d.municipio).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "es"));
    $("#f-muni").insertAdjacentHTML("beforeend",
      munis.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join(""));

    const usadas = [...new Set(estado.datos.map((d) => d.fuente))].sort();
    $("#f-fuentes").innerHTML = usadas.map((f) =>
      `<button class="chip" data-fuente="${esc(f)}" aria-pressed="false">${esc(f)}</button>`).join("");

    $("#filtros").hidden = false;
    $("#meta").hidden = false;

    $("#f-texto").addEventListener("input", (e) => { estado.f.texto = e.target.value.trim().toLowerCase(); pinta(); });
    $("#f-muni").addEventListener("change", (e) => { estado.f.muni = e.target.value; pinta(); });
    $("#f-pmin").addEventListener("input", (e) => { estado.f.pmin = e.target.value ? +e.target.value : null; pinta(); });
    $("#f-pmax").addEventListener("input", (e) => { estado.f.pmax = e.target.value ? +e.target.value : null; pinta(); });
    $("#f-dist").addEventListener("input", (e) => {
      estado.f.dist = +e.target.value; $("#f-dist-val").textContent = e.target.value; pinta();
    });
    $("#f-orden").addEventListener("change", (e) => { estado.f.orden = e.target.value; pinta(); });
    $("#f-fuentes").addEventListener("click", (e) => {
      const b = e.target.closest("[data-fuente]"); if (!b) return;
      const f = b.dataset.fuente;
      estado.f.fuentes.has(f) ? estado.f.fuentes.delete(f) : estado.f.fuentes.add(f);
      b.setAttribute("aria-pressed", estado.f.fuentes.has(f));
      pinta();
    });
    for (const [id, clave] of [["#f-verificados", "verificados"], ["#f-nuevos", "nuevos"]]) {
      $(id).addEventListener("click", (e) => {
        estado.f[clave] = !estado.f[clave];
        e.currentTarget.setAttribute("aria-pressed", estado.f[clave]);
        pinta();
      });
    }
    $("#f-reset").addEventListener("click", () => {
      estado.f = { texto: "", muni: "", pmin: null, pmax: null, dist: 40, orden: "distancia",
                   fuentes: new Set(), verificados: false, nuevos: false };
      $("#f-texto").value = ""; $("#f-muni").value = ""; $("#f-pmin").value = ""; $("#f-pmax").value = "";
      $("#f-dist").value = 40; $("#f-dist-val").textContent = "40"; $("#f-orden").value = "distancia";
      document.querySelectorAll('.chip[aria-pressed="true"]').forEach((c) => c.setAttribute("aria-pressed", "false"));
      pinta();
    });
    $("#overlay").addEventListener("click", cierraPanel);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") cierraPanel(); });
  }

  // ---------------------------------------------------------------- filtrado
  function filtra() {
    const f = estado.f;
    return estado.datos.filter((d) => {
      if (f.muni && d.municipio !== f.muni) return false;
      if (f.fuentes.size && !f.fuentes.has(d.fuente)) return false;
      if (f.verificados && d.cumple !== "total") return false;
      if (f.nuevos && !esNuevo(d)) return false;
      if (d.distancia_km != null && d.distancia_km > f.dist) return false;
      if (f.pmin != null && (d.precio == null || d.precio < f.pmin)) return false;
      if (f.pmax != null && (d.precio == null || d.precio > f.pmax)) return false;
      if (f.texto) {
        const blob = [d.titulo, d.municipio, d.provincia, d.direccion, d.referencia,
                      d.fuente, d.organismo, d.descripcion].filter(Boolean).join(" ").toLowerCase();
        if (!blob.includes(f.texto)) return false;
      }
      return true;
    });
  }

  function ordena(lista) {
    const c = { distancia: (a, b) => (a.distancia_km ?? 1e9) - (b.distancia_km ?? 1e9),
      "precio-asc": (a, b) => (a.precio ?? 1e12) - (b.precio ?? 1e12),
      "precio-desc": (a, b) => (b.precio ?? -1) - (a.precio ?? -1),
      nuevos: (a, b) => Date.parse(b.first_seen || 0) - Date.parse(a.first_seen || 0),
      superficie: (a, b) => (b.superficie_m2 ?? -1) - (a.superficie_m2 ?? -1) };
    return lista.sort(c[estado.f.orden] || c.distancia);
  }

  // ---------------------------------------------------------------- pintado
  function pinta() {
    const lista = ordena(filtra());
    const total = estado.datos.length;
    const nuevos = estado.datos.filter(esNuevo).length;
    const completos = estado.datos.filter((d) => d.cumple === "total").length;

    $("#resumen").innerHTML =
      `<b>${total}</b> inmuebles vigentes · <b>${completos}</b> con todos los criterios confirmados · ` +
      `<b>${nuevos}</b> nuevos esta semana · ${estado.fuentes.length} plataformas`;
    $("#contador").textContent = `${lista.length} resultado${lista.length === 1 ? "" : "s"}`;
    $("#actualizado").textContent = estado.generado
      ? "Actualizado " + new Date(estado.generado).toLocaleString("es-ES",
          { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

    const grid = $("#grid");
    grid.innerHTML = lista.map(tarjeta).join("");
    grid.querySelectorAll("[data-id]").forEach((el) =>
      el.addEventListener("click", () => abrePanel(el.dataset.id)));
    $("#vacio").hidden = lista.length > 0;
    $("#vacio").textContent = lista.length ? "" : "Ningún inmueble cumple estos filtros.";
  }

  function tarjeta(d) {
    const foto = d.imagen
      ? `<img loading="lazy" src="${esc(d.imagen)}" alt="${esc(d.titulo || "Inmueble")}"
             onerror="this.remove()">`
      : `<div class="sinfoto"><span>⌂</span>${esc(d.municipio || "Sin imagen")}</div>`;
    const chips = [
      d.superficie_m2 ? `<span class="dato">${num.format(d.superficie_m2)} m² const.</span>`
                      : `<span class="dato falta">sup. n/d</span>`,
      d.terreno_m2 ? `<span class="dato">${num.format(d.terreno_m2)} m² parcela</span>`
                   : `<span class="dato falta">parcela n/d</span>`,
      d.dormitorios ? `<span class="dato">${d.dormitorios} dorm.</span>`
                    : `<span class="dato falta">dorm. n/d</span>`,
    ].join("");
    return `
    <article class="card" data-id="${d.id}">
      <div class="foto">
        ${foto}
        <div class="badges">
          <span class="badge">${esc(d.fuente)}</span>
          ${esNuevo(d) ? '<span class="badge nuevo">NUEVO</span>' : ""}
          ${d.cumple === "parcial" ? '<span class="badge parcial">DATOS PARCIALES</span>' : ""}
        </div>
      </div>
      <div class="cuerpo">
        <div class="precio">${d.precio != null ? eur.format(d.precio) : "Precio n/d"}
          <small>${esc(d.estado || d.organismo || "")}</small></div>
        <div class="titulo">${esc(d.titulo || d.direccion || "Inmueble")}</div>
        <div class="ubi">📍 ${esc(d.municipio || d.provincia || "Ubicación n/d")}${
          d.distancia_km != null ? ` · ${d.distancia_km} km` : ""}</div>
        <div class="datos">${chips}</div>
      </div>
    </article>`;
  }

  // ---------------------------------------------------------------- ficha
  function abrePanel(id) {
    const d = estado.datos.find((x) => x.id === id);
    if (!d) return;
    const fila = (k, v) => v || v === 0 ? `<tr><th>${k}</th><td>${v}</td></tr>` : "";
    $("#panel-in").innerHTML = `
      <button class="cerrar" id="btn-cerrar" aria-label="Cerrar">×</button>
      <span class="badge" style="position:static;display:inline-block">${esc(d.fuente)}</span>
      <h2>${esc(d.titulo || d.direccion || "Inmueble")}</h2>
      <div class="ubi">📍 ${esc([d.direccion, d.municipio, d.provincia].filter(Boolean).join(", ") || "n/d")}${
        d.distancia_km != null ? ` · a ${d.distancia_km} km de Barcelona` : ""}</div>
      <div class="precio">${d.precio != null ? eur.format(d.precio) : "Precio no disponible"}</div>
      ${d.imagen ? `<img class="ficha-img" src="${esc(d.imagen)}" alt="" onerror="this.remove()">` : ""}
      ${d.cumple === "parcial" ? `<p class="aviso">Faltan datos por confirmar en origen:
        ${d.faltan.join(", ")}. Revisa la ficha original antes de decidir.</p>` : ""}
      <table class="tabla">
        ${fila("Superficie construida", d.superficie_m2 ? num.format(d.superficie_m2) + " m²" : "")}
        ${fila("Parcela / terreno", d.terreno_m2 ? num.format(d.terreno_m2) + " m²" : "")}
        ${fila("Dormitorios", d.dormitorios)}
        ${fila("Baños", d.banos)}
        ${fila("Valor de tasación", d.valor_tasacion != null ? eur.format(d.valor_tasacion) : "")}
        ${fila("Depósito", d.deposito != null ? eur.format(d.deposito) : "")}
        ${fila("Estado", esc(d.estado || ""))}
        ${fila("Fin de subasta", esc(d.fecha_fin || ""))}
        ${fila("Organismo", esc(d.organismo || ""))}
        ${fila("Referencia", esc(d.referencia || ""))}
        ${fila("Plataforma", esc(d.fuente))}
        ${fila("Detectado", d.first_seen ? new Date(d.first_seen).toLocaleDateString("es-ES") : "")}
      </table>
      ${d.descripcion ? `<div class="desc">${esc(d.descripcion)}</div>` : ""}
      <a class="cta" href="${esc(d.url)}" target="_blank" rel="noopener">Ver ficha en ${esc(d.fuente)} ↗</a>`;
    $("#btn-cerrar").addEventListener("click", cierraPanel);
    $("#panel").setAttribute("open", "");
    $("#overlay").setAttribute("open", "");
  }

  function cierraPanel() {
    $("#panel").removeAttribute("open");
    $("#overlay").removeAttribute("open");
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  init();
})();
