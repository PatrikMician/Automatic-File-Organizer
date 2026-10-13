"use strict";

const $ = (s) => document.querySelector(s);
let state = { path: "", items: [], selected: new Set(), sort: { key: "name", dir: 1 }, filter: "" };
let lastPlanKey = "";

const ICONS = {
  "Složka": "📁", "Obrázky": "🖼️", "Dokumenty": "📄", "Hudba": "🎵", "Videa": "🎬",
  "Archivy": "🗜️", "Kód": "💻", "Programy": "⚙️", "Ostatní": "📦",
};

// ------------------------------------------------------------- pomocné
async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch (_) { /* ne-JSON odpověď */ }
  if (!res.ok) throw new Error((data && data.error) || `Chyba ${res.status}`);
  return data;
}
const post = (url, body) => api(url, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

function fmtSize(n) {
  if (n == null) return "—";
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}
function toast(msg, error = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast show" + (error ? " error" : "");
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.className = "toast"), 2800);
}
function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };

// ------------------------------------------------------------- načtení
async function load(path = state.path) {
  const data = await api(`/api/list?path=${encodeURIComponent(path)}`);
  state.path = data.path; state.items = data.items; state.selected.clear();
  renderCrumbs(data.breadcrumbs); renderList(); loadTree(); loadStats();
}

function renderCrumbs(crumbs) {
  const el = $("#breadcrumbs"); el.innerHTML = "";
  crumbs.forEach((c, i) => {
    if (i) el.insertAdjacentHTML("beforeend", '<span class="sep">›</span>');
    const b = document.createElement("button");
    b.textContent = c.name; b.onclick = guard(() => load(c.path));
    el.appendChild(b);
  });
}

function sortedItems() {
  const { key, dir } = state.sort;
  const f = state.filter.toLowerCase();
  return state.items.filter((i) => i.name.toLowerCase().includes(f)).sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
    let x = a[key], y = b[key];
    if (key === "size") { x = x ?? -1; y = y ?? -1; }
    if (key === "modified") { // dd.mm.yyyy hh:mm -> yyyymmddhhmm
      const c = (s) => s.replace(/(\d+)\.(\d+)\.(\d+) (\d+):(\d+)/, "$3$2$1$4$5");
      x = c(x); y = c(y);
    }
    if (typeof x === "string") return x.localeCompare(y, "cs") * dir;
    return (x - y) * dir;
  });
}

function renderList() {
  const body = $("#file-list"); body.innerHTML = "";
  const items = sortedItems();
  $("#empty").hidden = items.length > 0;
  for (const it of items) {
    const tr = document.createElement("tr");
    tr.dataset.path = it.path;
    if (state.selected.has(it.path)) tr.classList.add("selected");
    tr.innerHTML = `
      <td><div class="name-cell"><span class="icon">${ICONS[it.category] || "📦"}</span>${esc(it.name)}</div></td>
      <td>${esc(it.category)}</td>
      <td class="num">${fmtSize(it.size)}</td>
      <td>${esc(it.modified)}</td>`;
    tr.onclick = (e) => {
      if (!(e.ctrlKey || e.metaKey)) state.selected.clear();
      state.selected.has(it.path) ? state.selected.delete(it.path) : state.selected.add(it.path);
      renderList(); updateStatus();
    };
    tr.ondblclick = guard(() => (it.is_dir ? load(it.path) : openFile(it)));
    body.appendChild(tr);
  }
  updateStatus();
}

function updateStatus() {
  const n = state.items.length, s = state.selected.size;
  $("#status").textContent = `${n} položek` + (s ? ` · vybráno ${s}` : "");
}

async function loadTree() {
  const t = await api("/api/tree");
  const el = $("#tree"); el.innerHTML = "";
  const build = (node, parent) => {
    const row = document.createElement("div");
    row.className = "tree-item" + (node.path === state.path ? " active" : "");
    row.textContent = "📁 " + node.name;
    row.onclick = guard(() => load(node.path));
    parent.appendChild(row);
    if (node.children.length) {
      const box = document.createElement("div"); box.className = "tree-children";
      node.children.forEach((c) => build(c, box)); parent.appendChild(box);
    }
  };
  build(t, el);
}

async function loadStats() {
  const s = await api(`/api/stats?path=${encodeURIComponent(state.path)}`);
  const el = $("#stats");
  if (!s.total) { el.innerHTML = '<div class="stat-row muted">Žádné soubory</div>'; return; }
  el.innerHTML = Object.entries(s.counts).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
    `<div class="stat-row"><span>${ICONS[k] || "📦"} ${esc(k)}</span>
     <div class="stat-bar"><i style="width:${(v / s.total) * 100}%"></i></div><span class="n">${v}</span></div>`).join("");
}

// ------------------------------------------------------------- náhled souboru
function openFile(it) {
  const url = `/api/preview?path=${encodeURIComponent(it.path)}`;
  $("#view-title").textContent = it.name;
  const body = $("#view-body"); body.innerHTML = "";
  if (["Obrázky"].includes(it.category) && it.ext !== "heic") body.innerHTML = `<img src="${url}" alt="">`;
  else if (it.category === "Videa") body.innerHTML = `<video src="${url}" controls></video>`;
  else if (it.category === "Hudba") body.innerHTML = `<audio src="${url}" controls></audio>`;
  else if (["txt", "md", "py", "js", "html", "css", "json", "csv", "xml", "sql"].includes(it.ext)) {
    fetch(url).then((r) => r.text()).then((t) => { const p = document.createElement("pre"); p.textContent = t.slice(0, 20000); body.appendChild(p); });
  } else body.innerHTML = `<p>Pro tento typ není náhled. <a href="/api/download?path=${encodeURIComponent(it.path)}">Stáhnout soubor</a></p>`;
  $("#dlg-view").showModal();
}

// ------------------------------------------------------------- akce
const selectedOne = () => {
  if (state.selected.size !== 1) { toast("Vyber právě jednu položku", true); return null; }
  return [...state.selected][0];
};

$("#btn-up").onclick = guard(() => load(state.path.split("/").slice(0, -1).join("/")));
$("#btn-upload").onclick = () => $("#file-input").click();
$("#file-input").onchange = guard(async (e) => { await upload(e.target.files); e.target.value = ""; });

$("#btn-mkdir").onclick = guard(async () => {
  const name = prompt("Název nové složky:");
  if (!name) return;
  await post("/api/mkdir", { path: state.path, name });
  await load();
});
$("#btn-rename").onclick = guard(async () => {
  const p = selectedOne(); if (!p) return;
  const old = p.split("/").pop();
  const name = prompt("Nový název:", old);
  if (!name || name === old) return;
  await post("/api/rename", { path: p, name });
  await load();
});
$("#btn-delete").onclick = guard(async () => {
  if (!state.selected.size) return toast("Nic není vybráno", true);
  if (!confirm(`Opravdu smazat ${state.selected.size} položek? Tuto akci nelze vrátit.`)) return;
  await post("/api/delete", { paths: [...state.selected] });
  toast("Smazáno"); await load();
});
$("#btn-undo").onclick = guard(async () => {
  if (!confirm("Vrátit poslední automatické uspořádání?")) return;
  const r = await post("/api/organize/undo", {});
  toast(`Vráceno ${r.restored} souborů`); await load();
});

document.querySelectorAll("th[data-sort]").forEach((th) => {
  th.onclick = () => {
    const k = th.dataset.sort;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : 1 };
    renderList();
  };
});
$("#search").oninput = (e) => { state.filter = e.target.value; renderList(); };

// ------------------------------------------------------------- nahrávání (drag & drop)
async function upload(files) {
  if (!files.length) return;
  const fd = new FormData(); fd.append("path", state.path);
  [...files].forEach((f) => fd.append("files", f));
  const r = await api("/api/upload", { method: "POST", body: fd });
  toast(`Nahráno souborů: ${r.saved}`); await load();
}
const dz = $("#dropzone");
["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragging"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragging"); }));
dz.addEventListener("drop", guard((e) => upload(e.dataTransfer.files)));

// ------------------------------------------------------------- organizér
const orgOptions = () => ({
  path: state.path,
  mode: document.querySelector("input[name=mode]:checked").value,
  recursive: $("#opt-recursive").checked,
  cleanup: $("#opt-cleanup").checked,
  size_limit_mb: parseFloat($("#size-limit").value) || 10,
});
const optKey = () => JSON.stringify(orgOptions());

$("#btn-organize").onclick = () => {
  $("#preview-box").hidden = true; $("#btn-run").disabled = true;
  $("#dlg-organize").showModal();
};
$("#dlg-organize").addEventListener("change", () => { $("#btn-run").disabled = optKey() !== lastPlanKey; });

$("#btn-preview").onclick = guard(async () => {
  const o = orgOptions();
  const r = await post("/api/organize/preview", o);
  lastPlanKey = optKey();
  $("#preview-box").hidden = false;
  $("#preview-summary").innerHTML = r.count
    ? Object.entries(r.summary).map(([k, v]) => `<span class="chip">${esc(k)}: ${v}</span>`).join("")
    : '<span class="muted">Není co přesouvat – vše je už uspořádané.</span>';
  $("#preview-list").innerHTML = r.plan.slice(0, 200).map((m) =>
    `<div><span>${esc(m.name)}</span><span>→ ${esc(m.folder)}/</span></div>`).join("");
  $("#btn-run").disabled = r.count === 0;
});

$("#btn-run").onclick = guard(async () => {
  const r = await post("/api/organize/run", orgOptions());
  $("#dlg-organize").close();
  toast(`Přesunuto souborů: ${r.moved}. Lze vrátit tlačítkem Zpět.`);
  await load();
});

load().catch((e) => toast(e.message, true));
