/* SkillConnect - Admin panel (UI-4). The server only answers if you really are an admin. */

const TABS = {
  users: { path: "/api/admin/users", cols: [["ID", "id"], ["Name", "full_name"], ["Email", "email"], ["Role", "role"], ["City", "city"]], search: true },
  providers: { path: "/api/admin/providers", cols: [["ID", "id"], ["Name", "full_name"], ["City", "city"], ["Skills", "skills_count"], ["Rating", "avg_rating"], ["Reviews", "review_count"], ["Requests", "requests_received"]], search: true },
  requests: { path: "/api/admin/requests", cols: [["ID", "id"], ["Status", "status"], ["Type", "service_mode"], ["Customer", "customer_name"], ["Provider", "provider_name"], ["Skill", "skill_name"]], status: true },
  skills: { path: "/api/admin/skills", cols: [["ID", "id"], ["Skill", "name"], ["Category", "category"], ["Source", "official"], ["Added by", "added_by"], ["Providers", "providers_count"], ["Requests", "requests_count"]], search: true, remove: true },
};
let tab = "users";

function cell(v, key) {
  if (key === "official") return v ? "Official" : "Custom";
  if (v === null || v === undefined || v === "") return "-";
  if (key === "avg_rating") return Number(v).toFixed(1);
  return String(v);
}

async function loadTab() {
  const cfg = TABS[tab];
  const out = document.getElementById("admin-table");
  const q = document.getElementById("admin-q").value.trim();
  const st = document.getElementById("admin-status").value;
  document.getElementById("admin-q").style.display = cfg.search ? "" : "none";
  document.getElementById("admin-status").style.display = cfg.status ? "" : "none";
  document.querySelectorAll("#admin-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  const params = new URLSearchParams({ page_size: "100" });
  if (cfg.search && q) params.set("q", q);
  if (cfg.status && st) params.set("status", st);
  out.replaceChildren(el("div", { class: "loading", text: "Loading..." }));
  try {
    const rows = await api(`${cfg.path}?${params}`);
    const head = el("tr", {}, cfg.cols.map(([t]) => el("th", { text: t })), cfg.remove ? el("th", { text: "" }) : null);
    const body = rows.map((r) => {
      const tr = el("tr", {}, cfg.cols.map(([, k]) => el("td", { text: cell(r[k], k) })));
      if (cfg.remove) {
        const td = el("td");
        if (!r.official) {
          const b = el("button", { class: "btn secondary", type: "button", text: "Delete" });
          b.addEventListener("click", async () => {
            if (!confirm(`Delete skill "${r.name}"?`)) return;
            try { await api(`/api/admin/skills/${r.id}`, { method: "DELETE" }); loadTab(); } catch (error) { alert(error.message); }
          });
          td.appendChild(b);
        }
        tr.appendChild(td);
      }
      return tr;
    });
    out.replaceChildren(el("p", { class: "muted small", text: `${rows.length} row${rows.length === 1 ? "" : "s"}` }),
      el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, body))));
  } catch (error) {
    out.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!document.getElementById("admin-table")) return;
  if (!getToken()) { window.location.href = "/login.html"; return; }
  document.querySelectorAll("#admin-tabs button").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.tab; document.getElementById("admin-q").value = ""; loadTab(); }));
  document.getElementById("admin-search").addEventListener("submit", (e) => { e.preventDefault(); loadTab(); });
  document.getElementById("admin-status").addEventListener("change", loadTab);
  loadTab();
});
