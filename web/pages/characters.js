// Characters: owned and unowned, filterable.
import { characters } from "../api.js";
import { badge, esc } from "../ui.js";

export async function render(main) {
  const all = await characters();
  const elements = [...new Set(all.map((c) => c.element))].sort();
  main.innerHTML = `<h1>Characters</h1>
    <div class="row" style="margin-bottom:12px">
      <select id="own"><option value="owned">Owned</option><option value="unowned">Not owned</option><option value="all">All</option></select>
      <select id="el"><option value="">All elements</option>${elements.map((e) => `<option>${esc(e)}</option>`).join("")}</select>
      <input id="q" placeholder="Search">
    </div><div class="card"><table id="t"></table></div>`;
  const draw = () => {
    const own = main.querySelector("#own").value, el = main.querySelector("#el").value, q = main.querySelector("#q").value.toLowerCase();
    const rows = all.filter((c) => (own === "all" || (own === "owned") === c.owned) && (!el || c.element === el) && c.name.toLowerCase().includes(q));
    main.querySelector("#t").innerHTML = `<tr><th>Character</th><th>Element</th><th>Rarity</th><th>Constellation</th><th>Level</th><th>Investment</th><th></th></tr>` +
      rows.map((c) => `<tr><td><a href="#/character/${encodeURIComponent(c.name)}"><span class="dot ${esc(c.element)}"></span> ${esc(c.name)}</a>
        ${c.provisional ? badge("Provisional", "warn") : ""}</td><td>${esc(c.element)}</td><td>${c.rarity}★</td>
        <td>${c.owned ? "C" + c.constellation : "—"}</td><td>${c.level ?? "—"}</td>
        <td>${c.investment != null ? `<div class="bar" style="width:90px"><span style="width:${c.investment * 100}%"></span></div>` : "—"}</td>
        <td>${c.in_plan ? badge("In plan", "info") : ""}</td></tr>`).join("");
  };
  main.querySelectorAll("select,input").forEach((x) => (x.oninput = draw));
  draw();
}
