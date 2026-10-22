// Dashboard: what should I care about right now?
import { get } from "../api.js";
import { badge, esc, lineup, teamCard } from "../ui.js";

export async function render(main) {
  const d = await get("/api/dashboard");
  const plan = d.plan;
  const meta = d.against_meta;
  const b = d.build_improvement;
  const warn = d.warnings.map((w) => `<li>${lineup(w.team)} ${badge(w.status === "provisional" ? "Provisional" : "Unusual", "warn")}
      <span class="muted small">${esc((w.reasons || []).join("; "))}</span></li>`).join("");
  main.innerHTML = `
    <h1>Your account</h1>
    <p class="lead">${d.account.owned} characters · data ${esc(d.account.data_level)} · snapshot ${esc(d.account.taken_at)}</p>
    <div class="grid two">
      <div class="card">
        <h3>Account plan</h3>
        <p class="muted small">Four teams with no character used twice, valued at their ceiling on your account
          (your characters properly built at your constellations).</p>
        ${plan.teams.map((t, i) => `<div class="spread" style="margin:6px 0">${lineup(t.lineup)}
          <span><b>${Math.round(t.ceiling.expected)}</b> <span class="muted small">± ${Math.round(t.ceiling.sd)}</span></span></div>`).join("")}
        ${meta ? `<p class="small">At full build this plan reaches <b>${Math.round(meta.ratio * 100)}%</b> of the strongest four-team plan in the game.</p>`
               : `<p class="muted small">Comparison with the strongest plan in the game is still computing…</p>`}
        <a href="#/teams">See recommended teams →</a>
      </div>
      ${teamCard(d.strongest_current_team, { title: "Strongest team today (current builds)" })}
      <div class="card">
        <h3>Spiral Abyss pair</h3>
        ${d.abyss ? d.abyss.teams.map((t, i) => `<div style="margin:6px 0"><span class="muted small">${i ? "Second half" : "First half"}</span><br>${lineup(t)}</div>`).join("") : ""}
        ${d.abyss && d.abyss.note ? `<p class="callout warn small">${esc(d.abyss.note)}</p>` : ""}
      </div>
      <div class="card">
        <h3>Highest-impact build improvement</h3>
        ${b ? `<p>Raise <b>${esc(b.member)}</b> (investment ${Math.round((b.member_investment ?? 0) * 100)}%).</p>
          <p class="small">${lineup(b.team)}</p>
          <p class="small">This team reaches <b>${b.current}</b> with your builds today against <b>${b.ceiling}</b> properly built.</p>
          <a href="#/character/${encodeURIComponent(b.member)}">${esc(b.member)}'s build →</a>` : `<p class="muted">Nothing stands out.</p>`}
      </div>
      <div class="card">
        <h3>Best pulls</h3>
        ${d.pulls ? `<p>${badge(d.pulls.group, d.pulls.group === "Clear recommendation" ? "good" : "info")}</p>
          <p>${lineup(d.pulls.characters)}</p>
          ${d.pulls.group !== "Clear recommendation" ? `<p class="muted small">The evidence cannot separate these, so their order is not a ranking.</p>` : ""}`
          : `<p class="muted">Pull values are still computing…</p>`}
        <a href="#/pulls">See all pulls →</a>
      </div>
      <div class="card">
        <h3>Evidence warnings</h3>
        ${warn ? `<ul class="items">${warn}</ul>` : `<p class="muted small">Your plan rests on solid evidence.</p>`}
      </div>
    </div>`;
}
