// Team Builder: any legal four characters, evaluated by the engine as you pick.
import { characters, post } from "../api.js";
import { badge, chip, esc, evidenceBadges, insights, lineup, mechanicsPanel, powerBlock, signed } from "../ui.js";

let team = [];

export async function render(main, { query }) {
  const all = await characters();
  team = (query.get("team") || "").split(",").filter(Boolean).slice(0, 4);
  main.innerHTML = `
    <h1>Team Builder</h1>
    <p class="lead">Pick any four characters. Unowned characters are valued fully built at C0.</p>
    <div class="slots" id="slots"></div>
    <div class="card" style="margin-top:12px">
      <div class="row">
        <input id="q" placeholder="Search characters" style="flex:1;min-width:180px">
        <select id="own"><option value="owned">Owned</option><option value="all">All characters</option></select>
        <button id="clear">Clear</button>
      </div>
      <div class="picker" id="picker"></div>
    </div>
    <div id="result"></div>`;
  const q = main.querySelector("#q"), own = main.querySelector("#own");
  const drawPicker = () => {
    const term = q.value.toLowerCase();
    main.querySelector("#picker").innerHTML = all
      .filter((c) => (own.value === "all" || c.owned) && c.name.toLowerCase().includes(term) && !team.includes(c.name))
      .map((c) => `<span class="chip ${c.owned ? "" : "unowned"}" data-pick="${esc(c.name)}"><span class="dot ${esc(c.element)}"></span>${esc(c.name)}${c.owned ? "" : " · not owned"}${c.provisional ? " · provisional" : ""}</span>`)
      .join("");
  };
  const drawSlots = () => {
    main.querySelector("#slots").innerHTML = [0, 1, 2, 3].map((i) => team[i]
      ? `<div class="slot filled">${chip(team[i])}<button data-remove="${i}" class="small">Remove</button></div>`
      : `<div class="slot"><span class="muted small">Slot ${i + 1}: pick below</span></div>`).join("");
  };
  const update = async () => {
    history.replaceState(null, "", `#/builder?team=${encodeURIComponent(team.join(","))}`);
    drawSlots(); drawPicker();
    const res = main.querySelector("#result");
    if (team.length < 4) { res.innerHTML = ""; return; }
    res.innerHTML = `<div class="loading">Evaluating…</div>`;
    res.innerHTML = view(await post("/api/team", { lineup: team }));
  };
  main.addEventListener("click", (ev) => {
    const p = ev.target.closest("[data-pick]"), r = ev.target.closest("[data-remove]"), s = ev.target.closest("[data-sub]");
    if (p && team.length < 4) { team.push(p.dataset.pick); update(); }
    if (r) { team.splice(Number(r.dataset.remove), 1); update(); }
    if (s) { team = s.dataset.sub.split(","); update(); }
  });
  main.querySelector("#clear").onclick = () => { team = []; update(); };
  q.oninput = drawPicker; own.onchange = drawPicker;
  update();
}

function view(r) {
  if (!r.legal) return `<div class="card"><h3>Not a legal team</h3><ul class="items">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
  const t = r.team;
  if (!t) return `<div class="card"><p class="muted">This team cannot be evaluated.</p></div>`;
  const mech = Object.entries(t.identity.mechanics || {}).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `<span class="chip">${esc(k.replace(/_/g, " "))} ${v.toFixed(2)}</span>`).join("");
  const shares = Object.entries(t.damage_shares || {}).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `<div class="spread small"><span>${esc(k)}</span><span>${Math.round(v * 100)}%</span></div><div class="bar"><span style="width:${v * 100}%"></span></div>`).join("");
  const S = r.substitutions || { direct: [], rebuild: [], experimental_hidden: 0 };
  const rebuild = S.rebuild.map((s) => `<tr><td>${chip(s.out)} → ${chip(s.in)}</td><td>${esc(s.label || "")}</td>
      <td>${s.comparison === "roughly_equal" ? `<span class="tie">roughly equal</span> (${signed(s.expected_change)})` : signed(s.expected_change)}</td>
      <td class="small muted">${esc((s.changes || []).join("; "))}</td><td><a href="#" data-sub="${esc(s.lineup.join(","))}" class="small">Try</a></td></tr>`).join("");
  const subs = S.direct.map((s) => `<tr>
      <td>${badge(s.kind, s.kind === "upgrade" ? "good" : s.kind === "alternative" ? "info" : "plain")}</td>
      <td>${chip(s.out)} → ${chip(s.in)}${s.provisional ? " " + badge("Provisional", "warn") : ""}</td>
      <td>${s.comparison === "roughly_equal" ? `<span class="tie">roughly equal</span> (${signed(s.expected_change)})` : signed(s.expected_change)}</td>
      <td class="small">${Math.round(s.probability_better * 100)}% that it is better${s.frees_for ? `<br>frees ${esc(s.out)} for ${esc(s.frees_for)}` : ""}</td>
      <td><a href="#" data-sub="${esc(s.lineup.join(","))}" class="small">Try</a></td></tr>`).join("");
  return `
    <div class="card" style="margin-top:12px">
      <div class="spread"><div>${lineup(t.lineup)}</div>${evidenceBadges(t)}</div>
      ${r.not_owned && r.not_owned.length ? `<p class="callout small">Not owned: ${esc(r.not_owned.join(", "))} (valued fully built at C0). Substitutions need an all-owned team.</p>` : ""}
      ${powerBlock(t)}
      <p class="muted small">Ceiling: your characters properly built at your constellations. Current: your builds today.
        Meta: community-standard builds. ${t.context.aoe ? `Against groups: ${Math.round(t.context.aoe.expected)} (AoE ${t.context.aoe_ratio}x).` : ""}</p>
    </div>
    <div class="grid two" style="margin-top:12px">
      <div class="card">
        <h3>How the team works</h3>
        <p><b>${esc(t.identity.label || "")}</b></p>
        <p class="small">Primary actor: <b>${esc(t.identity.primary_actor || "no single carry")}</b>
          · structure ${esc((t.identity.structure || "").replace(/_/g, " "))} (${esc(t.identity.source || "")})
          · sustain ${t.sustain >= 80 ? "dedicated healer or shield" : t.sustain > 0 ? "some" : "none"}</p>
        <div class="row" style="margin:6px 0">${mech}</div>
        ${shares ? `<h3>Damage share</h3>${shares}` : ""}
      </div>
      <div class="card">${insights(t)}</div>
    </div>
    ${mechanicsPanel(t)}
    ${r.substitutions ? `<div class="card" style="margin-top:12px"><h3>Substitutions from your roster</h3>
      <p class="muted small">Swaps that keep what this team depends on, read from the kits (its carry, the elements its reactions need, any
        function only the swapped character supplied such as swirl support or sustain, no new conflict, kit conditions).</p>
      ${subs ? `<table><tr><th>Kind</th><th>Swap</th><th>Change</th><th>Confidence</th><th></th></tr>${subs}</table>`
             : `<p class="muted small">No owned substitution is better or roughly equal.</p>`}
      <p class="muted small">Roughly equal means the evidence cannot separate the two teams.</p>
      ${rebuild ? `<h3>Alternative team styles</h3><p class="muted small">These change how the team works, but each is a credible team in its own right.</p>
        <table><tr><th>Swap</th><th>Becomes</th><th>Change</th><th>What changes</th><th></th></tr>${rebuild}</table>` : ""}
      ${S.experimental_hidden ? `<p class="muted small">${S.experimental_hidden} other swaps score in the model but break what the team depends on or are not recommendable, so they are not offered.</p>` : ""}
      </div>` : ""}`;
}
