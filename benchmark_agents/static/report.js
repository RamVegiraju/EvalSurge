"use strict";

const categories = ["model", "retrieval", "tool", "memory", "orchestration", "parallel"];
const labels = {model: "Model calls", retrieval: "Retrieval", tool: "Tools", memory: "Memory", orchestration: "Orchestration", parallel: "Parallel"};
const colors = {model: "#b39bef", retrieval: "#80c5ac", tool: "#e9b383", memory: "#ca95bf", orchestration: "#819dd0", parallel: "#9797ab"};
let report;
let offset = 0;
let selected;
let loading = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function number(value, digits = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function percent(value) {
  return typeof value === "number" && Number.isFinite(value) ? `${number(value * 100, 1)}%` : "—";
}

function humanize(value) {
  const text = String(value ?? "unknown").replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function badge(status) {
  const tone = ["completed", "available", "ready"].includes(status) ? "ok" :
    ["pending", "running", "evaluating", "profiling", "queued", "skipped"].includes(status) ? "" : "warning";
  return element("span", humanize(status), `badge ${tone}`);
}

function metric(title, value, unit, detail) {
  const card = element("section", undefined, "card");
  const kpi = element("div", value, "kpi");
  kpi.append(element("small", unit));
  card.append(element("div", title, "label"), kpi, element("div", detail, "detail"));
  return card;
}

function scorerName(recommendation) {
  const reference = report.run.plan.registered_scorers?.find(candidate => `registered:${candidate.alias}` === recommendation.scorer);
  return reference?.name ?? humanize(recommendation.scorer);
}

function scorerSource(recommendation, result) {
  const reference = report.run.plan.registered_scorers?.find(candidate => `registered:${candidate.alias}` === recommendation.scorer);
  if (reference) return `Registered MLflow · v${reference.version}`;
  return `MLflow catalog · ${result?.version ?? report.run.plan.rubric_version}`;
}

function drawSuggestions() {
  const plan = report.run.plan;
  document.getElementById("plan-source").textContent = `${plan.source === "llm" ? "LLM-suggested" : "Explicit selection"} · frozen plan ${plan.id.slice(0, 8)}`;
  const container = document.getElementById("suggestions");
  container.replaceChildren();
  for (const recommendation of plan.recommendations) {
    const card = element("article", undefined, "card suggestion");
    const heading = element("div", undefined, "section-heading");
    heading.append(element("h3", scorerName(recommendation)), badge(recommendation.status));
    const fields = element("div", undefined, "evidence-fields");
    fields.append(element("span", "Requires"));
    fields.append(...recommendation.required_fields.map(field => element("span", field, "field")));
    card.append(
      heading,
      element("code", recommendation.scorer),
      element("p", recommendation.reason),
      element("div", `${recommendation.eligible_samples} / ${recommendation.total_samples} input cases ready · pre-load evidence`, "readiness"),
      fields,
      element("p", scorerSource(recommendation), "detail")
    );
    container.append(card);
  }
  if (!plan.recommendations.length) container.append(element("p", "Performance-only run. No quality criteria were requested.", "muted"));
  document.getElementById("plan-note").textContent = plan.notes.join(" ");
}

function summary(title, value, detail) {
  const block = element("div");
  block.append(element("div", title, "label"), element("div", value, "summary-value"), element("div", detail, "detail"));
  return block;
}

function drawJudges() {
  const run = report.run;
  const results = run.evaluation.results ?? [];
  const recommendations = run.plan.recommendations;
  const status = run.evaluation.status ?? run.evaluation_status;
  document.getElementById("evaluation-status").replaceChildren(badge(status));
  const selectedAnswers = new Set(results.flatMap(result => result.request_ids ?? [])).size;
  const selectionsKnown = results.some(result => Array.isArray(result.request_ids));
  const errorsKnown = results.filter(result => typeof result.judge_errors === "number");
  const errors = errorsKnown.reduce((sum, result) => sum + result.judge_errors, 0);
  document.getElementById("evaluation-summary").replaceChildren(
    summary("Criteria with assessments", `${results.filter(result => result.scored > 0).length} / ${recommendations.length}`, "Any scored outcome, not a quality pass"),
    summary("Distinct answers selected", selectionsKnown ? String(selectedAnswers) : "—", "Shared selections counted once across judges"),
    summary("Reported judge errors", errorsKnown.length ? String(errors) : "—", `${errorsKnown.length} / ${recommendations.length} criteria report error counts`)
  );
  const table = element("table", undefined, "judge-table");
  const head = element("thead");
  const heading = element("tr");
  for (const text of ["Criterion", "Outcome", "Assessment coverage", "Status / errors", "Frozen source"]) {
    const cell = element("th", text);
    cell.scope = "col";
    heading.append(cell);
  }
  head.append(heading);
  const body = element("tbody");
  for (const recommendation of recommendations) {
    const result = results.find(candidate => candidate.scorer === recommendation.scorer);
    const row = element("tr");
    const criterion = element("td");
    criterion.append(element("div", scorerName(recommendation)), element("div", recommendation.scorer, "detail"));
    const outcome = element("td");
    if (typeof result?.pass_rate === "number" && Number.isFinite(result.pass_rate)) {
      outcome.append(element("strong", percent(result.pass_rate)), element("div", "boolean pass rate", "detail"));
    } else {
      const metrics = Object.entries(result?.metrics ?? {});
      outcome.append(element("strong", metrics.length ? "Score metrics" : "—"));
      for (const [name, value] of metrics) outcome.append(element("div", `${name}: ${typeof value === "number" ? number(value, 2) : String(value)}`, "detail"));
      if (!metrics.length) outcome.append(element("div", result?.scored > 0 ? "No numeric summary" : "No assessments", "detail"));
    }
    const coverage = element("td");
    if (result) {
      const eligible = result.eligible ?? result.coverage?.eligible;
      const selection = result.coverage?.selected ?? result.attempted;
      coverage.append(
        element("div", `${number(result.scored)} / ${number(result.attempted)} selected scored`),
        element("div", `${number(selection)} / ${number(eligible)} eligible selected`, "detail")
      );
    } else {
      coverage.append(element("div", "—"), element("div", "No captured-answer assessments", "detail"));
    }
    const state = element("td");
    const absentStatus = recommendation.status === "needs_data" ? "needs_data" :
      status === "completed" || status === "completed_with_gaps" ? "not_assessed" : status;
    state.append(badge(result?.status ?? absentStatus));
    if (typeof result?.judge_errors === "number") state.append(element("div", `${result.judge_errors} judge error${result.judge_errors === 1 ? "" : "s"}`, result.judge_errors ? "detail warning" : "detail"));
    if (!result && recommendation.status === "needs_data") state.append(element("div", `Required: ${recommendation.required_fields.join(", ")}`, "detail"));
    row.append(criterion, outcome, coverage, state, element("td", scorerSource(recommendation, result), "detail"));
    body.append(row);
  }
  table.append(head, body);
  const container = document.getElementById("judges");
  container.replaceChildren(recommendations.length ? table : element("p", "No evaluation was requested. Performance measurements remain available.", "muted"));
  document.getElementById("sampling-note").textContent = `Sampling: ${run.plan.sampling_policy ?? "not recorded"} · at most ${run.plan.max_scored_requests ?? "—"} answers per criterion. Rates describe scored samples only, not the full workload. Catalog judge model: ${run.plan.judge_model ?? "not configured"}; registered judges use operator configuration.`;
}

function focusedSpans(profile) {
  const byId = new Map(profile.spans.map(span => [span.span_id, span]));
  const enclosing = new Set(profile.spans.filter(span => byId.get(span.parent_id)?.category === span.category).map(span => span.parent_id));
  const operations = profile.spans.filter(span => span.category !== "orchestration" && !enclosing.has(span.span_id));
  return operations.length ? operations : profile.spans;
}

function drawWaterfall(profile) {
  selected = profile.request_id;
  document.querySelectorAll("#heatmap tbody tr").forEach(row => {
    const active = row.dataset.requestId === selected;
    row.classList.toggle("selected", active);
    row.querySelector("button").setAttribute("aria-pressed", String(active));
  });
  document.getElementById("waterfall-title").textContent = `Request ${profile.request_id.slice(0, 8)} · span waterfall`;
  const note = document.getElementById("waterfall-note");
  const waterfall = document.getElementById("waterfall");
  waterfall.replaceChildren();
  document.getElementById("show-framework").disabled = profile.status !== "available";
  if (profile.status !== "available") {
    note.textContent = `Client latency ${number(profile.latency_ms)} ms · trace gap: ${profile.status}. Internal time is unknown.`;
    return;
  }
  const all = document.getElementById("show-framework").checked;
  const spans = all ? profile.spans : focusedSpans(profile);
  const hidden = profile.spans.length - spans.length;
  note.textContent = `Agent-relative origin · ${number(profile.agent_duration_ms)} ms observed · ${number(profile.client_minus_agent_ms)} ms client-minus-agent, unattributed. Inclusive bars can overlap; not a critical path. ${hidden ? `${hidden} enclosing/framework span${hidden === 1 ? "" : "s"} hidden; focused view shows deepest spans per category.` : "All recorded spans shown."}`;
  for (const span of spans) {
    const row = element("div", undefined, "water-row");
    const label = element("span", `${all ? "› ".repeat(Math.min(span.depth, 5)) : ""}${span.name}`, "water-label");
    label.title = `${span.category} · ${span.status} · self ${number(span.self_ms, 2)} ms · start ${number(span.start_ms, 2)} ms`;
    const track = element("div", undefined, "water-track");
    const bar = element("div", undefined, "water-bar");
    const denominator = Math.max(profile.agent_duration_ms, 0.001);
    bar.style.left = `${span.start_ms / denominator * 100}%`;
    bar.style.width = `${span.duration_ms / denominator * 100}%`;
    bar.style.background = colors[span.category];
    bar.title = label.title;
    track.append(bar);
    row.append(label, track, element("span", `${number(span.duration_ms)} ms`, "number"));
    waterfall.append(row);
  }
}

function drawHeatmap() {
  const table = document.getElementById("heatmap");
  const heading = element("tr");
  for (const text of ["Request", ...categories.map(category => labels[category]), "Unattributed", "Client total"]) {
    const cell = element("th", text);
    cell.scope = "col";
    heading.append(cell);
  }
  const head = element("thead");
  head.append(heading);
  const body = element("tbody");
  const profiles = [...report.requests].sort((first, second) => (second.latency_ms ?? -1) - (first.latency_ms ?? -1));
  const maximum = Math.max(1, ...profiles.flatMap(profile => Object.values(profile.occupancy_ms)));
  for (const profile of profiles) {
    const row = element("tr");
    row.dataset.requestId = profile.request_id;
    const identifier = element("td");
    const button = element("button", `${profile.request_id.slice(0, 8)}${profile.success ? "" : " · failed"}`, "request-button");
    button.type = "button";
    button.setAttribute("aria-label", `Inspect request ${profile.request_id}`);
    button.addEventListener("click", () => drawWaterfall(profile));
    identifier.append(button);
    row.append(identifier);
    for (const category of categories) {
      const value = profile.occupancy_ms[category];
      const cell = element("td", number(value), "heat");
      if (typeof value === "number") cell.style.backgroundColor = `hsl(270 24% ${15 + 26 * value / maximum}%)`;
      else cell.classList.add("gap");
      cell.title = typeof value === "number" ? `${labels[category]}: ${number(value, 2)} ms wall occupancy` : `Internal timing unknown: ${profile.status}`;
      row.append(cell);
    }
    row.append(element("td", number(profile.client_minus_agent_ms), "heat"), element("td", `${number(profile.latency_ms)} ms`));
    body.append(row);
  }
  table.replaceChildren(head, body);
  document.getElementById("page").textContent = `${report.requests.length ? offset + 1 : 0}–${Math.min(offset + report.requests.length, report.total)} of ${report.total} attempts`;
  const choice = profiles.find(profile => profile.request_id === selected) ?? profiles[0];
  if (choice) drawWaterfall(choice);
  else {
    selected = undefined;
    document.getElementById("waterfall").replaceChildren();
    document.getElementById("waterfall-title").textContent = "Request span waterfall";
    document.getElementById("waterfall-note").textContent = "No request profiles on this page.";
    document.getElementById("show-framework").disabled = true;
  }
}

function drawPerformance() {
  const run = report.run;
  const timing = run.metrics.timing_successful_only ?? {};
  document.getElementById("metrics").replaceChildren(
    metric("Successful throughput", number(run.metrics.successful_tps, 2), "req/s", "Includes ramp-up and drain; not sustainable capacity"),
    metric("End-to-end latency · p95", number(timing.latency_ms?.p95), "ms", "Successful attempts only"),
    metric("Answer-text TTFT · p95", number(timing.ttft_ms?.p95), "ms", "First nonempty answer delta at this client"),
    metric("Request error rate", percent(run.metrics.error_rate), "", `${run.metrics.successful_requests ?? 0} successful / ${run.metrics.requests ?? 0} attempts`)
  );
  document.getElementById("coverage").textContent = `Trace coverage ${percent(report.profiling.coverage)}`;
  const anatomy = document.getElementById("anatomy");
  anatomy.replaceChildren();
  const total = Object.fromEntries(categories.map(category => [category, report.requests.reduce((sum, profile) => sum + (profile.occupancy_ms[category] ?? 0), 0)]));
  const duration = Object.values(total).reduce((sum, value) => sum + value, 0);
  for (const category of categories) {
    const row = element("div", undefined, "bar-row");
    const track = element("div", undefined, "track");
    const fill = element("div", undefined, "fill");
    fill.style.width = `${duration ? total[category] / duration * 100 : 0}%`;
    fill.style.background = colors[category];
    track.append(fill);
    row.append(element("span", labels[category]), track, element("span", duration ? percent(total[category] / duration) : "—", "number"));
    anatomy.append(row);
  }
  anatomy.append(element("p", `Anatomy covers this page only. ${report.profiling.traced_requests} / ${report.profiling.total_requests} attempts have correlated traces in the full run. Parallel occupancy may include duplicate instrumentation; it is not proof of independent concurrency.`, "muted"));
  const hotspots = document.getElementById("hotspots");
  hotspots.replaceChildren();
  const operations = report.profiling.hotspots.filter(hotspot => hotspot.category !== "orchestration");
  const visible = operations.length ? operations : report.profiling.hotspots;
  document.getElementById("hotspot-note").textContent = `${operations.length ? "Model, tool, retrieval, and memory operations" : "All observed categories"} · inclusive span p95 in this run; overlap is possible.`;
  for (const hotspot of visible.slice(0, 5)) {
    const row = element("div", undefined, "hotspot");
    const name = element("div", hotspot.name, "hotspot-name");
    name.append(element("small", `${labels[hotspot.category] ?? hotspot.category} · ${hotspot.observations} observations`));
    row.append(name, element("strong", `${number(hotspot.p95_ms)} ms`));
    hotspots.append(row);
  }
  if (!report.profiling.hotspots.length) hotspots.append(element("p", "No internal hotspot evidence is available.", "muted"));
}

function render() {
  const run = report.run;
  const config = run.config;
  document.getElementById("title").textContent = config.evaluation.agent_manifest?.name ?? "Hosted agent benchmark";
  document.getElementById("subtitle").textContent = config.evaluation.description;
  document.getElementById("status").replaceChildren(badge(run.status));
  const context = document.getElementById("context");
  context.replaceChildren();
  const entries = [
    ["Target", `${config.target.framework ?? "Endpoint only"} · ${config.target.url}`],
    ["Workload", `${config.evaluation.samples.length} cases · ${run.metrics.requests ?? 0} attempts`],
    ["Load", `${config.load.concurrency} closed-loop users · one load level`],
    ["Inference preflight", humanize(run.preflight?.status ?? "not_run")],
    ["Phase outcomes", `Load: ${run.load_status ?? "unknown"} · traces: ${run.profiling_status ?? "unknown"} · eval: ${run.evaluation_status}`],
  ];
  for (const [label, value] of entries) {
    const block = element("div");
    block.append(element("div", label, "label"), element("div", value, "value"));
    context.append(block);
  }
  if (run.preflight?.error) {
    const failure = element("div", undefined, "warning");
    failure.append(
      element("div", "Inference check failed — load did not start", "label"),
      element("p", run.preflight.error.message),
      element("code", run.preflight.error.code),
      element("div", `HTTP ${run.preflight.http_status ?? "unknown"} · request ${run.preflight.request_id ?? "not recorded"}`, "detail")
    );
    context.append(failure);
  }
  drawSuggestions();
  drawJudges();
  drawPerformance();
  drawHeatmap();
  const notes = [...report.profiling.notes, ...run.plan.notes, `Trace gaps: ${JSON.stringify(report.profiling.gaps)}. Run ID: ${run.id}.`];
  document.getElementById("notes").replaceChildren(...notes.map(note => element("li", note)));
  document.getElementById("report").hidden = false;
}

function updateControls() {
  document.getElementById("refresh").disabled = loading;
  document.getElementById("previous").disabled = loading || offset === 0;
  document.getElementById("next").disabled = loading || !report || offset + report.limit >= report.total;
}

async function load() {
  if (loading) return;
  const message = document.getElementById("message");
  const runId = document.getElementById("run-id").value.trim();
  document.getElementById("report").hidden = true;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(runId)) {
    report = undefined;
    message.textContent = "Enter a valid run UUID.";
    updateControls();
    return;
  }
  loading = true;
  updateControls();
  message.textContent = "Loading report evidence…";
  try {
    const key = document.getElementById("api-key").value;
    const url = new URL(`../v1/runs/${encodeURIComponent(runId)}/report?offset=${offset}&limit=25`, location.href);
    const response = await fetch(url.pathname + url.search, {headers: key ? {"X-API-Key": key} : {}, cache: "no-store", credentials: "same-origin"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message ?? `HTTP ${response.status}`);
    report = data;
    render();
    message.textContent = report.run.preflight?.error?.message ??
      `Run ${report.run.id} · ${humanize(report.run.status)}. Refresh to see later phase results.`;
    history.replaceState(null, "", `?run=${encodeURIComponent(runId)}`);
  } catch (error) {
    report = undefined;
    document.getElementById("report").hidden = true;
    message.textContent = error.message;
  } finally {
    loading = false;
    updateControls();
  }
}

document.getElementById("connect").addEventListener("submit", event => {
  event.preventDefault();
  if (loading) return;
  offset = 0;
  return load();
});
document.getElementById("previous").addEventListener("click", () => {
  if (loading || offset === 0) return;
  offset = Math.max(0, offset - 25);
  return load();
});
document.getElementById("next").addEventListener("click", () => {
  if (loading || !report || offset + report.limit >= report.total) return;
  offset += 25;
  return load();
});
document.getElementById("show-framework").addEventListener("change", () => {
  const profile = report?.requests.find(candidate => candidate.request_id === selected);
  if (profile) drawWaterfall(profile);
});
document.getElementById("legend").replaceChildren(...categories.slice(0, -1).map(category => {
  const item = element("span", undefined, "legend-item");
  const dot = element("span", undefined, "dot");
  dot.style.background = colors[category];
  item.append(dot, element("span", labels[category]));
  return item;
}));
updateControls();
const initial = new URLSearchParams(location.search).get("run");
if (initial) {
  document.getElementById("run-id").value = initial;
  load();
}
