/* OmniAssist web UI: session sidebar, streaming chat, and a live agent trace. */

const el = (id) => document.getElementById(id);
const messages = el("messages");
const traceBox = el("trace");
const toolsBox = el("tools");
const input = el("input");
const sendBtn = el("send");

let sessionId = null;
let socket = null;
let streaming = false;
let current = null; // { body, events }

/* Credentials: prefer a server-issued session, fall back to a pasted token. */
const urlToken = new URLSearchParams(location.search).get("token");
if (urlToken) history.replaceState({}, "", location.pathname);
let TOKEN = localStorage.getItem("omniassist_session") || urlToken || localStorage.getItem("omniassist_token") || "";
let AUTH_INFO = { mode: "open", requires_credential: false };

function authHeaders(extra = {}) {
  return TOKEN ? { ...extra, Authorization: `Bearer ${TOKEN}` } : extra;
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, { ...options, headers: authHeaders(options.headers) });
  if (res.status === 401 || res.status === 429) {
    localStorage.removeItem("omniassist_session");
    TOKEN = "";
    showGate(AUTH_INFO, res.status === 429 ? "Too many attempts. Wait a moment and retry." : "");
    throw new Error("unauthorized");
  }
  return res;
}

/* ---------------- rendering ---------------- */

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Minimal inline formatter: fenced code, inline code, bold.
function renderMarkdown(text) {
  const blocks = String(text).split(/```/);
  return blocks
    .map((block, i) => {
      if (i % 2 === 1) {
        const body = block.replace(/^[a-zA-Z0-9_-]*\n/, "");
        return `<pre><code>${escapeHtml(body)}</code></pre>`;
      }
      return escapeHtml(block)
        .replace(/`([^`\n]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    })
    .join("");
}

function clearEmptyState() {
  const empty = el("empty");
  if (empty) empty.remove();
}

function addMessage(role, content, { error = false } = {}) {
  clearEmptyState();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}${error ? " error" : ""}`;
  wrap.innerHTML = `
    <div class="avatar">${role === "user" ? "YOU" : "OA"}</div>
    <div class="body">
      <div class="role">${role === "user" ? "You" : "OmniAssist"}</div>
      <div class="content"></div>
    </div>`;
  const target = wrap.querySelector(".content");
  if (role === "user") target.textContent = content;
  else target.innerHTML = renderMarkdown(content);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
  return target;
}

function addThinking() {
  clearEmptyState();
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  wrap.innerHTML = `
    <div class="avatar">OA</div>
    <div class="body">
      <div class="role">OmniAssist</div>
      <div class="content"><span class="thinking"><i></i><i></i><i></i> working…</span></div>
    </div>`;
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
  return wrap;
}

/* ---------------- agent trace ---------------- */

const STEP_LABELS = {
  plan: "Plan",
  tool_call: "Tool call",
  tool_result: "Tool result",
  final: "Final answer",
  error: "Error",
};

function addTraceStep(type, content) {
  const step = document.createElement("div");
  step.className = `trace-step ${type}`;
  step.innerHTML = `<div class="step-title">${STEP_LABELS[type] || type}</div>
                    <div class="step-body"></div>`;
  step.querySelector(".step-body").textContent = content;
  traceBox.appendChild(step);
  traceBox.scrollTop = traceBox.scrollHeight;
}

function resetTrace() {
  traceBox.innerHTML = "";
  current = null;
}

/* ---------------- tools panel ---------------- */

async function loadTools() {
  try {
    const res = await apiFetch("/api/tools");
    const data = await res.json();
    if (!data.tools.length) {
      toolsBox.innerHTML = `<p class="muted">No tools registered.</p>`;
      return;
    }
    toolsBox.innerHTML = data.tools
      .map((t) => {
        const params = Object.entries(t.parameters)
          .map(([k, v]) => `${k}: ${v.type}${v.required ? "" : "?"}`)
          .join(", ");
        return `<div class="tool-card">
                  <div class="name">${escapeHtml(t.name)}</div>
                  <div class="desc">${escapeHtml(t.description || "No description")}</div>
                  ${params ? `<div class="params">(${escapeHtml(params)})</div>` : ""}
                </div>`;
      })
      .join("");
  } catch (e) {
    toolsBox.innerHTML = `<p class="muted">Could not load tools: ${escapeHtml(e.message)}</p>`;
  }
}

/* ---------------- health ---------------- */

async function loadHealth() {
  try {
    const res = await apiFetch("/api/health");
    const h = await res.json();
    el("version").textContent = h.version;
    el("model-text").textContent = h.model;
    const dot = el("status-dot");
    if (h.offline) {
      dot.className = "dot offline";
      el("status-text").textContent = "offline mode (no API key)";
    } else {
      dot.className = "dot ok";
      el("status-text").textContent = `${h.tools} tools ready`;
    }
    if (h.tool_load_errors && Object.keys(h.tool_load_errors).length) {
      toolsBox.insertAdjacentHTML(
        "afterbegin",
        Object.entries(h.tool_load_errors)
          .map(
            ([mod, err]) =>
              `<div class="tool-card tool-error"><div class="name">${escapeHtml(mod)} (not loaded)</div>
               <div class="desc">${escapeHtml(err)}</div></div>`
          )
          .join("")
      );
    }
  } catch (e) {
    el("status-text").textContent = "backend unreachable";
  }
}

/* ---------------- sessions ---------------- */

function renderSessions(list) {
  const box = el("session-list");
  if (!list.length) {
    box.innerHTML = `<p class="muted" style="font-size:12px;padding:4px 6px">No saved conversations yet.</p>`;
    return;
  }
  box.innerHTML = "";
  list.forEach((s) => {
    const item = document.createElement("div");
    item.className = `session-item${s.session_id === sessionId ? " active" : ""}`;
    item.innerHTML = `<div class="label">${escapeHtml(s.title)}</div>
                      <div class="meta">${s.message_count}</div>
                      <button class="del" title="Delete">×</button>`;
    item.querySelector(".label").onclick = () => openSession(s.session_id);
    item.querySelector(".meta").onclick = () => openSession(s.session_id);
    item.querySelector(".del").onclick = async (ev) => {
      ev.stopPropagation();
      await apiFetch(`/api/sessions/${encodeURIComponent(s.session_id)}`, { method: "DELETE" });
      if (s.session_id === sessionId) newChat();
      refreshSessions();
    };
    box.appendChild(item);
  });
}

async function refreshSessions() {
  try {
    const res = await apiFetch("/api/sessions");
    renderSessions((await res.json()).sessions);
  } catch { /* sidebar is non-critical */ }
}

async function openSession(id) {
  try {
    const res = await apiFetch(`/api/sessions/${encodeURIComponent(id)}`);
    if (!res.ok) return;
    const data = await res.json();
    sessionId = id;
    messages.innerHTML = "";
    resetTrace();
    (data.messages || []).forEach((m) => {
      addMessage(m.role, m.content, { error: m.role === "assistant" && /error/i.test(m.content.slice(0, 40)) });
      (m.events || []).forEach((ev) => {
        if (ev.type !== "session" && ev.type !== "done" && ev.type !== "final") addTraceStep(ev.type, ev.content);
      });
    });
    el("chat-title").textContent = data.title || (data.messages?.[0]?.content || "Conversation").slice(0, 48);
    refreshSessions();
  } catch { /* ignore */ }
}

function newChat() {
  sessionId = null;
  messages.innerHTML = "";
  resetTrace();
  el("chat-title").textContent = "New conversation";
  const div = document.createElement("div");
  div.className = "empty";
  div.id = "empty";
  div.innerHTML = `<h3>Ask OmniAssist to do something</h3>
    <p>It plans, calls tools, and iterates until the task is done.</p>`;
  messages.appendChild(div);
  refreshSessions();
}

/* ---------------- auth gate ---------------- */

function mount() {
  el("gate").classList.add("hidden");
  loadHealth();
  loadTools();
  refreshSessions();
  connect();
}

function showGate(info, message = "") {
  AUTH_INFO = info || AUTH_INFO;
  const gate = el("gate");
  gate.classList.remove("hidden");
  el("status-dot").className = "dot offline";
  el("status-text").textContent = "locked";

  const mode = AUTH_INFO.mode || "open";
  el("gate-token-pane").classList.toggle("hidden", mode !== "token");
  el("gate-totp-pane").classList.toggle("hidden", mode !== "totp");

  if (mode === "totp") {
    el("gate-title").textContent = "Two-factor code required";
    el("gate-sub").textContent = AUTH_INFO.totp_configured
      ? "Enter the 6-digit code from your authenticator app."
      : "No TOTP secret is configured on the server (OMNIASSIST_TOTP_SECRET). "
        + "Set it in .env to unlock — until then this screen cannot be passed.";
    el("gate-totp-input").focus();
  } else if (mode === "token") {
    el("gate-title").textContent = "Token required";
    el("gate-sub").textContent = "Paste your GUI Omni token to unlock.";
    el("gate-token-input").focus();
  } else {
    el("gate-title").textContent = "Access locked";
    el("gate-sub").textContent = "This server requires a credential.";
  }
  if (message) el("gate-error").textContent = message;
}

function gateError(text) {
  const box = el("gate-error");
  box.textContent = text;
  const card = document.querySelector(".gate-card");
  card.classList.remove("shake");
  void card.offsetWidth; /* restart the animation */
  card.classList.add("shake");
}

async function submitCredential(kind, value) {
  if (!value) return;
  try {
    const res = await fetch(`/api/auth/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: value }),
    });
    if (!res.ok) {
      gateError(res.status === 429 ? "Too many attempts. Wait a moment." : "Incorrect credential. Try again.");
      return;
    }
    const data = await res.json();
    TOKEN = data.session;
    localStorage.setItem("omniassist_session", TOKEN);
    el("gate-error").textContent = "";
    mount();
  } catch (e) {
    gateError(`Request failed: ${e.message}`);
  }
}

/* ---------------- websocket streaming ---------------- */

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const qs = TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : "";
  socket = new WebSocket(`${proto}://${location.host}/ws/run${qs}`);

  socket.onopen = () => {
    el("status-dot").className = "dot ok";
  };

  socket.onmessage = (raw) => {
    const ev = JSON.parse(raw.data);

    if (ev.type === "session") {
      sessionId = ev.content;
      return;
    }
    if (ev.type === "done") {
      streaming = false;
      sendBtn.disabled = false;
      if (current && !current.body.innerHTML.trim()) {
        current.body.innerHTML = renderMarkdown("(no output)");
      }
      current = null;
      refreshSessions();
      return;
    }

    if (ev.type === "plan") {
      addTraceStep("plan", ev.content);
      return;
    }
    if (ev.type === "tool_call") {
      addTraceStep("tool_call", `${ev.tool} ${JSON.stringify(ev.args)}`);
      return;
    }
    if (ev.type === "tool_result") {
      addTraceStep("tool_result", ev.content);
      return;
    }
    if (ev.type === "final") {
      if (current) current.body.innerHTML = renderMarkdown(ev.content);
      addTraceStep("final", ev.content);
      return;
    }
    if (ev.type === "error") {
      if (current) current.body.innerHTML = renderMarkdown(ev.content);
      current?.wrap.classList.add("error");
      addTraceStep("error", ev.content);
    }
  };

  socket.onclose = () => {
    el("status-dot").className = "dot offline";
    el("status-text").textContent = "reconnecting…";
    setTimeout(connect, 1500);
  };
}

function send(prompt) {
  if (!prompt.trim() || streaming) return;
  addMessage("user", prompt);
  const wrap = addThinking();
  current = { body: wrap.querySelector(".content"), wrap };
  resetTraceKeepCurrent();
  streaming = true;
  sendBtn.disabled = true;

  const payload = JSON.stringify({ prompt, session_id: sessionId });
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(payload);
  } else {
    // Fall back to the blocking REST endpoint if the socket is unavailable.
    apiFetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
    })
      .then((r) => r.json())
      .then((d) => {
        sessionId = d.session_id;
        current.body.innerHTML = renderMarkdown(d.response);
        d.events.forEach((ev) => {
          if (!["session", "done", "final"].includes(ev.type)) addTraceStep(ev.type, ev.content);
        });
      })
      .catch((e) => { current.body.innerHTML = renderMarkdown(`Request failed: ${e.message}`); })
      .finally(() => { streaming = false; sendBtn.disabled = false; refreshSessions(); });
  }
}

function resetTraceKeepCurrent() {
  traceBox.innerHTML = "";
}

/* ---------------- wiring ---------------- */

el("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value;
  input.value = "";
  input.style.height = "auto";
  send(text);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    el("composer").requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 200) + "px";
});

el("new-chat").onclick = newChat;

document.querySelectorAll(".suggestion").forEach((btn) => {
  btn.onclick = () => send(btn.dataset.prompt);
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`[data-panel="${tab.dataset.tab}"]`).classList.add("active");
  };
});

el("toggle-tools").onclick = () => {
  el("inspector").classList.toggle("open");
  document.querySelector('[data-tab="tools"]').click();
};
el("toggle-trace").onclick = () => {
  el("inspector").classList.toggle("open");
  document.querySelector('[data-tab="trace"]').click();
};

async function boot() {
  try {
    AUTH_INFO = await (await fetch("/api/auth")).json();
  } catch {
    AUTH_INFO = { mode: "open", requires_credential: false };
  }
  if (AUTH_INFO.requires_credential && !TOKEN) {
    showGate(AUTH_INFO);
    return;
  }
  mount();
}

/* Gate wiring: paste auto-submits the token; the 6-digit box auto-verifies. */
el("gate-token-submit").onclick = () => submitCredential("token", el("gate-token-input").value.trim());
el("gate-token-input").addEventListener("paste", (e) => {
  const text = (e.clipboardData || window.clipboardData).getData("text").trim();
  if (text) { e.preventDefault(); el("gate-token-input").value = text; submitCredential("token", text); }
});
el("gate-token-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitCredential("token", el("gate-token-input").value.trim());
});
el("gate-totp-submit").onclick = () => submitCredential("totp", el("gate-totp-input").value.trim());
el("gate-totp-input").addEventListener("input", () => {
  const box = el("gate-totp-input");
  box.value = box.value.replace(/\D/g, "").slice(0, 6);
  if (box.value.length === 6) submitCredential("totp", box.value);
});
el("gate-totp-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitCredential("totp", el("gate-totp-input").value.trim());
});

boot();
