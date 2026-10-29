"use strict";

const POLL_MS = 700;
const TYPE_LABELS = {
  CARD: "Card number", AADHAAR: "Aadhaar number", PAN: "PAN number", EMAIL: "Email address",
  PHONE: "Phone number", OTP: "One-time code", PASSWORD: "Password", API_KEY: "Secret key",
  IP_ADDRESS: "IP address", UPI: "UPI ID", IFSC: "Bank branch code", CVV: "Card security code",
  NAME: "Name", ADDRESS: "Home address", DOB: "Date of birth", MEDICAL: "Health details",
  ACCOUNT: "Account number", EXPIRY: "Card expiry date", FACE: "Face", CUSTOM: "Saved detail",
};
const STATUS_WORDS = {
  idle: "Getting ready", running: "Working on it", waiting: "Waiting for your OK",
  done: "All done", blocked: "Stopped to keep you safe",
};

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...kids) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...kids.filter((k) => k != null));
  return node;
};

const app = { state: { id: null }, scenario: null, imageKey: "", lastFocus: null, panel: null };

async function api(path, options = {}) {
  const init = { ...options };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, init);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const typeLabel = (type) => TYPE_LABELS[type] || type.toLowerCase().replace(/_/g, " ");

/* ---------- Main screen ---------- */

async function loadScenarios() {
  const scenarios = await api("/api/scenarios");
  const chips = $("chips");
  scenarios.forEach((s) => {
    const chip = el("button", { type: "button", className: "chip", textContent: s.title });
    chip.setAttribute("aria-pressed", "false");
    chip.addEventListener("click", () => pickScenario(s, chip));
    chips.append(chip);
  });
  if (scenarios.length && !app.scenario) app.scenario = scenarios[0].key;
}

function pickScenario(scenario, chip) {
  app.scenario = scenario.key;
  $("task").value = scenario.task;
  document.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === chip)));
}

async function startTask(event) {
  event.preventDefault();
  const go = event.submitter || document.querySelector(".task .primary");
  go.disabled = true;
  $("narration").textContent = "Starting...";
  try {
    await api("/api/session", { method: "POST", body: { scenario: app.scenario, task: $("task").value.trim() } });
  } catch {
    $("narration").textContent = "Could not start. Please try again.";
  } finally {
    go.disabled = false;
  }
}

function statusText(s) {
  if (s.blocked.length) return `Stopped ${plural(s.blocked.length, "unsafe message", "unsafe messages")}`;
  return `${plural(s.hidden.length, "thing", "things")} hidden · nothing private shared`;
}

function renderMain(s) {
  const status = $("status");
  if (!s.id) return;
  // A second device joining a running session adopts its task once.
  if (!$("task").value && document.activeElement !== $("task")) {
    $("task").value = s.task;
    app.scenario = s.scenario;
  }
  status.textContent = statusText(s);
  status.classList.toggle("is-blocked", s.blocked.length > 0);
  $("narration").textContent = s.narration || STATUS_WORDS[s.status] || "";
  $("empty").hidden = true;
  refreshImages(s);
  drawFrost(s);
  syncApproval(s.approval);
}

// Images only change when a new step runs, so key the reload on the event count.
function refreshImages(s) {
  const key = `${s.id}-${s.events.length}-${s.status}`;
  if (key === app.imageKey) return;
  app.imageKey = key;
  const stamp = Date.now();
  ["real", "ai"].forEach((kind) => {
    const loader = new Image();
    loader.onload = () => { $(`img-${kind}`).src = loader.src; };
    loader.src = `/api/session/image/${kind}?t=${stamp}`;
  });
}

function drawFrost(s) {
  const frost = $("frost");
  const img = $("img-real");
  const [w] = s.size || [0];
  frost.replaceChildren();
  if (!w || !img.clientWidth) return;
  const scale = img.clientWidth / w;
  (s.boxes || []).forEach(([x, y, bw, bh]) => {
    const veil = el("div", { className: "veil" }, el("span", { textContent: "Hidden" }));
    Object.assign(veil.style, {
      left: `${x * scale}px`, top: `${y * scale}px`, width: `${bw * scale}px`, height: `${bh * scale}px`,
    });
    frost.append(veil);
  });
}

function toggleAiView() {
  const on = $("ai-view").checked;
  $("img-ai").classList.toggle("is-shown", on);
  $("img-real").classList.toggle("is-shown", !on);
  $("frost").classList.toggle("is-off", on);
}

/* ---------- Sheets ---------- */

function openSheet(id, focusTarget) {
  const sheet = $(id);
  if (!sheet.hidden) return;
  app.lastFocus = document.activeElement;
  sheet.hidden = false;
  (focusTarget || sheet.querySelector("button")).focus();
}

function closeSheet(id) {
  const sheet = $(id);
  if (sheet.hidden) return;
  sheet.hidden = true;
  if (app.lastFocus && document.contains(app.lastFocus)) app.lastFocus.focus();
}

function trapFocus(event) {
  const sheet = [...document.querySelectorAll(".backdrop")].find((b) => !b.hidden);
  if (!sheet) return;
  if (event.key === "Escape" && sheet.id === "status-sheet") return closeSheet(sheet.id);
  if (event.key !== "Tab") return;
  const items = [...sheet.querySelectorAll("button:not([hidden])")];
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) { last.focus(); event.preventDefault(); }
  else if (!event.shiftKey && document.activeElement === last) { first.focus(); event.preventDefault(); }
}

function showStatusDetails() {
  const s = app.state;
  const list = $("status-list");
  list.replaceChildren();
  (s.blocked || []).forEach((reason) => {
    list.append(el("li", { className: "bad" }, el("strong", { textContent: "Stopped a message" }),
      el("span", { textContent: reason })));
  });
  (s.hidden || []).forEach((item) => {
    list.append(el("li", {}, el("strong", { textContent: typeLabel(item.type) }),
      el("span", { textContent: item.reason })));
  });
  if (!list.children.length) list.append(el("li", { textContent: "Nothing hidden yet." }));
  openSheet("status-sheet");
}

function syncApproval(approval) {
  if (!approval) return closeSheet("approval");
  if (!$("approval").hidden) return;
  $("approval-q").textContent = approval.question;
  $("why").textContent = approval.why;
  $("why").hidden = true;
  $("why-link").setAttribute("aria-expanded", "false");
  openSheet("approval", $("approve"));
}

async function answer(approved) {
  closeSheet("approval");
  await api("/api/session/approve", { method: "POST", body: { approved } }).catch(() => {});
}

function toggleWhy() {
  const why = $("why");
  why.hidden = !why.hidden;
  $("why-link").setAttribute("aria-expanded", String(!why.hidden));
}

/* ---------- Polling ---------- */

async function poll() {
  try {
    app.state = await api("/api/session");
    renderMain(app.state);
    if (app.panel) await refreshPanel();
  } catch {
    $("narration").textContent = "Lost connection. Retrying...";
  }
  setTimeout(poll, POLL_MS);
}

/* ---------- How it works (built only when opened) ---------- */

function card(title, ...kids) {
  return el("section", { className: "card" }, el("h3", { textContent: title }), ...kids);
}

function kvTable(value) {
  if (value === null || typeof value !== "object") return document.createTextNode(String(value));
  const table = el("table", { className: "kv" });
  Object.entries(value).forEach(([k, v]) => {
    table.append(el("tr", {}, el("th", { textContent: k }), el("td", {}, kvTable(v))));
  });
  return table;
}

function openPanel() {
  app.lastFocus = document.activeElement;
  const close = el("button", { type: "button", className: "secondary", textContent: "Back" });
  close.addEventListener("click", closePanel);
  const parts = {
    pipeline: el("ol", { className: "steps" }),
    raw: el("pre", { className: "mono", tabIndex: 0 }),
    outbound: el("pre", { className: "mono", tabIndex: 0 }),
    decisions: el("ul", { className: "list" }),
    evalBody: el("div", { className: "table-wrap" }),
    rules: el("div"),
    ai: el("div"),
  };
  const panel = el("div", { className: "panel", id: "how" },
    el("div", { className: "panel-inner" },
      el("div", { className: "panel-head" }, el("h2", { textContent: "How it works" }), close),
      card("Pipeline for this run", parts.pipeline),
      card("What the page said vs. what the AI received", el("div", { className: "pair" },
        el("div", {}, el("strong", { textContent: "Raw snapshot (stays local)" }), parts.raw),
        el("div", {}, el("strong", { textContent: "Outbound text sent to the LLM" }), parts.outbound))),
      card("Validation and approval decisions", parts.decisions),
      card("Evaluation", parts.evalBody),
      card("Privacy settings", el("p", { className: "note", textContent: "Changes take effect on the next step." }),
        parts.rules),
      card("AI choice", parts.ai),
      card("Leak test", leakTestControls())));
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", "How it works");
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") closePanel(); });
  document.body.append(panel);
  $("main").inert = true;
  app.panel = parts;
  close.focus();
  refreshPanel();
  loadEval();
  loadSettings();
}

function closePanel() {
  $("how").remove();
  $("main").inert = false;
  app.panel = null;
  if (app.lastFocus) app.lastFocus.focus();
}

async function refreshPanel() {
  const parts = app.panel;
  const s = app.state;
  const events = s.events || [];
  parts.pipeline.replaceChildren(...(events.length ? events : [{ kind: "-", detail: "No run yet", step: "" }])
    .map((e) => el("li", {}, el("span", { className: `kind ${e.kind}`, textContent: e.kind }),
      `${e.step ? `step ${e.step}: ` : ""}${e.detail}`)));
  (s.blocked || []).forEach((reason) => parts.pipeline.append(
    el("li", {}, el("span", { className: "kind block", textContent: "block" }), reason)));

  const inspect = s.id ? await api("/api/session/inspect") : {};
  if (!app.panel) return;
  parts.raw.textContent = inspect.raw || "No snapshot yet.";
  parts.outbound.textContent = inspect.outbound || "Nothing sent yet.";
  const decisions = events.filter((e) => ["validate", "approval", "execute", "block"].includes(e.kind))
    .map((e) => `step ${e.step} ${e.kind}: ${e.detail}`)
    .concat((inspect.history || []).map((h) => `history step ${h.step}: ${h.action} ${h.label || ""} -> ${h.result}`));
  parts.decisions.replaceChildren(...(decisions.length ? decisions : ["No decisions yet."])
    .map((text) => el("li", { textContent: text })));
}

async function loadEval(run = false) {
  const body = app.panel.evalBody;
  body.replaceChildren(el("p", { className: "note", textContent: run ? "Running quick evaluation..." : "Loading..." }));
  let data = {};
  try {
    data = await api("/api/eval" + (run ? "/run" : ""), run ? { method: "POST" } : {});
  } catch {
    data = {};
  }
  if (!app.panel) return;
  const button = el("button", { type: "button", className: "primary", textContent: "Run quick evaluation" });
  button.addEventListener("click", () => { button.disabled = true; loadEval(true); });
  const empty = !data || typeof data !== "object" || !Object.keys(data).length;
  body.replaceChildren(empty ? el("p", { textContent: "No results yet" }) : kvTable(data),
    el("div", { className: "row" }, button));
}

async function loadSettings() {
  const [config, rules] = await Promise.all([api("/api/config"), api("/api/rules")]);
  if (!app.panel) return;
  renderRules(config.types, rules);
  renderAiChoice(config);
}

const saveRules = (rules) => api("/api/rules", { method: "PUT", body: rules });

function renderRules(types, rules) {
  const grid = el("div", { className: "rules" });
  types.forEach((type) => {
    const on = el("input", { type: "checkbox", checked: rules.enabled[type] !== false, id: `rule-${type}` });
    const hint = el("input", { type: "checkbox", checked: !!rules.hints[type] });
    on.addEventListener("change", () => { rules.enabled[type] = on.checked; saveRules(rules); });
    hint.addEventListener("change", () => { rules.hints[type] = hint.checked; saveRules(rules); });
    grid.append(el("div", { className: "rule" },
      on, el("label", { htmlFor: on.id, textContent: `${typeLabel(type)} (${type})` }),
      el("label", { className: "hint" }, hint, "hint")));
  });

  const tags = el("div", { className: "row" });
  const drawTags = () => tags.replaceChildren(...rules.custom.map((pattern, i) => {
    const remove = el("button", { type: "button", textContent: "x", ariaLabel: `Remove ${pattern}` });
    remove.addEventListener("click", async () => { rules.custom.splice(i, 1); await saveRules(rules); drawTags(); });
    return el("span", { className: "tag" }, pattern, remove);
  }));
  const input = el("input", { type: "text", id: "custom-rule", placeholder: "e.g. ORD-\\d{6}" });
  const form = el("form", { className: "row" },
    el("label", { htmlFor: input.id, textContent: "Always hide..." }), input,
    el("button", { type: "submit", className: "secondary", textContent: "Add" }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pattern = input.value.trim();
    if (!pattern) return;
    rules.custom.push(pattern);
    input.value = "";
    await saveRules(rules);
    drawTags();
  });
  drawTags();
  app.panel.rules.replaceChildren(grid, form, tags);
}

function renderAiChoice(config) {
  const note = el("p", { className: "note" });
  const option = (value, text, disabled) => {
    const input = el("input", { type: "radio", name: "ai", value, checked: config.ai === value, disabled });
    input.addEventListener("change", async () => {
      const res = await api("/api/config", { method: "POST", body: { ai: value } });
      note.textContent = res.ok ? `Using ${text} from the next run.` : res.error;
    });
    return el("label", { className: "radio" }, input, text);
  };
  const box = app.panel.ai;
  box.replaceChildren(option("mock", "Mock (offline)", false),
    option("gemini", "Gemini", !config.gemini_available), note);
  if (!config.gemini_available) note.textContent = "Gemini is off: add GEMINI_API_KEY to .env to enable it.";
}

function leakTestControls() {
  const result = el("p", { className: "result", ariaLive: "polite" });
  const button = el("button", { type: "button", className: "primary", textContent: "Run leak test" });
  button.addEventListener("click", async () => {
    button.disabled = true;
    result.textContent = "Sending a planted secret past the sanitizer...";
    try {
      const res = await api("/api/leak-test", { method: "POST" });
      result.textContent = res.blocked ? "Blocked: the guard stopped a planted secret"
        : "Not blocked: the planted secret got through";
      result.classList.toggle("ok", !res.blocked);
    } catch {
      result.textContent = "The leak test could not run.";
    } finally {
      button.disabled = false;
    }
  });
  return el("div", {},
    el("p", { className: "note", textContent: "Sends a canary value straight to the guard, skipping the sanitizer." }),
    button, result);
}

/* ---------- Wiring ---------- */

function init() {
  $("task-form").addEventListener("submit", startTask);
  $("ai-view").addEventListener("change", toggleAiView);
  $("status").addEventListener("click", showStatusDetails);
  $("status-sheet").querySelector("[data-close]").addEventListener("click", () => closeSheet("status-sheet"));
  $("approve").addEventListener("click", () => answer(true));
  $("cancel").addEventListener("click", () => answer(false));
  $("why-link").addEventListener("click", toggleWhy);
  $("how-link").addEventListener("click", openPanel);
  document.addEventListener("keydown", trapFocus);
  $("img-real").addEventListener("load", () => drawFrost(app.state));
  window.addEventListener("resize", () => drawFrost(app.state));
  loadScenarios().catch(() => {});
  poll();
}

init();
