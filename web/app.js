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
// Privacy choices: one three-way choice per kind of private data, grouped the way people think about it.
const MODES = [["redact", "Hide"], ["ask", "Ask permission"], ["reveal", "Reveal"]];
const CHOICE_GROUPS = [
  ["Identity", [["AADHAAR", "Aadhaar number"], ["PAN", "PAN number"], ["NAME", "name"], ["DOB", "date of birth"],
    ["ADDRESS", "address"]]],
  ["Payments", [["CARD", "card number"], ["CVV", "card security code"], ["EXPIRY", "card expiry"],
    ["UPI", "UPI address"], ["IFSC", "bank code (IFSC)"], ["ACCOUNT", "account number"]]],
  ["Login", [["PASSWORD", "password"], ["OTP", "one-time code"], ["API_KEY", "API keys and secret keys"]]],
  ["Contact", [["EMAIL", "email"], ["PHONE", "phone"]]],
  ["Other", [["IP_ADDRESS", "IP address"], ["MEDICAL", "health details"], ["FACE", "faces"]]],
];
const CHOICE_NAMES = Object.fromEntries(CHOICE_GROUPS.flatMap(([, rows]) => rows));
const SAVED = "Saved. Applies from the next step.";
const LOCAL_ONLY = "Privacy choices can only be changed on the computer running PrivacyLens.";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);
// A phone on the Wi-Fi may watch the AI view but never the real page, so it only ever loads the AI image.
const IS_REMOTE = !LOCAL_HOSTS.has(location.hostname);

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...kids) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...kids.filter((k) => k != null));
  return node;
};

const app = {
  state: { id: null }, scenario: null, imageKey: "", lastFocus: null, panel: null,
  rules: { modes: {}, hints: {}, custom: [] }, choices: null,
  seen: null, bannerQueue: [], bannerTimer: 0,
};
const BANNER_MS = 3500;

async function api(path, options = {}) {
  const init = { ...options };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, init);
  if (!res.ok) {
    const error = new Error(`${path}: ${res.status}`);
    const body = await res.json().catch(() => ({}));
    error.status = res.status;
    error.detail = typeof body.detail === "string" ? body.detail : "";
    throw error;
  }
  return res.json();
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const typeLabel = (type) => TYPE_LABELS[type] || type.toLowerCase().replace(/_/g, " ");
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const choiceName = (type) => CHOICE_NAMES[type] || typeLabel(type).toLowerCase();

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
  const hidden = `${plural(s.hidden.length, "thing", "things")} hidden`;
  const shared = s.shared || [];
  if (!shared.length) return `${hidden} · nothing private shared`;
  const names = (byApproval) => [...new Set(shared.filter((x) => (x.by === "approval") === byApproval)
    .map((x) => choiceName(x.type)))];
  const groups = [[names(false), "shared by your choice"], [names(true), "shared with your permission"]]
    .filter(([list]) => list.length)
    .map(([list, words]) => `${capitalize(list.join(", "))} ${words}`);
  return [hidden, ...groups].join(" · ");
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
  (IS_REMOTE ? ["ai"] : ["real", "ai"]).forEach((kind) => {
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
  const share = approval.kind === "share";
  $("approve").textContent = share ? "Allow for this task" : "Approve";
  $("cancel").textContent = share ? "Do not share" : "Cancel";
  $("approval-q").textContent = approval.question;
  $("why").textContent = approval.why;
  $("why").hidden = true;
  $("why-link").setAttribute("aria-expanded", "false");
  hideBanner();
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

/* Hidden-item banner: a quiet note at the top whenever something new is hidden during a run */

function noticeHidden(s) {
  const key = (item) => `${s.id}:${item.placeholder || item.type}`;
  const items = s.id ? s.hidden || [] : [];
  // The first poll only learns what is already hidden, so a reload or a joining phone stays quiet.
  if (!app.seen) {
    app.seen = new Set(items.map(key));
    return;
  }
  items.filter((item) => !app.seen.has(key(item))).forEach((item) => {
    app.seen.add(key(item));
    app.bannerQueue.push(item);
  });
  const busy = !$("approval").hidden || !$("status-sheet").hidden || app.panel || app.choices;
  if (app.bannerQueue.length && !busy) {
    showBanner(app.bannerQueue);
    app.bannerQueue = [];
  }
}

function bannerText(items) {
  if (items.length > 3) return `${items.length} things hidden`;
  const names = [...new Set(items.map((item) => choiceName(item.type)))];
  const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names[0];
  return `${capitalize(list)} hidden`;
}

function bannerElement() {
  if ($("hidden-banner")) return $("hidden-banner");
  const svgNs = "http://www.w3.org/2000/svg";
  const icon = document.createElementNS(svgNs, "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  icon.classList.add("banner-icon");
  const shield = document.createElementNS(svgNs, "path");
  shield.setAttribute("d", "M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3Z");
  icon.append(shield);
  const button = el("button", { type: "button", className: "banner" }, icon,
    el("span", { className: "banner-text" }, el("strong", { className: "banner-title" }),
      el("span", { className: "banner-sub", textContent: "Kept on this device" })));
  button.addEventListener("click", () => { hideBanner(); showStatusDetails(); });
  const pause = () => clearTimeout(app.bannerTimer);
  const resume = () => {
    if (button.matches(":hover") || button.contains(document.activeElement)) return;
    app.bannerTimer = setTimeout(hideBanner, BANNER_MS);
  };
  button.addEventListener("mouseenter", pause);
  button.addEventListener("focus", pause);
  button.addEventListener("mouseleave", resume);
  button.addEventListener("blur", resume);
  const wrap = el("div", { id: "hidden-banner", className: "banner-wrap" }, button);
  wrap.setAttribute("role", "status");
  wrap.setAttribute("aria-live", "polite");
  document.body.append(wrap);
  return wrap;
}

function showBanner(items) {
  const wrap = bannerElement();
  const button = wrap.querySelector(".banner");
  // Wait a frame so a freshly created live region is in place before its text changes.
  requestAnimationFrame(() => {
    wrap.querySelector(".banner-title").textContent = bannerText(items);
    button.classList.add("is-shown");
    clearTimeout(app.bannerTimer);
    if (!button.matches(":hover") && !button.contains(document.activeElement)) {
      app.bannerTimer = setTimeout(hideBanner, BANNER_MS);
    }
  });
}

function hideBanner() {
  clearTimeout(app.bannerTimer);
  const button = $("hidden-banner") && $("hidden-banner").querySelector(".banner");
  if (button) button.classList.remove("is-shown");
}

async function poll() {
  try {
    app.state = await api("/api/session");
    renderMain(app.state);
    noticeHidden(app.state);
    if (app.panel) await refreshPanel();
  } catch {
    $("narration").textContent = "Lost connection. Retrying...";
  }
  setTimeout(poll, POLL_MS);
}

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
      card("Privacy settings", parts.rules),
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
  const [config, rules] = await Promise.all([api("/api/config"), api("/api/rules").catch(() => null)]);
  if (!app.panel) return;
  if (rules) app.rules = normalizeRules(rules);
  renderRulesSummary();
  renderAiChoice(config);
}

/* Privacy choices */

function normalizeRules(rules) {
  return {
    modes: rules && typeof rules.modes === "object" && rules.modes ? rules.modes : {},
    hints: (rules && rules.hints) || {},
    custom: rules && Array.isArray(rules.custom) ? rules.custom : [],
  };
}

const modeOf = (type) => (MODES.some(([value]) => value === app.rules.modes[type]) ? app.rules.modes[type] : "ask");
const saveRules = async (change) => { app.rules = normalizeRules(await api("/api/rules", { method: "PUT", body: change })); };
const choicesAllowed = () => LOCAL_HOSTS.has(location.hostname);

// Phones may watch and approve, but settings stay on the computer: hide the link rather than fail.
function lockChoices() {
  $("choices-link").hidden = true;
}

async function loadRules() {
  if (!choicesAllowed()) return lockChoices();
  $("choices-link").hidden = false;
  try {
    app.rules = normalizeRules(await api("/api/rules"));
  } catch (error) {
    if (error.status === 403) lockChoices();
  }
}

function renderRulesSummary() {
  if (!app.panel) return;
  const counts = { redact: 0, ask: 0, reveal: 0 };
  Object.keys(CHOICE_NAMES).forEach((type) => { counts[modeOf(type)] += 1; });
  const open = el("button", { type: "button", className: "secondary", textContent: "Open Privacy choices" });
  open.disabled = $("choices-link").hidden;
  open.addEventListener("click", openChoices);
  const custom = app.rules.custom.length;
  app.panel.rules.replaceChildren(
    el("p", { className: "summary",
      textContent: `Hide: ${counts.redact} · Ask permission: ${counts.ask} · Reveal: ${counts.reveal}` }),
    el("p", { className: "note", textContent: custom
      ? `Plus ${plural(custom, "rule", "rules")} of your own that always hide.` : "No rules of your own yet." }),
    open);
}

function setBackgroundInert(on) {
  $("main").inert = on || !!$("how");
  if ($("how")) $("how").inert = on;
}

async function openChoices() {
  if ($("choices")) return;
  app.choicesFocus = document.activeElement;
  const done = el("button", { type: "button", className: "secondary", textContent: "Done" });
  done.addEventListener("click", closeChoices);
  const saved = el("p", { className: "saved" });
  saved.setAttribute("role", "status");
  saved.setAttribute("aria-live", "polite");
  const body = el("div", { className: "choices-body" }, el("p", { className: "note", textContent: "Loading..." }));
  const sheet = el("div", { className: "choices-sheet" },
    el("div", { className: "choices-head" }, el("h2", { id: "choices-title", textContent: "Privacy choices" }), done),
    saved, body);
  sheet.setAttribute("role", "dialog");
  sheet.setAttribute("aria-modal", "true");
  sheet.setAttribute("aria-labelledby", "choices-title");
  const overlay = el("div", { className: "choices", id: "choices" }, sheet);
  overlay.addEventListener("keydown", (e) => { if (e.key === "Escape") closeChoices(); });
  document.body.append(overlay);
  setBackgroundInert(true);
  app.choices = { overlay, sheet, body, saved };
  done.focus();
  try {
    app.rules = normalizeRules(await api("/api/rules"));
  } catch (error) {
    if (!app.choices) return;
    if (error.status === 403) lockChoices();
    body.replaceChildren(el("p", { className: "note",
      textContent: error.status === 403 ? LOCAL_ONLY : "Could not load your choices. Please try again." }));
    return;
  }
  if (app.choices) renderChoices();
}

function closeChoices() {
  if (!app.choices) return;
  app.choices.overlay.remove();
  app.choices = null;
  setBackgroundInert(false);
  renderRulesSummary();
  const back = app.choicesFocus;
  if (back && document.contains(back)) back.focus();
  // The summary was redrawn, so return to its fresh "Open Privacy choices" button.
  else if (app.panel) app.panel.rules.querySelector("button").focus();
}

function say(text) {
  if (!app.choices) return;
  const box = app.choices.saved;
  box.textContent = "";
  // Clearing first makes screen readers announce a repeated message again.
  requestAnimationFrame(() => { box.textContent = text; });
}

function renderChoices() {
  const intro = el("p", { className: "choices-intro" },
    el("strong", { textContent: "Hide:" }), " the AI never sees it. ",
    el("strong", { textContent: "Ask permission (default):" }), " hidden unless the AI needs it and you say yes, for that task only. ",
    el("strong", { textContent: "Reveal:" }), " the AI can read it.");
  const groups = CHOICE_GROUPS.map(([title, rows]) =>
    card(title, ...rows.map(([type, name]) => choiceRow(type, name))));
  app.choices.body.replaceChildren(intro, ...groups, customRules());
}

function choiceRow(type, name) {
  const labelId = `choice-${type}`;
  const group = el("div", { className: "seg" });
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-labelledby", labelId);
  MODES.forEach(([value, text]) => {
    const input = el("input", { type: "radio", name: `mode-${type}`, value, checked: modeOf(type) === value });
    input.addEventListener("change", () => pickMode(type, name, input, group));
    group.append(el("label", { className: `seg-${value}` }, input, el("span", { textContent: text })));
  });
  return el("div", { className: "choice" },
    el("span", { className: "choice-name", id: labelId, textContent: capitalize(name) }), group);
}

function syncRow(type, group) {
  group.querySelector(`input[value="${modeOf(type)}"]`).checked = true;
}

async function pickMode(type, name, input, group) {
  const restore = () => { syncRow(type, group); group.querySelector("input:checked").focus(); };
  if (input.value === "reveal" && !(await confirmReveal(name))) return restore();
  try {
    await saveRules({ modes: { [type]: input.value } });
    if (!(type in app.rules.modes)) throw new Error("choice not saved");
    syncRow(type, group);
    say(SAVED);
  } catch (error) {
    if (error.status === 403) lockChoices();
    if (app.choices) restore();
    say(error.status === 403 ? LOCAL_ONLY : "Could not save that choice. Please try again.");
  }
}

function confirmReveal(name) {
  return new Promise((resolve) => {
    const cancel = el("button", { type: "button", className: "secondary", textContent: "Cancel" });
    const reveal = el("button", { type: "button", className: "primary danger", textContent: "Reveal" });
    const box = el("div", { className: "sheet" },
      el("h2", { id: "confirm-q", textContent: `The AI service will be able to read your ${name}. Continue?` }),
      el("div", { className: "confirm-actions" }, cancel, reveal));
    box.setAttribute("role", "alertdialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-labelledby", "confirm-q");
    const back = el("div", { className: "confirm-back" }, box);
    const returnTo = document.activeElement;
    const finish = (yes) => {
      back.remove();
      app.choices.sheet.inert = false;
      if (yes && returnTo) returnTo.focus();
      resolve(yes);
    };
    cancel.addEventListener("click", () => finish(false));
    reveal.addEventListener("click", () => finish(true));
    back.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); finish(false); }
      if (e.key === "Tab") { e.preventDefault(); (document.activeElement === cancel ? reveal : cancel).focus(); }
    });
    app.choices.overlay.append(back);
    app.choices.sheet.inert = true;
    cancel.focus();
  });
}

function customRules() {
  const input = el("input", { type: "text", id: "custom-rule", placeholder: "e.g. ORD-\\d{6}", autocomplete: "off" });
  const error = el("p", { className: "error" });
  error.setAttribute("role", "alert");
  const tags = el("ul", { className: "tags", ariaLabel: "Your rules" });
  const save = async (custom) => {
    error.textContent = "";
    try {
      await saveRules({ custom });
      drawTags();
      say(SAVED);
      return true;
    } catch (err) {
      if (err.status === 403) lockChoices();
      error.textContent = err.detail || (err.status === 403 ? LOCAL_ONLY : "Could not save that rule. Please try again.");
      return false;
    }
  };
  const drawTags = () => tags.replaceChildren(...app.rules.custom.map((pattern, i) => {
    const remove = el("button", { type: "button", className: "link", textContent: "Remove" });
    remove.setAttribute("aria-label", `Remove ${pattern}`);
    remove.addEventListener("click", () => save(app.rules.custom.filter((_, j) => j !== i)));
    return el("li", { className: "tag" }, el("span", { textContent: pattern }), remove);
  }));
  const form = el("form", { className: "row" },
    el("label", { htmlFor: input.id, className: "rule-label", textContent: "Always hide..." }), input,
    el("button", { type: "submit", className: "secondary", textContent: "Add" }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pattern = input.value.trim();
    if (pattern && await save([...app.rules.custom, pattern])) input.value = "";
  });
  drawTags();
  return card("Your own rules",
    el("p", { className: "note", textContent: "Anything that matches is always hidden, whatever you picked above." }),
    form, error, tags);
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
    option("gemini", "Gemini", !config.gemini_available),
    option("mock_fooled", "Offline test AI that obeys the page (shows attacks being stopped)", false), note);
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

function init() {
  $("task-form").addEventListener("submit", startTask);
  $("ai-view").addEventListener("change", toggleAiView);
  if (IS_REMOTE) {
    $("ai-view").checked = true;
    $("ai-view").disabled = true;
    toggleAiView();
  }
  $("status").addEventListener("click", showStatusDetails);
  $("status-sheet").querySelector("[data-close]").addEventListener("click", () => closeSheet("status-sheet"));
  $("approve").addEventListener("click", () => answer(true));
  $("cancel").addEventListener("click", () => answer(false));
  $("why-link").addEventListener("click", toggleWhy);
  $("how-link").addEventListener("click", openPanel);
  $("choices-link").addEventListener("click", openChoices);
  document.addEventListener("keydown", trapFocus);
  $("img-real").addEventListener("load", () => drawFrost(app.state));
  window.addEventListener("resize", () => drawFrost(app.state));
  loadScenarios().catch(() => {});
  loadRules();
  poll();
}

init();
