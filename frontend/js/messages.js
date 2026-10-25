/* SkillConnect - Messages page (UI-3). Needs app.js. Messages are shown with textContent only. */

let currentId = null;
let pollTimer = null;
let lastMessageId = 0;

function timeText(value) {
  return utcDate(value).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

async function loadInbox() {
  const box = document.getElementById("inbox");
  try {
    const items = await api("/api/messages/inbox");
    box.replaceChildren();
    if (items.length === 0) box.appendChild(el("p", { class: "empty", text: "No conversations yet. Open a request and use Chat." }));
    items.forEach((i) => {
      const row = el("a", { href: `/messages.html?request=${i.request_id}`, class: `inbox-item${i.request_id === currentId ? " on" : ""}` },
        el("strong", { text: i.other_party.full_name }),
        el("div", { class: "small muted", text: `${i.skill_name} · ${i.request_status}` }),
        el("div", { class: "small", text: `${i.last_message_is_mine ? "You: " : ""}${i.last_message}` }));
      box.appendChild(row);
    });
  } catch (error) {
    box.replaceChildren(el("div", { class: "notice error", text: error.message }));
  }
}

function bubble(m) {
  return el("div", { class: m.is_mine ? "bubble mine" : "bubble" },
    el("div", { class: "small muted", text: `${m.is_mine ? "You" : m.sender_name} · ${timeText(m.created_at)}` }),
    el("div", { text: m.body }));
}

async function loadConversation(first) {
  const thread = document.getElementById("thread");
  const form = document.getElementById("send-form");
  try {
    const c = await api(`/api/requests/${currentId}/messages${first ? "" : `?after_id=${lastMessageId}`}`);
    if (first) thread.replaceChildren();
    const status = document.getElementById("chat-status");
    status.textContent = `Request #${currentId} · ${c.request_status}`;
    form.style.display = c.can_send ? "" : "none";
    document.getElementById("closed-note").style.display = c.can_send ? "none" : "";
    if (first && c.messages.length === 0) thread.appendChild(el("p", { class: "empty", id: "no-msgs", text: "No messages yet. Say hello!" }));
    if (c.messages.length) {
      const none = document.getElementById("no-msgs");
      if (none) none.remove();
    }
    c.messages.forEach((m) => { thread.appendChild(bubble(m)); lastMessageId = Math.max(lastMessageId, m.id); });
    if (c.messages.length) thread.scrollTop = thread.scrollHeight;
  } catch (error) {
    clearInterval(pollTimer);
    thread.replaceChildren(el("div", { class: "notice error", text: error.message }));
    form.style.display = "none";
  }
}

function openChat() {
  document.getElementById("chat").style.display = "";
  loadConversation(true);
  clearInterval(pollTimer);
  pollTimer = setInterval(() => { if (!document.hidden) loadConversation(false); }, 8000);
}

document.addEventListener("DOMContentLoaded", () => {
  if (!document.getElementById("inbox")) return;
  if (!getToken()) { window.location.href = "/login.html"; return; }
  const id = Number(new URLSearchParams(window.location.search).get("request"));
  currentId = Number.isInteger(id) && id > 0 ? id : null;
  loadInbox();
  if (currentId) openChat();
  const form = document.getElementById("send-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("msg-body");
    const err = document.getElementById("msg-error");
    err.classList.remove("show");
    const body = input.value.trim();
    if (!body) return;
    try {
      await api(`/api/requests/${currentId}/messages`, { method: "POST", body: JSON.stringify({ body }) });
      input.value = "";
      loadConversation(false);
      loadInbox();
    } catch (error) {
      err.textContent = error.message;
      err.classList.add("show");
    }
  });
});
