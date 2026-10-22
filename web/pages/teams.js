// Recommended Teams: overlap allowed (strongest individual teams) or not (the account plan).
import { get } from "../api.js";
import { badge, esc, insights, lineup, teamCard } from "../ui.js";

export async function render(main, { query }) {
  const overlap = query.get("overlap") !== "0";
  main.innerHTML = `
    <h1>Recommended teams</h1>
    <div class="row" style="margin:6px 0 14px">
      <span class="toggle">
        <button id="on" class="${overlap ? "on" : ""}">Allow character overlap</button>
        <button id="off" class="${overlap ? "" : "on"}">No overlap (account plan)</button>
      </span>
    </div>
    <div id="body"><div class="loading">Loading…</div></div>`;
  main.querySelector("#on").onclick = () => (location.hash = "#/teams?overlap=1");
  main.querySelector("#off").onclick = () => (location.hash = "#/teams?overlap=0");
  const body = main.querySelector("#body");
  if (overlap) {
    const d = await get("/api/teams?overlap=1");
    body.innerHTML = `<p class="lead">Your best recommendable team for each core, strongest first. The same character can appear in several.
      Close variants are listed under each team.</p>
      <div class="grid">${d.teams.map((t) => teamCard(t, { title: `Best ${t.core} team`, extra:
        (t.admitted_because ? `<p class="callout warn small">Experimental, shown because: ${esc(t.admitted_because)}.</p>` : "") +
        (t.variants.length ? `<details style="margin-top:8px"><summary>${t.variants.length} variants</summary>${t.variants.map((v) =>
          `<div class="spread small" style="margin:6px 0">${lineup(v.lineup)}<span>${Math.round(v.ceiling.expected)} ± ${Math.round(v.ceiling.sd)} ${badge(v.recommendability.level, "plain")}</span></div>`).join("")}</details>` : "") +
        details(t) })).join("")}</div>
      ${d.not_recommended.length ? `<h2>High model value, not recommended</h2>
        <p class="muted small">The model scores these well, but they are experimental (unusual, weakly supported, or breaking a kit condition). Open one in the Team Builder to see why.</p>
        <div class="card">${d.not_recommended.map((t) => `<div class="spread small" style="margin:6px 0">${lineup(t.lineup)}
          <span>${Math.round(t.ceiling.expected)} ± ${Math.round(t.ceiling.sd)} ${badge(t.recommendability.level, "warn", (t.recommendability.reasons || []).join("; "))}
          <a href="#/builder?team=${encodeURIComponent(t.lineup.join(","))}">open</a></span></div>`).join("")}</div>` : ""}`;
    return;
  }
  const d = await get("/api/teams?overlap=0");
  const alloc = d.allocation || [];
  const byTeam = (t) => alloc.filter((a) => a.placed_on.join() === t.lineup.join());
  body.innerHTML = `
    <p class="lead">The best way to split your characters into four teams, with no character used twice. Each team
      counts only what it adds above a replacement team you could field anyway.</p>
    <div class="grid two">${d.teams.map((t, i) => teamCard(t, {
      title: `Team ${i + 1}`,
      extra: byTeam(t).map((a) => `<p class="callout small">${esc(a.text)}</p>`).join("") + details(t),
    })).join("")}</div>
    ${d.allocation_ready ? "" : `<p class="muted small">Support-allocation explanations are still computing; refresh in a moment.</p>`}
    ${d.raw_model_plan ? `<p class="callout small">The raw model's best plan differs by ${d.raw_model_plan.difference.expected} ± ${d.raw_model_plan.difference.sd} and uses teams the advisor does not recommend.</p>` : ""}
    ${alloc.length ? `<h2>Why some characters sit where they do</h2>
      <div class="card"><table><tr><th>Character</th><th>Kept on</th><th>Would be stronger on</th><th>Net for the account</th></tr>
      ${alloc.map((a) => `<tr><td><b>${esc(a.unit)}</b></td><td>${lineup(a.placed_on)}<br><span class="small muted">${a.team_b.now} → ${a.team_b.without_unit} without them</span></td>
        <td>${lineup(a.alternative_team)}<br><span class="small muted">${a.team_a.now} → ${a.team_a.with_unit} with them (for ${esc(a.swapped_with)})</span></td>
        <td>${a.net_account_effect >= 0 ? "+" : ""}${a.net_account_effect} ${a.comparison === "roughly_equal" ? badge("roughly equal", "plain") : badge("clear", "good")}</td></tr>`).join("")}
      </table></div>` : ""}
    ${d.ties.length ? `<h2>Choices the evidence cannot separate</h2><div class="card"><ul class="items">${d.ties.map((x) =>
      `<li>${lineup(x.team)}: <b>${esc(x.in)}</b> instead of <b>${esc(x.out)}</b> is roughly equal (${Math.round(x.probability_plan_better * 100)}% that the plan's pick is better)</li>`).join("")}</ul></div>` : ""}
    <h2>By content mode</h2>
    <div class="grid">${Object.entries(d.modes).map(([k, m]) => `<div class="card"><h3>${esc(modeName(k))}</h3>
      ${m.teams.map((t) => `<div style="margin:4px 0">${lineup(t)}</div>`).join("")}
      ${m.note ? `<p class="muted small">${esc(m.note)}</p>` : ""}</div>`).join("")}</div>`;
}

const details = (t) => `<details style="margin-top:8px"><summary>Strengths and problems</summary>${insights(t)}</details>`;
const modeName = (k) => ({ abyss: "Spiral Abyss", stygian: "Stygian Onslaught", general: "General (four teams)", theater: "Imaginarium Theater" }[k] || k);
