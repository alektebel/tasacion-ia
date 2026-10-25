// Mapa de la ficha: finca, testigos (color según el contraste con Catastro) y comparables del AVM.
(function () {
  const datos = JSON.parse(document.getElementById("datos-mapa").textContent);
  const el = document.getElementById("mapa");
  const puntos = [...datos.fincas, ...datos.testigos, ...datos.comparables];
  if (!puntos.length) {
    el.classList.add("vacio");
    el.textContent = "Ni la finca ni los testigos tienen coordenadas.";
    return;
  }

  const wmts = (capa, formato) =>
    `https://www.ign.es/wmts/${capa}&style=default&tilematrixset=GoogleMapsCompatible&Service=WMTS` +
    `&Request=GetTile&Version=1.0.0&Format=${formato}&TileMatrix={z}&TileCol={x}&TileRow={y}`;
  const base = L.tileLayer(wmts("ign-base?layer=IGNBaseTodo", "image/jpeg"),
    { maxZoom: 20, attribution: "© Instituto Geográfico Nacional" });
  const orto = L.tileLayer(wmts("pnoa-ma?layer=OI.OrthoimageCoverage", "image/jpeg"),
    { maxZoom: 20, attribution: "PNOA © Instituto Geográfico Nacional" });
  const catastro = L.tileLayer.wms("https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx", {
    layers: "Catastro", format: "image/png", transparent: true, maxZoom: 20, minZoom: 16,
    attribution: "Dirección General del Catastro",
  });

  const mapa = L.map(el, { layers: [base], scrollWheelZoom: false });
  // La vista va antes que las capas: Leaflet no puede dibujar círculos ni líneas sin ella.
  // Encuadre: finca y testigos; los comparables sólo si no hay nada más.
  const foco = [...datos.fincas, ...datos.testigos];
  mapa.fitBounds(L.latLngBounds((foco.length ? foco : puntos).map((p) => [p.lat, p.lon])).pad(0.15), { maxZoom: 17 });
  const euros = (v) => v == null ? "—" : Math.round(v).toLocaleString("es-ES") + " €";
  const num = (v, d = 0) => v == null ? "—" : Number(v).toLocaleString("es-ES", { maximumFractionDigits: d });
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const comparables = L.layerGroup(datos.comparables.map((c) =>
    L.circleMarker([c.lat, c.lon], { radius: 4, weight: 1, color: "#2f5d8a", fillColor: "#5b8fc7", fillOpacity: 0.7 })
      .bindPopup(`<strong>Comparable AVM</strong> · ${esc(c.portal)}<br>${euros(c.precio)} · ${num(c.sup)} m²` +
        ` · ${num(c.precio / c.sup)} €/m²` + (c.url ? `<br><a href="${esc(c.url)}" target="_blank" rel="noopener">Anuncio</a>` : ""))
  )).addTo(mapa);

  const principal = datos.fincas.find((f) => f.principal) || datos.fincas[0];
  const lineas = L.layerGroup().addTo(mapa);
  if (principal) {
    L.circle([principal.lat, principal.lon], { radius: 2000, color: "#6b7280", weight: 1, dashArray: "4 4", fill: false }).addTo(mapa);
  }

  // Varios testigos en el mismo portal se tapan: cada repetido se desplaza unos píxeles.
  const repetidos = {};
  datos.testigos.forEach((t) => {
    const clase = t.catastro || "sin";
    const clave = `${t.lat.toFixed(6)},${t.lon.toFixed(6)}`;
    const n = (repetidos[clave] = (repetidos[clave] || 0) + 1) - 1;
    if (principal) {
      L.polyline([[principal.lat, principal.lon], [t.lat, t.lon]],
        { color: "#9ca3af", weight: 1, dashArray: "2 4" }).addTo(lineas);
    }
    L.marker([t.lat, t.lon], {
      icon: L.divIcon({ className: "", html: `<span class="num-testigo ${clase}">${t.orden}</span>`, iconSize: [24, 24], iconAnchor: [12 - 18 * n, 12] }),
      zIndexOffset: 500 + n,
    }).bindPopup(
      `<strong>Testigo ${t.orden}</strong>${t.tipo !== "vivienda" ? " · " + esc(t.tipo) : ""}<br>${esc(t.direccion)}<br>` +
      `${euros(t.precio)} · ${num(t.sup, 2)} m² · ${num(t.eur_m2)} €/m²<br>` +
      `${t.distancia != null ? num(t.distancia / 1000, 2) + " km de la finca" : ""} · punto: ${esc(t.precision)}` +
      `<br>Catastro: ${esc((t.catastro || "sin contrastar").replace("_", " "))}`
    ).addTo(mapa);
  });

  datos.fincas.forEach((f) => {
    L.marker([f.lat, f.lon], {
      icon: L.divIcon({ className: "", html: `<span class="marca-finca${f.principal ? "" : " secundaria"}"></span>`, iconSize: [22, 22], iconAnchor: [11, 11] }),
      zIndexOffset: 1000,
    }).bindPopup(`<strong>Finca${f.principal ? "" : " (" + esc(f.tipo) + ")"}</strong><br>${esc(f.direccion)}` +
      (f.rc ? `<br>RC ${esc(f.rc)}` : "")).addTo(mapa);
  });

  L.control.layers({ "Mapa IGN": base, "Ortofoto PNOA": orto },
    { "Parcelas del Catastro (zoom ≥ 16)": catastro, "Comparables del AVM": comparables, "Líneas a la finca": lineas },
    { collapsed: true }).addTo(mapa);
  L.control.scale({ imperial: false }).addTo(mapa);
})();
