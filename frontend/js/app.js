const TOKEN_KEY = "skillconnect_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...(options.headers || {}),
  };
  const response = await fetch(path, { ...options, headers });
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : "Request failed.";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function currentPage() {
  const name = window.location.pathname.split("/").pop();
  return name || "index.html";
}

function renderNav() {
  const nav = document.querySelector("header nav");
  if (!nav) {
    return;
  }
  const page = currentPage();
  const loggedIn = Boolean(getToken());
  const links = [
    { href: "/", label: "Home", file: "index.html" },
    { href: "/search.html", label: "Search", file: "search.html" },
  ];
  if (loggedIn) {
    links.push({ href: "/dashboard.html", label: "Dashboard", file: "dashboard.html" });
  } else {
    links.push({ href: "/login.html", label: "Login", file: "login.html" });
    links.push({ href: "/register.html", label: "Register", file: "register.html" });
  }

  nav.innerHTML = "";
  links.forEach((link) => {
    const a = document.createElement("a");
    a.href = link.href;
    a.textContent = link.label;
    if (page === link.file || (page === "" && link.file === "index.html")) {
      a.classList.add("active");
    }
    nav.appendChild(a);
  });

  if (loggedIn) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "linkish";
    button.textContent = "Logout";
    button.addEventListener("click", async () => {
      try {
        await api("/api/auth/logout", { method: "POST" });
      } catch (error) {
        // Token may already be invalid; still clear it locally.
      }
      clearToken();
      window.location.href = "/login.html";
    });
    nav.appendChild(button);
  }
}

async function checkHealth() {
  const el = document.getElementById("health-status");
  if (!el) {
    return;
  }

  try {
    const data = await api("/api/health");
    const db = data.database_connected ? "MySQL connected" : "MySQL not connected yet";
    el.textContent = `Backend: ${data.status} · ${db}`;
    if (!data.database_connected) {
      el.classList.add("error");
    }
  } catch (error) {
    el.textContent = "Backend is not reachable. Start FastAPI first.";
    el.classList.add("error");
  }
}

function showFormError(message) {
  const el = document.getElementById("form-error");
  if (el) {
    el.textContent = message;
  }
}

function bindRegisterForm() {
  const form = document.getElementById("register-form");
  if (!form) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormError("");
    const payload = {
      full_name: form.full_name.value,
      email: form.email.value,
      password: form.password.value,
      role: form.role.value,
      phone: form.phone.value || null,
    };
    try {
      const data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setToken(data.access_token);
      window.location.href = "/dashboard.html";
    } catch (error) {
      showFormError(error.message);
    }
  });
}

function bindLoginForm() {
  const form = document.getElementById("login-form");
  if (!form) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFormError("");
    const payload = {
      email: form.email.value,
      password: form.password.value,
    };
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setToken(data.access_token);
      window.location.href = "/dashboard.html";
    } catch (error) {
      showFormError(error.message);
    }
  });
}

async function loadDashboard() {
  const box = document.getElementById("dashboard-user");
  if (!box) {
    return;
  }
  if (!getToken()) {
    window.location.href = "/login.html";
    return;
  }
  try {
    const user = await api("/api/auth/me");
    box.innerHTML = `
      <p><strong>Name:</strong> ${user.full_name}</p>
      <p><strong>Email:</strong> ${user.email}</p>
      <p><strong>Role:</strong> ${user.role}</p>
    `;
  } catch (error) {
    clearToken();
    window.location.href = "/login.html";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderNav();
  checkHealth();
  bindRegisterForm();
  bindLoginForm();
  loadDashboard();
});
