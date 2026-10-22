// What-If: what actually changes if I pull this character?
import { characters, get } from "../api.js";
import { badge, chip, esc, evidenceBadges, lineup, signed } from "../ui.js";

export async function render(main, { arg }) {
  const all = (await characters()).filter((c) => !c.owned);
  main.innerHTML = `<h1>What-If pull</h1>
    <div class="row" style="margin-bottom:12px">
      <select id="pick"><option value="">Choose an unowned character…</option>${all.map((c) =>
        `<option ${c.name === arg ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
    </div><div id="body"></div>`;
  main.querySelector("#pick").onchange = (e) => (location.hash = `#/whatif/${encodeURIComponent(e.target.value)}`);
  if (!arg) return;
  const body = main.querySelector("#body");
  body.innerHTML = `<div class="loading">Adding ${esc(arg)} to your account and re-planning…</div>`;
  const w = await get(`/api/whatif/${encodeURIComponent(arg)}`);
  if (w.unavailable) { body.innerHTML = `<div class="card"><p>${esc(arg)}: ${esc(w.unavailable)}</p></div>`; return; }
  const g = w.gain;
  const list = (xs) => (xs && xs.length ? `<ul class="items">${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="muted small">None.</p>`);
  const red = w.redundancy || {};
  const planCol = (p, title) => `<div class="card"><h3>${title}</h3>${p.teams.map((t) => `<div class="spread" style="margin:6px 0">${lineup(t.lineup)}
      <span><b>${Math.round(t.ceiling.expected)}</b></span></div>`).join("")}
      <p class="muted small">Plan value ${p.value} (sum of what each team adds above a replacement team).</p></div>`;
  body.innerHTML = `
    <div class="card">
      <div class="spread"><h3>${chip(w.character)} pull value</h3>${w.group ? badge(w.group, w.group === "Clear recommendation" ? "good" : "info") : ""}</div>
      <div class="power">
        <div><div class="k">Account gain</div><div class="v">${signed(g.expected)}<small> ± ${g.sd}</small></div></div>
        <div><div class="k">Gain is real</div><div class="v">${Math.round(w.probability_positive * 100)}%</div></div>
        <div><div class="k">Best team</div><div class="v">${signed(w.best_team_gain, 0)}</div></div>
        <div><div class="k">Second team</div><div class="v">${signed(w.second_team_gain, 0)}</div></div>
      </div>
      <div class="row">${badge(w.kind, "plain")}${w.provisional ? badge("Provisional", "warn") : ""}${w.coverage !== "complete" ? badge(`Mechanics coverage ${w.coverage}`, "warn") : ""}</div>
      <p class="small">${esc((w.explanation || []).join(" "))}</p>
      ${w.weapon_note ? `<p class="muted small">${esc(w.weapon_note)}</p>` : ""}
    </div>
    <div class="card" style="margin-top:12px"><h3>Where the gain comes from</h3>
      <ul class="items">${(w.plan_changes || []).map((c) => `<li class="${c.changed ? "" : "muted"}">${esc(c.text)}</li>`).join("")}</ul></div>
    ${w.experimental_lineup ? `<div class="card" style="margin-top:12px"><h3>Higher modeled experimental lineup</h3>${lineup(w.experimental_lineup.team.lineup)}
      <p class="muted small">${esc(w.experimental_lineup.note)} Raw-model account gain ${signed(w.experimental_lineup.raw_gain.expected)} ± ${w.experimental_lineup.raw_gain.sd}.</p>
      ${evidenceBadges(w.experimental_lineup.team)}</div>` : ""}
    ${w.best_team ? `<div class="card" style="margin-top:12px"><h3>Best new team (recommendable)</h3>${lineup(w.best_team.lineup)}
      <p class="muted small">${esc(w.best_team.identity.label || "")} · ceiling ${Math.round(w.best_team.ceiling.expected)} ± ${Math.round(w.best_team.ceiling.sd)}</p>
      ${evidenceBadges(w.best_team)}</div>` : ""}
    <h2>Before and after</h2>
    <div class="cols">${planCol(w.plan_before, "Your plan now")}${planCol(w.plan_after, `With ${esc(w.character)}`)}</div>
    <div class="grid two" style="margin-top:12px">
      <div class="card"><h3>Pros</h3>${list(w.pros)}</div>
      <div class="card"><h3>Cons</h3>${list(w.cons)}</div>
      <div class="card"><h3>What improves</h3>${list((w.improved || []).map((x) => `${x}'s team gets stronger`).concat((w.new_mechanics || []).map((m) => `New mechanic: ${m}`)))}
        <p class="small">${w.new_viable_teams || 0} lineups with ${esc(w.character)} clear the replacement level on your account.</p></div>
      <div class="card"><h3>What gets displaced</h3>${list(w.displaced)}
        <h3>Support contention</h3>${list(w.support_contention)}</div>
      <div class="card"><h3>Functional redundancy</h3>
        <table>${Object.entries(red).map(([k, v]) => `<tr><td>${esc(k.replace(/_/g, " "))}</td><td>${Math.round(v * 100)}%</td></tr>`).join("")}</table>
        <p class="muted small">Overlap with what your account already fields. It explains the gain; it never discounts it.</p></div>
    </div>`;
}
