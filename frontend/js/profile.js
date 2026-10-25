/* SkillConnect - My profile page (UI-4). Account info for everyone; provider section for providers. */

const WEEKDAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"];
const dayName = (d) => d.charAt(0) + d.slice(1).toLowerCase();

function field(label, input, hint) {
  return el("div", {}, el("label", { text: label }), input, hint ? el("div", { class: "hint", text: hint }) : null);
}

function flash(box, text, isError) {
  box.textContent = text;
  box.className = isError ? "notice error" : "notice ok";
  box.style.display = "";
  if (!isError) setTimeout(() => { box.style.display = "none"; }, 3000);
}

async function showPhotoControls(user, holder) {
  const input = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp" });
  const msg = el("div", { style: "display:none" });
  input.addEventListener("change", async () => {
    if (!input.files[0]) return;
    const fd = new FormData();
    fd.append("file", input.files[0]);
    try {
      const u = await api("/api/users/me/photo", { method: "POST", body: fd });
      holder.replaceChildren(avatar(u.full_name, u.photo_url, true));
      flash(msg, "Photo updated.", false);
    } catch (error) { flash(msg, error.message, true); }
  });
  return el("div", {}, input, el("div", { class: "hint", text: "JPG, PNG or WEBP, max 2 MB." }), msg);
}

async function accountSection(user) {
  const name = el("input", { type: "text", value: user.full_name, maxlength: "120" });
  const phone = el("input", { type: "tel", value: user.phone || "" });
  const bio = el("textarea", { rows: "3", maxlength: "1000" }); bio.value = user.bio || "";
  const city = el("input", { type: "text", value: user.location ? user.location.city : "", maxlength: "100" });
  const area = el("input", { type: "text", value: user.location && user.location.area ? user.location.area : "", maxlength: "100" });
  const pin = el("input", { type: "text", value: user.location && user.location.pincode ? user.location.pincode : "", maxlength: "6", inputmode: "numeric" });
  const msg = el("div", { style: "display:none" });
  const save = el("button", { class: "btn", type: "button", text: "Save profile" });
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api("/api/users/me/profile", { method: "PUT", body: JSON.stringify({
        full_name: name.value.trim(), phone: phone.value.trim() || null, bio: bio.value.trim() || null,
        location: city.value.trim() ? { city: city.value.trim(), area: area.value.trim() || null, pincode: pin.value.trim() || null } : null,
      }) });
      flash(msg, "Profile saved.", false);
    } catch (error) { flash(msg, error.message, true); }
    save.disabled = false;
  });
  const photoHolder = el("div", {}, avatar(user.full_name, user.photo_url, true));
  const photoControls = await showPhotoControls(user, photoHolder);
  return el("div", { class: "card" }, el("h2", { text: "My details" }),
    el("div", { class: "profile-head" }, photoHolder, photoControls),
    field("Full name", name), field("Email", el("input", { type: "email", value: user.email, disabled: "disabled" }), "Email cannot be changed."),
    field("Phone", phone), field("About me", bio),
    el("div", { class: "row2" }, field("City", city), field("Area", area)),
    field("Pincode", pin, "6 digits (optional)"),
    el("p", { class: "hint", text: "Your city is used for searching and for service requests." }), msg, save);
}

async function providerSections(root) {
  const p = await api("/api/providers/me");
  const cats = await api("/api/services/categories");

  // ---- professional details
  const desc = el("textarea", { rows: "4", maxlength: "2000" }); desc.value = p.description || "";
  const exp = el("input", { type: "number", min: "0", max: "60", value: p.experience_years ?? "" });
  const qual = el("input", { type: "text", maxlength: "255", value: p.qualification || "" });
  const area = el("input", { type: "text", maxlength: "255", value: p.working_area || "" });
  const mode = el("select", {}, [["BOTH", "One-time and regular"], ["NON_REGULAR", "One-time only"], ["REGULAR", "Regular only"]]
    .map(([v, t]) => el("option", { value: v, text: t, selected: p.service_mode === v ? "selected" : null })));
  const price = el("input", { type: "text", maxlength: "500", value: p.pricing_info || "", placeholder: "e.g. Rs 300 per visit" });
  const notes = el("input", { type: "text", maxlength: "255", value: p.availability_notes || "" });
  const m1 = el("div", { style: "display:none" });
  const s1 = el("button", { class: "btn", type: "button", text: "Save details" });
  s1.addEventListener("click", async () => {
    try {
      await api("/api/providers/me", { method: "PUT", body: JSON.stringify({
        description: desc.value.trim(), experience_years: exp.value === "" ? null : Number(exp.value),
        qualification: qual.value.trim() || null, working_area: area.value.trim() || null,
        service_mode: mode.value, pricing_info: price.value.trim() || null, availability_notes: notes.value.trim() || null }) });
      flash(m1, "Details saved.", false);
    } catch (error) { flash(m1, error.message, true); }
  });

  // ---- skills
  const chosen = new Set(p.skills.map((s) => s.id));
  const skillBox = el("div", {});
  cats.forEach((c) => {
    skillBox.appendChild(el("h3", { text: c.name, style: "margin-top:12px" }));
    skillBox.appendChild(el("div", { class: "days" }, c.skills.map((s) => {
      const cb = el("input", { type: "checkbox", value: String(s.id), class: "sk" });
      cb.checked = chosen.has(s.id);
      return el("label", {}, cb, s.name);
    })));
  });
  const m2 = el("div", { style: "display:none" });
  const s2 = el("button", { class: "btn", type: "button", text: "Save skills" });
  s2.addEventListener("click", async () => {
    const ids = [...document.querySelectorAll(".sk:checked")].map((c) => Number(c.value));
    try {
      await api("/api/providers/me/skills", { method: "PUT", body: JSON.stringify({ skill_ids: ids }) });
      flash(m2, "Skills saved.", false);
    } catch (error) { flash(m2, error.message, true); }
  });

  // ---- availability
  const rows = el("div", {});
  const addRow = (slot) => {
    const day = el("select", { class: "av-day" }, WEEKDAYS.map((d) => el("option", { value: d, text: dayName(d), selected: slot && slot.day_of_week === d ? "selected" : null })));
    const from = el("input", { type: "time", class: "av-from", value: slot ? slot.start_time.slice(0, 5) : "09:00" });
    const to = el("input", { type: "time", class: "av-to", value: slot ? slot.end_time.slice(0, 5) : "17:00" });
    const del = el("button", { class: "btn secondary", type: "button", text: "Remove" });
    const row = el("div", { class: "slot" }, day, from, to, del);
    del.addEventListener("click", () => row.remove());
    rows.appendChild(row);
  };
  p.availability.forEach(addRow);
  const addBtn = el("button", { class: "btn secondary", type: "button", text: "+ Add time slot" });
  addBtn.addEventListener("click", () => addRow(null));
  const m3 = el("div", { style: "display:none" });
  const s3 = el("button", { class: "btn", type: "button", text: "Save availability" });
  s3.addEventListener("click", async () => {
    const slots = [...rows.children].map((r) => ({ day_of_week: r.querySelector(".av-day").value, start_time: r.querySelector(".av-from").value, end_time: r.querySelector(".av-to").value }));
    try {
      await api("/api/providers/me/availability", { method: "PUT", body: JSON.stringify({ slots }) });
      flash(m3, "Availability saved.", false);
    } catch (error) { flash(m3, error.message, true); }
  });

  root.append(
    el("div", { class: "card" }, el("h2", { text: "Professional details" }),
      p.is_complete ? el("div", { class: "notice ok", text: "Your profile is complete and visible in search." }) : el("div", { class: "notice", text: "Add city, description and at least one skill to appear in search." }),
      field("Description (min 10 characters)", desc), el("div", { class: "row2" }, field("Experience (years)", exp), field("Service type", mode)),
      field("Qualification", qual), field("Working area", area), field("Pricing", price), field("Availability notes", notes), m1, s1),
    el("div", { class: "card" }, el("h2", { text: "My skills" }), skillBox, m2, s2),
    el("div", { class: "card" }, el("h2", { text: "Weekly availability" }), rows, addBtn, el("div", { style: "height:10px" }), m3, s3));
}

async function loadProfile() {
  const root = document.getElementById("profile-root");
  if (!root) return;
  if (!getToken()) { window.location.href = "/login.html"; return; }
  root.replaceChildren(el("div", { class: "loading", text: "Loading..." }));
  try {
    const user = await api("/api/users/me/profile");
    root.replaceChildren(await accountSection(user));
    if (user.role === "PROVIDER") await providerSections(root);
  } catch (error) {
    if (/token|authenticated|user not found/i.test(error.message)) { clearToken(); window.location.href = "/login.html"; return; }
    root.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}
document.addEventListener("DOMContentLoaded", loadProfile);
