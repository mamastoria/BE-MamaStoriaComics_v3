/* static/app.js — FIXED v2:
   ✅ Preview 2 halaman tampil di layar (pakai #previewWrap, #imgPart1, #imgPart2 di index.html)
   ✅ Tidak bergantung Range probe untuk set gambar (lebih kompatibel)
   ✅ Tombol download Part 1 & Part 2 (save ke lokal)
   ✅ Timer & overlay behavior tetap seperti versi kamu
*/

(() => {
  "use strict";

  // -------------------------
  // Helpers
  // -------------------------
  const $ = (sel, root = document) => root.querySelector(sel);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const nextFrame = () => new Promise((r) => requestAnimationFrame(() => r()));
  const forceRepaint = async () => { document.body.offsetHeight; await nextFrame(); await nextFrame(); };

  function safeJsonParse(text) { try { return JSON.parse(text); } catch { return null; } }
  function prettyJson(obj) { return JSON.stringify(obj, null, 2); }
  function setText(el, text) { if (el) el.textContent = text ?? ""; }
  function show(el, yes) { if (el) el.style.display = yes ? "" : "none"; }

  function uniq(list) { return Array.from(new Set(list || [])); }
  function clampMaxFive(list) { return (list || []).slice(0, 5); }

  // ---- filename helpers (title -> slug) ----
  function slugifyTitle(s) {
    const t = String(s || "").trim().toLowerCase();
    return t
      .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");
  }

  function getComicTitleFromScript(scriptObj) {
    return (
      scriptObj?.title ||
      scriptObj?.comic_title ||
      scriptObj?.meta?.title ||
      scriptObj?.metadata?.title ||
      scriptObj?.story_title ||
      scriptObj?.judul ||
      scriptObj?.nama ||
      ""
    );
  }

  function buildBaseFilename(scriptObj) {
    const rawTitle = getComicTitleFromScript(scriptObj);
    const slug = slugifyTitle(rawTitle);
    return slug ? `Mamastoria_${slug}` : `Mamastoria_komik`;
  }

  async function downloadBlobWithName(url, filename) {
    const r = await fetch(url, { method: "GET" });
    if (!r.ok) {
      const txt = await r.text().catch(() => "");
      throw new Error(`Download gagal ${r.status}: ${txt.slice(0, 200)}`);
    }
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  async function downloadFileWithName(url, filename) {
    // alias saja (biar konsisten dengan versi kamu)
    return downloadBlobWithName(url, filename);
  }

  // -------------------------
  // DOM
  // -------------------------
  const el = {
    healthDot: $("#healthDot"),
    healthText: $("#healthText"),
    styleChip: $("#styleChip"),
    nuChip: $("#nuChip"),

    story: $("#story"),
    style: $("#style"),
    styleNotes: $("#styleNotes"),

    nuWrap: $("#nuWrap"),
    nuGrid: $("#nuGrid"),
    btnNuDefault: $("#btnNuDefault"),
    btnNuClear: $("#btnNuClear"),

    btnMakeScript: $("#btnMakeScript"),
    btnFormatJson: $("#btnFormatJson"),
    btnReset: $("#btnReset"),

    btnCopyJson: $("#btnCopyJson"),
    btnDownloadJson: $("#btnDownloadJson"),
    btnRenderAll: $("#btnRenderAll"),

    scriptJson: $("#scriptJson"),

    stepText: $("#stepText"),
    jobText: $("#jobText"),
    pdfText: $("#pdfText"),
    renderChip: $("#renderChip"),

    pdfWrap: $("#pdfWrap"),
    pdfFrame: $("#pdfFrame"),
    pdfHint: $("#pdfHint"),
    btnGetPdf: $("#btnGetPdf"),
    btnOpenPdf: $("#btnOpenPdf"),
    btnReadAlong: $("#btnReadAlong"),

    // ✅ PREVIEW (HTML existing)
    previewWrap: $("#previewWrap"),
    imgPart1: $("#imgPart1"),
    imgPart2: $("#imgPart2"),
    previewChip: $("#previewChip"),
  };

  // -------------------------
  // State
  // -------------------------
  const state = {
    styles: [],
    styleDefault: "",
    nuances: [],
    nuancesDefault: [],
    selectedNuances: [],
    jobId: null,

    // nuances dropdown
    nuBtn: null,
    nuPanel: null,
    nuSearch: null,

    // timers
    timers: {
      runStartMs: null,
      tickHandle: null,
      steps: {
        script:  { startMs: null, endMs: null, status: "idle" },
        render1: { startMs: null, endMs: null, status: "idle" },
        render2: { startMs: null, endMs: null, status: "idle" },
        pdf:     { startMs: null, endMs: null, status: "idle" },
      },
    },

    // render control
    isPolling: false,
    lastJobStatus: null,

    // overlay close control
    userClosedOverlay: false,

    // preview download buttons injected
    previewDlMounted: false,
  };

  // -------------------------
  // Timers
  // -------------------------
  const nowMs = () => performance.now();

  function fmtSec(ms) {
    if (ms == null) return "—";
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const r = s - m * 60;
    return `${m}m ${r.toFixed(0)}s`;
  }

  function getStepDurationMs(stepKey) {
    const st = state.timers.steps[stepKey];
    if (!st || !st.startMs) return null;
    const end = st.endMs ?? nowMs();
    return Math.max(0, end - st.startMs);
  }

  function getTotalDurationMs() {
    if (!state.timers.runStartMs) return null;
    return Math.max(0, nowMs() - state.timers.runStartMs);
  }

  function ensureTickerRunning() {
    if (state.timers.tickHandle) return;
    state.timers.tickHandle = setInterval(() => {
      refreshAllStepBadges();
      refreshOverlayHintTimer();
    }, 200);
  }

  function stopTickerIfIdle() {
    const anyRunning = Object.values(state.timers.steps).some(s => s.status === "running");
    const overlayShown = $("#overlay")?.classList.contains("show");
    if (!anyRunning && !overlayShown && state.timers.tickHandle) {
      clearInterval(state.timers.tickHandle);
      state.timers.tickHandle = null;
    }
  }

  function resetTimers() {
    state.timers.runStartMs = null;
    for (const k of ["script","render1","render2","pdf"]) {
      state.timers.steps[k] = { startMs: null, endMs: null, status: "idle" };
    }
    refreshAllStepBadges();
    refreshOverlayHintTimer();
    stopTickerIfIdle();
  }

  function startRunTimer() {
    state.timers.runStartMs = nowMs();
    ensureTickerRunning();
  }

  function startStepTimer(stepKey) {
    const st = state.timers.steps[stepKey];
    if (!st) return;
    if (!state.timers.runStartMs) startRunTimer();
    if (!st.startMs) st.startMs = nowMs();
    st.endMs = null;
    st.status = "running";
    ensureTickerRunning();
  }

  function finishStepTimer(stepKey, finalStatus /* done|idle */) {
    const st = state.timers.steps[stepKey];
    if (!st) return;
    if (!st.startMs) st.startMs = nowMs();
    st.endMs = nowMs();
    st.status = finalStatus === "done" ? "done" : "idle";
    refreshAllStepBadges();
    refreshOverlayHintTimer();
    stopTickerIfIdle();
  }

  function markStepIdle(stepKey) {
    const st = state.timers.steps[stepKey];
    if (!st) return;
    st.status = "idle";
    refreshAllStepBadges();
    refreshOverlayHintTimer();
    stopTickerIfIdle();
  }

  function refreshOverlayHintTimer() {
    const hintEl = $("#loadingHint");
    if (!hintEl) return;
    const total = getTotalDurationMs();
    if (!total) return;
    const base = hintEl.textContent?.split(" • Total:")[0] ?? hintEl.textContent ?? "";
    hintEl.textContent = `${base} • Total: ${fmtSec(total)}`;
  }

  function refreshStepBadge(stepKey) {
    const stepEl = document.querySelector(`.step[data-step="${stepKey}"]`);
    if (!stepEl) return;
    const tag = stepEl.querySelector(".sTag");
    if (!tag) return;

    const current = (tag.textContent || "").split(" • ")[0].trim();
    const st = state.timers.steps[stepKey];
    const dur = getStepDurationMs(stepKey);

    const shouldShow = (st?.status === "running") || (st?.status === "done") || (dur != null && dur > 0);
    if (!shouldShow) return;

    tag.textContent = `${current} • ${fmtSec(dur)}`;
  }

  function refreshAllStepBadges() {
    ["script","render1","render2","pdf"].forEach(refreshStepBadge);
  }

  // -------------------------
  // Steps UI
  // -------------------------
  function setStep(step, st, label) {
    const stepEl = document.querySelector(`.step[data-step="${step}"]`);
    if (!stepEl) return;

    stepEl.classList.remove("idle", "running", "done");
    stepEl.classList.add(st);

    const tag = stepEl.querySelector(".sTag");
    if (tag) tag.textContent = label || (st === "running" ? "memproses" : st === "done" ? "selesai" : "menunggu");

    if (st === "running") startStepTimer(step);
    else if (st === "done") finishStepTimer(step, "done");
    else if (st === "idle") markStepIdle(step);

    refreshStepBadge(step);
  }

  function resetSteps() {
    ["script","render1","render2","pdf"].forEach(s => setStep(s, "idle", "menunggu"));
  }

  // -------------------------
  // Overlay (NO AUTO CLOSE)
  // -------------------------
  function ensureOverlayCloseButton() {
    const overlay = $("#overlay");
    const card = overlay?.querySelector(".loaderCard");
    if (!overlay || !card) return;

    if (card.querySelector("#btnOverlayClose")) return;

    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.justifyContent = "flex-end";
    row.style.gap = "8px";
    row.style.marginTop = "12px";

    const btn = document.createElement("button");
    btn.id = "btnOverlayClose";
    btn.type = "button";
    btn.className = "secondary mini";
    btn.textContent = "✅ Close";
    btn.style.pointerEvents = "auto";
    btn.onclick = () => {
      state.userClosedOverlay = true;
      overlay.classList.remove("show");
      stopTickerIfIdle();
    };

    row.appendChild(btn);
    card.appendChild(row);
  }

  function setOverlay(showIt, title, desc, hint, { allowClose = true } = {}) {
    const overlay = $("#overlay");
    if (!overlay) return;

    // user already closed, do not reopen unless explicitly asked
    if (showIt && state.userClosedOverlay) return;

    overlay.classList.toggle("show", !!showIt);

    const titleEl = $("#loadingTitle");
    const descEl  = $("#loadingDesc");
    const hintEl  = $("#loadingHint");
    if (titleEl && title != null) titleEl.textContent = title;
    if (descEl  && desc  != null) descEl.textContent  = desc;
    if (hintEl  && hint  != null) hintEl.textContent  = hint;

    ensureOverlayCloseButton();
    const btn = $("#btnOverlayClose");
    if (btn) btn.disabled = !allowClose;
  }

  function alertBox(kind, msg) {
    const box = $("#alertBox");
    const text = $("#alertText");
    if (!box || !text) return;
    box.classList.remove("ok", "bad", "warn");
    box.classList.add(kind || "warn");
    text.textContent = msg || "";
    show(box, true);
  }
  function clearAlert() {
    const box = $("#alertBox");
    if (box) show(box, false);
  }

  // -------------------------
  // API
  // -------------------------
  async function apiGet(path) {
    const r = await fetch(path, { method: "GET" });
    const txt = await r.text();
    if (!r.ok) throw new Error(`GET ${path} failed ${r.status}: ${txt.slice(0, 500)}`);
    return txt ? (safeJsonParse(txt) ?? txt) : null;
  }

  async function apiPost(path, payload) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    });
    const txt = await r.text();
    if (!r.ok) throw new Error(`POST ${path} failed ${r.status}: ${txt.slice(0, 800)}`);
    return txt ? (safeJsonParse(txt) ?? txt) : null;
  }

  async function isPdfReady(pdfUrl) {
    try {
      const head = await fetch(pdfUrl, { method: "HEAD" });
      if (head.ok) return true;
    } catch {}
    try {
      const r = await fetch(pdfUrl, { method: "GET", headers: { Range: "bytes=0-1" } });
      return r.ok || r.status === 206;
    } catch {
      return false;
    }
  }

  // -------------------------
  // Health
  // -------------------------
  async function loadHealth() {
    try {
      await apiGet("/health");
      el.healthDot?.classList.remove("warn","bad","ok");
      el.healthDot?.classList.add("ok");
      setText(el.healthText, "server ok");
    } catch {
      el.healthDot?.classList.remove("warn","bad","ok");
      el.healthDot?.classList.add("bad");
      setText(el.healthText, "server error");
    }
  }

  // -------------------------
  // Styles
  // -------------------------
  function updateStyleNotes() {
    if (!el.style) return;
    const sid = el.style.value;
    const s = state.styles.find((x) => x.style_id === sid);
    setText(el.styleNotes, s?.notes ? `📝 ${s.notes}` : "—");
    setText(el.styleChip, `Style: ${s?.label || sid || "—"}`);
  }

  function renderStyles() {
    if (!el.style) return;
    el.style.innerHTML = "";
    (state.styles || []).forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.style_id;
      opt.textContent = s.label || s.style_id;
      el.style.appendChild(opt);
    });
    const def = state.styleDefault || (state.styles?.[0]?.style_id ?? "");
    if (def) el.style.value = def;
    updateStyleNotes();
    el.style.addEventListener("change", updateStyleNotes);
  }

  async function loadStyles() {
    const data = await apiGet("/api/styles");
    state.styles = data?.styles || [];
    state.styleDefault = data?.default || "";
    renderStyles();
  }

  // -------------------------
  // Nuances
  // -------------------------
  function labelForNuance(id) {
    const n = (state.nuances || []).find((x) => x.id === id);
    return n?.label || id;
  }

  function updateNuSummaryText() {
    const labels = (state.selectedNuances || []).map(labelForNuance);
    const summary = labels.length ? labels.join(", ") : "—";
    setText(el.nuChip, `Nuansa: ${summary}`);
  }

  function ensureNuDropdownUI() {
    if (!el.nuWrap || !el.nuGrid) return;
    if (state.nuBtn && state.nuPanel) return;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "secondary mini";
    btn.style.width = "100%";
    btn.style.display = "flex";
    btn.style.justifyContent = "space-between";
    btn.style.alignItems = "center";
    btn.style.marginBottom = "10px";
    btn.innerHTML = `<span data-title>🎭 Pilih Nuansa</span><span style="opacity:.7">▾</span>`;

    const panel = document.createElement("div");
    panel.style.display = "none";
    panel.style.border = "1px solid rgba(15,23,42,.10)";
    panel.style.borderRadius = "16px";
    panel.style.background = "#fff";
    panel.style.boxShadow = "0 18px 60px rgba(2,6,23,.12)";
    panel.style.padding = "10px";
    panel.style.marginBottom = "10px";

    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "Cari nuansa…";
    search.style.width = "100%";
    search.style.padding = "10px 12px";
    search.style.borderRadius = "14px";
    search.style.border = "1px solid rgba(15,23,42,.10)";
    search.style.outline = "none";
    search.style.marginBottom = "10px";

    panel.appendChild(search);

    el.nuWrap.insertBefore(btn, el.nuWrap.firstChild);
    el.nuWrap.insertBefore(panel, btn.nextSibling);

    state.nuBtn = btn;
    state.nuPanel = panel;
    state.nuSearch = search;

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      panel.style.display = (panel.style.display === "block") ? "none" : "block";
      if (panel.style.display === "block") search.focus();
    });

    document.addEventListener("click", (e) => {
      if (!el.nuWrap.contains(e.target)) panel.style.display = "none";
    });

    search.addEventListener("input", () => {
      const q = (search.value || "").trim().toLowerCase();
      const chips = Array.from(el.nuGrid.querySelectorAll("label.nuChip"));
      chips.forEach((lab) => {
        const id = (lab.getAttribute("data-id") || "").toLowerCase();
        const txt = (lab.getAttribute("data-label") || "").toLowerCase();
        lab.style.display = (!q || id.includes(q) || txt.includes(q)) ? "" : "none";
      });
    });
  }

  function setSelectedNuances(list) {
    state.selectedNuances = clampMaxFive(uniq(list));
    if (el.nuGrid) {
      const all = Array.from(el.nuGrid.querySelectorAll('input[type="checkbox"]'));
      all.forEach(cb => { cb.checked = state.selectedNuances.includes(cb.value); });
      const labs = Array.from(el.nuGrid.querySelectorAll("label.nuChip"));
      labs.forEach(lab => {
        const cb = lab.querySelector('input[type="checkbox"]');
        if (!cb) return;
        lab.classList.toggle("on", cb.checked);
      });
    }
    updateNuSummaryText();
  }

  function renderNuances() {
    if (!el.nuGrid) return;
    ensureNuDropdownUI();

    if (state.nuPanel && el.nuGrid.parentElement !== state.nuPanel) {
      state.nuPanel.appendChild(el.nuGrid);
      el.nuGrid.style.display = "flex";
      el.nuGrid.style.flexWrap = "wrap";
      el.nuGrid.style.gap = "8px";
    }

    el.nuGrid.innerHTML = "";

    (state.nuances || []).forEach((n) => {
      const id = String(n.id || "").trim();
      if (!id) return;

      const label = String(n.label || id).trim();
      const chip = document.createElement("label");
      chip.className = "nuChip";
      chip.setAttribute("data-id", id);
      chip.setAttribute("data-label", label);
      chip.innerHTML = `
        <input type="checkbox" value="${id.replaceAll('"', "&quot;")}" />
        <div class="t"><span>${label}</span></div>
      `;

      const cb = chip.querySelector("input");
      cb.checked = state.selectedNuances.includes(id);
      chip.classList.toggle("on", cb.checked);

      cb.addEventListener("change", () => {
        const now = Array.from(el.nuGrid.querySelectorAll('input[type="checkbox"]:checked')).map(x => x.value);
        if (now.length > 5) {
          cb.checked = false;
          chip.classList.remove("on");
          alertBox("warn", "Maksimal 5 nuansa ya 😄");
          return;
        }
        clearAlert();
        chip.classList.toggle("on", cb.checked);
        setSelectedNuances(now);
      });

      chip.addEventListener("click", (e) => {
        if (e.target && e.target.tagName === "INPUT") return;
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event("change", { bubbles: true }));
      });

      el.nuGrid.appendChild(chip);
    });

    el.btnNuDefault && (el.btnNuDefault.onclick = () => { clearAlert(); setSelectedNuances(state.nuancesDefault || []); });
    el.btnNuClear && (el.btnNuClear.onclick = () => { clearAlert(); setSelectedNuances([]); });

    setSelectedNuances(state.nuancesDefault || []);
  }

  async function loadNuances() {
    const data = await apiGet("/api/nuances");
    state.nuances = data?.nuances || [];
    state.nuancesDefault = data?.default || [];
    renderNuances();
  }

  // -------------------------
  // Preview (HTML) + Download buttons
  // -------------------------
  function previewUrl(jobId, part /*1|2*/) {
    return `/api/preview/${jobId}/part${part}`;
  }

  function getScriptObjectFromEditor() {
    const txt = (el.scriptJson?.value || "").trim();
    return txt ? safeJsonParse(txt) : null;
  }

  function ensurePreviewDownloadButtons() {
    if (!el.previewWrap || state.previewDlMounted) return;

    const head = el.previewWrap.querySelector(".head");
    if (!head) return;

    // Tempatkan tombol ke area kanan (chips)
    const right = head.querySelector(".chips") || head;
    const holder = document.createElement("div");
    holder.style.display = "flex";
    holder.style.flexWrap = "wrap";
    holder.style.gap = "8px";
    holder.style.justifyContent = "flex-end";
    holder.style.alignItems = "center";

    const mkBtn = (label) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "secondary mini";
      b.textContent = label;
      return b;
    };

    const btn1 = mkBtn("⬇️ Part 1");
    const btn2 = mkBtn("⬇️ Part 2");

    btn1.onclick = async () => {
      try {
        clearAlert();
        const jobId = state.jobId;
        if (!jobId) return alertBox("warn", "Belum ada jobId. Render dulu ya 🙂");
        const scriptObj = getScriptObjectFromEditor();
        const base = buildBaseFilename(scriptObj);
        await downloadBlobWithName(previewUrl(jobId, 1), `${base}_part1.png`);
        alertBox("ok", "Part 1 terunduh ✅");
      } catch (e) {
        alertBox("bad", `Gagal download Part 1: ${e.message || e}`);
      }
    };

    btn2.onclick = async () => {
      try {
        clearAlert();
        const jobId = state.jobId;
        if (!jobId) return alertBox("warn", "Belum ada jobId. Render dulu ya 🙂");
        const scriptObj = getScriptObjectFromEditor();
        const base = buildBaseFilename(scriptObj);
        await downloadBlobWithName(previewUrl(jobId, 2), `${base}_part2.png`);
        alertBox("ok", "Part 2 terunduh ✅");
      } catch (e) {
        alertBox("bad", `Gagal download Part 2: ${e.message || e}`);
      }
    };

    holder.appendChild(btn1);
    holder.appendChild(btn2);

    // sisipkan sebelum chip preview biar rapi
    if (right.firstChild) right.insertBefore(holder, right.firstChild);
    else right.appendChild(holder);

    state.previewDlMounted = true;
  }

  function showPreviewWrap(yes) {
    if (!el.previewWrap) return;
    el.previewWrap.classList.toggle("show", !!yes);
  }

  function resetPreviewUI() {
    showPreviewWrap(false);
    if (el.imgPart1) el.imgPart1.removeAttribute("src");
    if (el.imgPart2) el.imgPart2.removeAttribute("src");
    if (el.previewChip) setText(el.previewChip, "preview: —");
  }

  function setPreviewChip(text) {
    if (el.previewChip) setText(el.previewChip, `preview: ${text}`);
  }

  function loadImageTo(imgEl, url) {
    return new Promise((resolve) => {
      if (!imgEl) return resolve(false);

      // penting: reset dulu biar browser reload walau URL sama
      imgEl.onload = () => resolve(true);
      imgEl.onerror = () => resolve(false);

      imgEl.src = `${url}?t=${Date.now()}`;
    });
  }

  async function updatePreview(jobId, stage /* "p1"|"p2"|"both" */, statusLabel) {
    ensurePreviewDownloadButtons();
    showPreviewWrap(true);
    setPreviewChip(statusLabel || "memuat…");

    let ok1 = true, ok2 = true;

    if (stage === "p1" || stage === "both") {
      ok1 = await loadImageTo(el.imgPart1, previewUrl(jobId, 1));
      if (!ok1) setPreviewChip("Part 1 belum siap / endpoint error");
    }

    if (stage === "p2" || stage === "both") {
      ok2 = await loadImageTo(el.imgPart2, previewUrl(jobId, 2));
      if (!ok2) setPreviewChip("Part 2 belum siap / endpoint error");
    }

    if (ok1 && ok2 && (stage === "both")) setPreviewChip("siap ✅");
    if (ok1 && stage === "p1") setPreviewChip("Part 1 siap ✅");
    if (ok2 && stage === "p2") setPreviewChip("Part 2 siap ✅");
  }

  // -------------------------
  // PDF UI
  // -------------------------
  function resetPdfUI() {
    el.pdfWrap && el.pdfWrap.classList.remove("show");
    if (el.pdfFrame) el.pdfFrame.src = "about:blank";
    if (el.pdfHint) {
      el.pdfHint.style.display = "";
      el.pdfHint.textContent = "Belum ada PDF. Render dulu ya 🙂";
    }
    el.btnGetPdf && (el.btnGetPdf.disabled = true);
    el.btnOpenPdf && (el.btnOpenPdf.disabled = true);
    el.btnReadAlong && (el.btnReadAlong.disabled = true);
  }

  function enablePdfButtons(jobId) {
    const pdfUrl = `/api/pdf/${jobId}`;
    const pdfDl  = `/api/pdf/${jobId}?download=1`;

    const scriptObj = getScriptObjectFromEditor();
    const baseName = buildBaseFilename(scriptObj);
    const pdfName = `${baseName}.pdf`;

    if (el.btnGetPdf) {
      el.btnGetPdf.disabled = false;
      el.btnGetPdf.onclick = async () => {
        try {
          clearAlert();
          await downloadFileWithName(pdfDl, pdfName);
          alertBox("ok", `PDF terunduh ✅ (${pdfName})`);
        } catch (e) {
          alertBox("bad", `Gagal download PDF: ${e.message || e}`);
        }
      };
    }
    if (el.btnOpenPdf) {
      el.btnOpenPdf.disabled = false;
      el.btnOpenPdf.onclick = () => window.open(pdfUrl, "_blank");
    }
    if (el.btnReadAlong) {
      el.btnReadAlong.disabled = false;
      el.btnReadAlong.onclick = () => window.open(`/viewer/${jobId}`, "_blank");
    }
  }

  async function loadPdfIntoIframe(jobId) {
    const pdfUrl = `/api/pdf/${jobId}`;
    const cacheBusted = `${pdfUrl}?t=${Date.now()}`;

    el.pdfWrap && el.pdfWrap.classList.add("show");
    if (el.pdfHint) el.pdfHint.style.display = "none";

    setStep("pdf", "running", "memuat");
    await forceRepaint();

    return new Promise((resolve) => {
      if (!el.pdfFrame) return resolve();

      let done = false;
      const watchdog = setTimeout(() => {
        if (done) return;
        done = true;
        setStep("pdf", "done", "selesai");
        resolve();
      }, 9000);

      el.pdfFrame.onload = () => {
        if (done) return;
        done = true;
        clearTimeout(watchdog);
        setStep("pdf", "done", "selesai");
        resolve();
      };

      el.pdfFrame.src = cacheBusted;
    });
  }

  // -------------------------
  // Download JSON helper
  // -------------------------
  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // -------------------------
  // Script Action
  // -------------------------
  async function makeScript() {
    clearAlert();
    const story = (el.story?.value || "").trim();
    if (!story) return alertBox("warn", "Cerita masih kosong 🙂 Isi dulu ya.");

    state.userClosedOverlay = false;

    resetTimers();
    startRunTimer();

    setOverlay(true, "🧠 Menyusun naskah…", "AI sedang membuat 2 bagian…", "Mohon tunggu", { allowClose: false });
    resetSteps();
    setStep("script", "running", "memproses");
    setText(el.stepText, "buat naskah");

    await forceRepaint();
    await sleep(60);

    try {
      const res = await apiPost("/api/script", {
        story,
        style_id: el.style?.value || null,
        nuances: state.selectedNuances || [],
      });

      const script = res?.script;
      if (!script) throw new Error("Server tidak mengembalikan 'script'.");

      el.scriptJson && (el.scriptJson.value = prettyJson(script));
      setStep("script", "done", "selesai");
      setText(el.stepText, "naskah siap");
      alertBox("ok", "Naskah berhasil dibuat ✅");

      resetPreviewUI();
      resetPdfUI();

      setOverlay(true, "✅ Naskah siap", "Silakan klik Render Part 1 & 2.", "Kamu bisa close box ini kapan saja.", { allowClose: true });
    } catch (e) {
      setStep("script", "idle", "gagal");
      finishStepTimer("script", "idle");
      setText(el.stepText, "gagal");
      alertBox("bad", `Gagal membuat naskah: ${e.message || e}`);

      setOverlay(true, "❌ Gagal", "Naskah gagal dibuat.", "Silakan close box ini lalu coba lagi.", { allowClose: true });
    }
  }

  function formatJson() {
    clearAlert();
    const txt = (el.scriptJson?.value || "").trim();
    if (!txt) return alertBox("warn", "Belum ada JSON 🙂");
    const obj = safeJsonParse(txt);
    if (!obj) return alertBox("bad", "JSON belum valid. Cek koma/kurung ya.");
    el.scriptJson.value = prettyJson(obj);
    alertBox("ok", "JSON dirapikan ✨");
  }

  function copyJson() {
    clearAlert();
    const txt = (el.scriptJson?.value || "").trim();
    if (!txt) return alertBox("warn", "Belum ada JSON 🙂");
    navigator.clipboard.writeText(txt).then(
      () => alertBox("ok", "JSON di-copy ✅"),
      () => alertBox("bad", "Gagal copy. Coba Ctrl+C.")
    );
  }

  function downloadJson() {
    clearAlert();
    const txt = (el.scriptJson?.value || "").trim();
    const obj = safeJsonParse(txt);
    if (!obj) return alertBox("bad", "JSON belum valid, belum bisa download.");
    const baseName = buildBaseFilename(obj);
    const name = `${baseName}_script.json`;
    downloadText(name, prettyJson(obj));
    alertBox("ok", `File JSON terunduh ✅ (${name})`);
  }

  // -------------------------
  // Render Polling
  // -------------------------
  async function pollJobUntilDoneAndPdf(jobId) {
    state.isPolling = true;
    state.lastJobStatus = null;

    const pdfUrl = `/api/pdf/${jobId}`;
    const maxLoops = 1800;
    const intervalMs = 1000;

    for (let i = 0; i < maxLoops; i++) {
      const j = await apiGet(`/api/job/${jobId}`);
      const st = j?.status || "unknown";
      const hasPdf = !!j?.has_pdf;

      const changed = st !== state.lastJobStatus;
      state.lastJobStatus = st;

      setText(el.renderChip, `render: ${st}`);
      setText(el.pdfText, hasPdf ? "siap" : "—");

      if (st === "queued") {
        if (changed) {
          setStep("render1", "running", "antri");
          setStep("render2", "idle", "menunggu");
          setStep("pdf", "idle", "menunggu");
        }
        setOverlay(true, "🎬 Render komik…", "Antri render…", "Jangan tutup tab", { allowClose: false });
      }

      else if (st === "rendering_part_1") {
        if (changed) {
          setStep("render1", "running", "jalan");
          setStep("render2", "idle", "menunggu");
        }
        // ✅ tampilkan preview part1
        await updatePreview(jobId, "p1", "part 1…");
        setOverlay(true, "🎬 Render Part 1…", "Sedang membuat komik Part 1", "Jangan tutup tab", { allowClose: false });
      }

      else if (st === "rendering_part_2") {
        if (changed) {
          setStep("render1", "done", "selesai");
          setStep("render2", "running", "jalan");
        } else {
          if (state.timers.steps.render1.status === "running") setStep("render1", "done", "selesai");
          if (state.timers.steps.render2.status !== "running") setStep("render2", "running", "jalan");
        }

        // ✅ tampilkan preview part1 & part2
        await updatePreview(jobId, "both", "part 2…");
        setOverlay(true, "🎬 Render Part 2…", "Sedang membuat komik Part 2", "Jangan tutup tab", { allowClose: false });
      }

      else if (st === "done") {
        if (state.timers.steps.render1.status === "running") setStep("render1", "done", "selesai");
        if (state.timers.steps.render2.status === "running") setStep("render2", "done", "selesai");
        else setStep("render2", "done", "selesai");

        // ✅ pastikan preview siap
        await updatePreview(jobId, "both", "siap ✅");

        setStep("pdf", "running", "menyusun");
        setOverlay(true, "🧾 Menyusun PDF…", "Render selesai. PDF sedang dibuat…", "Jangan tutup tab", { allowClose: false });

        const ready = hasPdf ? true : await isPdfReady(pdfUrl);
        if (ready) return true;

        setText(el.pdfText, "menyusun…");
      }

      else if (st === "error") {
        setStep("render1", "idle", "gagal");
        setStep("render2", "idle", "gagal");
        setStep("pdf", "idle", "gagal");
        throw new Error(j?.error || "Job error");
      }

      refreshOverlayHintTimer();
      await sleep(intervalMs);
    }

    throw new Error("Timeout menunggu render/pdf selesai.");
  }

  async function startRenderAll() {
    if (state.isPolling) return alertBox("warn", "Render masih berjalan. Tunggu sampai selesai ya 🙂");

    clearAlert();
    state.userClosedOverlay = false;

    if (!state.timers.runStartMs) startRunTimer();

    setOverlay(true, "🎬 Memulai render…", "Menyiapkan data…", "Jangan tutup tab", { allowClose: false });
    setStep("script", "done", "siap");
    setStep("render1", "running", "menyiapkan");
    setStep("render2", "idle", "menunggu");
    setStep("pdf", "idle", "menunggu");
    setText(el.stepText, "render");

    await forceRepaint();
    await sleep(60);

    const txt = (el.scriptJson?.value || "").trim();
    if (!txt) {
      setOverlay(true, "⚠️ Belum ada JSON", "Klik Buat Naskah dulu.", "Kamu bisa close box ini.", { allowClose: true });
      return alertBox("warn", "Belum ada naskah JSON 🙂");
    }

    const scriptObj = safeJsonParse(txt);
    if (!scriptObj) {
      setOverlay(true, "❌ JSON tidak valid", "Perbaiki JSON dulu.", "Kamu bisa close box ini.", { allowClose: true });
      return alertBox("bad", "JSON tidak valid.");
    }

    try {
      resetPreviewUI();
      resetPdfUI();

      setText(el.renderChip, "render: queued");
      setText(el.pdfText, "—");

      const res = await apiPost("/api/render_all_start", { script: scriptObj });
      const jobId = res?.job_id;
      if (!jobId) throw new Error("Server tidak mengembalikan job_id.");

      state.jobId = jobId;
      setText(el.jobText, jobId);

      await pollJobUntilDoneAndPdf(jobId);

      await loadPdfIntoIframe(jobId);
      enablePdfButtons(jobId);

      setText(el.stepText, "done");
      setText(el.pdfText, "siap");
      setText(el.renderChip, "render: done ✅");
      alertBox("ok", "Render selesai ✅ Preview & PDF siap.");

      setOverlay(true, "✅ Selesai", "Preview sudah muncul. PDF juga sudah tampil.", "Silakan close box ini jika sudah selesai.", { allowClose: true });
    } catch (e) {
      console.error(e);
      setText(el.renderChip, "render: error");
      setText(el.pdfText, "error");

      setStep("render1", "idle", "gagal");
      setStep("render2", "idle", "gagal");
      setStep("pdf", "idle", "gagal");

      if (el.pdfHint) {
        el.pdfHint.style.display = "";
        el.pdfHint.textContent = "PDF gagal dimuat. Coba Render ulang atau buka Tab Baru saat PDF tersedia.";
      }

      // kalau preview endpoint error, ini akan kebaca dari onerror img
      alertBox("bad", `Gagal render: ${e.message || e}`);
      setOverlay(true, "❌ Gagal", "Render/PDF gagal.", "Silakan close box ini lalu coba lagi.", { allowClose: true });
    } finally {
      state.isPolling = false;
      stopTickerIfIdle();
    }
  }

  function resetAll() {
    clearAlert();
    if (el.story) el.story.value = "";
    if (el.scriptJson) el.scriptJson.value = "";
    state.jobId = null;
    state.isPolling = false;
    state.lastJobStatus = null;
    state.userClosedOverlay = false;

    setText(el.stepText, "siap");
    setText(el.jobText, "—");
    setText(el.pdfText, "—");
    setText(el.renderChip, "render: —");
    setPreviewChip("—");

    setSelectedNuances(state.nuancesDefault || []);
    if (state.styleDefault && el.style) {
      el.style.value = state.styleDefault;
      updateStyleNotes();
    }

    resetPreviewUI();
    resetPdfUI();
    resetSteps();
    resetTimers();

    const overlay = $("#overlay");
    overlay?.classList.remove("show");
  }

  // -------------------------
  // Boot
  // -------------------------
  function wireActions() {
    el.btnMakeScript && (el.btnMakeScript.onclick = makeScript);
    el.btnRenderAll && (el.btnRenderAll.onclick = startRenderAll);
    el.btnFormatJson && (el.btnFormatJson.onclick = formatJson);
    el.btnCopyJson && (el.btnCopyJson.onclick = copyJson);
    el.btnDownloadJson && (el.btnDownloadJson.onclick = downloadJson);
    el.btnReset && (el.btnReset.onclick = resetAll);
  }

  async function init() {
    console.log("[NanoBanana] app.js loaded ✅");

    wireActions();
    resetPreviewUI();
    resetPdfUI();
    resetTimers();
    resetSteps();

    ensureOverlayCloseButton();
    ensurePreviewDownloadButtons();

    await loadHealth();

    try {
      await Promise.all([loadStyles(), loadNuances()]);
      clearAlert();
    } catch (e) {
      console.error(e);
      alertBox("bad", `Gagal load style/nuansa: ${e.message || e}`);
    }

    updateStyleNotes();
    updateNuSummaryText();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
