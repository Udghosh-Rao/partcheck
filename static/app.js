// PartCheck front-end. Plain JS, no external libraries (works fully offline).
const $ = (s) => document.querySelector(s);
const SVGNS = "http://www.w3.org/2000/svg";
const state = { project: null, parts: [], step: 1, files: [], hl: -1, results: new Map() };

// ------------------------------------------------------------------ helpers
async function api(url, opts = {}) {
  const r = await fetch(url, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg, ms = 2500) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}
function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  parent && parent.appendChild(n);
  return n;
}
function setupDrop(label, input, onFiles) {
  input.onchange = () => { onFiles([...input.files]); input.value = ""; };
  label.ondragover = (e) => { e.preventDefault(); label.classList.add("over"); };
  label.ondragleave = () => label.classList.remove("over");
  label.ondrop = (e) => {
    e.preventDefault(); label.classList.remove("over");
    const files = [...e.dataTransfer.files].filter((f) => f.type.startsWith("image/"));
    files.length ? onFiles(files) : toast("Please drop image files");
  };
}

// ------------------------------------------------------------------ steps
function goto(step) {
  if (step >= 2 && !state.project?.has_reference) return toast("Upload a reference photo first");
  if (step === 3 && !state.parts.length) return toast("Mark and name at least one part first");
  state.step = step;
  [1, 2, 3].forEach((i) => $("#step" + i).classList.toggle("hidden", i !== step));
  renderSteps();
  if (step === 2) renderParts();
}
function renderSteps() {
  document.querySelectorAll("#steps button").forEach((b) => {
    const s = +b.dataset.step;
    b.classList.toggle("active", s === state.step);
    b.classList.toggle("done", (s === 1 && state.project?.has_reference) || (s === 2 && state.parts.length > 0));
  });
}
document.querySelectorAll("[data-step]").forEach((b) => (b.onclick = () => goto(+b.dataset.step)));
document.querySelectorAll("[data-goto]").forEach((b) => (b.onclick = () => goto(+b.dataset.goto)));

// ------------------------------------------------------------------ step 1: reference
async function loadProject() {
  state.project = await api("/api/project");
  state.parts = state.project.parts;
  $("#thr").value = state.project.threshold;
  $("#thrVal").textContent = (+state.project.threshold).toFixed(2);
  const has = state.project.has_reference;
  $("#refDrop").classList.toggle("hidden", has); $("#how").classList.toggle("hidden", has);
  $("#refPreview").classList.toggle("hidden", !has);
  if (has) { $("#refThumb").src = state.project.reference_url; $("#refImg").src = state.project.reference_url; }
  renderSteps();
}
setupDrop($("#refDrop"), $("#refInput"), async (files) => {
  if (state.parts.length && !confirm("A new reference clears the named parts. Continue?")) return;
  const fd = new FormData(); fd.append("file", files[0]);
  try {
    toast("Uploading…");
    await api("/api/reference", { method: "POST", body: fd });
    await loadProject(); $("#results").innerHTML = ""; state.files = [];
    toast("Reference saved ✓"); goto(2);
  } catch (e) { toast("⚠ " + e.message); }
});
$("#replaceRef").onclick = () => $("#refInput").click();

// ------------------------------------------------------------------ step 2: parts editor
const stage = $("#stage"), svg = $("#overlay"), img = $("#refImg");
let drag = null, pending = null;

img.onload = () => svg.setAttribute("viewBox", `0 0 ${img.naturalWidth} ${img.naturalHeight}`);
svg.setAttribute("preserveAspectRatio", "none");

function toImg(e) {
  const r = img.getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
           y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
}
function renderParts() {
  const W = img.naturalWidth || 1, H = img.naturalHeight || 1;
  svg.innerHTML = "";
  const fs = Math.max(14, Math.round(W / 60));
  state.parts.forEach((p, i) => {
    el("rect", { x: p.x * W, y: p.y * H, width: p.w * W, height: p.h * H, class: "box" + (i === state.hl ? " hl" : ""), "data-i": i }, svg);
    const hs = Math.max(10, W / 90);
    el("rect", { x: (p.x + p.w) * W - hs / 2, y: (p.y + p.h) * H - hs / 2, width: hs, height: hs, class: "handle", "data-r": i }, svg);
    const t = el("text", { x: p.x * W + 3, y: p.y * H - 5, class: "lbl", "font-size": fs }, svg);
    t.textContent = p.name;
  });
  const d = drag || pending;
  if (d) el("rect", { x: d.x * W, y: d.y * H, width: d.w * W, height: d.h * H, class: "box draft" }, svg);

  const list = $("#partList"); list.innerHTML = "";
  state.parts.forEach((p, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="pill">${i + 1}</span><input value=""><button class="x" title="Delete">✕</button>`;
    const inp = li.querySelector("input"); inp.value = p.name;
    inp.onchange = () => { if (inp.value.trim()) { p.name = inp.value.trim(); saveParts(); } else inp.value = p.name; };
    li.querySelector(".x").onclick = () => { state.parts.splice(i, 1); saveParts(); };
    li.onmouseenter = () => { state.hl = i; renderParts.svgOnly(); };
    li.onmouseleave = () => { state.hl = -1; renderParts.svgOnly(); };
    list.appendChild(li);
  });
  $("#partCount").textContent = state.parts.length;
  $("#emptyHint").classList.toggle("hidden", state.parts.length > 0);
}
// re-render only the svg (keeps focus in list inputs)
renderParts.svgOnly = () => {
  svg.querySelectorAll("rect.box:not(.draft)").forEach((r, i) => r.setAttribute("class", "box" + (i === state.hl ? " hl" : "")));
};

stage.onmousedown = (e) => {
  if (e.button !== 0 || e.target.closest(".name-pop")) return;
  if (pending) cancelName();
  const p = toImg(e);
  const ri = e.target.getAttribute("data-r"), mi = e.target.getAttribute("data-i");
  if (ri !== null) { edit = { mode: "resize", i: +ri }; return; }
  if (mi !== null) { const q = state.parts[+mi]; edit = { mode: "move", i: +mi, dx: p.x - q.x, dy: p.y - q.y, moved: false }; return; }
  drag = { sx: p.x, sy: p.y, x: p.x, y: p.y, w: 0, h: 0 };
};
let edit = null;
window.addEventListener("mousemove", (e) => {
  if (!edit) return;
  const p = toImg(e), q = state.parts[edit.i];
  if (edit.mode === "move") {
    q.x = Math.min(1 - q.w, Math.max(0, p.x - edit.dx)); q.y = Math.min(1 - q.h, Math.max(0, p.y - edit.dy)); edit.moved = true;
  } else { q.w = Math.max(0.005, p.x - q.x); q.h = Math.max(0.005, p.y - q.y); edit.moved = true; }
  renderParts();
});
window.addEventListener("mouseup", () => { if (edit) { if (edit.moved) saveParts(); edit = null; } });
window.addEventListener("mousemove", (e) => {
  if (!drag) return;
  const p = toImg(e);
  Object.assign(drag, { x: Math.min(p.x, drag.sx), y: Math.min(p.y, drag.sy), w: Math.abs(p.x - drag.sx), h: Math.abs(p.y - drag.sy) });
  renderParts();
});
window.addEventListener("mouseup", (e) => {
  if (!drag) return;
  const d = drag; drag = null;
  const r = img.getBoundingClientRect();
  if (d.w * r.width < 6 || d.h * r.height < 6) return renderParts();
  pending = d; renderParts(); askName(d);
});
function nextName() {
  let i = state.parts.length + 1;
  while (state.parts.some((p) => p.name === "Part " + i)) i++;
  return "Part " + i;
}
function askName(d) {
  const pop = $("#namePop"), r = img.getBoundingClientRect();
  pop.classList.remove("hidden");
  const left = Math.min(d.x * r.width, r.width - 300), top = (d.y + d.h) * r.height + 8;
  pop.style.left = Math.max(4, left) + "px";
  pop.style.top = (top + 60 > r.height ? d.y * r.height - 56 : top) + "px";
  const inp = $("#nameInput"); inp.value = ""; inp.placeholder = nextName(); inp.focus();
}
function confirmName() {
  if (!pending) return;
  let name = $("#nameInput").value.trim() || $("#nameInput").placeholder;
  if (state.parts.some((p) => p.name.toLowerCase() === name.toLowerCase())) return toast(`"${name}" already exists — pick another name`);
  state.parts.push({ name, x: pending.x, y: pending.y, w: pending.w, h: pending.h });
  pending = null; $("#namePop").classList.add("hidden"); saveParts();
}
function cancelName() { pending = null; $("#namePop").classList.add("hidden"); renderParts(); }
$("#nameOk").onclick = confirmName;
$("#nameCancel").onclick = cancelName;
$("#nameInput").onkeydown = (e) => { if (e.key === "Enter") confirmName(); if (e.key === "Escape") cancelName(); };
$("#clearParts").onclick = () => { if (state.parts.length && confirm("Remove all parts?")) { state.parts = []; saveParts(); } };
window.addEventListener("keydown", (e) => {
  if (state.step === 2 && (e.metaKey || e.ctrlKey) && e.key === "z" && !pending && document.activeElement.tagName !== "INPUT") {
    e.preventDefault(); if (state.parts.pop()) { saveParts(); toast("Undone"); }
  }
});
async function saveParts() {
  renderParts(); renderSteps();
  try { state.parts = (await api("/api/parts", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.parts) })).parts; }
  catch (e) { toast("⚠ Could not save: " + e.message); }
}

// ------------------------------------------------------------------ step 3: inspect
setupDrop($("#testDrop"), $("#testInput"), (files) => runInspect(files, true));
$("#thr").oninput = () => ($("#thrVal").textContent = (+$("#thr").value).toFixed(2));
$("#thr").onchange = () => api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ threshold: +$("#thr").value }) })
  .then(() => toast("Sensitivity saved — press Re-run to apply"));
$("#rerun").onclick = () => state.files.length && runInspect(state.files, false);
$("#clearRes").onclick = () => { state.files = []; state.results.clear(); renderSummary(); $("#results").innerHTML = ""; $("#resToolbar").classList.add("hidden"); };
$("#showAll").onchange = () => document.querySelectorAll(".pres,.lbl.okl").forEach((n) => n.classList.toggle("hidden", !$("#showAll").checked));

async function runInspect(files, append) {
  if (!append) { $("#results").innerHTML = ""; state.results.clear(); }
  else state.files.push(...files);
  if (!append) files = state.files;
  $("#resToolbar").classList.remove("hidden");
  // one request per photo so each card appears as soon as it's ready
  await Promise.all(files.map(async (f) => {
    const card = document.createElement("div");
    card.className = "card loading"; card.innerHTML = `<div><div class="spinner"></div><p>Checking ${f.name}…</p></div>`;
    $("#results").prepend(card);
    const fd = new FormData(); fd.append("files", f);
    try {
      const { results } = await api("/api/inspect", { method: "POST", body: fd });
      renderResult(card, results[0], f); state.results.set(f, results[0]); renderSummary();
    } catch (e) { card.className = "card bad"; card.innerHTML = `<div class="err">⚠ ${f.name}: ${e.message}</div>`; }
  }));
}

function renderResult(card, r, file) {
  if (r.error) { card.className = "card bad"; card.innerHTML = `<div class="err">⚠ ${r.filename}: ${r.error}</div>`; return; }
  card.className = "card " + (r.ok ? "ok" : "bad");
  const url = URL.createObjectURL(file);
  const n = r.missing.length;
  card.innerHTML = `
    <div class="verdict">
      <div class="big">${r.ok ? "✔ OK" : "✖ MISSING"}</div>
      <div>${r.ok ? `<div class="sub">All ${r.parts.length} parts present</div>`
        : `<div class="names"></div><div class="sub">${n} of ${r.parts.length} parts missing</div>`}</div>
    </div>
    <div class="view"><img src="${url}"><svg viewBox="0 0 ${r.size[0]} ${r.size[1]}" preserveAspectRatio="none"></svg></div>
    <div class="meta"><span class="fn"></span><span>${r.ms} ms · aligned by ${r.alignment.method}${r.alignment.inliers ? ` (${r.alignment.inliers} matches)` : ""}</span></div>
    <div class="scores"></div>`;
  card.querySelector(".fn").textContent = r.filename;
  if (!r.ok) card.querySelector(".names").textContent = r.missing.join(", ");
  const s = card.querySelector("svg"), fs = Math.max(16, Math.round(r.size[0] / 45));
  const showAll = $("#showAll").checked;
  r.parts.forEach((p) => {
    const pts = p.polygon.map((q) => q.join(",")).join(" ");
    const poly = el("polygon", { points: pts, class: p.present ? "pres" : "miss" }, s);
    if (p.present && !showAll) poly.classList.add("hidden");
    const t = el("text", { x: p.polygon[0][0] + 2, y: p.polygon[0][1] - 6, class: "lbl " + (p.present ? "okl" : "bad"), "font-size": fs }, s);
    t.textContent = p.present ? p.name : "✖ " + p.name;
    if (p.present && !showAll) t.classList.add("hidden");
    const c = document.createElement("span");
    c.className = "chip " + (p.present ? "ok" : "bad");
    c.title = "Similarity to reference (0–1)";
    c.textContent = `${p.present ? "✓" : "✖"} ${p.name} · ${p.score.toFixed(2)}`;
    c.onclick = () => { poly.classList.remove("hidden"); t.classList.remove("hidden"); poly.classList.add("focus");
      setTimeout(() => poly.classList.remove("focus"), 1500); };
    card.querySelector(".scores").appendChild(c);
  });
  card.querySelector(".view").onclick = (e) => {
    const lb = $("#lightbox"), inner = lb.querySelector(".lb-inner");
    inner.innerHTML = ""; const v = e.currentTarget.cloneNode(true); v.style.cursor = "zoom-out"; inner.appendChild(v);
    lb.classList.remove("hidden");
  };
}
$("#lightbox").onclick = () => $("#lightbox").classList.add("hidden");
window.addEventListener("keydown", (e) => e.key === "Escape" && $("#lightbox").classList.add("hidden"));

// ------------------------------------------------------------------ boot
loadProject().then(() => {
  if (state.project.has_reference && state.parts.length) goto(3);
  else if (state.project.has_reference) goto(2);
  else goto(1);
}).catch((e) => toast("⚠ Server not reachable: " + e.message, 6000));

// ------------------------------------------------------------------ summary + export
function renderSummary() {
  const rs = [...state.results.values()].filter((r) => !r.error);
  const ok = rs.filter((r) => r.ok).length, bad = rs.length - ok;
  $("#summary").classList.toggle("hidden", !rs.length);
  $("#sumTotal").textContent = rs.length; $("#sumOk").textContent = ok; $("#sumBad").textContent = bad;
}
$("#exportCsv").onclick = () => {
  const rows = [["photo", "verdict", "missing_parts", ...state.parts.map((p) => p.name + " score")]];
  for (const r of state.results.values()) {
    if (r.error) continue;
    const sc = Object.fromEntries(r.parts.map((p) => [p.name, p.score]));
    rows.push([r.filename, r.ok ? "OK" : "MISSING", r.missing.join("; "), ...state.parts.map((p) => sc[p.name] ?? "")]);
  }
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "partcheck_report.csv"; a.click();
};
