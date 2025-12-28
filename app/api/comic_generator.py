from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys
import os

# Add root directory to python path to import core
# Assuming this file is in app/api/, root is ../../
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    import core
except ImportError:
    # If standard import fails, try relative or adjust path logic
    # This fallback is unlikely needed if run from root
    import core

router = APIRouter()

STATIC_DIR = ROOT_DIR / "static"

# ============================================================
# REQUEST MODELS
# ============================================================
class ScriptRequest(BaseModel):
    story: str = Field(..., min_length=1)
    style_id: Optional[str] = Field(
        default=None,
        description="One of: " + ", ".join(core.COMIC_STYLES.keys()),
    )
    nuances: List[str] = Field(
        default_factory=list,
        description="List of nuance ids from /api/nuances",
    )


class RenderPartRequest(BaseModel):
    script: Dict[str, Any] = Field(..., description="Edited/confirmed script JSON from /api/script")
    part_no: int = Field(..., ge=1, le=2)


class RenderAllRequest(BaseModel):
    script: Dict[str, Any] = Field(..., description="Confirmed script JSON from /api/script")


# ============================================================
# ROUTES
# ============================================================

@router.get("/health-check-ai")
def health_ai():
    return {
        "status": "ok",
        "project_id": core.PROJECT_ID,
        "text_model": core.TEXT_MODEL,
        "image_model": core.IMAGE_MODEL,
        "parts": core.PARTS,
        "panels_per_part": core.PANELS_PER_PART,
        "total_panels": core.TOTAL_PANELS,
        "option": "B_text_inside_image",
        "target_canvas": core.TARGET_CANVAS,
        "target_ar": core.TARGET_AR,
        "styles": list(core.COMIC_STYLES.keys()),
        "nuances": list(core.COMIC_NUANCES.keys()),
        "no_text_in_image": core.NO_TEXT_IN_IMAGE,
        "pdf_export_dir": str(core.EXPORT_DIR),
    }


@router.get("/api/styles")
def api_styles():
    styles = []
    for sid, s in core.COMIC_STYLES.items():
        styles.append(
            {
                "style_id": sid,
                "label": s["label"],
                "notes": s.get("notes", ""),
                "art_style": s["art_style"],
                "color_mood": s["color_mood"],
                "line_style": s["line_style"],
                "camera": s["camera"],
            }
        )
    return {"default": core.DEFAULT_STYLE_ID, "styles": styles}


@router.get("/api/nuances")
def api_nuances():
    out = []
    for nid, n in core.COMIC_NUANCES.items():
        out.append({"id": nid, "label": n.get("label", nid)})
    return {"default": core.DEFAULT_NUANCES, "nuances": out}

# Note: The root "/" endpoint is handled in app/main.py, but we can have it here if we want specific logic 
# or just keep it there. I'll omit "/" here and let app/main.py handle serving index.html.

@router.post("/api/script")
def api_script(req: ScriptRequest):
    story = (req.story or "").strip()
    if not story:
        raise HTTPException(status_code=400, detail="story is empty")

    try:
        script = core.make_two_part_script(story, req.style_id, req.nuances)

        sid, st = core.get_style(req.style_id)
        chosen_nuances = core.normalize_nuances(req.nuances)

        return JSONResponse(
            {
                "script": script,
                "meta": {
                    "project_id": core.PROJECT_ID,
                    "text_model": core.TEXT_MODEL,
                    "parts": core.PARTS,
                    "panels_per_part": core.PANELS_PER_PART,
                    "style_id": sid,
                    "style_label": st["label"],
                    "nuances": chosen_nuances,
                    "nuance_labels": core.nuance_label_summary(chosen_nuances),
                },
            }
        )
    except Exception as e:
        core.logger.exception("Script generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/render_part")
def api_render_part(req: RenderPartRequest):
    """
    Render satu part (langsung synchronous) untuk debug/manual.
    """
    try:
        payload = core.render_part_payload(req.script, int(req.part_no))
        return JSONResponse(payload)
    except Exception as e:
        core.logger.exception("Render part failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/render_all_start")
def api_render_all_start(req: RenderAllRequest):
    try:
        job_id = core.start_render_all_job(req.script)
        return JSONResponse({"job_id": job_id, "status": "queued"})
    except Exception as e:
        core.logger.exception("Start render_all job failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/job/{job_id}")
def api_job(job_id: str):
    core.cleanup_jobs()
    job = core.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found (expired or invalid)")

    part1 = job.get("part1") or {}
    part2 = job.get("part2") or {}

    # has preview full-page file? (requires core.py patch to store grid_path / part*_full_path)
    has_preview_1 = bool(part1.get("grid_path") or part1.get("part_full_path"))
    has_preview_2 = bool(part2.get("grid_path") or part2.get("part_full_path"))

    resp: Dict[str, Any] = {
        "job_id": job["job_id"],
        "status": job["status"],
        "error": job.get("error"),
        "has_part1": bool(job.get("part1")),
        "has_part2": bool(job.get("part2")),
        "has_pdf": bool(job.get("pdf_path")),
        "has_read": bool(job.get("read_pages")),
        "has_preview_part1": has_preview_1,
        "has_preview_part2": has_preview_2,
    }
    return JSONResponse(resp)


@router.get("/api/read/{job_id}")
def api_read(job_id: str):
    pages = core.get_read(job_id)
    if pages is None:
        raise HTTPException(status_code=404, detail="job_id not found (expired or invalid)")
    return JSONResponse({"job_id": job_id, "pages": pages})


@router.get("/api/pdf/{job_id}")
def api_pdf(job_id: str, download: int = Query(0)):
    """
    Serve the final comic as PDF (1 panel per page).
    """
    try:
        pdf_path = core.ensure_job_pdf(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"nanobanana_comic_{job_id}.pdf"
    disp = "attachment" if download == 1 else "inline"

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="{filename}"'},
    )


@router.get("/api/preview/{job_id}/{part_no}")
def api_preview(job_id: str, part_no: int):
    """
    Return full 3×3 page image before split.
    """
    core.cleanup_jobs()
    job = core.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found (expired or invalid)")

    try:
        pno = int(part_no)
    except Exception:
        raise HTTPException(status_code=400, detail="part_no must be 1 or 2")
    if pno not in (1, 2):
        raise HTTPException(status_code=400, detail="part_no must be 1 or 2")

    part = job.get("part1") if pno == 1 else job.get("part2")
    if not part:
        raise HTTPException(status_code=404, detail="part not ready yet")

    path_str = (part or {}).get("grid_path") or (part or {}).get("part_full_path")
    if not path_str:
        raise HTTPException(status_code=404, detail="preview path not available (core.py belum menyimpan file full page)")

    p = Path(str(path_str))
    if not p.exists():
        raise HTTPException(status_code=404, detail="preview file not found on disk")

    return FileResponse(str(p), media_type="image/png")


@router.get("/viewer/{job_id}")
def viewer(job_id: str):
    core.cleanup_jobs()
    job = core.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found (expired or invalid)")

    html = """<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <title>NanoBanana Viewer</title>
  <style>
    :root{ --bg:#0b1220; --card:#0f1a33; --text:#e9efff; --muted:#93a4c7; --acc:#00c2ff; --acc2:#ff3d7f; }
    *{box-sizing:border-box}
    body{ margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; background:linear-gradient(120deg,#0b1220,#09142a); color:var(--text); }
    .top{ position:sticky; top:0; z-index:5; background:rgba(11,18,32,.82); backdrop-filter:blur(10px); border-bottom:1px solid rgba(255,255,255,.08); }
    .bar{ max-width:980px; margin:0 auto; padding:12px 14px; display:flex; gap:10px; align-items:center; justify-content:space-between; flex-wrap:wrap; }
    .title{ font-weight:800; letter-spacing:.2px; }
    .btns{ display:flex; gap:8px; flex-wrap:wrap; }
    button{ cursor:pointer; border:0; border-radius:14px; padding:10px 12px; font-weight:800; color:#08101f;
            background:linear-gradient(135deg,var(--acc),var(--acc2)); }
    button.secondary{ background:#ffffff; }
    button.ghost{ background:transparent; color:var(--muted); border:1px solid rgba(255,255,255,.12); }
    button:disabled{ opacity:.55; cursor:not-allowed; }
    .wrap{ max-width:980px; margin:0 auto; padding:14px; }
    .hint{ color:var(--muted); font-size:13px; line-height:1.35; margin:10px 0 14px; }
    .page{ background:#fff; border-radius:16px; overflow:hidden; margin:12px 0; box-shadow:0 18px 60px rgba(0,0,0,.35); }
    canvas{ width:100%; height:auto; display:block; }
    .pmeta{ padding:10px 12px; background:#fff; color:#0b1220; border-top:1px solid rgba(0,0,0,.08); font-size:13px; }
    .pmeta b{ color:#0b1220; }
    .status{ color:var(--muted); font-size:12.5px; }
    input[type="range"]{ width:160px; }
    .ctl{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .chip{ padding:6px 10px; border:1px solid rgba(255,255,255,.12); border-radius:999px; color:var(--muted); font-size:12.5px; }
    .spinner{ width:14px; height:14px; border-radius:999px; border:2px solid rgba(255,255,255,.25); border-top-color:#fff; display:inline-block; animation:spin 1s linear infinite; vertical-align:-2px; margin-right:6px;}
    @keyframes spin{ to{ transform:rotate(360deg);} }
  </style>
</head>
<body data-job-id="__JOB_ID__">
  <div class="top">
    <div class="bar">
      <div>
        <div class="title">📖 NanoBanana Read-Along Viewer</div>
        <div class="status" id="st"><span class="spinner"></span>Loading…</div>
      </div>

      <div class="ctl">
        <span class="chip" id="chipPage">page: -/-</span>
        <label class="chip">speed:
          <input id="rate" type="range" min="0.7" max="1.3" step="0.05" value="1.0" />
          <span id="rateV">1.0×</span>
        </label>
      </div>

      <div class="btns">
        <button id="btnPlay" disabled>▶️ Play</button>
        <button id="btnPause" class="secondary" disabled>⏸ Pause</button>
        <button id="btnStop" class="ghost" disabled>⏹ Stop</button>
        <button id="btnOpen" class="secondary" disabled>🪟 Open PDF</button>
        <button id="btnDl" class="ghost" disabled>⬇️ Download</button>
      </div>
    </div>
  </div>

  <div class="wrap">
    <div class="hint">
      Viewer ini merender PDF per halaman (panel-by-panel) dan pakai suara browser untuk membacakan <b>narasi+dialog</b> dari script.
      Saat bacaan berpindah, halaman otomatis di-scroll mengikuti.
    </div>
    <div id="pages"></div>
  </div>

  <script type="module">
    // ✅ Robust PDF.js: ESM import (no global pdfjsLib)
    import * as pdfjsLib from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.min.mjs";

    const JOB_ID = document.body.getAttribute('data-job-id');
    const PDF_URL = `/api/pdf/${JOB_ID}`;
    const PDF_DL  = `/api/pdf/${JOB_ID}?download=1`;
    const READ_URL = `/api/read/${JOB_ID}`;

    const st = document.getElementById('st');
    const pagesEl = document.getElementById('pages');

    const btnPlay = document.getElementById('btnPlay');
    const btnPause = document.getElementById('btnPause');
    const btnStop = document.getElementById('btnStop');
    const btnOpen = document.getElementById('btnOpen');
    const btnDl = document.getElementById('btnDl');

    const chipPage = document.getElementById('chipPage');
    const rate = document.getElementById('rate');
    const rateV = document.getElementById('rateV');

    rate.addEventListener('input', () => rateV.textContent = Number(rate.value).toFixed(2) + '×');

    btnOpen.onclick = () => window.open(PDF_URL, '_blank');
    btnDl.onclick = () => window.location.href = PDF_DL;

    // PDF.js worker (must match version)
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.7.76/pdf.worker.min.mjs";

    let readPages = [];
    let currentIndex = 0;
    let speaking = false;
    let utter = null;

    function getTtsText(p){
      // ✅ prefer clean tts_text; fallback to text for older jobs
      return ((p && (p.tts_text || p.text)) || "") + "";
    }

    function nextSpeakableIndex(fromIdx){
      for (let i = Math.max(0, fromIdx); i < readPages.length; i++){
        const t = getTtsText(readPages[i]).trim();
        if (t.length > 0) return i;
      }
      return -1;
    }

    function stopAll(){
      speaking = false;
      currentIndex = 0;
      btnPlay.disabled = !(('speechSynthesis' in window) && ('SpeechSynthesisUtterance' in window) && readPages.length);
      btnPause.disabled = true;
      btnStop.disabled = true;
      window.speechSynthesis.cancel();
      chipPage.textContent = 'page: -/-';
    }

    function pause(){
      speaking = false;
      btnPlay.disabled = false;
      btnPause.disabled = true;
      window.speechSynthesis.cancel();
    }

    function speakIndex(i){
      const idx = nextSpeakableIndex(i);
      if (idx === -1){
        stopAll();
        return;
      }

      currentIndex = idx;
      const p = readPages[idx];

      chipPage.textContent = `page: ${p.page_no}/${readPages.length}`;

      const node = document.getElementById('page-' + p.page_no);
      if (node){
        node.scrollIntoView({behavior:'smooth', block:'start'});
      }

      window.speechSynthesis.cancel();

      const tts = getTtsText(p).trim();
      utter = new SpeechSynthesisUtterance(tts);
      utter.lang = 'id-ID';
      utter.rate = Number(rate.value) || 1.0;

      utter.onend = () => {
        if (!speaking) return;
        speakIndex(currentIndex + 1);
      };
      utter.onerror = () => {
        if (!speaking) return;
        // if an error happens on one page, skip forward
        speakIndex(currentIndex + 1);
      };

      window.speechSynthesis.speak(utter);
    }

    function play(){
      if (!readPages.length) return;
      const start = nextSpeakableIndex(currentIndex);
      if (start === -1) return;

      speaking = true;
      btnPlay.disabled = true;
      btnPause.disabled = false;
      btnStop.disabled = false;
      speakIndex(start);
    }

    btnPlay.onclick = play;
    btnPause.onclick = pause;
    btnStop.onclick = stopAll;

    async function waitUntilDone(){
      for (let i=0; i<600; i++){
        const r = await fetch(`/api/job/${JOB_ID}`);
        if (!r.ok) throw new Error('job not found');
        const j = await r.json();

        if (j.status === 'done') return true;
        if (j.status === 'error') throw new Error(j.error || 'job error');

        st.textContent = `⏳ Masih proses… (${j.status})`;
        await new Promise(res => setTimeout(res, 1000));
      }
      throw new Error('Timeout menunggu render selesai.');
    }

    async function loadAll(){
      st.textContent = '⏳ Cek status render…';
      await waitUntilDone();

      st.textContent = 'Memuat PDF & teks bacaan…';

      const r = await fetch(READ_URL);
      if (!r.ok) throw new Error('read not found');
      const js = await r.json();
      readPages = js.pages || [];

      const canSpeak = ('speechSynthesis' in window) && ('SpeechSynthesisUtterance' in window);
      btnPlay.disabled = !(canSpeak && readPages.length);
      btnPause.disabled = true;
      btnStop.disabled = true;

      btnOpen.disabled = false;
      btnDl.disabled = false;

      const pdf = await pdfjsLib.getDocument(PDF_URL).promise;
      const total = pdf.numPages;

      st.textContent = `PDF siap ✅ (${total} halaman). Scroll bebas, atau tekan Play untuk read-along.`;

      for (let n = 1; n <= total; n++){
        const page = await pdf.getPage(n);
        const viewport = page.getViewport({scale: 1.6});

        const wrap = document.createElement('div');
        wrap.className = 'page';
        wrap.id = 'page-' + n;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        wrap.appendChild(canvas);

        const meta = document.createElement('div');
        meta.className = 'pmeta';
        const rp = readPages[n-1];
        const title = (rp && rp.panel_title) ? rp.panel_title : '';
        meta.innerHTML = rp
          ? `<b>Halaman ${n}</b> • Bagian ${rp.part_no} Panel ${rp.panel_no} • ${title}`
          : `<b>Halaman ${n}</b>`;
        wrap.appendChild(meta);

        pagesEl.appendChild(wrap);

        await page.render({canvasContext: ctx, viewport}).promise;
      }

      document.addEventListener('visibilitychange', () => {
        if (document.hidden) pause();
      });
    }

    loadAll().catch(err => {
      console.error(err);
      st.textContent = 'Gagal memuat viewer: ' + (err?.message || err);
      // disable controls on failure
      btnPlay.disabled = true; btnPause.disabled = true; btnStop.disabled = true;
      btnOpen.disabled = false; btnDl.disabled = false;
    });
  </script>
</body>
</html>
"""
    html = html.replace("__JOB_ID__", job_id)
    return HTMLResponse(html)
