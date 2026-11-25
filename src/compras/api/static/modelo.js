/* Evaluador del modelo LightGBM en el navegador (y en Node, para los tests de paridad).
 * Lee `modelo.json` (exportado por compras.deploy.web) y reproduce la predicción de LightGBM:
 * suma de las hojas de cada árbol + sigmoide. Las contribuciones por variable se calculan por
 * camino (cambio del valor interno del nodo en cada división), una aproximación de SHAP.
 * Fuente de los datos: Dirección ChileCompra.
 */
(function (raiz) {
  "use strict";

  function codificar(m, lic) {
    // Mismas variables y mismo orden que compras.api.app.Modelo.variables
    const fecha = lic.fecha_publicacion ? new Date(lic.fecha_publicacion) : new Date();
    const hist = (tabla, clave) => {
      const h = clave != null ? tabla[clave] : undefined;
      const n = h ? h.n : 0, d = h ? h.desiertas : 0;
      return [n, (d + m.suavizado.m * m.suavizado.p0) / (n + m.suavizado.m)];
    };
    const [orgN, orgTasa] = hist(m.historial_organismos, lic.codigo_organismo);
    const [rubN, rubTasa] = hist(m.historial_rubros, lic.rubro_principal);
    const moneda = lic.moneda || "CLP";
    const monto = moneda === "CLP" && lic.monto_estimado_clp != null ? Number(lic.monto_estimado_clp) : null;
    const dia = fecha.getDay() === 0 ? 7 : fecha.getDay(); // ISO: lunes=1 … domingo=7
    const crudo = {
      tipo: lic.tipo, convocatoria: lic.convocatoria === undefined ? "publica" : lic.convocatoria,
      rubro_principal: lic.rubro_principal, moneda: moneda, region: lic.region,
      etapas: lic.etapas, dia_semana_publicacion: dia, hora_publicacion: fecha.getHours(),
      n_items: lic.n_items, n_rubros: lic.n_rubros == null ? 1 : lic.n_rubros,
      monto_visible: lic.monto_visible == null ? null : Number(lic.monto_visible),
      monto_desconocido: monto == null ? 1 : 0,
      log_monto_estimado_clp: monto == null ? null : Math.log1p(monto),
      org_n_previas: orgN, org_tasa_desierta_previa: orgTasa,
      rubro_n_previas: rubN, rubro_tasa_desierta_previa: rubTasa,
    };
    return m.variables.map((v) => {
      const x = crudo[v];
      if (m.categorias[v]) {
        const etiqueta = x == null ? "desconocido" : String(x);
        const i = m.categorias[v].indexOf(etiqueta);
        return i < 0 ? NaN : i; // no vista en entrenamiento → faltante
      }
      return x == null || x === "" ? NaN : Number(x);
    });
  }

  function ir(nodo, x) {
    const v = x[nodo.f];
    if (nodo.cat) {
      if (Number.isNaN(v) || v < 0) return nodo.der; // LightGBM: categoría faltante → derecha
      return nodo.cat.includes(Math.trunc(v)) ? nodo.izq : nodo.der;
    }
    let val = v;
    if (Number.isNaN(val)) {
      if (nodo.faltante === "NaN") return nodo.izq_por_defecto ? nodo.izq : nodo.der;
      val = 0; // missing_type None: NaN se trata como 0
    }
    if (nodo.faltante === "Zero" && Math.abs(val) <= 1e-35) return nodo.izq_por_defecto ? nodo.izq : nodo.der;
    return val <= nodo.umbral ? nodo.izq : nodo.der;
  }

  function valor(n) { return n.hoja !== undefined ? n.hoja : n.interno; }

  function predecir(m, lic) {
    const x = codificar(m, lic);
    const contrib = new Array(m.variables.length).fill(0);
    let suma = 0;
    for (const arbol of m.arboles) {
      let nodo = arbol;
      while (nodo.hoja === undefined) {
        const sig = ir(nodo, x);
        contrib[nodo.f] += valor(sig) - nodo.interno;
        nodo = sig;
      }
      suma += nodo.hoja;
    }
    const p = 1 / (1 + Math.exp(-suma));
    const u = m.umbrales;
    const nivel = p >= u.alto ? "alto" : p >= u.medio ? "medio" : "bajo";
    const factores = contrib.map((c, i) => ({ variable: m.etiquetas[m.variables[i]] || m.variables[i], contribucion: c }))
      .filter((f) => Math.abs(f.contribucion) > 1e-6)
      .sort((a, b) => Math.abs(b.contribucion) - Math.abs(a.contribucion)).slice(0, 3)
      .map((f) => ({ ...f, efecto: f.contribucion > 0 ? "sube el riesgo" : "baja el riesgo" }));
    const h = lic.codigo_organismo != null ? m.historial_organismos[lic.codigo_organismo] : undefined;
    return {
      probabilidad_desierta: p, nivel, tasa_base: m.tasa_base, factores,
      historial_organismo: { conocido: !!h, nombre: h ? h.nombre : null, licitaciones_resueltas: h ? h.n : 0 },
    };
  }

  const api = { codificar, predecir };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.ModeloDesierta = api;
})(typeof window !== "undefined" ? window : globalThis);
