// Best pulls: confidence groups from compare(), not a fake strict ranking.
import { get, sleep } from "../api.js";
import { badge, chip, esc, lineup, signed } from "../ui.js";

const GROUPS = [
  ["Clear recommendation", "good", "Beats every alternative by more than the uncertainty."],
  ["Competitive / roughly equal", "info", "The evidence cannot separate these from the leader. Their order is not a ranking."],
  ["Lower-value", "plain", "Meaningfully below the leading group."],
  ["Provisional / insufficient evidence", "warn", "No simulations of the character yet, or no team on your account can be evaluated."],
];

export async function render(main) {
  main.innerHTML = `<h1>Best pulls</h1>
    <p class="lead">What each unowned character changes in your account plan, fully built at C0.</p><div id="body"></div>`;
  const body = main.querySelector("#body");
  for (;;) {
    const d = await get("/api/pulls");
    body.innerHTML = (d.complete ? "" : `<p class="callout small">Computing pull values: ${d.progress[0]} of ${d.progress[1]} characters…</p>`) +
      GROUPS.map(([g, kind, help]) => {
        const items = d.groups[g] || [];
        if (!items.length) return "";
        return `<h2>${badge(g, kind)}</h2><p class="muted small">${esc(help)}</p><div class="grid">${items.map(card).join("")}</div>`;
      }).join("");
    if (d.complete) return;
    await sleep(2500);
  }
}

function card(c) {
  if (c.unavailable) return `<div class="card"><h3>${chip(c.character)}</h3><p class="muted small">${esc(c.unavailable)}</p></div>`;
  const g = c.gain;
  const reason = (c.pros && c.pros[0]) || (c.explanation && c.explanation[0]) || "";
  const state = c.best_team && c.best_team.evidence ? c.best_team.evidence.state : "";
  return `<div class="card">
    <div class="spread"><h3>${chip(c.character)}</h3><a class="small" href="#/whatif/${encodeURIComponent(c.character)}">What-If →</a></div>
    <div class="power"><div><div class="k">Account gain</div><div class="v">${signed(g.expected)}<small> ± ${g.sd}</small></div></div>
      <div><div class="k">Gain is real</div><div class="v">${Math.round(c.probability_positive * 100)}%</div></div></div>
    <div class="row">${badge(c.kind, "plain")}${badge({ simulation: "Simulated", interpolation: "Interpolated", "kit-model": "Provisional" }[state] || state, state === "simulation" ? "good" : state === "kit-model" ? "warn" : "info")}${c.no_change ? badge("no change", "plain") : ""}</div>
    ${c.best_team ? `<p class="small" style="margin:8px 0 2px">Best team: ${lineup(c.best_team.lineup)}</p>` : ""}
    <p class="small">${esc(reason)}</p>
    <p class="small muted">${esc((c.gain_source || []).join(" · "))}</p>
    ${c.experimental_lineup ? `<p class="small muted">Higher modeled experimental lineup: ${esc(c.experimental_lineup.team.lineup.join(" / "))} (${signed(c.experimental_lineup.raw_gain.expected)}), not recommended.</p>` : ""}
  </div>`;
}
