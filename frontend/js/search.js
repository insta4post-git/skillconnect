/* SkillConnect - search page (UI-2). Needs app.js first. */

function initials(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}

function avatar(name, photoUrl, big) {
  const box = el("div", { class: big ? "avatar big" : "avatar" });
  if (photoUrl && photoUrl.startsWith("/uploads/")) {
    box.appendChild(el("img", { src: photoUrl, alt: "" }));
  } else {
    box.textContent = initials(name);
  }
  return box;
}

function stars(avg) {
  if (!avg) return "No reviews yet";
  const full = Math.round(avg);
  return "★".repeat(full) + "☆".repeat(5 - full);
}

function ratingLine(avg, count) {
  return el("div", { class: "small" },
    avg ? el("span", { class: "stars", text: stars(avg) }) : null,
    avg ? ` ${avg.toFixed(1)} (${count} review${count === 1 ? "" : "s"})` : el("span", { class: "muted", text: "No reviews yet" }));
}

function placeText(loc) {
  if (!loc) return "Location not set";
  return [loc.area, loc.city].filter(Boolean).join(", ");
}

function providerCard(p) {
  return el("div", { class: "card provider-card" },
    avatar(p.full_name, p.photo_url),
    el("div", { class: "info" },
      el("h3", {}, el("a", { href: `/provider.html?id=${p.user_id}`, text: p.full_name })),
      el("div", { class: "small muted", text: `${placeText(p.location)}${p.experience_years ? ` · ${p.experience_years} yrs experience` : ""}` }),
      ratingLine(p.avg_rating, p.review_count),
      el("div", { class: "chips" }, p.skills.map((s) => el("span", { class: "chip", text: s.name }))),
      p.summary ? el("p", { class: "small", text: p.summary }) : null,
      el("a", { class: "btn secondary", href: `/provider.html?id=${p.user_id}`, text: "View profile" })));
}

const state = { page: 1 };

function buildQuery() {
  const f = document.getElementById("filters");
  const params = new URLSearchParams();
  const add = (k, v) => { if (v) params.set(k, v); };
  add("q", f.q.value.trim());
  add("category_id", f.category_id.value);
  add("city", f.city.value.trim());
  add("area", f.area.value.trim());
  add("service_type", f.service_type.value);
  add("min_rating", f.min_rating.value);
  if (f.near_me.checked) params.set("near_me", "true");
  params.set("page", String(state.page));
  params.set("page_size", "10");
  return params.toString();
}

async function runSearch() {
  const box = document.getElementById("results");
  const pager = document.getElementById("pager");
  box.replaceChildren(el("div", { class: "loading", text: "Searching..." }));
  pager.replaceChildren();
  try {
    const data = await api(`/api/search/providers?${buildQuery()}`);
    box.replaceChildren(el("p", { class: "muted small", text: `${data.total} provider${data.total === 1 ? "" : "s"} found` }));
    if (data.results.length === 0) {
      box.appendChild(el("div", { class: "card empty", text: "No providers match. Try fewer filters." }));
    }
    data.results.forEach((p) => box.appendChild(providerCard(p)));
    if (data.page > 1 || data.has_more) {
      const prev = el("button", { class: "btn secondary", type: "button", text: "Previous" });
      const next = el("button", { class: "btn secondary", type: "button", text: "Next" });
      prev.disabled = data.page <= 1;
      next.disabled = !data.has_more;
      prev.addEventListener("click", () => { state.page -= 1; runSearch(); });
      next.addEventListener("click", () => { state.page += 1; runSearch(); });
      pager.append(prev, el("span", { class: "small muted", text: `Page ${data.page}` }), next);
    }
  } catch (error) {
    box.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}

async function initSearch() {
  const f = document.getElementById("filters");
  if (!f) return;
  try {
    const cats = await api("/api/services/categories");
    cats.forEach((c) => f.category_id.appendChild(el("option", { value: String(c.id), text: c.name })));
  } catch (e) { /* the filter simply stays empty */ }
  if (!getToken()) {
    f.near_me.disabled = true;
    document.getElementById("near-me-label").textContent = "Near me (log in to use)";
  }
  f.addEventListener("submit", (event) => {
    event.preventDefault();
    state.page = 1;
    runSearch();
  });
  runSearch();
}

document.addEventListener("DOMContentLoaded", initSearch);
