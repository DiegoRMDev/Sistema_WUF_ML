// Cliente integrado de la maqueta WUF Predict.
const HOME = { analista: "dashboard", marketing: "dashboard", ayuda: "dashboard" };
const ROLE_LABELS = {
  analista: "Analista de Datos",
  marketing: "Marketing",
  ayuda: "Área de Ayuda",
};
const API_BASE = window.WUF_CONFIG?.apiBaseUrl?.replace(/\/$/, "");
let currentPrioritizationReport = null;
let selectedSegmentationModelId = null;
let segmentationScatterRequestId = 0;
let selectedSegmentationScatterCluster = null;
let currentUser = null;
let alertItems = [];

function $(id) { return document.getElementById(id); }
const toastEntries = new Map();

// Los avisos de todos los módulos se muestran en una región global común.
function setNotice(id, text = "", state = "") {
  const current = toastEntries.get(id);
  if (current?.timer) window.clearTimeout(current.timer);
  if (!text) {
    current?.element.remove();
    toastEntries.delete(id);
    return;
  }

  const region = $("toastRegion");
  if (!region) return;
  const severity = ["success", "warning", "error", "loading"].includes(state) ? state : "info";
  const labels = { success: "Listo", warning: "Aviso", error: "Error", loading: "Procesando", info: "Información" };
  const symbols = { success: "✓", warning: "!", error: "×", loading: "…", info: "i" };
  let element = current?.element;
  if (!element) {
    element = document.createElement("div");
    element.className = "toast";
    const icon = document.createElement("span");
    icon.className = "toast-icon";
    icon.setAttribute("aria-hidden", "true");
    const content = document.createElement("div");
    content.className = "toast-content";
    const title = document.createElement("strong");
    title.className = "toast-title";
    const message = document.createElement("span");
    message.className = "toast-message";
    content.append(title, message);
    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "toast-dismiss";
    dismiss.setAttribute("aria-label", "Cerrar mensaje");
    dismiss.textContent = "×";
    dismiss.addEventListener("click", () => dismissToast(id));
    element.append(icon, content, dismiss);
    region.append(element);
  }

  element.className = `toast toast-${severity}`;
  element.setAttribute("role", severity === "error" ? "alert" : "status");
  element.setAttribute("aria-live", severity === "error" ? "assertive" : "polite");
  element.setAttribute("aria-atomic", "true");
  element.querySelector(".toast-icon").textContent = symbols[severity];
  element.querySelector(".toast-title").textContent = labels[severity];
  element.querySelector(".toast-message").textContent = text;

  // Los mensajes de proceso siguen visibles hasta que la operación termine; los demás caducan solos.
  const timeout = { success: 5500, warning: 8000, error: 9000, info: 6500 }[severity];
  const entry = { element, timer: null };
  if (severity !== "loading") {
    entry.timer = window.setTimeout(() => {
      if (toastEntries.get(id) === entry) dismissToast(id);
    }, timeout);
  }
  toastEntries.set(id, entry);
}

function dismissToast(id) {
  const entry = toastEntries.get(id);
  if (!entry) return;
  if (entry.timer) window.clearTimeout(entry.timer);
  entry.element.remove();
  toastEntries.delete(id);
}
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
  setNotice("loginError");
  const button = event.currentTarget.querySelector("button[type=submit]");
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
    setNotice("loginError", cause.message, "error");
  } finally {
    button.disabled = false;
  }
  return false;
}

function logout(message = "") {
  sessionStorage.removeItem("wuf.session");
  currentUser = null;
  alertItems = [];
  updateAlertBadge(0);
  location.hash = "";
  $("app").style.display = "none";
  $("login").style.display = "flex";
  setNotice("loginError", message, message ? "error" : "");
}

function enterApp(user, view) {
  currentUser = user;
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
  refreshAlertBadge();
}

function updateCurrentUser(user) {
  // Mantiene el nombre, el avatar y la ficha de configuración sincronizados tras editar el perfil.
  currentUser = user;
  $("whoName").textContent = user.nombre;
  $("whoRole").textContent = user.email;
  $("avatarTxt").textContent = user.nombre.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  $("cfgNombre").value = user.nombre;
  $("cfgEmail").value = user.email;
}

async function saveProfileName(event) {
  event.preventDefault();
  const button = $("saveProfileButton");
  button.disabled = true;
  setNotice("profileMessage", "Guardando el nombre…", "loading");
  try {
    const user = await api("/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ nombre: $("cfgNombre").value.trim() }),
    });
    updateCurrentUser(user);
    setNotice("profileMessage", "Nombre actualizado.", "success");
  } catch (cause) {
    setNotice("profileMessage", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function changeAccountPassword(event) {
  event.preventDefault();
  const button = $("changePasswordButton");
  const newPassword = $("cfgPass1").value;
  if (newPassword !== $("cfgPass2").value) {
    setNotice("passwordMessage", "La confirmación no coincide con la nueva contraseña.", "error");
    return;
  }
  button.disabled = true;
  setNotice("passwordMessage", "Actualizando la contraseña…", "loading");
  try {
    await api("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: $("cfgCurrentPassword").value,
        new_password: newPassword,
        confirm_password: $("cfgPass2").value,
      }),
    });
    $("passwordForm").reset();
    setNotice("passwordMessage", "Contraseña actualizada.", "success");
  } catch (cause) {
    setNotice("passwordMessage", cause.message, "error");
  } finally {
    button.disabled = false;
  }
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
  if (name !== "configuracion") $("passwordForm")?.reset();
  activeView.classList.remove("hidden");
  document.querySelectorAll(".navitem").forEach((nav) => nav.classList.toggle("active", nav.dataset.view === name));
  $("topTitle").textContent = activeView.querySelector("h1")?.textContent || "WUF Predict";
  closeSidebar();
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  window.scrollTo(0, 0);
  if (name === "dashboard") loadDashboard();
  if (name === "recoleccion") {
    // Al volver a la sección se limpia cualquier aviso de la visita anterior.
    setNotice("collectionMessage");
    loadCollection();
  }
  if (name === "dataset") loadDataset();
  if (name === "entrenamiento") {
    loadModels();
    loadConsistencyReport();
    loadSegmentationModels();
    refreshAlertBadge();
  }
  if (name === "alertas") loadAlerts();
  if (name === "catalogo") loadCatalog();
  if (name === "reporte") loadPrioritizationReport();
}

// El Dashboard solo resume resultados persistidos por los módulos anteriores.
async function loadDashboard() {
  const activityRows = $("dashboardActivityRows");
  const evolutionRows = $("dashboardEvolutionRows");
  if (!activityRows || !evolutionRows) return;
  activityRows.replaceChildren(modelTableMessage("Cargando actividad…", 2));
  evolutionRows.replaceChildren(modelTableMessage("Cargando capturas…", 7));
  try {
    const summary = await api("/dashboard/summary");
    renderDashboard(summary);
  } catch (cause) {
    $("dashboardLead").textContent = "No se pudo cargar el resumen del sistema.";
    activityRows.replaceChildren(modelTableMessage("No se pudo cargar la actividad.", 2));
    evolutionRows.replaceChildren(modelTableMessage("No se pudo cargar la evolución.", 7));
    setNotice("dashboardLoad", cause.message, "error");
  }
}

function dashboardCell(row, value, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = value == null ? "—" : String(value);
  row.append(cell);
  return cell;
}

function renderDashboard(data) {
  setNotice("dashboardLoad");
  const capture = data.captura;
  const hasCapture = Boolean(capture);
  const oe1 = data.oe1 || {};
  const oe2 = data.oe2 || {};
  const oe3 = data.oe3 || {};
  const catalog = data.catalogo || {};

  $("dashboardLead").textContent = hasCapture
    ? `Semana ${capture.semana} · captura ${formatCaptureDate(capture.fecha_captura)}`
    : "Todavía no hay capturas completadas.";

  $("dashboardOe1Value").textContent = oe1.version == null ? "—" : String(oe1.prioridad_alta ?? 0);
  $("dashboardOe1Meta").textContent = hasCapture
    ? `de ${catalog.disponibles ?? 0} disponibles`
    : "—";
  $("dashboardOe1Target").textContent = `Mascotas de baja probabilidad con prioridad alta · meta: +${oe1.meta_aumento_porcentaje ?? 25} %`;

  $("dashboardOe2Value").textContent = String(oe2.alertas_altas_abiertas ?? 0);
  $("dashboardOe2Target").textContent = `Perfiles con riesgo alto abiertos · meta de exactitud del catálogo: ${oe2.meta_exactitud_porcentaje ?? 98} %`;

  $("dashboardOe3Value").textContent = hasCapture ? String(oe3.perfiles_con_criterios ?? 0) : "—";
  $("dashboardOe3Meta").textContent = hasCapture
    ? `de ${catalog.disponibles ?? 0} disponibles`
    : "—";
  const oe3Coverage = oe3.cobertura_porcentaje;
  const oe3Assigned = oe3.perfiles_con_criterios_asignados;
  const oe3Eligible = oe3.perfiles_con_criterios;
  $("dashboardOe3Target").textContent = oe3Coverage == null
    ? `Perfiles con criterios de desventaja · meta de cobertura: ${oe3.meta_cobertura_porcentaje ?? 100} %`
    : `${oe3.segmentos} segmentos · cobertura ${oe3Assigned}/${oe3Eligible} · meta: ${oe3.meta_cobertura_porcentaje ?? 100} %`;

  $("dashboardCatalogEmpty").hidden = hasCapture;
  $("dashboardCatalogTable").hidden = !hasCapture;
  if (hasCapture) {
    $("dashboardCatalogTotal").textContent = String(catalog.perfiles_total ?? 0);
    $("dashboardCatalogAvailable").textContent = String(catalog.disponibles ?? 0);
    $("dashboardCatalogUnavailable").textContent = String(catalog.no_disponibles ?? 0);
    $("dashboardCatalogUnpublished").textContent = String(catalog.sin_publicar ?? 0);
    const prioritiesExist = oe1.version != null;
    $("dashboardCatalogPriorities").textContent = prioritiesExist
      ? `${catalog.prioridad_alta ?? 0} / ${catalog.prioridad_media ?? 0} / ${catalog.prioridad_baja ?? 0}`
      : "Sin predicción vigente";
  }

  const evolutionRows = $("dashboardEvolutionRows");
  evolutionRows.replaceChildren();
  const history = Array.isArray(data.evolucion) ? data.evolucion : [];
  if (!history.length) {
    evolutionRows.append(modelTableMessage("Todavía no hay capturas completadas.", 7));
  } else {
    history.forEach((item) => {
      const row = document.createElement("tr");
      dashboardCell(row, `Semana ${item.semana} · ${formatCaptureDate(item.fecha_captura)}`);
      dashboardCell(row, item.perfiles_total, "num");
      dashboardCell(row, item.perfiles_disponibles, "num");
      dashboardCell(row, item.oe1?.version == null ? "—" : item.oe1.prioridad_alta, "num");
      dashboardCell(row, item.oe2?.version == null ? "—" : item.oe2.riesgo_alto, "num");
      dashboardCell(row, item.oe3?.perfiles_con_criterios ?? "—", "num");
      dashboardCell(row, item.oe3?.version == null ? "—" : item.oe3.segmentos, "num");
      evolutionRows.append(row);
    });
  }

  const activityRows = $("dashboardActivityRows");
  activityRows.replaceChildren();
  const activity = Array.isArray(data.actividad) ? data.actividad : [];
  if (!activity.length) {
    activityRows.append(modelTableMessage("Aún no hay actividad registrada.", 2));
  } else {
    activity.forEach((item) => {
      const row = document.createElement("tr");
      dashboardCell(row, item.accion || "Actividad");
      const detail = [item.detalle, formatReportDate(item.fecha)].filter(Boolean).join(" · ");
      dashboardCell(row, detail, "muted num");
      activityRows.append(row);
    });
  }
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

function formatReportDate(value) {
  if (!value) return "—";
  // PostgreSQL guarda estas horas como hora local de Lima sin zona; se explicita -05:00 al mostrarlas.
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
    ? value.replace(" ", "T")
    : `${value.replace(" ", "T")}-05:00`;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "short", timeStyle: "short", timeZone: "America/Lima",
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
      setNotice("collectionMessage", connectionFailure
        ? "No se pudo conectar con la API. Comprueba que el backend siga ejecutándose en 127.0.0.1:8000; si acabas de cambiar dependencias o .env, reinícialo."
        : cause.message, "error");
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
  const file = input.files?.[0];
  if (!file) {
    setNotice("collectionMessage", "Elige un archivo CSV antes de iniciar la importación.", "error");
    return;
  }

  button.disabled = true;
  chooseButton.disabled = true;
  setNotice("collectionMessage", `Importando ${file.name}…`, "loading");
  try {
    const formData = new FormData();
    formData.append("file", file, file.name);
    const result = await api("/collection-runs", { method: "POST", body: formData });
    const outcome = `Captura ${result.estado}: ${result.perfiles_persistidos} perfiles guardados y ${result.perfiles_rechazados} rechazados.${result.mensaje_error ? ` ${result.mensaje_error}` : ""}`;
    const severity = result.estado === "fallida" ? "error"
      : result.estado === "parcial" || result.perfiles_rechazados > 0 ? "warning" : "success";
    setNotice("collectionMessage", outcome, severity);
    input.value = "";
    $("collectionFileName").textContent = "No hay archivo seleccionado.";
    button.disabled = true;
    await loadCollection();
  } catch (cause) {
    setNotice("collectionMessage", cause.message, "error");
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
  setNotice("datasetMessage");
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
    setNotice("datasetMessage", cause.message, "error");
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
  setNotice("datasetMessage");
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
  setNotice("datasetMessage", "Generando una versión con el periodo seleccionado…", "loading");
  try {
    await api("/datasets", {
      method: "POST",
      body: JSON.stringify({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta }),
    });
    await loadDataset();
    setNotice("datasetMessage", "Dataset generado correctamente.", "success");
  } catch (cause) {
    setNotice("datasetMessage", cause.message, "error");
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
    setNotice("datasetMessage", "Descarga del dataset iniciada.", "success");
  } catch (cause) {
    setNotice("datasetMessage", cause.message, "error");
  }
}

function modelStatusPresentation(status) {
  return ({
    vigente: ["Vigente", "alta"],
    publicable: ["Listo para publicar", "media"],
    no_publicable: ["No supera el umbral", "baja"],
    publicado: ["Publicado anteriormente", "neutral"],
  })[status] || [status || "Desconocido", "neutral"];
}

function appendTextCell(row, value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value;
  if (className) cell.className = className;
  row.append(cell);
  return cell;
}

function formatMetric(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(1)} %` : "—";
}

async function loadModels() {
  const history = $("modelHistory");
  history.replaceChildren(modelTableMessage("Cargando versiones…"));
  setNotice("modelMessage");
  try {
    const [options, modelPage] = await Promise.all([api("/models/options"), api("/models")]);
    window.modelDefaults = options.defaults;
    populateModelDatasets(options.datasets);
    $("modelThreshold").textContent = `Accuracy mínima para publicar: ${formatMetric(options.defaults.min_accuracy)}. Semilla reproducible: ${options.defaults.random_state}.`;
    $("modelTestSize").value = String(options.defaults.test_size);
    $("modelTrees").value = options.defaults.n_estimators;
    renderModels(modelPage.items);
  } catch (cause) {
    history.replaceChildren(modelTableMessage("No se pudo cargar el historial de modelos."));
    setNotice("modelMessage", cause.message, "error");
  }
}

async function loadConsistencyReport() {
  try {
    const report = await api("/consistency/latest");
    renderConsistencyReport(report);
  } catch (cause) {
    setNotice("consistencyTrainingMessage", cause.message, "error");
  }
}

async function loadSegmentationModels() {
  const history = $("segmentationHistory");
  history.replaceChildren(modelTableMessage("Cargando segmentaciones…", 7));
  try {
    const [options, page] = await Promise.all([
      api("/segmentation/options"), api("/segmentation/models"),
    ]);
    const capture = options.captura;
    const permittedClusters = new Set(options.segmentos_permitidos || []);
    const clusterSelect = $("segmentationK");
    [...clusterSelect.options].forEach((option) => {
      option.disabled = !permittedClusters.has(Number(option.value));
    });
    if (clusterSelect.selectedOptions[0]?.disabled && permittedClusters.size) {
      clusterSelect.value = String(Math.min(...permittedClusters));
    }
    $("segmentationOptionsSummary").textContent = capture
      ? `Captura semana ${capture.semana} · ${options.perfiles_disponibles} mascotas disponibles; ${options.perfiles_con_criterios} cumplen uno o más criterios de perfil desfavorecido. K-Means agrupa todas. Variables: edad, tamaño, energía y condición especial.`
      : "Importa una captura completa antes de entrenar K-Means.";
    $("trainSegmentationButton").disabled = options.estado !== "listo";
    renderSegmentationModels(page.items || []);
  } catch (cause) {
    history.replaceChildren(modelTableMessage("No se pudo cargar el historial de segmentación.", 7));
    $("segmentationOptionsSummary").textContent = cause.message;
    $("trainSegmentationButton").disabled = true;
  }
}

function renderSegmentationModels(models) {
  const storedActive = models.find((model) => model.es_vigente);
  const active = models.find((model) => model.es_vigente && model.compatible_enfoque);
  const selected = models.find((model) => model.id_modelo_segmentacion === selectedSegmentationModelId)
    || active || storedActive;
  const title = $("segmentationModelTitle");
  const status = $("segmentationModelStatus");
  const summary = $("segmentationModelSummary");
  const cards = $("segmentationClusterSummaries");
  cards.replaceChildren();
  if (!selected) {
    title.textContent = "Segmentación vigente";
    status.textContent = "Sin modelo";
    status.className = "tag neutral";
    summary.textContent = "Entrena una versión K-Means para agrupar todas las mascotas disponibles.";
  } else {
    const isActive = Boolean(selected.es_vigente);
    title.textContent = `${isActive ? "Segmentación vigente" : "Detalle de versión"} · K-Means ${selected.version}`;
    const isCompatible = Boolean(selected.compatible_enfoque);
    status.textContent = isActive && !isCompatible
      ? "Requiere reentrenamiento"
      : isCompatible && isActive ? "Vigente"
        : isCompatible && selected.estado === "candidato" ? "Pendiente de activar"
          : isCompatible ? "Anterior" : "Método anterior";
    // Reutiliza el color de estado activo que ya emplean los otros modelos.
    status.className = `tag ${isActive && isCompatible ? "alta" : "neutral"}`;
    summary.textContent = `${selected.cantidad_perfiles} perfiles · ${selected.cantidad_clusters} segmentos · silhouette ${Number(selected.silhouette_score).toFixed(3)} · captura semana ${selected.semana_referencia} · ${formatReportDate(selected.fecha_entrenamiento)}.${isCompatible ? "" : " Esta versión agrupó solo perfiles que cumplían criterios; entrena una nueva versión para cubrir todo el catálogo."}`;
    (selected.resumen_clusters || []).forEach((cluster) => {
      const card = document.createElement("div");
      card.className = "segmentation-cluster-card";
      const heading = document.createElement("strong");
      heading.textContent = `${cluster.nombre}: ${cluster.cantidad_perfiles} perfiles`;
      const details = document.createElement("span");
      const age = cluster.edad_mediana_meses === null ? "edad mediana no disponible" : `edad mediana ${cluster.edad_mediana_meses} meses`;
      const concentration = cluster.perfiles_con_atributos_desfavorecidos === undefined
        ? ""
        : ` · Con atributos desfavorecidos: ${cluster.perfiles_con_atributos_desfavorecidos} de ${cluster.cantidad_perfiles} (${Number(cluster.porcentaje_con_atributos_desfavorecidos).toFixed(1)} %)`;
      details.textContent = `Tamaño frecuente: ${cluster.tamano_frecuente} · Energía frecuente: ${cluster.energia_frecuente} · ${age} · edades estimadas: ${cluster.edades_estimadas} · edades no indicadas: ${cluster.edades_no_indicadas}${concentration}`;
      card.append(heading, details);
      cards.append(card);
    });
  }

  const scatterCard = $("segmentationScatterCard");
  if (selected) {
    scatterCard.hidden = false;
    void loadSegmentationScatter(selected.id_modelo_segmentacion);
  } else {
    // Invalida cualquier solicitud anterior si ya no hay un modelo que mostrar.
    segmentationScatterRequestId += 1;
    scatterCard.hidden = true;
  }

  const body = $("segmentationHistory");
  body.replaceChildren();
  if (!models.length) body.append(modelTableMessage("Todavía no hay modelos de segmentación.", 7));
  models.forEach((model) => {
    const row = document.createElement("tr");
    appendTextCell(row, model.version);
    appendTextCell(row, `Semana ${model.semana_referencia} · ${formatCaptureDate(model.fecha_captura_referencia)}`);
    appendTextCell(row, String(model.cantidad_perfiles), "num");
    appendTextCell(row, String(model.cantidad_clusters), "num");
    appendTextCell(row, Number(model.silhouette_score).toFixed(3), "num");
    appendTextCell(row, model.es_vigente && !model.compatible_enfoque
      ? "Requiere reentrenamiento"
      : !model.compatible_enfoque ? "Método anterior"
        : model.es_vigente ? "Vigente" : model.estado === "candidato" ? "Pendiente de activar" : "Anterior");
    const action = document.createElement("td");
    const actionGroup = document.createElement("div");
    actionGroup.className = "segmentation-actions";
    const view = document.createElement("button");
    view.type = "button";
    view.dataset.segmentationView = String(model.id_modelo_segmentacion);
    view.textContent = "Ver";
    actionGroup.append(view);
    if (model.estado === "candidato" && model.compatible_enfoque) {
      const activate = document.createElement("button");
      activate.type = "button";
      activate.className = "primary";
      activate.dataset.segmentationActivate = String(model.id_modelo_segmentacion);
      activate.textContent = "Activar";
      actionGroup.append(activate);
    }
    if (model.es_vigente && model.compatible_enfoque) {
      const refresh = document.createElement("button");
      refresh.type = "button";
      refresh.dataset.segmentationRefresh = "true";
      refresh.textContent = "Actualizar captura";
      actionGroup.append(refresh);
    }
    action.append(actionGroup);
    row.append(action);
    body.append(row);
  });
}

async function loadSegmentationScatter(modelId) {
  const requestId = ++segmentationScatterRequestId;
  const host = $("segmentationScatter");
  const legend = $("segmentationScatterLegend");
  host.textContent = "Cargando gráfico…";
  legend.replaceChildren();
  selectedSegmentationScatterCluster = null;
  $("segmentationScatterNote").textContent = "Preparando la proyección de los perfiles de esta versión…";
  try {
    const plot = await api(`/segmentation/models/${encodeURIComponent(modelId)}/scatter`);
    if (requestId !== segmentationScatterRequestId) return;
    renderSegmentationScatter(plot);
  } catch (cause) {
    if (requestId !== segmentationScatterRequestId) return;
    host.textContent = cause.message || "No se pudo cargar el gráfico de dispersión.";
    $("segmentationScatterNote").textContent = "No se pudo preparar la proyección de esta versión.";
  }
}

function renderSegmentationScatter(plot) {
  const host = $("segmentationScatter");
  const legend = $("segmentationScatterLegend");
  host.replaceChildren();
  legend.replaceChildren();
  const points = plot.points || [];
  if (!points.length) {
    host.textContent = "Esta versión no tiene perfiles para graficar.";
    $("segmentationScatterNote").textContent = "No hay perfiles asignados a esta versión.";
    return;
  }

  // El SVG es nativo para evitar añadir una librería de gráficos al frontend.
  const svgNs = "http://www.w3.org/2000/svg";
  const makeSvgElement = (name, attributes = {}) => {
    const element = document.createElementNS(svgNs, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  };
  const width = 760;
  const height = 430;
  const plotArea = { left: 72, right: 735, top: 24, bottom: 350 };
  const svg = makeSvgElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `Dispersión de ${points.length} perfiles agrupados por K-Means, versión ${plot.version}`,
    class: "segmentation-scatter-svg",
  });
  const title = makeSvgElement("title");
  title.textContent = `Segmentos de K-Means ${plot.version}`;
  svg.append(title);

  const xValues = points.map((point) => Number(point.x));
  const yValues = points.map((point) => Number(point.y));
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  const x = (value) => plotArea.left + ((Number(value) - xMin) / xRange) * (plotArea.right - plotArea.left);
  const y = (value) => plotArea.bottom - ((Number(value) - yMin) / yRange) * (plotArea.bottom - plotArea.top);
  const tickValue = (value) => Math.abs(Number(value)) < 0.05 ? "0" : Number(value).toFixed(1);

  // Las marcas numéricas muestran la escala de las coordenadas PCA de cada punto.
  for (let index = 0; index <= 4; index += 1) {
    const gridX = plotArea.left + ((plotArea.right - plotArea.left) * index) / 4;
    const gridY = plotArea.top + ((plotArea.bottom - plotArea.top) * index) / 4;
    const valueX = xMin + (xRange * index) / 4;
    const valueY = yMax - (yRange * index) / 4;
    svg.append(makeSvgElement("line", { x1: gridX, y1: plotArea.top, x2: gridX, y2: plotArea.bottom, class: "segmentation-scatter-grid" }));
    svg.append(makeSvgElement("line", { x1: plotArea.left, y1: gridY, x2: plotArea.right, y2: gridY, class: "segmentation-scatter-grid" }));
    const xTick = makeSvgElement("text", { x: gridX, y: plotArea.bottom + 20, "text-anchor": "middle", class: "segmentation-scatter-tick" });
    xTick.textContent = tickValue(valueX);
    const yTick = makeSvgElement("text", { x: plotArea.left - 9, y: gridY + 4, "text-anchor": "end", class: "segmentation-scatter-tick" });
    yTick.textContent = tickValue(valueY);
    svg.append(xTick, yTick);
  }
  svg.append(makeSvgElement("line", { x1: plotArea.left, y1: plotArea.bottom, x2: plotArea.right, y2: plotArea.bottom, class: "segmentation-scatter-axis" }));
  svg.append(makeSvgElement("line", { x1: plotArea.left, y1: plotArea.top, x2: plotArea.left, y2: plotArea.bottom, class: "segmentation-scatter-axis" }));

  const variance = plot.explained_variance_ratio || [];
  const firstVariance = Number(variance[0] || 0) * 100;
  const secondVariance = Number(variance[1] || 0) * 100;
  const combinedVariance = firstVariance + secondVariance;
  $("segmentationScatterNote").textContent = `La vista 2D resume ${combinedVariance.toFixed(1)} % de la variación (PC1: ${firstVariance.toFixed(1)} %; PC2: ${secondVariance.toFixed(1)} %). Cada punto es un perfil; el gráfico proyecta las variables para mostrarlas, mientras K-Means agrupa usando todas las variables. Selecciona un segmento en la leyenda para enfocarlo; vuelve a pulsarlo para mostrar todos.`;
  const xLabel = makeSvgElement("text", { x: (plotArea.left + plotArea.right) / 2, y: 405, "text-anchor": "middle", class: "segmentation-scatter-label" });
  xLabel.textContent = `Componente principal 1 (${firstVariance.toFixed(1)} %)`;
  const yLabel = makeSvgElement("text", { x: 18, y: (plotArea.top + plotArea.bottom) / 2, transform: `rotate(-90 18 ${(plotArea.top + plotArea.bottom) / 2})`, "text-anchor": "middle", class: "segmentation-scatter-label" });
  yLabel.textContent = `Componente principal 2 (${secondVariance.toFixed(1)} %)`;
  svg.append(xLabel, yLabel);

  const counts = new Map();
  points.forEach((point) => {
    const cluster = Number(point.numero_segmento);
    counts.set(cluster, (counts.get(cluster) || 0) + 1);
    const circle = makeSvgElement("circle", {
      cx: x(point.x), cy: y(point.y), r: 6,
      class: `segmentation-scatter-point cluster-${cluster}`,
      "data-point-cluster": cluster,
      tabindex: "0",
      "aria-label": `${point.sku} ${point.nombre}, segmento ${cluster}, atributos desfavorecidos: ${(point.atributos_desfavorecidos || []).join(", ") || "ninguno"}, PC1 ${tickValue(point.x)}, PC2 ${tickValue(point.y)}`,
    });
    const tooltip = makeSvgElement("title");
    tooltip.textContent = `${point.sku} · ${point.nombre} · Segmento ${cluster} · Atributos desfavorecidos: ${(point.atributos_desfavorecidos || []).join(", ") || "ninguno"} · PC1 ${tickValue(point.x)} · PC2 ${tickValue(point.y)}`;
    circle.append(tooltip);
    svg.append(circle);
  });
  host.append(svg);

  [...counts.entries()].sort(([left], [right]) => left - right).forEach(([cluster, count]) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "segmentation-legend-item";
    item.dataset.scatterCluster = String(cluster);
    item.setAttribute("aria-pressed", "false");
    item.title = "Enfocar este segmento; vuelve a pulsar para mostrar todos";
    const swatch = document.createElement("span");
    swatch.className = `segmentation-legend-swatch cluster-${cluster}`;
    swatch.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = `Segmento ${cluster} · ${count} perfiles`;
    item.append(swatch, label);
    legend.append(item);
  });
}

// La leyenda permite enfocar un grupo sin eliminar perfiles del gráfico.
function applySegmentationScatterFilter(cluster) {
  selectedSegmentationScatterCluster = cluster;
  document.querySelectorAll("[data-point-cluster]").forEach((point) => {
    point.classList.toggle("is-filtered", cluster !== null && point.dataset.pointCluster !== String(cluster));
  });
  document.querySelectorAll("[data-scatter-cluster]").forEach((button) => {
    button.setAttribute("aria-pressed", String(Number(button.dataset.scatterCluster) === cluster));
  });
}

async function trainSegmentationModel() {
  const button = $("trainSegmentationButton");
  button.disabled = true;
  setNotice("segmentationMessage", "Entrenando y evaluando agrupaciones…", "loading");
  try {
    const candidate = await api("/segmentation/models/train", {
      method: "POST", body: JSON.stringify({ cantidad_clusters: Number($("segmentationK").value) }),
    });
    selectedSegmentationModelId = candidate.id_modelo_segmentacion;
    await loadSegmentationModels();
    setNotice("segmentationMessage", `K-Means ${candidate.version} agrupó ${candidate.cantidad_perfiles} mascotas disponibles. Silhouette ${Number(candidate.silhouette_score).toFixed(3)}; revisa los grupos y actívalo si te resultan útiles.`, "success");
  } catch (cause) {
    setNotice("segmentationMessage", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function activateSegmentationModel(modelId, button) {
  button.disabled = true;
  setNotice("segmentationMessage", "Aplicando K-Means a la captura vigente…", "loading");
  try {
    const result = await api(`/segmentation/models/${encodeURIComponent(modelId)}/activate`, { method: "POST" });
    selectedSegmentationModelId = result.id_modelo_segmentacion;
    await loadSegmentationModels();
    setNotice("segmentationMessage", `Segmentación ${result.version} activada para ${result.asignaciones_actualizadas} mascotas disponibles de la semana ${result.semana_aplicada}.`, "success");
  } catch (cause) {
    setNotice("segmentationMessage", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function refreshSegmentationModel(button) {
  button.disabled = true;
  setNotice("segmentationMessage", "Actualizando segmentos para la última captura…", "loading");
  try {
    const result = await api("/segmentation/models/current/refresh", { method: "POST" });
    await Promise.all([loadSegmentationModels(), loadPrioritizationReport()]);
    setNotice("segmentationMessage", `Se actualizaron ${result.asignaciones_actualizadas} perfiles en la semana ${result.semana_aplicada}.`, "success");
  } catch (cause) {
    setNotice("segmentationMessage", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

function renderConsistencyReport(report) {
  const model = report.model;
  const summary = $("consistencyModelSummary");
  const metrics = $("consistencyMetrics");
  const importance = $("consistencyImportance");
  const matrixBody = $("consistencyConfusion");
  metrics.replaceChildren();
  importance.replaceChildren();
  matrixBody.replaceChildren();

  if (!model) {
    $("consistencyResults").hidden = true;
    $("consistencyDiagramCard").hidden = true;
    $("consistencyTreeDiagram").replaceChildren();
    summary.textContent = "";
    $("consistencyModelStatus").textContent = "";
    $("consistencyModelStatus").hidden = true;
    $("consistencyEvaluationNote").textContent = "";
    $("consistencyEvaluationNote").hidden = true;
    importance.append(modelText("p", "Sin resultados todavía.", "muted"));
    matrixBody.append(modelTableMessage("Sin resultados todavía.", 4));
    $("consistencyRules").textContent = "";
    $("consistencyRulesDetails").hidden = true;
    renderConsistencyHistory(report.history || []);
    return;
  }

  $("consistencyResults").hidden = false;
  const metadata = model.metadatos_entrenamiento || {};
  renderConsistencyTreeDiagram(metadata.diagrama_arbol, model.version);
  const parameters = metadata.parametros || {};
  const trainCount = Number(model.nro_registros_entrenamiento) || 0;
  const testCount = Number(model.nro_registros_prueba) || 0;
  const testedRows = trainCount + testCount;
  const modelStatus = $("consistencyModelStatus");
  modelStatus.textContent = model.es_vigente
    ? `Modelo vigente · ${model.version}`
    : `Versión histórica consultada · ${model.version}`;
  modelStatus.hidden = false;
  summary.textContent = `${model.es_vigente ? "Árbol vigente" : "Detalle del árbol"} ${model.version} · ${trainCount} observaciones de entrenamiento · ${testCount} de prueba (${formatMetric(parameters.test_size)}) · profundidad ${parameters.max_depth} · ${formatDate(model.fecha_entrenamiento)}.`;
  [["Accuracy", model.accuracy_score], ["F1 macro", model.f1_macro_score]].forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "metric";
    card.append(modelText("div", formatMetric(value), "n"), modelText("div", label, "l"));
    metrics.append(card);
  });
  const distribution = `Distribución de prioridades de referencia: baja ${metadata.conteo_clases_proxy?.bajo || 0}, media ${metadata.conteo_clases_proxy?.medio || 0}, alta ${metadata.conteo_clases_proxy?.alto || 0} · ${testedRows} observaciones en entrenamiento y prueba.`;
  const comparison = metadata.comparacion_arbol_regla_catalogo;
  const comparisonText = comparison
    ? ` En la última captura, el árbol coincidió con la regla en ${comparison.coincidencias} de ${comparison.total} perfiles.`
    : "";
  $("consistencyEvaluationNote").textContent = `${distribution}${comparisonText}`;
  $("consistencyEvaluationNote").hidden = false;
  const importances = model.importancia_variables || [];
  importances.forEach((item) => {
    const label = modelText("div", item.feature);
    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.width = `${Math.max(1, Number(item.importance) * 100)}%`;
    track.append(fill);
    importance.append(label, track, modelText("div", Number(item.importance).toFixed(3), "v"));
  });
  const risks = ["bajo", "medio", "alto"];
  (model.matriz_confusion || []).forEach((values, index) => {
    const row = document.createElement("tr");
    appendTextCell(row, `Real: ${risks[index] || "—"}`);
    values.forEach((value) => appendTextCell(row, String(value), "num"));
    matrixBody.append(row);
  });
  if (!matrixBody.children.length) matrixBody.append(modelTableMessage("Sin matriz disponible.", 4));
  const rules = (model.reglas_arbol || "").trim();
  $("consistencyRules").textContent = rules;
  $("consistencyRulesDetails").hidden = !rules;
  renderConsistencyHistory(report.history || [], model.id_modelo_consistencia);
}

// Dibuja cada versión desde la estructura del estimador que envió el backend.
function renderConsistencyTreeDiagram(treeData, version) {
  const section = $("consistencyDiagramCard");
  const container = $("consistencyTreeDiagram");
  container.replaceChildren();
  if (!treeData || typeof treeData !== "object") {
    section.hidden = true;
    return;
  }

  const svgNamespace = "http://www.w3.org/2000/svg";
  const makeSvgElement = (tag, attributes = {}) => {
    const element = document.createElementNS(svgNamespace, tag);
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, String(value)));
    return element;
  };
  const countLeaves = (node) => (node.left && node.right
    ? countLeaves(node.left) + countLeaves(node.right) : 1);
  const depthOf = (node) => (node.left && node.right
    ? 1 + Math.max(depthOf(node.left), depthOf(node.right)) : 0);

  const leaves = countLeaves(treeData);
  const depth = depthOf(treeData);
  const nodeWidth = 210;
  const nodeHeight = 82;
  const columnGap = 245;
  const horizontalPadding = 32;
  const verticalPadding = 28;
  const rowGap = 140;
  const width = Math.max(500, horizontalPadding * 2 + leaves * columnGap);
  const height = verticalPadding * 2 + (depth + 1) * rowGap;
  let leafIndex = 0;
  const positions = [];

  function place(node, level) {
    let centerX;
    if (node.left && node.right) {
      const leftX = place(node.left, level + 1);
      const rightX = place(node.right, level + 1);
      centerX = (leftX + rightX) / 2;
    } else {
      centerX = horizontalPadding + leafIndex * columnGap + columnGap / 2;
      leafIndex += 1;
    }
    positions.push({ node, level, centerX, top: verticalPadding + level * rowGap });
    return centerX;
  }
  place(treeData, 0);

  const svg = makeSvgElement("svg", {
    class: "tree-diagram-svg",
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    role: "img",
    "aria-label": `Diagrama del árbol de decisión ${version}`,
  });
  const title = makeSvgElement("title");
  title.textContent = `Árbol de decisión ${version}`;
  const description = makeSvgElement("desc");
  description.textContent = "Las ramas muestran las condiciones y las hojas el nivel de riesgo asignado.";
  svg.append(title, description);

  const nodePositions = new Map(positions.map((position) => [position.node, position]));
  positions.forEach(({ node, centerX, top }) => {
    if (!node.left || !node.right) return;
    [[node.left, "≤"], [node.right, ">"]].forEach(([child, direction]) => {
      const childPosition = nodePositions.get(child);
      const startY = top + nodeHeight;
      const endY = childPosition.top;
      const path = makeSvgElement("path", {
        class: "tree-diagram-edge",
        d: `M ${centerX} ${startY} L ${childPosition.centerX} ${endY}`,
      });
      svg.append(path);
      const edgeLabel = makeSvgElement("text", {
        class: "tree-diagram-edge-label",
        x: (centerX + childPosition.centerX) / 2,
        y: (startY + endY) / 2 - 4,
      });
      const threshold = Number(node.threshold).toLocaleString("es-PE", { maximumFractionDigits: 2 });
      edgeLabel.textContent = `${direction} ${threshold}`;
      svg.append(edgeLabel);
    });
  });

  const riskLabels = { bajo: "Bajo", medio: "Medio", alto: "Alto" };
  positions.forEach(({ node, centerX, top }) => {
    const group = makeSvgElement("g", { class: `tree-node risk-${node.prediction}` });
    group.append(makeSvgElement("rect", {
      x: centerX - nodeWidth / 2, y: top, width: nodeWidth, height: nodeHeight, rx: 10,
    }));
    const firstLine = makeSvgElement("text", { x: centerX, y: top + 26 });
    firstLine.textContent = node.feature || `Riesgo: ${riskLabels[node.prediction] || node.prediction}`;
    const secondLine = makeSvgElement("text", {
      class: "tree-node-secondary", x: centerX, y: top + 48,
    });
    secondLine.textContent = node.feature
      ? `Condición: ≤ ${Number(node.threshold).toLocaleString("es-PE", { maximumFractionDigits: 2 })}`
      : `${node.samples} observaciones`;
    group.append(firstLine, secondLine);
    if (node.feature) {
      const thirdLine = makeSvgElement("text", {
        class: "tree-node-secondary", x: centerX, y: top + 66,
      });
      thirdLine.textContent = `${node.samples} observaciones`;
      group.append(thirdLine);
    }
    svg.append(group);
  });
  container.append(svg);
  section.hidden = false;
}

function renderConsistencyHistory(history, selectedModelId = null) {
  const body = $("consistencyHistory");
  body.replaceChildren();
  if (!history.length) {
    body.append(modelTableMessage("Todavía no hay versiones.", 6));
    return;
  }
  history.forEach((version) => {
    const row = document.createElement("tr");
    appendTextCell(row, version.version);
    appendTextCell(row, version.es_vigente ? "Vigente" : "Anterior");
    appendTextCell(row, formatMetric(version.accuracy_score));
    appendTextCell(row, formatMetric(version.f1_macro_score));
    appendTextCell(row, formatDate(version.fecha_entrenamiento));
    const cell = document.createElement("td");
    const button = modelText("button", "Ver");
    button.type = "button";
    button.dataset.consistencyModelId = String(version.id_modelo_consistencia);
    button.disabled = Number(selectedModelId) === Number(version.id_modelo_consistencia);
    cell.append(button);
    row.append(cell);
    body.append(row);
  });
}

async function showConsistencyVersion(modelId) {
  try {
    const report = await api(`/consistency/history/${modelId}`);
    renderConsistencyReport(report);
  } catch (cause) {
    setNotice("consistencyTrainingMessage", cause.message, "error");
  }
}

async function loadAlerts() {
  setNotice("alertsMessage");
  try {
    const report = await api("/alerts");
    alertItems = report.items || [];
    updateAlertBadge(report.total_abiertas || 0);
    const openCount = Number(report.total_abiertas) || 0;
    $("consistencyAlertsSummary").textContent = `${openCount} alertas pendientes o en revisión · ${alertItems.length} alertas en el historial.`;
    renderAlerts();
  } catch (cause) {
    updateAlertBadge(0);
    setNotice("alertsMessage", cause.message, "error");
    $("consistencyItems").replaceChildren(modelText("p", "No se pudo cargar la bandeja de alertas.", "muted pad"));
    $("resolvedAlertItems").replaceChildren(modelText("p", "No se pudo cargar la bandeja de alertas.", "muted pad"));
    $("openAlertsCount").textContent = "—";
    $("resolvedAlertsCount").textContent = "—";
    $("consistencyFilterCount").textContent = "—";
  }
}

async function refreshAlertBadge() {
  if (!currentUser || !["analista", "ayuda"].includes(currentUser.rol)) return;
  try {
    const report = await api("/alerts");
    updateAlertBadge(report.total_abiertas || 0);
  } catch (_cause) {
    updateAlertBadge(0);
  }
}

function updateAlertBadge(openCount) {
  const badge = $("alertBadge");
  if (!badge) return;
  badge.textContent = String(openCount);
  badge.hidden = openCount <= 0;
}

function renderAlerts() {
  const openContainer = $("consistencyItems");
  const resolvedContainer = $("resolvedAlertItems");
  const search = ($("consistencySearch")?.value || "").trim().toLocaleLowerCase("es-PE");
  const selectedState = $("alertStateFilter")?.value || "todos";
  const filtered = alertItems.filter((item) => {
    const matchesText = !search || `${item.sku} ${item.nombre}`.toLocaleLowerCase("es-PE").includes(search);
    return matchesText && (selectedState === "todos" || item.estado === selectedState);
  });
  const openItems = filtered.filter((item) => item.estado !== "resuelta");
  const resolvedItems = filtered.filter((item) => item.estado === "resuelta");
  openContainer.replaceChildren();
  resolvedContainer.replaceChildren();
  $("consistencyFilterCount").textContent = `Mostrando ${filtered.length} de ${alertItems.length}`;
  $("openAlertsCount").textContent = String(openItems.length);
  $("resolvedAlertsCount").textContent = String(resolvedItems.length);
  const openEmptyMessage = !alertItems.length
    ? "Todavía no hay alertas. El Analista debe ejecutar una evaluación HU04 para detectar perfiles de prioridad alta."
    : "No hay alertas pendientes o en revisión que coincidan con los filtros.";
  const resolvedEmptyMessage = !alertItems.length
    ? "Todavía no hay alertas resueltas."
    : "No hay alertas resueltas que coincidan con los filtros.";
  if (!openItems.length) openContainer.append(modelText("p", openEmptyMessage, "muted pad"));
  if (!resolvedItems.length) resolvedContainer.append(modelText("p", resolvedEmptyMessage, "muted pad"));

  filtered.forEach((item) => {
    const container = item.estado === "resuelta" ? resolvedContainer : openContainer;
    const row = document.createElement("article");
    row.className = "alert-row";
    const content = document.createElement("div");
    const name = modelText("p", "", "name");
    name.append(document.createTextNode(`${item.nombre} · ${item.sku} `));
    name.append(modelText("span", "Riesgo alto", "tag baja"));
    const stateLabels = { pendiente: "Pendiente", en_revision: "En revisión", resuelta: "Resuelta" };
    const stateClass = item.estado === "resuelta" ? "alta" : item.estado === "en_revision" ? "media" : "baja";
    name.append(modelText("span", stateLabels[item.estado] || item.estado, `tag ${stateClass}`));
    const observedDays = item.dias_sin_cambio_observado;
    const observedDaysLabel = observedDays === null || observedDays === undefined
      ? "Días sin cambio no registrados"
      : `${observedDays} días sin cambio observado`;
    const detail = modelText("p",
      `Semana ${item.semana} · ${observedDaysLabel} · árbol ${item.version_arbol}`, "meta");
    const generated = modelText("p", `Alerta creada ${formatDate(item.fecha)} · última detección ${formatDate(item.fecha_ultima_deteccion)}`, "meta");
    const reason = modelText("p", item.justificacion, "justif");
    content.append(name, detail, generated, reason);
    const history = document.createElement("details");
    history.className = "alert-history";
    const historyTitle = document.createElement("summary");
    historyTitle.textContent = `Historial de atención (${item.historial_atencion.length})`;
    history.append(historyTitle);
    if (!item.historial_atencion.length) {
      history.append(modelText("p", "Todavía no se registraron acciones de atención.", "muted"));
    } else {
      item.historial_atencion.forEach((event) => {
        history.append(modelText("p",
          `${event.estado_anterior.replaceAll("_", " ")} → ${event.estado_nuevo.replaceAll("_", " ")} · ${event.atendido_por} · ${formatDate(event.fecha)} · ${event.nota}`, "alert-history-event"));
      });
    }
    content.append(history);
    row.append(content);
    if (currentUser?.rol === "ayuda" && item.estado !== "resuelta") {
      const actions = document.createElement("div");
      actions.className = "alert-actions";
      const note = document.createElement("textarea");
      note.rows = 2;
      note.maxLength = 500;
      note.required = true;
      note.dataset.alertNote = String(item.id_alerta);
      note.placeholder = "Registra qué comprobaste (máximo 500 caracteres)";
      note.setAttribute("aria-label", `Nota de atención para ${item.nombre}`);
      actions.append(note);
      if (item.estado === "pendiente") {
        const startButton = document.createElement("button");
        startButton.type = "button";
        startButton.className = "secondary";
        startButton.textContent = "Iniciar revisión";
        startButton.dataset.alertId = String(item.id_alerta);
        startButton.dataset.alertState = "en_revision";
        actions.append(startButton);
      }
      const resolveButton = document.createElement("button");
      resolveButton.type = "button";
      resolveButton.className = "primary";
      resolveButton.textContent = "Resolver";
      resolveButton.dataset.alertId = String(item.id_alerta);
      resolveButton.dataset.alertState = "resuelta";
      actions.append(resolveButton);
      row.append(actions);
    }
    container.append(row);
  });
}

async function attendAlert(button) {
  const alertId = Number(button.dataset.alertId);
  const note = document.querySelector(`textarea[data-alert-note="${alertId}"]`);
  const cleanedNote = note?.value.trim() || "";
  if (!cleanedNote) {
    setNotice("alertsMessage", "Escribe una nota breve antes de guardar la atención.", "warning");
    note?.focus();
    return;
  }
  const buttons = [...document.querySelectorAll(`[data-alert-id="${alertId}"]`)];
  buttons.forEach((entry) => { entry.disabled = true; });
  try {
    const result = await api(`/alerts/${alertId}/attention`, {
      method: "PATCH",
      body: JSON.stringify({ estado_nuevo: button.dataset.alertState, nota: cleanedNote }),
    });
    await loadAlerts();
    setNotice("alertsMessage", `Alerta de ${result.nombre} actualizada a ${result.estado.replaceAll("_", " ")}.`, "success");
  } catch (cause) {
    setNotice("alertsMessage", cause.message, "error");
    buttons.forEach((entry) => { entry.disabled = false; });
  }
}

async function trainConsistencyModel() {
  const button = $("trainConsistencyButton");
  button.disabled = true;
  setNotice("consistencyTrainingMessage", "Preparando el historial y entrenando el árbol…", "loading");
  try {
    const report = await api("/consistency/train", {
      method: "POST",
      body: JSON.stringify({
        profundidad_maxima: Number($("consistencyDepth").value),
        proporcion_prueba: Number($("consistencyTestSize").value),
      }),
    });
    renderConsistencyReport(report);
    const alertSummary = report.alertas_hu07 || { nuevas: 0, actualizadas: 0 };
    await refreshAlertBadge();
    setNotice(
      "consistencyTrainingMessage",
      `Evaluación ${report.model.version} guardada para ${report.items.length} perfiles. Alertas nuevas: ${alertSummary.nuevas}; actualizadas: ${alertSummary.actualizadas}.`,
      "success",
    );
  } catch (cause) {
    setNotice("consistencyTrainingMessage", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

function populateModelDatasets(datasets) {
  const select = $("modelDataset");
  const previous = select.value;
  select.replaceChildren();
  datasets.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id_dataset;
    option.textContent = `${dataset.version} · ${dataset.registros} filas · ${dataset.permanece} permanecen · ${dataset.salio_catalogo} salieron · ${dataset.indeterminada} indeterminadas`;
    select.append(option);
  });
  if (datasets.some((dataset) => String(dataset.id_dataset) === previous)) select.value = previous;
  $("trainModelButton").disabled = datasets.length === 0;
  if (!datasets.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Genera primero un dataset en Dataset Histórico";
    select.append(option);
  }
}

function modelTableMessage(message, columnCount = 6) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columnCount;
  cell.className = "muted";
  cell.textContent = message;
  row.append(cell);
  return row;
}

function renderModels(models) {
  const current = models.find((model) => model.es_vigente);
  const latest = current || models[0];
  renderModelDetails(latest);
  const body = $("modelHistory");
  body.replaceChildren();
  if (!models.length) {
    body.append(modelTableMessage("Todavía no hay entrenamientos registrados."));
    return;
  }
  models.forEach((model) => {
    const row = document.createElement("tr");
    appendTextCell(row, model.version);
    appendTextCell(row, model.dataset_version);
    const statusCell = document.createElement("td");
    const [statusText, statusClass] = modelStatusPresentation(model.estado);
    const badge = document.createElement("span");
    badge.className = `tag ${statusClass}`;
    badge.textContent = statusText;
    statusCell.append(badge);
    row.append(statusCell);
    appendTextCell(row, formatMetric(model.accuracy_score));
    appendTextCell(row, formatDate(model.fecha_entrenamiento));
    const actionCell = document.createElement("td");
    const actionGroup = document.createElement("div");
    actionGroup.className = "model-actions";
    const viewButton = document.createElement("button");
    viewButton.type = "button";
    viewButton.textContent = "Ver";
    viewButton.setAttribute("aria-label", `Ver detalles de ${model.version}`);
    // El historial mantiene cada evaluación para que se pueda consultar después de publicar.
    viewButton.addEventListener("click", () => renderModelDetails(model));
    actionGroup.append(viewButton);
    if (model.estado === "publicable") {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "primary";
      button.textContent = "Publicar y predecir";
      button.addEventListener("click", () => activateModel(model.id_modelo));
      actionGroup.append(button);
    } else if (model.es_vigente) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Actualizar predicciones";
      button.addEventListener("click", () => refreshPredictions(model.id_modelo));
      actionGroup.append(button);
    }
    actionCell.append(actionGroup);
    row.append(actionCell);
    body.append(row);
  });
}

function renderModelDetails(model) {
  const badge = $("modelStatus");
  const title = $("modelTitle");
  const summary = $("modelSummary");
  const metrics = $("modelMetrics");
  const importance = $("modelImportance");
  const confusionBody = $("modelConfusion");
  const note = $("modelEvaluationNote");
  metrics.replaceChildren();
  importance.replaceChildren();
  confusionBody.replaceChildren();
  if (!model) {
    title.textContent = "Modelo vigente";
    badge.className = "tag neutral";
    badge.textContent = "Sin modelo";
    summary.textContent = "Entrena y publica una versión para ver sus métricas.";
    importance.append(modelText("p", "Sin resultados todavía.", "muted"));
    confusionBody.append(modelTableMessage("Sin resultados todavía.", 3));
    note.textContent = "";
    return;
  }
  const [statusText, statusClass] = modelStatusPresentation(model.estado);
  title.textContent = model.es_vigente
    ? `Modelo vigente: Random Forest ${model.version}`
    : `Detalle de versión: Random Forest ${model.version}`;
  badge.className = `tag ${statusClass}`;
  badge.textContent = statusText;
  const meta = model.metadatos_entrenamiento || {};
  summary.textContent = `Dataset ${model.dataset_version} · ${model.nro_registros_entrenamiento} filas de entrenamiento · ${model.nro_registros_prueba} de prueba (${formatMetric(meta.test_size)}) · ${model.nro_registros_excluidos} indeterminadas excluidas · ${formatDate(model.fecha_entrenamiento)} · ${meta.n_estimators || "—"} árboles · profundidad ${meta.max_depth ?? "sin límite"}`;

  [["Accuracy", model.accuracy_score], ["Precision", model.precision_score],
    ["Recall", model.recall_score], ["F1-score", model.f1_score]].forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "metric";
    card.append(modelText("div", formatMetric(value), "n"), modelText("div", label, "l"));
    metrics.append(card);
  });
  const values = model.importancia_variables || [];
  if (!values.length) importance.append(modelText("p", "Sin resultados de importancia.", "muted"));
  const max = Math.max(0.000001, ...values.map((item) => Number(item.importance) || 0));
  values.forEach((item) => {
    const label = modelText("div", String(item.feature).replace(/^(numeric|categorical)__/, "").replaceAll("_", " "));
    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.width = `${Math.max(1, Number(item.importance) / max * 100)}%`;
    track.append(fill);
    importance.append(label, track, modelText("div", Number(item.importance).toFixed(3), "v"));
  });
  const matrix = model.matriz_confusion || [];
  const labels = ["Permanece", "Salió del catálogo"];
  if (matrix.length === 2) {
    matrix.forEach((valuesRow, index) => {
      const row = document.createElement("tr");
      appendTextCell(row, `Real: ${labels[index]}`);
      valuesRow.forEach((value) => appendTextCell(row, String(value), "num"));
      confusionBody.append(row);
    });
  } else confusionBody.append(modelTableMessage("No hay matriz de confusión.", 3));
  const classCounts = meta.conteo_clases || {};
  note.textContent = `Prueba por grupos de SKU; distribución entrenable: ${classCounts.permanece || 0} permanecen y ${classCounts.salio_catalogo || 0} salieron. Clase positiva: “Salió del catálogo”. Umbral de publicación: ${formatMetric(model.umbral_accuracy)}. Motivos de exclusión: ${JSON.stringify(meta.motivos_excluidos || {})}.`;
}

function modelText(tagName, value, className = "") {
  const element = document.createElement(tagName);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}

async function trainModel() {
  const button = $("trainModelButton");
  button.disabled = true;
  setNotice("modelMessage", "Preparando los datos y entrenando el modelo…", "loading");
  const depth = $("modelDepth").value;
  try {
    const model = await api("/models/train", {
      method: "POST",
      body: JSON.stringify({
        id_dataset: Number($("modelDataset").value),
        proporcion_prueba: Number($("modelTestSize").value),
        cantidad_arboles: Number($("modelTrees").value),
        profundidad_maxima: depth ? Number(depth) : null,
      }),
    });
    setNotice("modelMessage", model.estado === "publicable"
      ? `Entrenamiento ${model.version} finalizado. Revisa las métricas y publícalo desde el historial si estás de acuerdo.`
      : `Entrenamiento ${model.version} finalizado, pero Accuracy no alcanza el umbral; queda guardado sin publicar.`, model.estado === "publicable" ? "success" : "warning");
    await loadModels();
    // Muestra de inmediato la evaluación de la versión recién entrenada, esté o no publicable.
    renderModelDetails(model);
    setNotice("modelMessage", model.estado === "publicable"
      ? `Entrenamiento ${model.version} finalizado. Revisa las métricas y publícalo desde el historial si estás de acuerdo.`
      : `Entrenamiento ${model.version} finalizado, pero Accuracy no alcanza el umbral; queda guardado sin publicar.`, model.estado === "publicable" ? "success" : "warning");
  } catch (cause) {
    setNotice("modelMessage", cause.message, "error");
  } finally {
    button.disabled = !$("modelDataset").value;
  }
}

async function activateModel(modelId) {
  setNotice("modelMessage", "Verificando el artefacto, publicando el modelo y calculando predicciones…", "loading");
  try {
    const result = await api(`/models/${modelId}/activate`, { method: "POST", body: JSON.stringify({}) });
    setNotice("modelMessage", `${result.version} publicado. Se generaron ${result.predicciones_generadas} predicciones para mascotas disponibles.`, "success");
    await loadModels();
    setNotice("modelMessage", `${result.version} publicado. Se generaron ${result.predicciones_generadas} predicciones para mascotas disponibles.`, "success");
  } catch (cause) {
    setNotice("modelMessage", cause.message, "error");
  }
}

async function refreshPredictions(modelId) {
  setNotice("modelMessage", "Calculando predicciones para la última captura completa…", "loading");
  try {
    const result = await api(`/models/${modelId}/refresh-predictions`, {
      method: "POST", body: JSON.stringify({}),
    });
    setNotice("modelMessage", `Predicciones del modelo ${result.version} actualizadas: ${result.predicciones_generadas} perfiles disponibles.`, "success");
    await loadModels();
    setNotice("modelMessage", `Predicciones del modelo ${result.version} actualizadas: ${result.predicciones_generadas} perfiles disponibles.`, "success");
  } catch (cause) {
    setNotice("modelMessage", cause.message, "error");
  }
}

async function loadCatalog() {
  const body = $("catalogRows");
  setNotice("catalogMessage");
  $("catalogFilterCount").textContent = "Cargando catálogo…";
  body.replaceChildren(modelTableMessage("Cargando catálogo…", 13));
  try {
    const result = await api("/models/predictions");
    body.replaceChildren();
    $("catalogLead").textContent = result.mensaje || (result.modelo_version
      ? `Catálogo vigente · predicciones del modelo ${result.modelo_version}.`
      : "Aún no hay un modelo publicado; los datos del catálogo se mostrarán sin predicciones.");
    if (!result.items.length) {
      body.append(modelTableMessage(result.mensaje || "Todavía no hay mascotas registradas en el catálogo.", 13));
      $("catalogFilterCount").textContent = "Mostrando 0 de 0";
      return;
    }
    result.items.forEach((pet) => {
      const row = document.createElement("tr");
      row.dataset.catalogPet = "true";
      row.dataset.search = normalizeCatalogSearch(`${pet.sku} ${pet.nombre}`);
      row.dataset.state = pet.estado_publicado;
      row.dataset.priority = pet.nivel_prioridad?.toLocaleLowerCase("es-PE") || "sin_prioridad";
      appendTextCell(row, pet.sku);
      appendTextCell(row, pet.nombre);
      appendTextCell(row, pet.especie);
      appendTextCell(row, pet.sexo === "H" ? "Hembra" : pet.sexo === "M" ? "Macho" : pet.sexo);
      appendTextCell(row, formatPetAge(pet.edad_meses, pet.edad_estimada));
      appendTextCell(row, pet.tipo_pelaje);
      appendTextCell(row, pet.tamano);
      appendTextCell(row, pet.nivel_energia);
      appendTextCell(row, pet.condicion_detalle || (pet.condicion_especial ? "Sí" : "Ninguna"), "wrap");
      appendTextCell(row, String(pet.orden_publicacion), "num");
      const state = document.createElement("td");
      const stateTag = document.createElement("span");
      stateTag.className = "tag neutral";
      stateTag.textContent = ({
        disponible: "Disponible", no_disponible: "No disponible", sin_publicar: "Sin publicar",
      })[pet.estado_publicado] || pet.estado_publicado;
      state.append(stateTag);
      row.append(state);
      const probability = document.createElement("td");
      if (pet.probabilidad_adopcion === null || pet.probabilidad_adopcion === undefined) {
        probability.textContent = pet.estado_publicado === "disponible" ? "Sin predicción" : "No aplica";
      } else {
        probability.textContent = formatMetric(pet.probabilidad_adopcion);
        probability.title = `Estimación proxy calculada a partir de la salida del catálogo · ${result.modelo_version}`;
      }
      row.append(probability);
      const priority = document.createElement("td");
      if (pet.nivel_prioridad) {
        const [label, cssClass] = pet.nivel_prioridad === "Alta" ? ["Alta", "alta"]
          : pet.nivel_prioridad === "Media" ? ["Media", "media"] : ["Baja", "baja"];
        const tag = document.createElement("span");
        tag.className = `tag ${cssClass}`;
        tag.textContent = label;
        priority.append(tag);
      } else priority.textContent = "—";
      row.append(priority);
      body.append(row);
    });
    applyCatalogFilters();
  } catch (cause) {
    body.replaceChildren(modelTableMessage("No se pudo cargar el catálogo.", 13));
    $("catalogFilterCount").textContent = "Mostrando 0 de 0";
    setNotice("catalogMessage", cause.message, "error");
  }
}

function normalizeCatalogSearch(value) {
  return value.toLocaleLowerCase("es-PE").normalize("NFD").replace(/\p{Diacritic}/gu, "");
}

function applyCatalogFilters() {
  const body = $("catalogRows");
  const rows = [...body.querySelectorAll("tr[data-catalog-pet]")];
  const query = normalizeCatalogSearch($("catalogSearch").value.trim());
  const selectedState = $("catalogStateFilter").value;
  const selectedPriority = $("catalogPriorityFilter").value;
  let visible = 0;

  body.querySelector("#catalogNoMatches")?.remove();
  rows.forEach((row) => {
    const matches = (!query || row.dataset.search.includes(query))
      && (!selectedState || row.dataset.state === selectedState)
      && (!selectedPriority || row.dataset.priority === selectedPriority);
    row.hidden = !matches;
    if (matches) visible += 1;
  });
  $("catalogFilterCount").textContent = `Mostrando ${visible} de ${rows.length}`;
  if (rows.length && !visible) {
    const emptyRow = modelTableMessage("No hay mascotas que coincidan con los filtros.", 13);
    emptyRow.id = "catalogNoMatches";
    body.append(emptyRow);
  }
}

function formatPetAge(months, estimated) {
  if (months === null || months === undefined) return "No indicada";
  const years = Math.floor(Number(months) / 12);
  const remainingMonths = Number(months) % 12;
  const age = years ? `${years} ${years === 1 ? "año" : "años"}${remainingMonths ? ` ${remainingMonths} meses` : ""}`
    : `${remainingMonths} ${remainingMonths === 1 ? "mes" : "meses"}`;
  return `${age}${estimated ? " (est.)" : ""}`;
}

async function loadPrioritizationReport() {
  const body = $("reportRows");
  currentPrioritizationReport = null;
  void loadPrioritizationHistory();
  $("reportLead").textContent = "Cargando la última captura y las predicciones del modelo vigente…";
  $("reportEmpty").hidden = true;
  $("reportChartCard").hidden = true;
  $("reportOe3Summary").hidden = true;
  $("reportOe3Toolbar").hidden = true;
  $("reportOe3TableCard").hidden = true;
  $("reportToolbar").hidden = true;
  $("reportTotal").textContent = "";
  body.replaceChildren(modelTableMessage("Cargando reporte…", 10));
  setNotice("reportMessage");
  try {
    const report = await api("/reports/current");
    if (report.estado !== "listo") {
      $("reportLead").textContent = "El reporte semanal aún no está disponible.";
      $("reportEmpty").textContent = report.mensaje || "No hay información para mostrar.";
      $("reportEmpty").hidden = false;
      body.replaceChildren(modelTableMessage(report.mensaje || "No hay datos para mostrar.", 10));
      // Mantiene visible la sección OE3 incluso antes de importar la primera captura.
      if (report.estado === "sin_capturas") {
        renderOe3Report({ estado: "sin_capturas", total: 0, segmentos: [], items: [] });
      }
      return;
    }
    currentPrioritizationReport = report;
    $("reportLead").textContent = `Semana ${report.semana} · captura ${formatCaptureDate(report.fecha_captura)} · ${report.total} mascotas disponibles.`;
    $("reportTotal").textContent = `${report.total} registros`;
    renderPrioritizationChart(report.prioridades, report.total);
    $("reportChartCard").hidden = false;
    $("reportToolbar").hidden = false;
    renderPrioritizationRows(report.items);
    renderOe3Report(report.oe3 || {});
  } catch (cause) {
    $("reportLead").textContent = "No se pudo cargar el reporte semanal.";
    $("reportEmpty").textContent = cause.message;
    $("reportEmpty").hidden = false;
    body.replaceChildren(modelTableMessage("No se pudo cargar el reporte.", 10));
    setNotice("reportMessage", cause.message, "error");
  }
}

async function loadPrioritizationHistory() {
  const body = $("reportHistoryRows");
  body.replaceChildren(modelTableMessage("Cargando historial…", 9));
  try {
    const result = await api("/reports/history");
    renderPrioritizationHistory(result.items || []);
  } catch (cause) {
    body.replaceChildren(modelTableMessage("No se pudo cargar el historial de reportes.", 9));
    setNotice("reportHistory", cause.message, "error");
  }
}

function renderPrioritizationHistory(items) {
  const body = $("reportHistoryRows");
  body.replaceChildren();
  if (!items.length) {
    body.replaceChildren(modelTableMessage("Aún no hay reportes guardados. Exporta el reporte actual como PDF o Excel para registrarlo aquí.", 9));
    return;
  }
  items.forEach((report) => {
    const row = document.createElement("tr");
    appendTextCell(row, formatReportDate(report.fecha_generacion));
    appendTextCell(row, `Semana ${report.semana}`);
    appendTextCell(row, report.modelo_version);
    appendTextCell(row, report.segmentacion_version || "—");
    appendTextCell(row, String(report.total_oe1 || 0), "num");
    appendTextCell(row, String(report.total_oe3 || 0), "num");
    appendTextCell(row, String(report.formato).toUpperCase());
    appendTextCell(row, report.usuario || "—");
    const action = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "report-history-action";
    button.dataset.reportHistoryId = String(report.id_reporte);
    button.dataset.reportFormat = String(report.formato).toLowerCase();
    button.textContent = `Descargar ${String(report.formato).toUpperCase()}`;
    action.append(button);
    row.append(action);
    body.append(row);
  });
}

async function downloadSavedReport(reportId, format, button) {
  button.disabled = true;
  try {
    const headers = new Headers();
    const current = session();
    if (current?.accessToken) headers.set("Authorization", `Bearer ${current.accessToken}`);
    const response = await fetch(`${API_BASE}/reports/history/${encodeURIComponent(reportId)}/export`, { headers });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail?.message || "No se pudo recuperar el reporte.");
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `reporte_priorizacion_${reportId}.${format}`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    setNotice("reportHistory", `Reporte ${format.toUpperCase()} descargado.`, "success");
  } catch (cause) {
    setNotice("reportHistory", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

function renderPrioritizationChart(counts, total) {
  const entries = [
    ["alta", "reportHighCount", "reportHighBar"],
    ["media", "reportMediumCount", "reportMediumBar"],
    ["baja", "reportLowCount", "reportLowBar"],
  ];
  const maximum = Math.max(1, ...entries.map(([key]) => Number(counts[key]) || 0));
  entries.forEach(([key, countId, barId]) => {
    const count = Number(counts[key]) || 0;
    $(countId).textContent = String(count);
    $(barId).style.height = `${Math.max(8, Math.round((count / maximum) * 112))}px`;
    $(barId).setAttribute("aria-label", `${count} mascotas con prioridad ${key}`);
  });
  $("reportBars").setAttribute("aria-label", `Distribución de ${total} mascotas por prioridad`);
}

function renderPrioritizationRows(items) {
  const body = $("reportRows");
  body.replaceChildren();
  items.forEach((pet) => {
    const row = document.createElement("tr");
    row.dataset.reportPet = "true";
    row.dataset.search = normalizeCatalogSearch(`${pet.sku} ${pet.nombre}`);
    row.dataset.priority = String(pet.nivel_prioridad || "").toLocaleLowerCase("es-PE");
    appendTextCell(row, pet.sku);
    appendTextCell(row, pet.nombre);
    appendTextCell(row, pet.especie);
    appendTextCell(row, pet.sexo === "H" ? "Hembra" : pet.sexo === "M" ? "Macho" : pet.sexo);
    appendTextCell(row, formatPetAge(pet.edad_meses, pet.edad_estimada));
    appendTextCell(row, pet.tamano);
    appendTextCell(row, pet.condicion_especial ? (pet.condicion_detalle || "Condición especial") : "Ninguna", "wrap");
    appendTextCell(row, String(pet.orden_publicacion), "num");
    appendTextCell(row, formatMetric(pet.probabilidad_adopcion), "num");
    const priorityCell = document.createElement("td");
    const priorityName = String(pet.nivel_prioridad || "").toLocaleLowerCase("es-PE");
    const priorityTag = document.createElement("span");
    priorityTag.className = `tag ${priorityName}`;
    priorityTag.textContent = pet.nivel_prioridad;
    priorityCell.append(priorityTag);
    row.append(priorityCell);
    body.append(row);
  });
  applyPrioritizationFilters();
}

function applyPrioritizationFilters() {
  const body = $("reportRows");
  const rows = [...body.querySelectorAll("tr[data-report-pet]")];
  const query = normalizeCatalogSearch($("reportSearch").value.trim());
  const priority = $("reportPriorityFilter").value;
  body.querySelector("#reportNoMatches")?.remove();
  let visible = 0;
  rows.forEach((row) => {
    const matches = (!query || row.dataset.search.includes(query))
      && (!priority || row.dataset.priority === priority);
    row.hidden = !matches;
    if (matches) visible += 1;
  });
  $("reportFilterCount").textContent = `Mostrando ${visible} de ${rows.length}`;
  if (rows.length && visible === 0) {
    const empty = modelTableMessage("No hay mascotas que coincidan con los filtros.", 10);
    empty.id = "reportNoMatches";
    body.append(empty);
  }
}

function renderOe3Report(oe3) {
  const summaries = oe3.segmentos || [];
  const items = oe3.items || [];
  $("reportOe3Summary").hidden = false;
  $("reportOe3SummaryMeta").textContent = oe3.modelo_version
    ? `K-Means ${oe3.modelo_version} · ${Number(oe3.total) || 0} mascotas disponibles · ${Number(oe3.total_desfavorecidos) || 0} con atributos desfavorecidos`
    : `${Number(oe3.total) || 0} mascotas disponibles · ${Number(oe3.total_desfavorecidos) || 0} con atributos desfavorecidos`;
  const messages = {
    sin_capturas: "Importa una captura completa para agrupar las mascotas disponibles.",
    sin_modelo: "Entrena y activa K-Means desde Entrenamiento para agrupar el catálogo.",
    requiere_reentrenamiento: "El modelo activo es de la versión anterior del análisis. Entrena y activa un modelo nuevo para agrupar todo el catálogo.",
    pendiente_actualizacion: "La captura cambió. El Analista debe actualizar los segmentos antes de incluirlos en un reporte.",
  };
  $("reportOe3State").textContent = messages[oe3.estado]
    || (Number.isFinite(Number(oe3.silhouette_score))
      ? `Agrupación por atributos del perfil · silhouette ${Number(oe3.silhouette_score).toFixed(3)}.`
      : "Agrupación por atributos del perfil.");
  const summaryHost = $("reportOe3Clusters");
  summaryHost.replaceChildren();
  summaries.forEach((summary) => {
    const card = document.createElement("div");
    card.className = "segmentation-cluster-card";
    const title = document.createElement("strong");
    title.textContent = `${summary.nombre}: ${summary.cantidad_perfiles} perfiles`;
    const detail = document.createElement("span");
    const age = summary.edad_mediana_meses === null ? "edad no indicada" : `edad mediana ${summary.edad_mediana_meses} meses`;
    const concentration = summary.perfiles_con_atributos_desfavorecidos === undefined
      ? ""
      : ` · ${summary.perfiles_con_atributos_desfavorecidos} de ${summary.cantidad_perfiles} con atributos desfavorecidos (${Number(summary.porcentaje_con_atributos_desfavorecidos).toFixed(1)} %)`;
    detail.textContent = `Tamaño frecuente: ${summary.tamano_frecuente} · Energía frecuente: ${summary.energia_frecuente} · ${age}${concentration}`;
    card.append(title, detail);
    summaryHost.append(card);
  });
  $("reportOe3TableCard").hidden = false;
  $("reportOe3Toolbar").hidden = items.length === 0;
  $("reportOe3Total").textContent = `${items.length} mascotas disponibles`;
  const select = $("reportOe3Filter");
  select.replaceChildren(new Option("Todos", ""));
  summaries.forEach((summary) => select.add(new Option(summary.nombre, String(summary.numero_segmento))));
  renderOe3Rows(items, oe3.estado);
}

function renderOe3Rows(items, state = "") {
  const body = $("reportOe3Rows");
  body.replaceChildren();
  if (!items.length) {
    const message = state === "sin_capturas"
      ? "Todavía no hay capturas completas para listar perfiles."
      : state === "requiere_reentrenamiento"
      ? "El modelo vigente usa el enfoque anterior. Entrena y activa uno nuevo para agrupar todo el catálogo."
      : state === "pendiente_actualizacion"
      ? "No hay asignaciones para la última captura. Actualiza K-Means desde Entrenamiento."
      : "Todavía no hay una segmentación OE3 aplicada a esta captura.";
    body.append(modelTableMessage(message, 5));
    $("reportOe3FilterCount").textContent = "";
    return;
  }
  items.forEach((profile) => {
    const row = document.createElement("tr");
    row.dataset.oe3Profile = "true";
    row.dataset.search = normalizeCatalogSearch(`${profile.sku} ${profile.nombre}`);
    row.dataset.cluster = String(profile.numero_segmento);
    const criteria = (profile.criterios_desfavorecidos || []).map((item) => `${item.nombre}${item.estimado ? " (est.)" : ""}`);
    appendTextCell(row, profile.sku);
    appendTextCell(row, profile.nombre);
    appendTextCell(row, criteria.join(" · ") || "Ninguno", "wrap");
    appendTextCell(row, profile.segmento_nombre);
    const summary = profile.segmento_resumen || {};
    const age = summary.edad_mediana_meses === null ? "edad no indicada" : `mediana ${summary.edad_mediana_meses} meses`;
    const concentration = summary.perfiles_con_atributos_desfavorecidos === undefined
      ? ""
      : ` · ${summary.perfiles_con_atributos_desfavorecidos}/${summary.cantidad_perfiles} (${Number(summary.porcentaje_con_atributos_desfavorecidos).toFixed(1)} %) con atributos desfavorecidos`;
    appendTextCell(row, `Tamaño ${summary.tamano_frecuente || "—"} · energía ${summary.energia_frecuente || "—"} · ${age}${concentration}`, "wrap");
    body.append(row);
  });
  applyOe3Filters();
}

function applyOe3Filters() {
  const body = $("reportOe3Rows");
  const rows = [...body.querySelectorAll("tr[data-oe3-profile]")];
  const query = normalizeCatalogSearch($("reportOe3Search").value.trim());
  const cluster = $("reportOe3Filter").value;
  body.querySelector("#reportOe3NoMatches")?.remove();
  let visible = 0;
  rows.forEach((row) => {
    const matches = (!query || row.dataset.search.includes(query)) && (!cluster || row.dataset.cluster === cluster);
    row.hidden = !matches;
    if (matches) visible += 1;
  });
  $("reportOe3FilterCount").textContent = `Mostrando ${visible} de ${rows.length}`;
  if (rows.length && !visible) {
    const empty = modelTableMessage("No hay perfiles que coincidan con los filtros.", 5);
    empty.id = "reportOe3NoMatches";
    body.append(empty);
  }
}

async function exportPrioritizationReport(format) {
  if (!currentPrioritizationReport) return;
  const button = $(format === "pdf" ? "exportReportPdf" : "exportReportXlsx");
  button.disabled = true;
  setNotice("reportExport", `Generando archivo ${format.toUpperCase()}…`, "loading");
  try {
    const headers = new Headers();
    const current = session();
    if (current?.accessToken) headers.set("Authorization", `Bearer ${current.accessToken}`);
    const response = await fetch(`${API_BASE}/reports/export?formato=${format === "xlsx" ? "xlsx" : "pdf"}`, {
      method: "POST", headers,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail?.message || "No se pudo generar el archivo.");
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    const date = String(currentPrioritizationReport.fecha_captura).replaceAll("-", "");
    link.href = URL.createObjectURL(blob);
    link.download = `reporte_priorizacion_semana_${currentPrioritizationReport.semana}_${date}.${format}`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    setNotice("reportExport", `Reporte ${format.toUpperCase()} descargado y registrado.`, "success");
    void loadPrioritizationHistory();
  } catch (cause) {
    setNotice("reportExport", cause.message, "error");
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) window.lucide.createIcons();
  applyTheme(localStorage.getItem("wuf.theme") || "sistema");
  document.querySelectorAll("[data-model-tab]").forEach((tab) => {
    tab.addEventListener("click", () => selectModelTab(tab.dataset.modelTab));
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const tabs = [...document.querySelectorAll("[data-model-tab]")];
        const currentIndex = tabs.indexOf(tab);
        const step = event.key === "ArrowRight" ? 1 : -1;
        const nextTab = tabs[(currentIndex + step + tabs.length) % tabs.length];
        const next = nextTab.dataset.modelTab;
        selectModelTab(next);
        nextTab.focus();
      }
    });
  });
  document.querySelectorAll(".navitem").forEach((nav) => {
    nav.addEventListener("click", (event) => { event.preventDefault(); showView(nav.dataset.view); });
  });
  window.addEventListener("hashchange", () => { if (session()) showView(location.hash.slice(1)); });
  $("profileForm").addEventListener("submit", saveProfileName);
  $("passwordForm").addEventListener("submit", changeAccountPassword);
  $("chooseCollectionFileButton").addEventListener("click", () => $("collectionCsvFile").click());
  $("collectionCsvFile").addEventListener("change", (event) => {
    const file = event.currentTarget.files?.[0];
    $("collectionFileName").textContent = file ? file.name : "No hay archivo seleccionado.";
    $("runCollectionButton").disabled = !file;
    setNotice("collectionMessage");
  });
  $("runCollectionButton").addEventListener("click", runCollection);
  $("generateDatasetButton").addEventListener("click", generateDataset);
  $("exportDatasetButton").addEventListener("click", exportDataset);
  $("trainModelButton").addEventListener("click", trainModel);
  $("trainSegmentationButton").addEventListener("click", trainSegmentationModel);
  $("segmentationHistory").addEventListener("click", (event) => {
    const view = event.target.closest("button[data-segmentation-view]");
    const activate = event.target.closest("button[data-segmentation-activate]");
    const refresh = event.target.closest("button[data-segmentation-refresh]");
    if (view) {
      selectedSegmentationModelId = Number(view.dataset.segmentationView);
      void api("/segmentation/models")
        .then((page) => renderSegmentationModels(page.items || []))
        .catch((cause) => setNotice("segmentationMessage", cause.message, "error"));
    } else if (activate) {
      activateSegmentationModel(Number(activate.dataset.segmentationActivate), activate);
    } else if (refresh) {
      refreshSegmentationModel(refresh);
    }
  });
  $("segmentationScatterLegend").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-scatter-cluster]");
    if (!button) return;
    const cluster = Number(button.dataset.scatterCluster);
    applySegmentationScatterFilter(selectedSegmentationScatterCluster === cluster ? null : cluster);
  });
  $("trainConsistencyButton").addEventListener("click", trainConsistencyModel);
  $("consistencyHistory").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-consistency-model-id]");
    if (button) showConsistencyVersion(Number(button.dataset.consistencyModelId));
  });
  $("consistencySearch").addEventListener("input", renderAlerts);
  $("alertStateFilter").addEventListener("change", renderAlerts);
  $("view-alertas").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-alert-id][data-alert-state]");
    if (button) attendAlert(button);
  });
  $("catalogSearch").addEventListener("input", applyCatalogFilters);
  $("catalogStateFilter").addEventListener("change", applyCatalogFilters);
  $("catalogPriorityFilter").addEventListener("change", applyCatalogFilters);
  $("reportSearch").addEventListener("input", applyPrioritizationFilters);
  $("reportPriorityFilter").addEventListener("change", applyPrioritizationFilters);
  $("reportOe3Search").addEventListener("input", applyOe3Filters);
  $("reportOe3Filter").addEventListener("change", applyOe3Filters);
  $("reportHistoryRows").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-report-history-id]");
    if (button) downloadSavedReport(button.dataset.reportHistoryId, button.dataset.reportFormat, button);
  });
  $("reportChartCard").addEventListener("click", (event) => {
    const button = event.target.closest(".report-help-button");
    if (!button) return;
    const help = button.closest(".report-help");
    const shouldOpen = !help.classList.contains("is-open");
    document.querySelectorAll("#reportChartCard .report-help.is-open").forEach((item) => {
      item.classList.remove("is-open");
      item.querySelector(".report-help-button")?.setAttribute("aria-expanded", "false");
    });
    if (shouldOpen) {
      help.classList.add("is-open");
      button.setAttribute("aria-expanded", "true");
    }
  });
  $("reportChartCard").addEventListener("focusout", (event) => {
    const help = event.target.closest(".report-help");
    if (!help || help.contains(event.relatedTarget)) return;
    help.classList.remove("is-open");
    help.querySelector(".report-help-button")?.setAttribute("aria-expanded", "false");
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("#reportChartCard .report-help")) return;
    document.querySelectorAll("#reportChartCard .report-help.is-open").forEach((item) => {
      item.classList.remove("is-open");
      item.querySelector(".report-help-button")?.setAttribute("aria-expanded", "false");
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll("#reportChartCard .report-help.is-open").forEach((item) => {
      item.classList.remove("is-open");
      item.querySelector(".report-help-button")?.setAttribute("aria-expanded", "false");
    });
  });
  $("exportReportPdf").addEventListener("click", () => exportPrioritizationReport("pdf"));
  $("exportReportXlsx").addEventListener("click", () => exportPrioritizationReport("xlsx"));
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

// Alterna los paneles de entrenamiento y mantiene accesible el estado activo.
function selectModelTab(name) {
  const panels = { adoption: "adoptionPanel", consistency: "consistencyPanel", segmentation: "segmentationPanel" };
  document.querySelectorAll("[data-model-tab]").forEach((tab) => {
    const active = tab.dataset.modelTab === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  Object.entries(panels).forEach(([key, panelId]) => { $(panelId).hidden = key !== name; });
}
