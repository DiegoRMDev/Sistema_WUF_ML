// Cliente integrado de la maqueta WUF Predict.
const HOME = { analista: "dashboard", marketing: "dashboard", ayuda: "dashboard" };
const ROLE_LABELS = {
  analista: "Analista de Datos",
  marketing: "Marketing",
  ayuda: "Área de Ayuda",
};
const API_BASE = window.WUF_CONFIG?.apiBaseUrl?.replace(/\/$/, "");

function $(id) { return document.getElementById(id); }
// Los avisos solo ocupan espacio cuando realmente hay un mensaje que mostrar.
function setNotice(id, text = "", state = "") {
  const notice = $(id);
  if (!notice) return;
  notice.textContent = text;
  notice.dataset.state = state;
  notice.hidden = !text;
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
  if (name === "entrenamiento") loadModels();
  if (name === "catalogo") loadCatalog();
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
  setNotice("datasetMessage", "Generando una versión con el periodo seleccionado…");
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
  setNotice("modelMessage", "Preparando los datos y entrenando el modelo…");
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
      : `Entrenamiento ${model.version} finalizado, pero Accuracy no alcanza el umbral; queda guardado sin publicar.`, model.estado === "publicable" ? "success" : "error");
    await loadModels();
    // Muestra de inmediato la evaluación de la versión recién entrenada, esté o no publicable.
    renderModelDetails(model);
    setNotice("modelMessage", model.estado === "publicable"
      ? `Entrenamiento ${model.version} finalizado. Revisa las métricas y publícalo desde el historial si estás de acuerdo.`
      : `Entrenamiento ${model.version} finalizado, pero Accuracy no alcanza el umbral; queda guardado sin publicar.`, model.estado === "publicable" ? "success" : "error");
  } catch (cause) {
    setNotice("modelMessage", cause.message, "error");
  } finally {
    button.disabled = !$("modelDataset").value;
  }
}

async function activateModel(modelId) {
  setNotice("modelMessage", "Verificando el artefacto, publicando el modelo y calculando predicciones…");
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
  setNotice("modelMessage", "Calculando predicciones para la última captura completa…");
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
  $("trainModelButton").addEventListener("click", trainModel);
  $("catalogSearch").addEventListener("input", applyCatalogFilters);
  $("catalogStateFilter").addEventListener("change", applyCatalogFilters);
  $("catalogPriorityFilter").addEventListener("change", applyCatalogFilters);
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
