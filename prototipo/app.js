// WUF Predict - navegación del prototipo
const USERS = {
  "analista@wuf.pe":  { nombre: "Analista de Datos", rol: "analista",  etiqueta: "Analista de Datos", iniciales: "AD" },
  "marketing@wuf.pe": { nombre: "Equipo de Marketing", rol: "marketing", etiqueta: "Equipo de Marketing", iniciales: "EM" },
  "ayuda@wuf.pe":     { nombre: "Área de Ayuda", rol: "ayuda", etiqueta: "Área de Ayuda", iniciales: "AA" },
};
const PASSWORD = "wuf2026";
const HOME = { analista: "dashboard", marketing: "dashboard", ayuda: "dashboard" };

function $(id) { return document.getElementById(id); }
function session() { try { return JSON.parse(sessionStorage.getItem("wuf.session")); } catch (e) { return null; } }

function login(event) {
  event.preventDefault();
  const email = $("email").value.trim().toLowerCase();
  const user = USERS[email];
  if (!user || $("password").value !== PASSWORD) {
    $("loginError").textContent = "Correo o contraseña incorrectos.";
    return false;
  }
  sessionStorage.setItem("wuf.session", JSON.stringify({ email: email, rol: user.rol }));
  $("loginError").textContent = "";
  enterApp(HOME[user.rol]);
  return false;
}

function logout() {
  sessionStorage.removeItem("wuf.session");
  location.hash = "";
  $("app").style.display = "none";
  $("login").style.display = "flex";
}

function enterApp(view) {
  const s = session();
  const user = USERS[s.email];
  $("login").style.display = "none";
  $("app").style.display = "block";
  $("roleHint").textContent = user.etiqueta;
  $("whoName").textContent = user.nombre;
  $("whoRole").textContent = s.email;
  $("avatarTxt").textContent = user.iniciales;
  $("cfgNombre").value = user.nombre;
  $("cfgEmail").value = s.email;
  document.querySelectorAll("[data-roles]").forEach(function (el) {
    el.classList.toggle("hidden", el.dataset.roles.split(" ").indexOf(s.email ? user.rol : "") === -1);
  });
  showView(view);
}

function allowed(view) {
  const s = session();
  if (!s) return false;
  const item = document.querySelector('.navitem[data-view="' + view + '"]');
  return !!item && item.dataset.roles.split(" ").indexOf(s.rol) !== -1;
}

function showView(name) {
  if (!allowed(name)) name = HOME[session().rol];
  document.querySelectorAll(".view").forEach(function (v) { v.classList.add("hidden"); });
  $("view-" + name).classList.remove("hidden");
  document.querySelectorAll(".navitem").forEach(function (n) { n.classList.toggle("active", n.dataset.view === name); });
  $("topTitle").textContent = document.querySelector('#view-' + name + ' h1').textContent;
  $("sidebar").classList.remove("open");
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
  window.scrollTo(0, 0);
}

function applyTheme(value) {
  if (value === "sistema") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", value);
  localStorage.setItem("wuf.theme", value);
  $("cfgTema").value = value;
}

document.addEventListener("DOMContentLoaded", function () {
  lucide.createIcons();
  applyTheme(localStorage.getItem("wuf.theme") || "sistema");
  document.querySelectorAll(".navitem").forEach(function (n) {
    n.addEventListener("click", function (e) { e.preventDefault(); showView(n.dataset.view); });
  });
  window.addEventListener("hashchange", function () { if (session()) showView(location.hash.slice(1)); });
  const s = session();
  if (s && USERS[s.email]) enterApp(location.hash.slice(1) || HOME[s.rol]);
});
