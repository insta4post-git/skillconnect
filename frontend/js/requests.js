/* SkillConnect - My requests page (UI-3). Needs app.js and search.js first. */

let ME = null;
let reviewed = new Set();

function whenText(r) {
  if (r.scheduled_at) return new Date(r.scheduled_at).toLocaleString();
  const days = (r.working_days || []).map((d) => d.slice(0, 3)).join(", ");
  return `${r.start_date} to ${r.end_date} (${days}) ${r.start_time ? r.start_time.slice(0, 5) : ""}-${r.end_time ? r.end_time.slice(0, 5) : ""}`;
}

async function doAction(id, action, box) {
  box.textContent = "";
  if (action === "cancel" && !confirm("Cancel this request?")) return;
  if (action === "reject" && !confirm("Reject this request?")) return;
  try {
    await api(`/api/requests/${id}/${action}`, { method: "POST" });
    loadRequests();
  } catch (error) {
    box.textContent = error.message;
    box.classList.add("show");
  }
}

function reviewForm(r, holder) {
  const rating = el("select", { id: `rt-${r.id}` },
    [5, 4, 3, 2, 1].map((n) => el("option", { value: String(n), text: `${n} ${"★".repeat(n)}` })));
  const comment = el("textarea", { rows: "2", maxlength: "1000", placeholder: "Write a short review (optional)" });
  const err = el("div", { class: "form-error" });
  const send = el("button", { class: "btn", type: "button", text: "Submit review" });
  send.addEventListener("click", async () => {
    err.classList.remove("show");
    send.disabled = true;
    try {
      await api(`/api/requests/${r.id}/review`, { method: "POST", body: JSON.stringify({ rating: Number(rating.value), comment: comment.value.trim() || null }) });
      loadRequests();
    } catch (error) {
      err.textContent = error.message;
      err.classList.add("show");
      send.disabled = false;
    }
  });
  holder.replaceChildren(el("label", { text: "Your rating" }), rating, comment, err, send);
}

function requestCard(r) {
  const isCustomer = ME.role === "CUSTOMER";
  const other = isCustomer ? r.provider : r.customer;
  const err = el("div", { class: "form-error" });
  const actions = el("div", { class: "btn-row", style: "justify-content:flex-start;margin-top:10px" });
  const add = (label, action, secondary) => {
    const b = el("button", { class: secondary ? "btn secondary" : "btn", type: "button", text: label });
    b.addEventListener("click", () => doAction(r.id, action, err));
    actions.appendChild(b);
  };
  if (!isCustomer && r.status === "PENDING") { add("Accept", "accept"); add("Reject", "reject", true); }
  if (!isCustomer && r.status === "ACCEPTED") { add("Mark completed", "complete"); }
  if (r.status === "PENDING" || r.status === "ACCEPTED") { add("Cancel", "cancel", true); }
  if (r.status === "PENDING" || r.status === "ACCEPTED") {
    actions.appendChild(el("a", { class: "btn secondary", href: `/messages.html?request=${r.id}`, text: "Chat" }));
  }
  const reviewHolder = el("div");
  if (isCustomer && r.status === "COMPLETED") {
    if (reviewed.has(r.id)) {
      actions.appendChild(el("span", { class: "badge", text: "Reviewed ✔" }));
    } else {
      const b = el("button", { class: "btn", type: "button", text: "Write a review" });
      b.addEventListener("click", () => reviewForm(r, reviewHolder));
      actions.appendChild(b);
    }
    actions.appendChild(el("a", { class: "btn secondary", href: `/messages.html?request=${r.id}`, text: "View chat" }));
  }
  return el("div", { class: "card" },
    el("div", { class: "welcome", style: "margin:0" },
      el("h3", { text: `${r.skill.name} · ${other.full_name}` }),
      el("span", { class: `badge st-${r.status}`, text: r.status })),
    el("div", { class: "small muted", text: `${r.service_mode === "REGULAR" ? "Regular" : "One-time"} · ${whenText(r)}` }),
    r.location ? el("div", { class: "small", text: `Location: ${placeText(r.location)}${r.address_details ? ` · ${r.address_details}` : ""}` }) : null,
    r.details ? el("p", { class: "small", text: r.details }) : null,
    (other.email || other.phone) ? el("div", { class: "notice", text: `Contact: ${[other.email, other.phone].filter(Boolean).join(" · ")}` }) : null,
    actions, err, reviewHolder);
}

async function loadRequests() {
  const root = document.getElementById("requests-root");
  const status = document.getElementById("status-filter").value;
  root.replaceChildren(el("div", { class: "loading", text: "Loading..." }));
  try {
    if (!ME) ME = await api("/api/auth/me");
    if (ME.role === "ADMIN") { window.location.href = "/admin.html"; return; }
    if (ME.role === "CUSTOMER") {
      const mine = await api("/api/reviews/mine");
      reviewed = new Set(mine.map((x) => x.request_id));
    }
    const rows = await api(`/api/requests/mine?page_size=50${status ? `&status=${status}` : ""}`);
    root.replaceChildren();
    if (rows.length === 0) {
      root.appendChild(el("div", { class: "card empty", text: ME.role === "CUSTOMER" ? "No requests yet. Find a provider to get started." : "No requests yet." }));
    }
    rows.forEach((r) => root.appendChild(requestCard(r)));
  } catch (error) {
    if (/token|authenticated|user not found/i.test(error.message)) { clearToken(); window.location.href = "/login.html"; return; }
    root.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (!document.getElementById("requests-root")) return;
  if (!getToken()) { window.location.href = "/login.html"; return; }
  document.getElementById("status-filter").addEventListener("change", loadRequests);
  loadRequests();
});
