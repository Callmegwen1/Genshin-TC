// Thin client for the local JSON API (gtc/app/server.py). The page never computes anything the engine owns.
export async function get(path) {
  for (;;) {
    const r = await fetch(path);
    if (r.status === 503) { await sleep(1000); continue; } // still loading the account
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    return r.json();
  }
}

export async function post(path, body) {
  for (;;) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.status === 503) { await sleep(1000); continue; }
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    return r.json();
  }
}

export const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

let catalog = null;
export async function characters() {
  if (!catalog) catalog = await get("/api/characters");
  return catalog;
}
export async function elementOf(name) {
  const c = (await characters()).find((x) => x.name === name);
  return c ? c.element : "";
}
