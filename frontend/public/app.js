// Cliente integrado de la maqueta WUF Predict.
const HOME = { analista: "dashboard", marketing: "dashboard", ayuda: "dashboard" };
const ROLE_LABELS = {
  analista: "Analista de Datos",
  marketing: "Marketing",
  ayuda: "Área de Ayuda",
};
const API_BASE = window.WUF_CONFIG?.apiBaseUrl?.replace(/\/$/, "");

function $(id) { return document.getElementById(id); }
function session() {
  try { return JSON.parse(sessionStorage.getItem("wuf.session")); }
  catch (_error) { return null; }
}

async function api(path, options = {}) {
  if (!API_BASE) throw new Error("Configura frontend/public/config.js con la dirección de la API.");
  const current = session();
  const headers = new Headers(options.headers || {});
  // FormData requiere que el navegador construya el boundary del Content-Type.
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (current?.accessToken) headers.set("Authorization", `Bearer ${current.accessToken}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.status === 401 && path !== "/auth/login") {
    logout("La sesión venció. Inicia sesión nuevamente.");
    throw new Error("La sesión venció.");
  }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || "No se pudo completar la solicitud.");
  }
  return data;
}

async function login(event) {
  event.preventDefault();
  const error = $("loginError");
  const button = event.currentTarget.querySelector("button[type=submit]");
  error.textContent = "";
  button.disabled = true;
  try {
    const token = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: $("email").value.trim(), password: $("password").value }),
    });
    sessionStorage.setItem("wuf.session", JSON.stringify({ accessToken: token.access_token }));
    const user = await api("/auth/me");
    $("password").value = "";
    enterApp(user, HOME[user.rol]);
  } catch (cause) {
    error.textContent = cause.message;
  } finally {
    button.disabled = false;
  }
  return false;
}

function logout(message = "") {
  sessionStorage.removeItem("wuf.session");
  location.hash = "";
  $("app").style.display = "none";
  $("login").style.display = "flex";
  $("loginError").textContent = message;
}

function enterApp(user, view) {
  $("login").style.display = "none";
  $("app").style.display = "block";
  $("roleHint").textContent = ROLE_LABELS[user.rol] || user.rol;
  $("whoName").textContent = user.nombre;
  $("whoRole").textContent = user.email;
  $("avatarTxt").textContent = user.nombre.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  if ($("cfgNombre")) $("cfgNombre").value = user.nombre;
  if ($("cfgEmail")) $("cfgEmail").value = user.email;
  document.querySelectorAll("[data-roles]").forEach((element) => {
    element.classList.toggle("hidden", !element.dataset.roles.split(" ").includes(user.rol));
  });
  showView(view || HOME[user.rol]);
}

function allowed(view) {
  const current = session();
  const link = document.querySelector(`.navitem[data-view="${CSS.escape(view)}"]`);
  return Boolean(current && link && !link.classList.contains("hidden"));
}

function showView(name) {
  if (!allowed(name)) name = "dashboard";
  document.querySelectorAll(".view").forEach((view) => view.classList.add("hidden"));
  const activeView = $(`view-${name}`);
  if (!activeView) return;
  activeView.classList.remove("hidden");
  document.querySelectorAll(".navitem").forEach((nav) => nav.classList.toggle("active", nav.dataset.view === name));
  $("topTitle").textContent = activeView.querySelector("h1")?.textContent || "WUF Predict";
  closeSidebar();
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  window.scrollTo(0, 0);
  if (name === "recoleccion") {
    // Al volver a la sección se limpia cualquier aviso de la visita anterior.
    $("collectionMessage").textContent = "";
    $("collectionMessage").dataset.state = "";
    loadCollection();
  }
  if (name === "dataset") loadDataset();
}

function openSidebar() {
  $("sidebar").classList.add("open");
  $("sidebarBackdrop").hidden = false;
  $("sidebarToggle").setAttribute("aria-expanded", "true");
  document.body.classList.add("sidebar-open");
}

function closeSidebar() {
  $("sidebar").classList.remove("open");
  $("sidebarBackdrop").hidden = true;
  $("sidebarToggle").setAttribute("aria-expanded", "false");
  document.body.classList.remove("sidebar-open");
}

function applyTheme(value) {
  if (value === "sistema") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", value);
  localStorage.setItem("wuf.theme", value);
  if ($("cfgTema")) $("cfgTema").value = value;
}

function formatDate(value) {
  if (!value) return "—";
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "short", timeStyle: "short", timeZone: "America/Lima",
  }).format(parsed);
}

function formatCaptureDate(value) {
  if (!value) return "—";
  // Las fechas de captura son calendarios (sin hora); UTC evita desplazarlas al día anterior en Lima.
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "short", timeZone: "UTC",
  }).format(parsed);
}

function statusPresentation(status) {
  const values = {
    completada: ["Completada", "alta"],
    parcial: ["Parcial", "media"],
    fallida: ["Fallida", "baja"],
    en_proceso: ["En proceso", "neutral"],
  };
  return values[status] || [status || "Desconocido", "neutral"];
}

function makeStatusTag(status) {
  const [label, cssClass] = statusPresentation(status);
  const tag = document.createElement("span");
  tag.className = `tag ${cssClass}`;
  tag.textContent = label;
  return tag;
}

async function loadCollection() {
  const body = $("collectionRuns");
  if (!body) return;
  body.replaceChildren(makeMessageRow("Cargando historial…"));
  try {
    const [overview, page] = await Promise.all([
      api("/collection-runs/overview"),
      api("/collection-runs"),
    ]);
    renderCollectionOverview(overview);
    renderCollectionRuns(page.items);
  } catch (cause) {
    if (session()) {
      // Separa el estado vacío de una falla de conexión para no mostrar errores como si fueran filas.
      body.replaceChildren(makeMessageRow("No se pudo cargar el historial de recolecciones."));
      const connectionFailure = cause instanceof TypeError && /fetch/i.test(cause.message);
      $("collectionMessage").textContent = connectionFailure
        ? "No se pudo conectar con la API. Comprueba que el backend siga ejecutándose en 127.0.0.1:8000; si acabas de cambiar dependencias o .env, reinícialo."
        : cause.message;
      $("collectionMessage").dataset.state = "error";
    }
  }
}

function renderCollectionOverview(overview) {
  const latest = overview.ultima_captura;
  $("collectionLatest").textContent = latest
    ? `${formatCaptureDate(latest.fecha_captura)} · semana ${latest.semana} · ${latest.perfiles_total} perfiles`
    : "Todavía no hay capturas completadas.";
  const status = $("collectionLatestStatus");
  status.replaceWith(makeStatusTag(latest?.estado || "Sin datos"));
  const newStatus = $("collectionOverview").querySelector(".tag");
  newStatus.id = "collectionLatestStatus";
}

function renderCollectionRuns(runs) {
  const body = $("collectionRuns");
  body.replaceChildren();
  if (!runs.length) {
    body.append(makeMessageRow("No hay ejecuciones registradas."));
    return;
  }
  runs.forEach((run) => {
    const row = document.createElement("tr");
    [run.semana, formatCaptureDate(run.fecha_captura), run.perfiles_total, run.perfiles_disponibles,
      run.perfiles_no_disponibles, run.perfiles_sin_publicar].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "—");
      row.append(cell);
    });
    const statusCell = document.createElement("td");
    statusCell.append(makeStatusTag(run.estado));
    row.append(statusCell);
    body.append(row);
  });
}

function makeMessageRow(message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 7;
  cell.className = "muted";
  cell.textContent = message;
  row.append(cell);
  return row;
}

async function runCollection() {
  const button = $("runCollectionButton");
  const chooseButton = $("chooseCollectionFileButton");
  const input = $("collectionCsvFile");
  const message = $("collectionMessage");
  const file = input.files?.[0];
  if (!file) {
    message.textContent = "Elige un archivo CSV antes de iniciar la importación.";
    message.dataset.state = "error";
    return;
  }

  button.disabled = true;
  chooseButton.disabled = true;
  message.textContent = `Importando ${file.name}…`;
  message.dataset.state = "";
  try {
    const formData = new FormData();
    formData.append("file", file, file.name);
    const result = await api("/collection-runs", { method: "POST", body: formData });
    message.textContent = `Captura ${result.estado}: ${result.perfiles_persistidos} perfiles guardados y ${result.perfiles_rechazados} rechazados.${result.mensaje_error ? ` ${result.mensaje_error}` : ""}`;
    message.dataset.state = result.estado === "completada" ? "success" : "error";
    input.value = "";
    $("collectionFileName").textContent = "No hay archivo seleccionado.";
    button.disabled = true;
    await loadCollection();
  } catch (cause) {
    message.textContent = cause.message;
    message.dataset.state = "error";
    // Al limpiar el input se permite volver a elegir el mismo nombre tras corregir un CSV fallido.
    input.value = "";
    $("collectionFileName").textContent = "No hay archivo seleccionado.";
  } finally {
    chooseButton.disabled = false;
    button.disabled = !input.files?.[0];
  }
}

function datasetStateLabel(state) {
  return ({ disponible: "Disponible", no_disponible: "No disponible", sin_publicar: "Sin publicar" })[state]
    || "Sin registro";
}

function datasetLabelTag(label, reason) {
  const presentation = {
    permanece: ["Permanece", "alta"],
    salio_catalogo: ["Salió del catálogo", "baja"],
    indeterminada: ["Indeterminada", "neutral"],
  }[label] || ["Sin etiqueta", "neutral"];
  const tag = document.createElement("span");
  tag.className = `tag ${presentation[1]}`;
  tag.textContent = presentation[0];
  const content = document.createElement("div");
  content.append(tag);
  if (label === "indeterminada" && reason) {
    // El motivo ayuda a interpretar por qué esta fila no sirve como etiqueta de entrenamiento.
    const explanation = document.createElement("small");
    explanation.className = "dataset-reason";
    explanation.textContent = ({
      estado_sin_evidencia_concluyente: "Se observó «Sin publicar» sin una salida concluyente posterior.",
      sin_captura_posterior: "No hay captura posterior para confirmar el resultado.",
    })[reason] || "No hubo evidencia concluyente durante el seguimiento.";
    content.append(explanation);
  }
  return content;
}

async function loadDataset() {
  const body = $("datasetRows");
  window.datasetRowsData = null;
  window.currentDatasetId = null;
  window.currentDatasetRunCount = 0;
  $("datasetFilterCount").textContent = "";
  $("datasetMessage").textContent = "";
  $("datasetMessage").dataset.state = "";
  body.replaceChildren(makeMessageRow("Cargando datasets…"));
  try {
    const [sources, page] = await Promise.all([api("/datasets/sources"), api("/datasets")]);
    window.datasetSources = sources.items;
    populateDatasetCaptureChoices(sources.items);
    const latest = page.items[0];
    if (!latest) {
      resetDatasetTableHeader();
      $("datasetVersion").textContent = "Sin dataset";
      $("datasetSummary").textContent = "Todavía no hay datasets generados.";
      $("datasetProvenance").textContent = "Importa al menos tres capturas completas y elige un horizonte de seguimiento.";
      $("exportDatasetButton").disabled = true;
      $("datasetFilterCount").textContent = "Mostrando 0 de 0";
      body.replaceChildren(makeDatasetMessageRow("Todavía no hay registros de dataset."));
      return;
    }
    const dataset = await api(`/datasets/${latest.id_dataset}`);
    renderDataset(dataset);
  } catch (cause) {
    $("exportDatasetButton").disabled = true;
    window.datasetRowsData = null;
    window.currentDatasetId = null;
    resetDatasetTableHeader();
    $("datasetVersion").textContent = "No disponible";
    $("datasetSummary").textContent = "No se pudo cargar el dataset.";
    $("datasetProvenance").textContent = "";
    $("datasetFilterCount").textContent = "Mostrando 0 de 0";
    $("datasetMessage").textContent = cause.message;
    $("datasetMessage").dataset.state = "error";
    body.replaceChildren(makeDatasetMessageRow("No se pudo cargar el dataset histórico."));
  }
}

function populateDatasetCaptureChoices(captures) {
  const uniqueDates = [...new Map(captures.map((capture) => [capture.fecha_captura, capture])).values()];
  for (const selectId of ["datasetFrom", "datasetTo"]) {
    const select = $(selectId);
    const previous = select.value;
    select.replaceChildren();
    uniqueDates.forEach((capture) => {
      const option = document.createElement("option");
      option.value = capture.fecha_captura;
      option.textContent = `Semana ${capture.semana} · ${formatCaptureDate(capture.fecha_captura)} · ${capture.perfiles_total} perfiles`;
      select.append(option);
    });
    if (uniqueDates.some((capture) => capture.fecha_captura === previous)) select.value = previous;
  }
  if (uniqueDates.length) {
    if (!$("datasetFrom").value) $("datasetFrom").value = uniqueDates[0].fecha_captura;
    if (!$("datasetTo").value) $("datasetTo").value = uniqueDates.at(-1).fecha_captura;
  }
  updateDatasetHorizon();
}

function updateDatasetHorizon() {
  const start = $("datasetFrom").value;
  const end = $("datasetTo").value;
  const startTime = Date.parse(`${start}T00:00:00Z`);
  const endTime = Date.parse(`${end}T00:00:00Z`);
  const days = Number.isFinite(startTime) && Number.isFinite(endTime)
    ? (endTime - startTime) / 86_400_000 : 0;
  const selected = (window.datasetSources || []).filter((capture) =>
    capture.fecha_captura >= start && capture.fecha_captura <= end);
  const weeks = days / 7;
  const valid = selected.length >= 3 && Number.isInteger(weeks) && weeks >= 2;
  $("datasetHorizon").textContent = valid
    ? `Horizonte: ${weeks} ${weeks === 1 ? "semana" : "semanas"} · ${selected.length} capturas completas incluidas.`
    : "Elige un periodo con al menos tres capturas completas y dos semanas de seguimiento.";
  $("generateDatasetButton").disabled = !valid;
}

function makeDatasetMessageRow(message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 4 + (window.currentDatasetRunCount || 0);
  cell.className = "muted";
  cell.textContent = message;
  row.append(cell);
  return row;
}

function resetDatasetTableHeader() {
  const header = document.createElement("tr");
  ["ID", "Mascota", "Orden", "Etiqueta final"].forEach((label) => {
    const cell = document.createElement("th");
    cell.textContent = label;
    header.append(cell);
  });
  $("datasetHead").replaceChildren(header);
}

function renderDataset(data) {
  const meta = data.dataset;
  const runs = data.runs;
  const pets = data.pets;
  // La API entrega el motivo en los detalles de auditoría; se vincula por SKU con la fila visible.
  const reasonsBySku = new Map((data.details || []).map((detail) => [detail.sku, detail.motivo_indeterminado]));
  window.datasetRowsData = { runs, pets, reasonsBySku };
  window.currentDatasetId = meta.id_dataset;
  window.currentDatasetRunCount = runs.length;
  $("datasetVersion").textContent = `Versión ${meta.version}`;
  $("datasetSummary").textContent = `· ${meta.nro_registros} registros · ${meta.permanece} permanecen · ${meta.salio} salieron del catálogo${meta.indeterminada ? ` · ${meta.indeterminada} indeterminadas` : ""}`;
  $("datasetProvenance").textContent = `Rango ${formatCaptureDate(meta.fecha_desde)}–${formatCaptureDate(meta.fecha_hasta)} · etiquetas derivadas del catálogo (proxy) · regla ${meta.version_regla_etiquetado}`;
  $("datasetMessage").textContent = "";
  $("datasetMessage").dataset.state = "";
  $("exportDatasetButton").disabled = false;

  const head = $("datasetHead");
  const header = document.createElement("tr");
  ["ID", "Mascota", "Orden"].forEach((label) => {
    const cell = document.createElement("th"); cell.textContent = label; header.append(cell);
  });
  runs.forEach((run) => {
    const cell = document.createElement("th");
    cell.textContent = `Semana ${run.semana}`;
    cell.title = formatCaptureDate(run.fecha_captura);
    header.append(cell);
  });
  const labelHeader = document.createElement("th"); labelHeader.textContent = "Etiqueta final"; header.append(labelHeader);
  head.replaceChildren(header);

  applyDatasetFilters();
}

function applyDatasetFilters() {
  const data = window.datasetRowsData;
  if (!data) {
    $("datasetFilterCount").textContent = "Mostrando 0 de 0";
    return;
  }
  const query = $("datasetSearch").value.trim().toLocaleLowerCase("es-PE");
  const selectedLabel = $("datasetLabelFilter").value;
  const filtered = data.pets.filter((pet) => {
    const matchesText = !query || `${pet.sku} ${pet.nombre}`.toLocaleLowerCase("es-PE").includes(query);
    return matchesText && (!selectedLabel || pet.etiqueta === selectedLabel);
  });
  const body = $("datasetRows"); body.replaceChildren();
  $("datasetFilterCount").textContent = `Mostrando ${filtered.length} de ${data.pets.length}`;
  if (!filtered.length) { body.append(makeDatasetMessageRow("No hay mascotas que coincidan con los filtros.")); return; }
  filtered.forEach((pet) => {
    const row = document.createElement("tr");
    [pet.sku, pet.nombre, String(pet.orden_publicacion)].forEach((value, index) => {
      const cell = document.createElement("td");
      if (index === 2) cell.className = "num";
      cell.textContent = value;
      row.append(cell);
    });
    data.runs.forEach((run) => {
      const cell = document.createElement("td");
      cell.textContent = datasetStateLabel(pet.estados[String(run.id_ejecucion)]);
      row.append(cell);
    });
    const label = document.createElement("td");
    label.append(datasetLabelTag(pet.etiqueta, data.reasonsBySku.get(pet.sku)));
    row.append(label);
    body.append(row);
  });
}

async function generateDataset() {
  const button = $("generateDatasetButton");
  button.disabled = true;
  const fechaDesde = $("datasetFrom").value;
  const fechaHasta = $("datasetTo").value;
  $("datasetMessage").textContent = "Generando una versión con el periodo seleccionado…";
  $("datasetMessage").dataset.state = "";
  try {
    await api("/datasets", {
      method: "POST",
      body: JSON.stringify({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta }),
    });
    await loadDataset();
    $("datasetMessage").textContent = "Dataset generado correctamente.";
    $("datasetMessage").dataset.state = "success";
  } catch (cause) {
    $("datasetMessage").textContent = cause.message;
    $("datasetMessage").dataset.state = "error";
  } finally { button.disabled = false; }
}

async function exportDataset() {
  if (!window.currentDatasetId) return;
  const current = session();
  try {
    const response = await fetch(`${API_BASE}/datasets/${window.currentDatasetId}/export`, {
      headers: { Authorization: `Bearer ${current.accessToken}` },
    });
    if (!response.ok) throw new Error("No se pudo exportar el dataset.");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `dataset_${window.currentDatasetId}.csv`;
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  } catch (cause) {
    $("datasetMessage").textContent = cause.message;
    $("datasetMessage").dataset.state = "error";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) window.lucide.createIcons();
  applyTheme(localStorage.getItem("wuf.theme") || "sistema");
  document.querySelectorAll(".navitem").forEach((nav) => {
    nav.addEventListener("click", (event) => { event.preventDefault(); showView(nav.dataset.view); });
  });
  window.addEventListener("hashchange", () => { if (session()) showView(location.hash.slice(1)); });
  $("chooseCollectionFileButton").addEventListener("click", () => $("collectionCsvFile").click());
  $("collectionCsvFile").addEventListener("change", (event) => {
    const file = event.currentTarget.files?.[0];
    $("collectionFileName").textContent = file ? file.name : "No hay archivo seleccionado.";
    $("runCollectionButton").disabled = !file;
    $("collectionMessage").textContent = "";
    $("collectionMessage").dataset.state = "";
  });
  $("runCollectionButton").addEventListener("click", runCollection);
  $("generateDatasetButton").addEventListener("click", generateDataset);
  $("exportDatasetButton").addEventListener("click", exportDataset);
  $("datasetFrom").addEventListener("change", () => {
    if ($("datasetTo").value <= $("datasetFrom").value) {
      const nextCapture = (window.datasetSources || []).find((capture) =>
        capture.fecha_captura > $("datasetFrom").value);
      if (nextCapture) $("datasetTo").value = nextCapture.fecha_captura;
    }
    updateDatasetHorizon();
  });
  $("datasetTo").addEventListener("change", updateDatasetHorizon);
  $("datasetSearch").addEventListener("input", applyDatasetFilters);
  $("datasetLabelFilter").addEventListener("change", applyDatasetFilters);
  $("sidebarToggle").addEventListener("click", openSidebar);
  $("sidebarClose").addEventListener("click", closeSidebar);
  $("sidebarBackdrop").addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSidebar();
  });
  const current = session();
  if (!current?.accessToken) return;
  try {
    const user = await api("/auth/me");
    enterApp(user, location.hash.slice(1) || HOME[user.rol]);
  } catch (_cause) {
    sessionStorage.removeItem("wuf.session");
  }
});
