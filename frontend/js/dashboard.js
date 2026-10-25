/* SkillConnect - dashboard page (UI-1). Needs app.js loaded first. */

function statCard(num, label) {
  return el("div", { class: "card stat" }, el("div", { class: "num", text: String(num) }), el("div", { class: "label", text: label }));
}

function when(r) {
  if (r.scheduled_at) return new Date(r.scheduled_at).toLocaleString();
  if (r.start_date) return `${r.start_date} to ${r.end_date}`;
  return "";
}

// viewerRole decides which person we show: a customer sees the provider and vice versa.
function requestList(items, viewerRole, emptyText) {
  if (!items || items.length === 0) return el("p", { class: "empty", text: emptyText });
  const ul = el("ul", { class: "list" });
  items.forEach((r) => {
    const other = viewerRole === "CUSTOMER" ? r.provider : r.customer;
    const left = el("div", {},
      el("strong", { text: r.skill.name }),
      el("div", { class: "small muted", text: `${other.full_name} · ${when(r)}` }));
    if (other.email || other.phone) {
      left.appendChild(el("div", { class: "small", text: [other.email, other.phone].filter(Boolean).join(" · ") }));
    }
    ul.appendChild(el("li", {}, left, el("span", { class: `badge st-${r.status}`, text: r.status })));
  });
  return ul;
}

function section(title, ...content) {
  return el("div", { class: "card" }, el("h2", { text: title }), ...content);
}

function statsRow(counts, extra = []) {
  return el("div", { class: "grid cols-4", style: "margin-bottom:16px" },
    statCard(counts.total, "Total requests"),
    statCard(counts.pending, "Pending"),
    statCard(counts.accepted, "Accepted"),
    statCard(counts.completed, "Completed"),
    ...extra);
}

function renderCustomer(d) {
  return [
    statsRow(d.requests, [statCard(d.reviews_pending, "Reviews to write")]),
    el("div", { class: "grid cols-2" },
      section("Recent requests", requestList(d.recent_requests, "CUSTOMER", "You have not sent any request yet.")),
      section("Accepted services", requestList(d.accepted_services, "CUSTOMER", "No accepted service yet."))),
    section("Quick actions", el("div", { class: "btn-row", style: "justify-content:flex-start" },
      el("a", { class: "btn", href: "/search.html", text: "Find a provider" }))),
  ];
}

function renderProvider(d) {
  const c = d.checklist;
  const item = (ok, text) => el("li", { class: ok ? "yes" : "no", text: `${ok ? "✔" : "✘"} ${text}` });
  const rating = d.avg_rating ? `${d.avg_rating.toFixed(1)} ★ (${d.review_count} reviews)` : "No reviews yet";
  return [
    c.visible_in_search ? null : el("div", { class: "notice", text: "Your profile is not visible in search yet. Complete the items marked ✘ below." }),
    statsRow(d.requests, [statCard(d.skills_count, "Skills"), statCard(rating, "Rating")]),
    el("div", { class: "grid cols-2" },
      section("Incoming requests", requestList(d.incoming_requests, "PROVIDER", "No pending requests.")),
      section("Accepted jobs", requestList(d.accepted_jobs, "PROVIDER", "No accepted jobs yet."))),
    section("Profile checklist", el("ul", { class: "checklist" },
      item(c.has_location, "Location added"),
      item(c.has_description, "Description added"),
      item(c.has_skills, "At least one skill added"),
      item(c.has_availability, "Availability added"))),
  ];
}

function renderAdmin(d) {
  return [
    el("div", { class: "grid cols-4", style: "margin-bottom:16px" },
      statCard(d.users.total, "Users"),
      statCard(d.users.customers, "Customers"),
      statCard(d.users.providers, "Providers"),
      statCard(d.new_users_7d, "New (7 days)"),
      statCard(d.skills_total, "Skills"),
      statCard(d.requests.total, "Requests"),
      statCard(d.messages_total, "Messages"),
      statCard(d.reviews_total, "Reviews")),
    section("Requests by status", el("ul", { class: "list" },
      ...["pending", "accepted", "rejected", "cancelled", "completed"].map((s) =>
        el("li", {}, el("span", { text: s.toUpperCase() }), el("strong", { text: String(d.requests[s]) }))))),
  ];
}

async function loadDashboard() {
  const root = document.getElementById("dashboard-root");
  if (!root) return;
  if (!getToken()) {
    window.location.href = "/login.html";
    return;
  }
  root.replaceChildren(el("div", { class: "loading", text: "Loading your dashboard..." }));
  try {
    const me = await api("/api/auth/me");
    const role = me.role;
    const path = { CUSTOMER: "customer", PROVIDER: "provider", ADMIN: "admin" }[role];
    const data = await api(`/api/dashboard/${path}`);
    const render = { CUSTOMER: renderCustomer, PROVIDER: renderProvider, ADMIN: renderAdmin }[role];
    root.replaceChildren(
      el("div", { class: "welcome" },
        el("div", {}, el("h1", { text: `Hello, ${me.full_name}` }), el("span", { class: "badge", text: role })),
      ),
      ...render(data).filter(Boolean));
  } catch (error) {
    // 401 means the login expired; anything else is shown to the user.
    if (/token|authenticated|user not found/i.test(error.message)) {
      clearToken();
      window.location.href = "/login.html";
      return;
    }
    root.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}

document.addEventListener("DOMContentLoaded", loadDashboard);
