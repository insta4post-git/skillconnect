/* SkillConnect - shared helpers used by every page (UI-1).
   Rule: user text is ALWAYS shown with textContent, never innerHTML (prevents XSS). */

const TOKEN_KEY = "skillconnect_token";

function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
}
function setToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token); } catch (e) { /* storage blocked */ }
}
function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* ignore */ }
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch (e) {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  let data = null;
  try { data = await response.json(); } catch (e) { data = null; }
  if (!response.ok) {
    throw new Error(errorText(data, response.status));
  }
  return data;
}

// Turns FastAPI error bodies into one readable message.
function errorText(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) {
    return data.detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "";
        const msg = String(d.msg || "Invalid value").replace(/^Value error, /, "");
        return field && field !== "body" ? `${field}: ${msg}` : msg;
      })
      .join("\n");
  }
  if (status === 429) return "Too many attempts. Please wait a minute and try again.";
  return "Something went wrong. Please try again.";
}

// el("div", {class: "card"}, "text", childNode) - builds elements safely.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === null || value === undefined || value === false) return;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  });
  children.flat().forEach((child) => {
    if (child === null || child === undefined || child === false) return;
    node.appendChild(typeof child === "string" || typeof child === "number" ? document.createTextNode(String(child)) : child);
  });
  return node;
}

// Role is read from the token only to decide which menu links to SHOW.
// The server still checks the real role on every request.
function tokenRole() {
  try {
    const payload = JSON.parse(atob(getToken().split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.role || null;
  } catch (e) { return null; }
}

// Server times without a zone are UTC (messages, reviews); add the Z so the browser converts to local time.
function utcDate(value) {
  return new Date(/[zZ]$|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
}

function currentPage() {
  return window.location.pathname.split("/").pop() || "index.html";
}

function logout() {
  api("/api/auth/logout", { method: "POST" })
    .catch(() => {})
    .finally(() => {
      clearToken();
      window.location.href = "/login.html";
    });
}

function renderNav() {
  const nav = document.querySelector("header nav");
  if (!nav) return;
  const page = currentPage();
  const loggedIn = Boolean(getToken());
  const links = [
    ["/", "Home", "index.html"],
    ["/search.html", "Find providers", "search.html"],
  ];
  if (loggedIn) {
    const role = tokenRole();
    links.push(["/dashboard.html", "Dashboard", "dashboard.html"]);
    if (role === "ADMIN") {
      links.push(["/admin.html", "Admin", "admin.html"]);
    } else {
      links.push(["/requests.html", "Requests", "requests.html"]);
      links.push(["/messages.html", "Messages", "messages.html"]);
    }
    links.push(["/profile.html", "My profile", "profile.html"]);
  } else {
    links.push(["/login.html", "Login", "login.html"]);
    links.push(["/register.html", "Register", "register.html"]);
  }
  nav.replaceChildren();
  links.forEach(([href, label, file]) => {
    nav.appendChild(el("a", { href, class: page === file ? "active" : null, text: label }));
  });
  if (loggedIn) {
    const button = el("button", { type: "button", class: "linkish", text: "Logout" });
    button.addEventListener("click", () => {
      if (confirm("Are you sure you want to log out?")) {
        logout();
      }
    });
    nav.appendChild(button);
  }
}

function showFormError(message) {
  const box = document.getElementById("form-error");
  if (!box) return;
  box.textContent = message || "";
  box.classList.toggle("show", Boolean(message));
}

function bindForm(formId, endpoint, buildPayload, busyText) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormError("");
    const button = form.querySelector("button[type=submit]");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
    try {
      const data = await api(endpoint, { method: "POST", body: JSON.stringify(buildPayload(form)) });
      setToken(data.access_token);
      window.location.href = "/dashboard.html";
    } catch (error) {
      showFormError(error.message);
      button.disabled = false;
      button.textContent = original;
    }
  });
}

function bindAuthForms() {
  bindForm("login-form", "/api/auth/login", (f) => ({
    email: f.email.value.trim(),
    password: f.password.value,
  }), "Logging in...");
  bindForm("register-form", "/api/auth/register", (f) => ({
    full_name: f.full_name.value.trim(),
    email: f.email.value.trim(),
    password: f.password.value,
    role: f.role.value,
    phone: f.phone.value.trim() || null,
  }), "Creating account...");
}

// If a logged-in user opens login/register, send them to the dashboard.
function redirectIfLoggedIn() {
  const page = currentPage();
  if (getToken() && (page === "login.html" || page === "register.html")) {
    window.location.href = "/dashboard.html";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  redirectIfLoggedIn();
  renderNav();
  bindAuthForms();
});