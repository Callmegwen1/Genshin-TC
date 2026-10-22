// Hash router. Each page module exports render(main, params).
import { get, sleep } from "./api.js";
import { loadElements, setStatus } from "./ui.js";

const pages = {
  dashboard: () => import("./pages/dashboard.js"),
  builder: () => import("./pages/builder.js"),
  teams: () => import("./pages/teams.js"),
  pulls: () => import("./pages/pulls.js"),
  whatif: () => import("./pages/whatif.js"),
  characters: () => import("./pages/characters.js"),
  character: () => import("./pages/character.js"),
};

function parse() {
  const [path, query] = (location.hash.slice(1) || "/").split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  return { page: parts[0] || "dashboard", arg: parts[1], query: new URLSearchParams(query || "") };
}

async function waitForLoad(main) {
  for (;;) {
    const s = await get("/api/status");
    if (s.loaded) return s;
    main.innerHTML = `<div class="loading">Analysing your account (${s.stage})…</div>`;
    await sleep(1000);
  }
}

async function statusLoop() {
  for (;;) {
    try {
      const s = await get("/api/status");
      setStatus(s.background_done ? `Ready · loaded in ${s.timings.load}s` :
        `Pull values ${s.pulls_done}/${s.pulls_total}…`);
      if (s.background_done) return;
    } catch { /* server restarting */ }
    await sleep(2000);
  }
}

async function route() {
  const main = document.getElementById("app");
  const { page, arg, query } = parse();
  document.querySelectorAll("nav a[data-nav]").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === page || (page === "character" && a.dataset.nav === "characters")));
  const load = pages[page] || pages.dashboard;
  main.innerHTML = `<div class="loading">Loading…</div>`;
  try {
    const mod = await load();
    await mod.render(main, { arg, query });
  } catch (e) {
    main.innerHTML = `<div class="card"><h3>Something went wrong</h3><p class="muted">${String(e.message || e)}</p></div>`;
    console.error(e);
  }
}

(async () => {
  const main = document.getElementById("app");
  await waitForLoad(main);
  await loadElements();
  statusLoop();
  window.addEventListener("hashchange", route);
  route();
})();
