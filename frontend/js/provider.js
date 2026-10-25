/* SkillConnect - public provider profile + request form (UI-2). Needs app.js and search.js first. */

const DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"];
const cap = (s) => s.charAt(0) + s.slice(1).toLowerCase();

function reviewItem(r) {
  return el("div", { class: "review" },
    el("div", {}, el("span", { class: "stars", text: "★".repeat(r.rating) + "☆".repeat(5 - r.rating) }), ` ${r.reviewer_name}`),
    el("div", { class: "small muted", text: `${r.skill_name} · ${new Date(r.created_at).toLocaleDateString()}` }),
    r.comment ? el("p", { class: "small", text: r.comment }) : null);
}

function breakdown(b, total) {
  const rows = [["5", b.five], ["4", b.four], ["3", b.three], ["2", b.two], ["1", b.one]];
  return el("div", {}, rows.map(([label, n]) => {
    const bar = el("span");
    bar.style.width = total ? `${Math.round((n / total) * 100)}%` : "0%";
    return el("div", { class: "bar-row" }, el("span", { text: `${label}★` }), el("div", { class: "bar" }, bar), el("span", { text: String(n) }));
  }));
}

function renderProfile(p) {
  return [
    el("div", { class: "card" },
      el("div", { class: "profile-head" },
        avatar(p.full_name, p.photo_url, true),
        el("div", {},
          el("h1", { text: p.full_name }),
          el("div", { class: "muted", text: placeText(p.location) }),
          ratingLine(p.avg_rating, p.review_count),
          el("div", { class: "small muted", text: `${p.completed_jobs} completed job${p.completed_jobs === 1 ? "" : "s"}${p.experience_years ? ` · ${p.experience_years} yrs experience` : ""}` }))),
      el("div", { class: "chips" }, p.skills.map((s) => el("span", { class: "chip", text: s.name }))),
      p.description ? el("p", { text: p.description }) : null,
      p.qualification ? el("p", { class: "small" }, el("strong", { text: "Qualification: " }), p.qualification) : null,
      p.working_area ? el("p", { class: "small" }, el("strong", { text: "Working area: " }), p.working_area) : null,
      p.pricing_info ? el("p", { class: "small" }, el("strong", { text: "Pricing: " }), p.pricing_info) : null,
      p.available_days.length ? el("p", { class: "small" }, el("strong", { text: "Available: " }), p.available_days.map(cap).join(", ")) : null),
    el("div", { class: "card" },
      el("h2", { text: "Reviews" }),
      p.review_count ? breakdown(p.rating_breakdown, p.review_count) : null,
      p.recent_reviews.length ? p.recent_reviews.map(reviewItem) : el("p", { class: "empty", text: "No reviews yet." })),
  ];
}

function requestForm(p) {
  let mode = "short";
  const card = el("div", { class: "card", id: "request-card" }, el("h2", { text: "Send a request" }));
  const shortBtn = el("button", { type: "button", class: "on", text: "One-time job" });
  const longBtn = el("button", { type: "button", text: "Regular work" });
  const skill = el("select", { id: "r-skill", required: "required" }, p.skills.map((s) => el("option", { value: String(s.id), text: s.name })));
  const shortBox = el("div", {},
    el("div", { class: "row2" },
      el("div", {}, el("label", { for: "r-date", text: "Date" }), el("input", { id: "r-date", type: "date" })),
      el("div", {}, el("label", { for: "r-time", text: "Start time" }), el("input", { id: "r-time", type: "time" }))),
    el("label", { for: "r-hours", text: "Duration (hours)" }),
    el("input", { id: "r-hours", type: "number", min: "0.5", max: "12", step: "0.5", value: "2" }));
  const dayBoxes = DAYS.map((d) => el("label", {}, el("input", { type: "checkbox", value: d, class: "r-day" }), cap(d).slice(0, 3)));
  const longBox = el("div", { style: "display:none" },
    el("div", { class: "row2" },
      el("div", {}, el("label", { for: "r-start", text: "Start date" }), el("input", { id: "r-start", type: "date" })),
      el("div", {}, el("label", { for: "r-end", text: "End date" }), el("input", { id: "r-end", type: "date" }))),
    el("label", { text: "Working days" }), el("div", { class: "days" }, dayBoxes),
    el("div", { class: "row2" },
      el("div", {}, el("label", { for: "r-from", text: "Daily start" }), el("input", { id: "r-from", type: "time" })),
      el("div", {}, el("label", { for: "r-to", text: "Daily end" }), el("input", { id: "r-to", type: "time" }))));
  const details = el("textarea", { id: "r-details", rows: "3", maxlength: "1000", placeholder: "Describe the work (at least 10 characters)" });
  const address = el("input", { id: "r-address", type: "text", maxlength: "255", placeholder: "House no., landmark (optional)" });
  const msg = el("div", { class: "form-error", id: "r-error", role: "alert" });
  const ok = el("div", { class: "notice ok", style: "display:none" });
  const submit = el("button", { class: "btn", type: "submit", text: "Send request" });
  const form = el("form", { novalidate: "novalidate" },
    el("div", { class: "tabs" }, shortBtn, longBtn),
    el("label", { for: "r-skill", text: "Skill needed" }), skill,
    shortBox, longBox,
    el("label", { for: "r-details", text: "Details" }), details,
    el("label", { for: "r-address", text: "Address details" }), address,
    el("div", { class: "hint", text: "The location saved in your profile is used for this request." }),
    msg, ok, submit);
  const setMode = (m) => {
    mode = m;
    shortBtn.classList.toggle("on", m === "short");
    longBtn.classList.toggle("on", m === "long");
    shortBox.style.display = m === "short" ? "" : "none";
    longBox.style.display = m === "long" ? "" : "none";
  };
  shortBtn.addEventListener("click", () => setMode("short"));
  longBtn.addEventListener("click", () => setMode("long"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    msg.classList.remove("show");
    const v = (id) => document.getElementById(id).value;
    const base = {
      provider_id: p.user_id,
      skill_id: Number(skill.value),
      details: details.value.trim(),
      address_details: address.value.trim() || null,
    };
    let path, body;
    if (mode === "short") {
      path = "/api/requests/short-term";
      body = { ...base, service_date: v("r-date"), start_time: v("r-time"), duration_hours: Number(v("r-hours")) };
    } else {
      path = "/api/requests/regular";
      body = { ...base, start_date: v("r-start"), end_date: v("r-end"),
        working_days: [...document.querySelectorAll(".r-day:checked")].map((c) => c.value),
        start_time: v("r-from"), end_time: v("r-to") };
    }
    submit.disabled = true;
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      ok.textContent = "Request sent! The provider will accept or reject it. Track it on your dashboard.";
      ok.style.display = "";
      form.querySelectorAll("input,select,textarea").forEach((x) => { x.disabled = true; });
      submit.textContent = "Sent";
    } catch (error) {
      msg.textContent = error.message;
      msg.classList.add("show");
      submit.disabled = false;
    }
  });
  card.appendChild(form);
  return card;
}

function requestArea(p, me) {
  if (!me) {
    return el("div", { class: "card" }, el("h2", { text: "Send a request" }),
      el("p", {}, el("a", { href: "/login.html", text: "Log in" }), " or ", el("a", { href: "/register.html", text: "create a customer account" }), " to send a request."));
  }
  if (me.role !== "CUSTOMER") {
    return el("div", { class: "notice", text: "Only customer accounts can send requests." });
  }
  if (p.skills.length === 0) {
    return el("div", { class: "notice", text: "This provider has not added any skills yet." });
  }
  return requestForm(p);
}

async function loadProvider() {
  const root = document.getElementById("provider-root");
  if (!root) return;
  const id = Number(new URLSearchParams(window.location.search).get("id"));
  if (!Number.isInteger(id) || id < 1) {
    root.replaceChildren(el("div", { class: "notice error", text: "Provider not found." }));
    return;
  }
  root.replaceChildren(el("div", { class: "loading", text: "Loading..." }));
  try {
    const p = await api(`/api/providers/${id}`);
    let me = null;
    if (getToken()) {
      try { me = await api("/api/auth/me"); } catch (e) { me = null; }
    }
    root.replaceChildren(el("div", { class: "grid cols-2" },
      el("div", {}, ...renderProfile(p)), el("div", {}, requestArea(p, me))));
  } catch (error) {
    root.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}

document.addEventListener("DOMContentLoaded", loadProvider);
