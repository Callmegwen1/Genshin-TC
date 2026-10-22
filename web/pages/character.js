// One character: build, problems, best teams (basic for the MVP).
import { get } from "../api.js";
import { badge, esc, teamCard } from "../ui.js";

const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export async function render(main, { arg }) {
  const c = await get(`/api/characters/${encodeURIComponent(arg)}`);
  const teams = (c.best_teams || []).map((t, i) => teamCard(t, { title: `Best team #${i + 1}` })).join("");
  if (!c.owned) {
    main.innerHTML = `<h1><span class="dot ${esc(c.element)}"></span> ${esc(c.name)}</h1>
      <p class="lead">${c.rarity}★ ${esc(c.element)} ${esc(c.weapon_type)} · not owned</p>
      <p><a href="#/whatif/${encodeURIComponent(c.name)}">What happens if I pull ${esc(c.name)}? →</a></p>
      <h2>Best teams on your account if pulled</h2><div class="grid">${teams || `<p class="muted">None evaluated yet.</p>`}</div>`;
    return;
  }
  const inv = c.investment || {};
  const stats = Object.entries(c.stats || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("");
  const arts = (c.artifacts || []).map((a) => `<tr><td>${esc(a.slot)}</td><td>${esc(a.set)}</td><td>+${a.level}</td><td>${esc(a.main)}</td>
     <td class="small">${a.substats.map((s) => `${esc(s.key)} ${s.value}`).join(", ")}</td></tr>`).join("");
  main.innerHTML = `<h1><span class="dot ${esc(c.element)}"></span> ${esc(c.name)}</h1>
    <p class="lead">${c.rarity}★ ${esc(c.element)} · C${c.constellation} · level ${c.level} · talents ${c.talents.normal}/${c.talents.skill}/${c.talents.burst}
      · ${esc(c.weapon.name)} R${c.weapon.refinement} level ${c.weapon.level}</p>
    <div class="grid two">
      <div class="card"><h3>Build</h3>
        <table><tr><th>Part</th><th>Investment</th></tr>${["level", "talents", "weapon", "artifacts", "total"].map((k) =>
          `<tr><td>${k}</td><td>${pct(inv[k])}</td></tr>`).join("")}</table>
        <p class="small">Own damage today: <b>${pct(c.build_factor)}</b> of a community-standard build (calibrated build model).</p>
        ${c.build_problems.length ? `<h3>Build problems</h3><ul class="items">${c.build_problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : badge("Fully built", "good")}
      </div>
      <div class="card"><h3>Current stats</h3>${stats ? `<table>${stats}</table>` : `<p class="muted small">Not imported.</p>`}</div>
    </div>
    ${arts ? `<h2>Artifacts</h2><div class="card"><table><tr><th>Slot</th><th>Set</th><th>Level</th><th>Main</th><th>Substats</th></tr>${arts}</table></div>` : ""}
    <h2>Best teams with ${esc(c.name)}</h2><div class="grid">${teams}</div>`;
}
