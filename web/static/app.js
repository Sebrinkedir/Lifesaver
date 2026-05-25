// LifeSaver web UI — WebSocket client + chat renderer
//
// Backend events handled:
//   user_echo, system, scan_start,
//   agent_start, agent_findings, agent_error,
//   scan_complete, chat_open, chat_closed,
//   agent_typing, agent_reply

const chat       = document.getElementById("chat");
const form       = document.getElementById("composer");
const input      = document.getElementById("cmdInput");
const sendBtn    = document.getElementById("sendBtn");
const connStatus = document.getElementById("connStatus");

// Structured log of everything that shows up in the chat — used to build
// the PDF on demand. Filled in handle() below as events arrive.
const conversationLog = [];

const AGENT_LABELS = {
  security:    "Security Agent",
  performance: "Performance Agent",
  logic:       "Logic Agent",
};

const SEV_COLOR = {
  HIGH:   "#ef4444",
  MEDIUM: "#f59e0b",
  LOW:    "#10b981",
};

const DEFAULT_PLACEHOLDER = "python main.py test_php.php";
// Cleared once a conversation is open — the hint bubble has the agent
// prefix list; the input itself stays free of suggestions.
const CHAT_PLACEHOLDER    = "";

let ws;
let activeAgentBubble = null;  // findings bubble being filled by the current agent
let typingBubble      = null;  // current 'thinking…' bubble for a follow-up reply

// ---------- WebSocket bootstrap ----------

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/scan`);

  ws.addEventListener("open", () => {
    connStatus.textContent = "connected";
    connStatus.className   = "status ok";
    sendBtn.disabled       = false;
  });

  ws.addEventListener("close", () => {
    connStatus.textContent = "disconnected — retrying...";
    connStatus.className   = "status err";
    sendBtn.disabled       = true;
    setTimeout(connect, 1500);
  });

  ws.addEventListener("error", () => {
    connStatus.textContent = "error";
    connStatus.className   = "status err";
  });

  ws.addEventListener("message", (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    handle(msg);
  });
}

connect();

// ---------- form submit ----------

form.addEventListener("submit", (e) => {
  e.preventDefault();
  send(input.value.trim());
});

function send(cmd) {
  if (!cmd) return;

  // Client-only commands: handled in the browser, never sent to the server.
  const lower = cmd.toLowerCase();
  if (lower === "pdf" || lower === "/pdf" || lower === "download" || lower === "/download") {
    input.value = "";
    handlePdfCommand(cmd);
    return;
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ command: cmd }));
  input.value = "";
  setBusy(true);
}

function handlePdfCommand(cmd) {
  // Echo the command into the chat AND the log so subsequent PDFs include it.
  renderUser(cmd);
  conversationLog.push({ ts: new Date(), type: "user_echo", command: cmd });

  try {
    // downloadPdf returns true on success, false if the library is missing
    // (it has already shown its own system message in that case).
    if (downloadPdf()) {
      renderSystem("PDF generated — check your browser's Downloads folder.");
    }
  } catch (err) {
    renderSystem(`Could not generate PDF: ${(err && err.message) || err}`);
  }
}

function setBusy(busy) {
  input.disabled  = busy;
  sendBtn.disabled = busy || !ws || ws.readyState !== WebSocket.OPEN;
  if (!busy) input.focus();
}

function setChatMode(open) {
  input.placeholder = open ? CHAT_PLACEHOLDER : DEFAULT_PLACEHOLDER;
}

// ---------- event dispatch ----------

function handle(msg) {
  // Log first so the PDF captures everything the user saw (including
  // intermediate states like typing, which we skip in the PDF later).
  logEvent(msg);

  switch (msg.type) {
    case "user_echo":          renderUser(msg.command); break;
    case "system":             renderSystem(msg.message); setBusy(false); break;
    case "scan_start":         renderScanStart(msg); break;
    case "agent_start":        renderAgentStart(msg); break;
    case "agent_findings":     renderAgentFindings(msg); break;
    case "agent_typing":       renderAgentTyping(msg); break;
    case "agent_reply":        renderAgentReply(msg); setBusy(false); break;
    case "agent_error":        renderAgentError(msg); setBusy(false); break;
    case "scan_complete":      renderScanComplete(msg); break;
    case "chat_open":          renderChatOpen(msg); setBusy(false); break;
    case "chat_closed":        renderChatClosed(msg); setBusy(false); break;
    default: console.warn("unknown event", msg);
  }
}

function logEvent(msg) {
  // Skip noisy intermediate events that have no useful PDF representation.
  if (msg.type === "agent_typing" || msg.type === "agent_start") return;
  conversationLog.push({ ts: new Date(), ...msg });
}

// ---------- renderers ----------

function appendBubble(extraClass = "") {
  const div = document.createElement("div");
  div.className = `bubble ${extraClass}`.trim();
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function renderUser(cmd) {
  const b = appendBubble("user");
  const pre = document.createElement("pre");
  pre.textContent = cmd;
  b.appendChild(pre);
}

function renderSystem(message) {
  const b = appendBubble("system");
  b.textContent = message;
}

function renderScanStart({ file, language, lines }) {
  const b = appendBubble("system");
  b.innerHTML = `
    <div class="scan-meta">
      <div><span class="label">File</span><span class="value">${escapeHtml(file)}</span></div>
      <div><span class="label">Language</span><span class="value">${escapeHtml(language)}</span></div>
      <div><span class="label">Lines</span><span class="value">${lines}</span></div>
    </div>
  `;
}

function renderAgentStart({ step, total, agent, model }) {
  const b = appendBubble(`agent-${agent}`);
  b.innerHTML = `
    <div class="role">
      <span class="agent-dot"></span>
      <span>[${step}/${total}] ${AGENT_LABELS[agent] || agent}</span>
      <span class="muted role-model">${escapeHtml(model)}</span>
    </div>
    <div class="thinking">
      <span>scanning</span>
      <span class="dots"><span></span><span></span><span></span></span>
    </div>
  `;
  activeAgentBubble = b;
}

function renderAgentFindings({ agent, model, findings }) {
  const target = activeAgentBubble || appendBubble(`agent-${agent}`);
  activeAgentBubble = null;

  const list = document.createElement("div");
  list.className = "findings";

  if (!findings || findings.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-row";
    empty.textContent = "No findings from this agent.";
    list.appendChild(empty);
  } else {
    for (const f of findings) list.appendChild(renderFinding(f));
  }

  target.innerHTML = `
    <div class="role">
      <span class="agent-dot"></span>
      <span>${AGENT_LABELS[agent] || agent}</span>
      <span class="muted role-model">${escapeHtml(model)} &middot; ${findings.length} finding(s)</span>
    </div>
  `;
  target.appendChild(list);
  chat.scrollTop = chat.scrollHeight;
}

function renderAgentTyping({ agent, model }) {
  if (typingBubble) {
    typingBubble.remove();
    typingBubble = null;
  }
  const b = appendBubble(`agent-${agent} reply typing`);
  b.innerHTML = `
    <div class="role">
      <span class="agent-dot"></span>
      <span>${AGENT_LABELS[agent] || agent}</span>
      <span class="muted role-model">${escapeHtml(model || "")}</span>
    </div>
    <div class="thinking">
      <span>thinking</span>
      <span class="dots"><span></span><span></span><span></span></span>
    </div>
  `;
  typingBubble = b;
}

function renderAgentReply({ agent, model, text }) {
  const target = typingBubble || appendBubble(`agent-${agent} reply`);
  typingBubble = null;
  target.className = `bubble agent-${agent} reply`;
  target.innerHTML = `
    <div class="role">
      <span class="agent-dot"></span>
      <span>${AGENT_LABELS[agent] || agent}</span>
      <span class="muted role-model">${escapeHtml(model || "")}</span>
    </div>
    <div class="reply-body">${renderMarkdownish(text || "")}</div>
  `;
  chat.scrollTop = chat.scrollHeight;
}

function renderChatOpen({ hint_title, hint_lines, hint }) {
  setChatMode(true);
  const b = appendBubble("system chat-hint");

  // New structured form: hint_title + hint_lines[]. Falls back to legacy
  // single 'hint' string with newlines if a server still sends that.
  const title = hint_title || "Conversation open";
  let lines = Array.isArray(hint_lines) ? hint_lines : null;
  if (!lines && typeof hint === "string") lines = hint.split("\n");
  lines = lines || [];

  const html = lines
    .map((line) => line.length ? escapeHtml(line) : "&nbsp;")
    .join("<br>");

  b.innerHTML = `
    <div class="chat-hint-body">
      <strong>${escapeHtml(title)}</strong>
      <div class="chat-hint-lines">${html}</div>
    </div>
  `;
}

function renderChatClosed(_msg) {
  setChatMode(false);

  // Wipe everything: DOM, in-page state, and the PDF log so the next
  // download doesn't include the previous session.
  chat.innerHTML = "";
  activeAgentBubble = null;
  typingBubble = null;
  conversationLog.length = 0;

  // Drop a fresh welcome bubble so the chat is usable right away.
  const b = appendBubble("system intro");
  b.innerHTML = `
    <p>Conversation closed. Type a scan command to start a new one &mdash; for example:</p>
    <pre class="cmd-example">python main.py test_php.php</pre>
  `;
}

function renderFinding(f) {
  const sev   = (f.severity || "LOW").toUpperCase();
  const color = SEV_COLOR[sev] || SEV_COLOR.LOW;
  const conf  = Number.isFinite(f.confidence) ? Number(f.confidence) : 0;
  const pct   = Math.max(0, Math.min(100, Math.round(conf * 100)));

  const wrap = document.createElement("div");
  wrap.className = "finding";

  wrap.appendChild(makeGauge(pct, color));

  const body = document.createElement("div");
  body.className = "body";
  body.innerHTML = `
    <p class="title">${escapeHtml(f.description || "")}</p>
    <p class="reason">${escapeHtml(f.reason || "")}</p>
    <div class="meta">
      <span class="pill">Line ${escapeHtml(String(f.line ?? "?"))}</span>
      <span class="pill">WAS ${(f.WAS ?? conf).toFixed ? (f.WAS ?? conf).toFixed(2) : (f.WAS ?? conf)}</span>
      <span class="pill">Confidence ${conf.toFixed(2)}</span>
    </div>
  `;
  wrap.appendChild(body);

  const badge = document.createElement("span");
  badge.className = `sev ${sev}`;
  badge.textContent = sev;
  wrap.appendChild(badge);

  return wrap;
}

function makeGauge(pct, color) {
  const r = 24, c = 2 * Math.PI * r;
  const offset = c * (1 - pct / 100);
  const div = document.createElement("div");
  div.className = "gauge";
  div.innerHTML = `
    <svg width="56" height="56">
      <circle cx="28" cy="28" r="${r}" stroke="#3f3f46" stroke-width="6" fill="none"/>
      <circle cx="28" cy="28" r="${r}" stroke="${color}" stroke-width="6" fill="none"
              stroke-linecap="round"
              stroke-dasharray="${c.toFixed(2)}"
              stroke-dashoffset="${offset.toFixed(2)}"/>
    </svg>
    <span class="gauge-text" style="color:${color}">${pct}%</span>
  `;
  return div;
}

function renderAgentError({ agent, message }) {
  const target = typingBubble || activeAgentBubble || appendBubble(`agent-${agent}`);
  typingBubble = null;
  activeAgentBubble = null;
  target.innerHTML = `
    <div class="role">
      <span class="agent-dot"></span>
      <span>${AGENT_LABELS[agent] || agent} — error</span>
    </div>
    <p style="color: var(--high); margin: 6px 0 0;">${escapeHtml(message)}</p>
  `;
}

function renderScanComplete({ file, totals, reliability, kept_findings }) {
  const b = appendBubble("summary");
  const isReliable = reliability >= 85;

  const totalCells = [
    ["Security",    totals.security],
    ["Performance", totals.performance],
    ["Logic",       totals.logic],
    ["Total",       totals.total],
    ["Kept ≥0.6",   totals.kept],
  ].map(([k, v]) => `<div class="t"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");

  b.innerHTML = `
    <h3>${escapeHtml(file)} &mdash; scan complete</h3>
    <div class="totals">${totalCells}</div>
    <div class="reliability ${isReliable ? "" : "warn"}">
      <span class="label">Reliability</span>
      <span class="value">${reliability}% &middot; ${isReliable ? "RELIABLE" : "NEEDS MORE RUNS"}</span>
    </div>
  `;

  if (kept_findings && kept_findings.length > 0) {
    const list = document.createElement("div");
    list.className = "findings";
    list.style.marginTop = "12px";
    for (const f of kept_findings) list.appendChild(renderFinding(f));
    b.appendChild(list);
  }
}

// ---------- helpers ----------

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Render a tiny subset of markdown safely: paragraphs, code spans, and
// fenced ``` blocks. Everything else is plain escaped text.
function renderMarkdownish(text) {
  const fences = [];
  const fenced = text.replace(/```([a-zA-Z]*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
    fences.push(escapeHtml(code));
    return ` FENCE${fences.length - 1} `;
  });
  let safe = escapeHtml(fenced);
  safe = safe.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`);
  safe = safe.replace(/ FENCE(\d+) /g, (_m, i) => `<pre>${fences[+i]}</pre>`);
  return safe
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`)
    .join("");
}

setChatMode(false);

// ---------- PDF export ----------

const AGENT_COLOR_RGB = {
  security:    [239, 68, 68],
  performance: [96, 165, 250],
  logic:       [192, 132, 252],
};

const SEV_RGB = {
  HIGH:   [239, 68, 68],
  MEDIUM: [245, 158, 11],
  LOW:    [16, 185, 129],
};

function downloadPdf() {
  if (!window.jspdf || !window.jspdf.jsPDF) {
    renderSystem(
      "PDF library failed to load. The file at " +
      "/static/jspdf.umd.min.js may be missing — reload the page and try again."
    );
    return false;
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 40;

  // Cursor state, mutated by the helpers below.
  const cursor = { y: margin };
  const ensureSpace = (need) => {
    if (cursor.y + need > pageH - margin) {
      doc.addPage();
      cursor.y = margin;
    }
  };
  const writeText = (text, opts = {}) => {
    const x = opts.x ?? margin;
    const width = opts.width ?? (pageW - x - margin);
    const lh = opts.lh ?? 12;
    const lines = doc.splitTextToSize(String(text ?? ""), width);
    for (const line of lines) {
      ensureSpace(lh);
      doc.text(line, x, cursor.y);
      cursor.y += lh;
    }
  };

  // ----- header -----
  doc.setFont("helvetica", "bold").setFontSize(20).setTextColor(0, 0, 0);
  doc.text("LifeSaver — Conversation Export", margin, cursor.y);
  cursor.y += 22;
  doc.setFont("helvetica", "normal").setFontSize(10).setTextColor(120, 120, 120);
  doc.text(new Date().toLocaleString(), margin, cursor.y);
  cursor.y += 18;
  doc.setDrawColor(200, 200, 200);
  doc.line(margin, cursor.y, pageW - margin, cursor.y);
  cursor.y += 14;
  doc.setTextColor(0, 0, 0);

  if (conversationLog.length === 0) {
    doc.setFont("helvetica", "italic").setFontSize(11).setTextColor(120, 120, 120);
    doc.text("(no conversation yet — type a scan command first)", margin, cursor.y);
  }

  for (const e of conversationLog) {
    renderPdfEntry(doc, e, { margin, pageW, ensureSpace, writeText, cursor });
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  doc.save(`lifesaver-conversation-${stamp}.pdf`);
  return true;
}

function renderPdfEntry(doc, e, ctx) {
  const { margin, ensureSpace, writeText, cursor } = ctx;
  const black = () => doc.setTextColor(0, 0, 0);
  const mute  = () => doc.setTextColor(120, 120, 120);
  const color = (rgb) => doc.setTextColor(rgb[0], rgb[1], rgb[2]);

  switch (e.type) {
    case "user_echo": {
      ensureSpace(28);
      doc.setFont("helvetica", "bold").setFontSize(10);
      color([16, 163, 127]);
      doc.text("You", margin, cursor.y); cursor.y += 12;
      doc.setFont("helvetica", "normal").setFontSize(10); black();
      writeText(e.command || "", { lh: 12 });
      cursor.y += 8;
      break;
    }
    case "system": {
      ensureSpace(18);
      doc.setFont("helvetica", "italic").setFontSize(9); mute();
      writeText(e.message || "", { lh: 11 });
      cursor.y += 6; black();
      break;
    }
    case "scan_start": {
      ensureSpace(30);
      doc.setFont("helvetica", "bold").setFontSize(11); black();
      doc.text(
        `Scan started — ${e.file || ""}   ·   ${e.language || ""}   ·   ${e.lines || 0} lines`,
        margin, cursor.y
      );
      cursor.y += 18;
      break;
    }
    case "agent_findings": {
      const rgb = AGENT_COLOR_RGB[e.agent] || [120, 120, 120];
      ensureSpace(28);
      doc.setFont("helvetica", "bold").setFontSize(11); color(rgb);
      doc.text(
        `${(e.agent || "").toUpperCase()} AGENT  —  ${(e.findings || []).length} finding(s)`,
        margin, cursor.y
      );
      cursor.y += 16;
      doc.setFont("helvetica", "normal").setFontSize(9); black();
      for (const f of (e.findings || [])) {
        ensureSpace(40);
        const sevRgb = SEV_RGB[(f.severity || "LOW").toUpperCase()] || [120, 120, 120];
        doc.setFont("helvetica", "bold"); color(sevRgb);
        writeText(`[${(f.severity || "?").toUpperCase()}] ${f.description || ""}`,
                  { x: margin + 12, lh: 12 });
        doc.setFont("helvetica", "normal"); mute();
        const conf = Number(f.confidence) || 0;
        const was  = Number(f.WAS ?? conf);
        ensureSpace(12);
        doc.text(
          `Line ${String(f.line ?? "?")}   ·   Confidence ${conf.toFixed(2)}   ·   WAS ${was.toFixed(2)}`,
          margin + 12, cursor.y
        );
        cursor.y += 12; black();
        if (f.reason) {
          writeText(`Reason: ${f.reason}`, { x: margin + 12, lh: 12 });
        }
        cursor.y += 6;
      }
      cursor.y += 4;
      break;
    }
    case "agent_reply": {
      const rgb = AGENT_COLOR_RGB[e.agent] || [16, 163, 127];
      ensureSpace(22);
      doc.setFont("helvetica", "bold").setFontSize(10); color(rgb);
      const name = (e.agent || "agent").charAt(0).toUpperCase()
                 + (e.agent || "agent").slice(1) + " Agent";
      doc.text(name, margin, cursor.y); cursor.y += 14;
      doc.setFont("helvetica", "normal").setFontSize(10); black();
      writeText(e.text || "", { x: margin + 12, lh: 13 });
      cursor.y += 8;
      break;
    }
    case "agent_error": {
      ensureSpace(22);
      doc.setFont("helvetica", "bold").setFontSize(10); color([239, 68, 68]);
      doc.text(`${(e.agent || "agent")} — error`, margin, cursor.y); cursor.y += 14;
      doc.setFont("helvetica", "normal").setFontSize(10); black();
      writeText(e.message || "", { x: margin + 12, lh: 13 });
      cursor.y += 8;
      break;
    }
    case "scan_complete": {
      ensureSpace(60);
      doc.setFont("helvetica", "bold").setFontSize(12); black();
      doc.text(`Summary — ${e.file || ""}`, margin, cursor.y); cursor.y += 16;
      doc.setFont("helvetica", "normal").setFontSize(10);
      const t = e.totals || {};
      const r = e.reliability || 0;
      doc.text(
        `Security: ${t.security ?? 0}   Performance: ${t.performance ?? 0}   ` +
        `Logic: ${t.logic ?? 0}   Total: ${t.total ?? 0}   Kept ≥0.6: ${t.kept ?? 0}`,
        margin, cursor.y
      ); cursor.y += 14;
      const rel = r >= 85 ? "RELIABLE" : "NEEDS MORE RUNS";
      doc.text(`Reliability: ${r}% — ${rel}`, margin, cursor.y);
      cursor.y += 18;
      break;
    }
    case "chat_open": {
      ensureSpace(14);
      doc.setFont("helvetica", "italic").setFontSize(9); mute();
      doc.text("— conversation open —", margin, cursor.y); cursor.y += 14; black();
      break;
    }
    case "chat_closed": {
      ensureSpace(14);
      doc.setFont("helvetica", "italic").setFontSize(9); mute();
      doc.text("— conversation closed —", margin, cursor.y); cursor.y += 14; black();
      break;
    }
    default:
      // agent_typing etc. — filtered out in logEvent.
      break;
  }
}
