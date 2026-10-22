// Shared UI pieces. Evidence is always visible as badges, never only in a tooltip.
import { characters } from "./api.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let elements = {};
export async function loadElements() {
  for (const c of await characters()) elements[c.name] = c.element;
}

export function chip(name, extra = "") {
  return `<span class="chip"><span class="dot ${esc(elements[name] || "")}"></span>${esc(name)}${extra}</span>`;
}

export const lineup = (names) => `<span class="row">${names.map((n) => chip(n)).join("")}</span>`;

export function badge(text, kind = "plain", title = "") {
  return `<span class="badge ${kind}" ${title ? `title="${esc(title)}"` : ""}>${esc(text)}</span>`;
}

// Evidence badges for a team: confidence, where the number comes from, and anything unusual about it.
export function evidenceBadges(team) {
  const e = team.evidence || {};
  const out = [];
  const rec = (team.recommendability || {}).level;
  if (rec) out.push(badge(rec.charAt(0).toUpperCase() + rec.slice(1), { established: "good", credible: "info", experimental: "warn", unsupported: "bad" }[rec],
    (team.recommendability.reasons || []).join("; ")));
  const conf = e.badge || "Low";
  out.push(badge(`${conf} confidence`, conf === "High" ? "good" : conf === "Medium" ? "info" : "warn"));
  const state = { simulation: "Simulated", interpolation: "Interpolated", "kit-model": "Provisional", "rules-only": "Rules only", none: "No estimate" }[e.state] || e.state;
  if (state) out.push(badge(state, e.state === "simulation" ? "good" : e.state === "interpolation" ? "info" : "warn"));
  // partial mechanics coverage has its own badge below; "Unusual" is shown only for a real unusual finding
  const unusual = (team.status_reasons || []).filter((r) => !/^mechanics coverage/.test(r));
  if (team.status === "unusual" && unusual.length) out.push(badge("Unusual", "warn", unusual.join("; ")));
  if (team.status === "provisional" && e.state !== "kit-model") out.push(badge("Provisional", "warn"));
  if (e.quality === "poor") out.push(badge("Poor community evidence", "bad", (e.quality_reasons || []).join("; ")));
  if (e.quality === "mixed") out.push(badge("Mixed community data", "warn", (e.quality_reasons || []).join("; ")));
  if (e.coverage && e.coverage !== "complete") out.push(badge(`Mechanics coverage ${e.coverage}`, "warn"));
  return `<span class="row">${out.join("")}</span>`;
}

export const pm = (x) => (x == null ? "?" : `${Math.round(x.expected)}<small> ± ${Math.round(x.sd)}</small>`);
export const signed = (x, d = 1) => (x == null ? "?" : `${x >= 0 ? "+" : ""}${Number(x).toFixed(d)}`);

export function powerBlock(team) {
  return `<div class="power">
    <div><div class="k">Ceiling</div><div class="v">${pm(team.ceiling)}</div></div>
    <div><div class="k">Current</div><div class="v">${pm(team.current)}</div></div>
    <div><div class="k">Meta</div><div class="v">${pm(team.meta)}</div></div>
  </div>`;
}

export function insights(team) {
  const s = (team.strengths || []).map((x) => `<li title="${esc(x.evidence)}">${esc(x.text)} <span class="muted small">${esc(x.evidence)}</span></li>`).join("");
  const p = (team.problems || []).map((x) => `<li class="sev-${x.severity}">${esc(x.text)} <span class="muted small">${esc(x.evidence || "")}</span></li>`).join("");
  return `<div class="cols">
    <div><h3>Strengths</h3>${s ? `<ul class="items">${s}</ul>` : `<p class="muted small">Nothing the evidence can point to.</p>`}</div>
    <div><h3>Problems</h3>${p ? `<ul class="items">${p}</ul>` : `<p class="muted small">None found.</p>`}</div>
  </div>`;
}

// Mechanics read from the kits (gtc/team_mechanics.py): representation only, never power.
const FN_ORDER = ["on-field damage", "off-field damage", "driver", "sustain", "swirl support", "grouping", "battery", "buffs", "debuffs"];

export function mechanicsPanel(team) {
  const m = team.mechanics;
  if (!m) return "";
  const fns = Object.entries(m.supplied_functions || {})
    .sort((a, b) => (FN_ORDER.indexOf(a[0]) + 99 * !FN_ORDER.includes(a[0])) - (FN_ORDER.indexOf(b[0]) + 99 * !FN_ORDER.includes(b[0])))
    .map(([f, who]) => `<tr><td>${esc(f)}</td><td>${who.map((n) => chip(n)).join(" ")}</td></tr>`).join("");
  const missing = (m.missing_functions || []).map((f) => badge(f.replace(" (soft)", ""), /soft/.test(f) ? "plain" : "warn",
    /soft/.test(f) ? "Soft: fine in short fights" : "Nobody on the team supplies this")).join(" ");
  const edges = {};
  for (const s of m.synergies || []) (edges[`${s.from} → ${s.to}`] ||= []).push(s);
  const syn = Object.entries(edges).map(([k, xs]) => `<li>${esc(k)} <span class="muted small">${esc([...new Set(xs.map((x) => x.effect))].join("; "))}${
    xs.some((x) => x.state === "conditional") ? " (conditional)" : ""}</span></li>`).join("");
  const conf = (m.conflicts || []).map((c) => `<li class="sev-${c.severity === "harm" ? "high" : "low"}">${esc(c.text)}
    <span class="muted small">${c.severity === "harm" ? "harm" : "caution"}; resolved by ${esc(c.resolved_by)}</span></li>`).join("");
  const opp = (m.opportunity_losses || []).map((o) => `<li class="sev-medium">${esc(o.text)}</li>`).join("");
  const deps = (m.reaction_dependencies || []).map((d) => `${badge(`${d.member}: ${d.reaction}`, d.met ? "good" : "warn",
    d.met ? "this team can trigger it" : "this team cannot trigger it")}`).join(" ");
  const kc = m.kit_coverage || {};
  const cov = [
    ...(kc.reviewed || []).map((n) => badge(n, "good", "reviewed kit (checked against the official text)")),
    ...(kc.compiled || []).map((n) => badge(n, "info", "compiled kit: LLM-extracted from the official text, checked, not human-reviewed")),
    ...(kc.derived || []).map((n) => badge(n, "warn", "derived kit: roles and field time from measurements only; buffs unknown")),
  ].join(" ");
  return `<div class="card" style="margin-top:12px">
    <h3>Mechanics</h3>
    <p class="muted small">Read from the character kits. This explains how the team works and what it lacks; it never changes the power numbers.</p>
    <div class="cols">
      <div>
        <h3>Who does what</h3><table>${fns}</table>
        ${missing ? `<p class="small" style="margin-top:8px">Missing: ${missing}</p>` : ""}
        ${deps ? `<h3>Reactions the kits need</h3><div class="row">${deps}</div>` : ""}
      </div>
      <div>
        <h3>Buffs that reach a damage dealer</h3>${syn ? `<ul class="items">${syn}</ul>` : `<p class="muted small">None found in the kits.</p>`}
        ${conf ? `<h3>Conflicts</h3><ul class="items">${conf}</ul>` : ""}
        ${opp ? `<h3>Unused potential</h3><ul class="items">${opp}</ul>` : ""}
      </div>
    </div>
    <p class="small" style="margin-top:8px">Kits: ${cov}</p>
  </div>`;
}

export function teamCard(team, { title = "", extra = "", link = true } = {}) {
  const q = encodeURIComponent(team.lineup.join(","));
  return `<div class="card">
    <div class="spread"><h3>${esc(title)}</h3>${link ? `<a class="small" href="#/builder?team=${q}">Open in Team Builder</a>` : ""}</div>
    ${lineup(team.lineup)}
    <div class="muted small" style="margin-top:6px">${esc(team.identity.label || "")}</div>
    ${powerBlock(team)}
    ${evidenceBadges(team)}
    ${extra}
  </div>`;
}

export function setStatus(text) {
  document.getElementById("status").textContent = text;
}
