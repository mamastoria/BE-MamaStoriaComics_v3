# core.py
from __future__ import annotations

import os
import re
import json
import base64
import logging
import threading
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest

from PIL import Image

# PDF
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nanobanana_core")


# ============================================================
# ENV
# ============================================================
def _env(name: str, default: str) -> str:
    return (os.getenv(name, default) or default).strip()


def _project_id() -> str:
    """
    Resolve project id safely.
    Priority:
    - GOOGLE_CLOUD_PROJECT (recommended)
    - GCLOUD_PROJECT
    - GOOGLE_PROJECT
    - PROJECT_ID (legacy support)
    """
    pid = (
        os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        or os.getenv("GCLOUD_PROJECT", "").strip()
        or os.getenv("GOOGLE_PROJECT", "").strip()
        or os.getenv("PROJECT_ID", "").strip()
        or "nanobananacomic-482111"  # Fallback
    )
    if not pid:
        # Should not happen with fallback
        print("WARNING: Project ID not found in env, using default.")
        return "nanobananacomic-482111"
    if "NAMA_PROJECT" in pid.upper():
        raise RuntimeError(f"Invalid placeholder project id detected: {pid}")
    return pid


PROJECT_ID = _project_id()

# ✅ Vertex should be regional (global often fails / causes weird permission errors)
VERTEX_LOCATION = _env("VERTEX_LOCATION", "global")

TEXT_MODEL = _env("TEXT_MODEL", "gemini-3-flash-preview")
IMAGE_MODEL = _env("IMAGE_MODEL", "gemini-3-pro-image-preview")

PARTS = 2
PANELS_PER_PART = 9
TOTAL_PANELS = PARTS * PANELS_PER_PART

TARGET_CANVAS = _env("TARGET_CANVAS", "portrait")
TARGET_AR = _env("TARGET_AR", "2:3")

# Option B requires text-in-image (caption + speech bubble inside the image)
NO_TEXT_IN_IMAGE = _env("NO_TEXT_IN_IMAGE", "0") == "1"
if NO_TEXT_IN_IMAGE:
    logger.warning("NO_TEXT_IN_IMAGE=1 detected, but Option B requires text in image. Set NO_TEXT_IN_IMAGE=0.")

TEXT_MAX_TOKENS = int(_env("TEXT_MAX_TOKENS", "4096"))
AIP_BASE = "https://aiplatform.googleapis.com/v1"

logger.info(
    "BOOT → project=%s location=%s text_model=%s image_model=%s",
    PROJECT_ID,
    VERTEX_LOCATION,
    TEXT_MODEL,
    IMAGE_MODEL,
)

# GCS Storage Configuration
GCS_BUCKET_NAME = _env("GOOGLE_BUCKET_NAME", "nanobanana-storage")
GCS_PANEL_PREFIX = "comics/panels"  # panels stored at: comics/panels/{job_id}/...
GCS_PDF_PREFIX = "comics/pdfs"
GCS_GRID_PREFIX = "comics/grids"

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# GCS UPLOAD HELPERS
# ============================================================
def _get_gcs_client():
    """Get GCS client using ADC or service account."""
    try:
        from google.cloud import storage as gcs_storage
        return gcs_storage.Client(project=PROJECT_ID)
    except Exception as e:
        logger.warning(f"Failed to create GCS client: {e}")
        return None


def upload_image_to_gcs(
    image_bytes: bytes,
    gcs_path: str,
    content_type: str = "image/png"
) -> Optional[str]:
    """
    Upload image bytes to GCS bucket.
    Returns public URL or None if failed.
    
    Path format: comics/panels/{job_id}/part{part_no}_panel{panel_idx}.png
    """
    client = _get_gcs_client()
    if not client:
        logger.warning("GCS client not available, skipping upload")
        return None
    
    try:
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(image_bytes, content_type=content_type)
        blob.make_public()
        
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_path}"
        logger.info(f"Uploaded to GCS: {public_url}")
        return public_url
    except Exception as e:
        logger.warning(f"GCS upload failed for {gcs_path}: {e}")
        return None


def upload_panel_to_gcs(
    job_id: str,
    part_no: int,
    panel_idx: int,
    panel_img: Image.Image
) -> Optional[str]:
    """
    Upload a single panel image to GCS.
    Returns the public URL.
    
    Storage path: comics/panels/{job_id}/part{part_no}_panel{panel_idx}.png
    """
    buf = BytesIO()
    panel_img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    
    gcs_path = f"{GCS_PANEL_PREFIX}/{job_id}/part{part_no}_panel{panel_idx}.png"
    return upload_image_to_gcs(img_bytes, gcs_path)


def upload_grid_to_gcs(
    job_id: str,
    part_no: int,
    grid_img: Image.Image
) -> Optional[str]:
    """
    Upload full grid page image to GCS.
    Returns the public URL.
    
    Storage path: comics/grids/{job_id}/part{part_no}_grid.png
    """
    buf = BytesIO()
    grid_img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    
    gcs_path = f"{GCS_GRID_PREFIX}/{job_id}/part{part_no}_grid.png"
    return upload_image_to_gcs(img_bytes, gcs_path)


def get_panel_gcs_url(job_id: str, part_no: int, panel_idx: int) -> str:
    """Get the expected GCS URL for a panel (for database storage)."""
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{GCS_PANEL_PREFIX}/{job_id}/part{part_no}_panel{panel_idx}.png"


def get_cover_url(job_id: str) -> str:
    """Get the cover URL (Panel 1 from Part 1)."""
    return get_panel_gcs_url(job_id, 1, 0)


def upload_panels_parallel(
    job_id: str,
    part_no: int,
    panel_images: List[Image.Image],
    max_workers: int = 4
) -> List[Optional[str]]:
    """
    Upload multiple panels in PARALLEL for faster processing.
    
    Args:
        job_id: Job ID
        part_no: Part number (1 or 2)
        panel_images: List of PIL Image objects
        max_workers: Number of parallel upload threads
        
    Returns:
        List of GCS URLs (or None for failed uploads)
    """
    import concurrent.futures
    
    def upload_single(args):
        panel_idx, panel_img = args
        return upload_panel_to_gcs(job_id, part_no, panel_idx, panel_img)
    
    # Create list of (index, image) tuples
    indexed_panels = list(enumerate(panel_images))
    
    # Upload in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        urls = list(executor.map(upload_single, indexed_panels))
    
    successful = len([u for u in urls if u])
    logger.info(f"Parallel upload: {successful}/{len(panel_images)} panels uploaded for part {part_no}")
    
    return urls


# ============================================================
# JOB PERSISTENCE (disk) — survive reload/restart
# ============================================================
def _job_file(job_id: str) -> Path:
    return EXPORT_DIR / f"job_{job_id}.json"


def _save_job_to_disk(job: Dict[str, Any]) -> None:
    """
    Persist job state so /api/job, /api/read, /api/pdf survive reload.
    """
    try:
        _job_file(job["job_id"]).write_text(
            json.dumps(job, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to save job to disk")


def _load_job_from_disk(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        p = _job_file(job_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load job from disk")
        return None


# ============================================================
# FILE HELPERS for full-page preview
# ============================================================
def _grid_png_path(job_id: str, part_no: int) -> Path:
    # konsisten & mudah ditebak
    return EXPORT_DIR / f"nanobanana_grid_{job_id}_part{int(part_no)}.png"


def _safe_unlink(path_str: Optional[str]) -> None:
    if not path_str:
        return
    try:
        Path(path_str).unlink(missing_ok=True)
    except Exception:
        pass


def _cleanup_preview_files_from_job(job: Dict[str, Any]) -> None:
    """
    Hapus file preview full-page (grid png) yang disimpan per part.
    """
    try:
        for k in ("part1", "part2"):
            part = job.get(k)
            if isinstance(part, dict):
                _safe_unlink(part.get("grid_path"))
    except Exception:
        pass


# ============================================================
# COMIC STYLES
# ============================================================
COMIC_STYLES: Dict[str, Dict[str, str]] = {
    "modern_clean": {
        "label": "Modern Clean (default)",
        "art_style": "clean modern comic, crisp shapes, readable facial expressions",
        "color_mood": "bright balanced, cinematic warm highlights",
        "line_style": "clean ink lines, sharp edges",
        "camera": "simple cinematic framing, clear focal points",
        "notes": "Best all-around, safe for phone readability.",
    },
    "manga_bw": {
        "label": "Manga B&W",
        "art_style": "Japanese manga style, expressive faces, dynamic speed lines, halftone shading",
        "color_mood": "black and white, high contrast, halftone dots",
        "line_style": "fine manga inking, varied line weight",
        "camera": "dramatic angles, action-ready panels",
        "notes": "Monochrome look; strong emotion/action.",
    },
    "pixar_3d": {
        "label": "3D Animated",
        "art_style": "high-quality 3D animated film still, soft materials, appealing characters",
        "color_mood": "vibrant cinematic lighting, soft glow",
        "line_style": "no ink outlines; 3D render edges",
        "camera": "cinematic depth of field, friendly close-ups",
        "notes": "Feels like movie frames; cute & family-friendly.",
    },
    "watercolor_storybook": {
        "label": "Watercolor Storybook",
        "art_style": "storybook illustration, watercolor wash, hand-painted feel",
        "color_mood": "pastel warm, soft gradients, paper texture",
        "line_style": "gentle sketch lines, painterly edges",
        "camera": "storybook framing, calm compositions",
        "notes": "Soft, emotional, cocok buat kisah keluarga.",
    },
    "retro_american": {
        "label": "Retro American (Golden Age)",
        "art_style": "retro American comic, bold shapes, vintage printing vibe",
        "color_mood": "limited palette, slightly desaturated, print texture",
        "line_style": "bold ink outlines, classic crosshatching",
        "camera": "classic hero shots, strong silhouettes",
        "notes": "Keren buat poster panel #1 yang “komik klasik”.",
    },
}
DEFAULT_STYLE_ID = "modern_clean"


def get_style(style_id: Optional[str]) -> Tuple[str, Dict[str, str]]:
    sid = (style_id or "").strip() or DEFAULT_STYLE_ID
    if sid not in COMIC_STYLES:
        sid = DEFAULT_STYLE_ID
    return sid, COMIC_STYLES[sid]


# ============================================================
# COMIC NUANCES
# ============================================================
COMIC_NUANCES: Dict[str, Dict[str, str]] = {
    "comedy": {"label": "Komedi"},
    "adventure": {"label": "Petualangan"},
    "education": {"label": "Edukasi"},
    "drama": {"label": "Drama"},
    "mystery": {"label": "Misteri"},
    "horror_light": {"label": "Horror Ringan"},
    "romance_light": {"label": "Romantis Ringan"},
}
DEFAULT_NUANCES: List[str] = ["adventure"]


def normalize_nuances(nuances: Optional[List[str]]) -> List[str]:
    chosen: List[str] = []
    for nid in (nuances or []):
        nid = (nid or "").strip()
        if nid and nid in COMIC_NUANCES and nid not in chosen:
            chosen.append(nid)
    if not chosen:
        chosen = list(DEFAULT_NUANCES)
    return chosen[:5]


def nuance_label_summary(nuances: List[str]) -> str:
    labels = []
    for nid in nuances:
        labels.append((COMIC_NUANCES.get(nid) or {}).get("label", nid))
    return ", ".join(labels)


def nuance_rules_text(nuances: List[str]) -> str:
    rules = []
    if "comedy" in nuances:
        rules.append("- Sisipkan humor visual dan dialog singkat yang lucu (tanpa mengejek).")
    if "adventure" in nuances:
        rules.append("- Pacing cepat, ada tantangan/tujuan kecil, rasa eksplorasi terasa.")
    if "education" in nuances:
        rules.append("- Sisipkan pelajaran/fakta sederhana yang relevan di beberapa panel.")
    if "drama" in nuances:
        rules.append("- Emosi & relasi terasa kuat; momen hening/haru diperjelas.")
    if "mystery" in nuances:
        rules.append("- Tambahkan petunjuk kecil (clue) di panel_context; rasa misteri konsisten.")
    if "horror_light" in nuances:
        rules.append("- Atmosfer spooky-cute, tanpa gore/trauma, tetap playful.")
    if "romance_light" in nuances:
        rules.append("- Momen manis/awkward-cute, gesture halus, tetap family-friendly.")
    if "romance_light" in nuances:
        rules.append("- Momen manis/awkward-cute, gesture halus, tetap family-friendly.")
    if not rules:
        rules.append("- Nuansa harus terasa di narasi, dialog, pacing, dan visual.")
    return "\n".join(rules)


# ============================================================
# SYSTEM PROMPT (TEXT MODEL)
# ============================================================
SYSTEM_PROMPT = """
Kamu adalah editor komik profesional.

Tugas:
- Ubah input user menjadi naskah komik dalam 2 BAGIAN besar.
- Output WAJIB JSON valid dan hanya JSON (tanpa teks lain).
- Konsistensi karakter harus ketat.
- Setiap BAGIAN wajib tepat 9 PANEL.
- Family-friendly.
- Setiap panel wajib ada:
  panel_no, panel_title, narration, dialogues (max 2 baris), panel_context (visual wajib).
- Untuk BAGIAN 1 PANEL 1: itu adalah poster film + judul komik (desain poster, cinematic).
- panel_context harus konkret (tempat, aksi, ekspresi, objek penting).
""".strip()


# ============================================================
# AUTH (ADC)
# ============================================================
def get_access_token() -> str:
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    if not creds.token:
        raise RuntimeError("Failed to obtain access token from ADC.")
    return creds.token


# ============================================================
# VERTEX REST: generateContent helper
# ============================================================
def vertex_generate_content(
    *,
    model: str,
    contents: List[Dict[str, Any]],
    generation_config: Optional[Dict[str, Any]] = None,
    safety_settings: Optional[List[Dict[str, Any]]] = None,
    timeout_s: int = 180,
) -> Dict[str, Any]:
    # ✅ regional endpoint path
    url = (
        f"{AIP_BASE}/projects/{PROJECT_ID}/locations/{VERTEX_LOCATION}"
        f"/publishers/google/models/{model}:generateContent"
    )

    payload: Dict[str, Any] = {"contents": contents}
    if generation_config:
        payload["generationConfig"] = generation_config
    if safety_settings:
        payload["safetySettings"] = safety_settings

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    logger.info("VERTEX generateContent → project=%s location=%s model=%s", PROJECT_ID, VERTEX_LOCATION, model)

    r = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    if r.status_code >= 400:
        raise RuntimeError(f"Vertex generateContent error {r.status_code}: {r.text[:4000]}")
    return r.json()


def extract_text_from_response(data: Dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"No candidates returned: {json.dumps(data)[:1200]}")
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    texts: List[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("text") is not None:
            texts.append(str(p["text"]))
    return "".join(texts).strip()


def extract_inline_images_from_response(data: Dict[str, Any]) -> List[Tuple[str, bytes]]:
    out: List[Tuple[str, bytes]] = []
    candidates = data.get("candidates") or []
    for cand in candidates:
        content = (cand or {}).get("content") or {}
        parts = content.get("parts") or []
        for p in parts:
            if not isinstance(p, dict):
                continue
            inline = p.get("inlineData") or p.get("inline_data")
            if not inline or not isinstance(inline, dict):
                continue
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            b64 = inline.get("data")
            if not b64:
                continue
            try:
                img_bytes = base64.b64decode(b64)
                out.append((mime, img_bytes))
            except Exception:
                continue
    return out


# ============================================================
# JSON + PIL HELPERS
# ============================================================
def safe_json_from_text(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("Empty response from text model")

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text.strip(),
        flags=re.IGNORECASE | re.MULTILINE,
    )

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not m:
        raise ValueError(f"Cannot find JSON object in response:\n{cleaned[:800]}")
    return json.loads(m.group(0))


def b64_png(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def split_grid_3x3(img: Image.Image) -> List[Image.Image]:
    w, h = img.size
    cell_w = w // 3
    cell_h = h // 3
    panels: List[Image.Image] = []
    for row in range(3):
        for col in range(3):
            left = col * cell_w
            top = row * cell_h
            right = (col + 1) * cell_w if col < 2 else w
            bottom = (row + 1) * cell_h if row < 2 else h
            panels.append(img.crop((left, top, right, bottom)))
    return panels


# ============================================================
# SCRIPT SHAPE VALIDATION + NORMALIZATION
# ============================================================
def _normalize_dialogues_in_panel(panel: Dict[str, Any]) -> None:
    dlg = panel.get("dialogues")
    if isinstance(dlg, list):
        panel["dialogues"] = [str(x).strip() for x in dlg if str(x).strip()][:2]
        return
    if dlg is None:
        panel["dialogues"] = []
        return
    s = str(dlg).strip()
    panel["dialogues"] = [s] if s else []


def validate_script_shape(script: Dict[str, Any]) -> None:
    if not isinstance(script, dict):
        raise ValueError("Script must be a JSON object.")

    parts = script.get("parts")
    if not isinstance(parts, list) or len(parts) != 2:
        raise ValueError("Script JSON must contain exactly 2 parts in 'parts'.")

    for part in parts:
        if not isinstance(part, dict):
            raise ValueError("Each part must be an object.")
        try:
            part_no = int(part.get("part_no") or 0)
        except Exception:
            part_no = 0
        if part_no not in (1, 2):
            raise ValueError("Each part must have part_no 1 or 2.")

        panels = part.get("panels")
        if not isinstance(panels, list) or len(panels) != 9:
            raise ValueError(f"Part {part_no} must have exactly 9 panels.")

        nums: List[int] = []
        for p in panels:
            if not isinstance(p, dict):
                continue
            try:
                nums.append(int(p.get("panel_no")))
            except Exception:
                nums.append(-999)

        if sorted(nums) != list(range(1, 10)):
            raise ValueError(f"Part {part_no} panels must be numbered 1..9 (got {nums}).")
        if len(set(nums)) != 9:
            raise ValueError(f"Part {part_no} panel_no has duplicates (got {nums}).")

        for p in panels:
            if not isinstance(p, dict):
                raise ValueError(f"Part {part_no} has invalid panel item.")
            for k in ("panel_no", "panel_title", "narration", "dialogues", "panel_context"):
                if k not in p:
                    raise ValueError(f"Part {part_no} panel {p.get('panel_no')} missing key: {k}")
            _normalize_dialogues_in_panel(p)


# ============================================================
# STEP 2: MAKE TWO-PART SCRIPT (ROBUST JSON + REPAIR PASS)
# ============================================================
def make_two_part_script(user_story: str, style_id: Optional[str], nuances: Optional[List[str]] = None) -> Dict[str, Any]:
    sid, st = get_style(style_id)
    chosen_nuances = normalize_nuances(nuances)
    nuance_summary = nuance_label_summary(chosen_nuances)
    nuance_rules = nuance_rules_text(chosen_nuances)

    nuance_lines = [f"- {nid} ({(COMIC_NUANCES.get(nid) or {}).get('label', nid)})" for nid in chosen_nuances]

    prompt = f"""
Buat naskah komik dari input user berikut.

USER_INPUT:
{user_story}

STYLE CHOICE (apply consistently):
- style_id: {sid}
- style_label: {st["label"]}
- art_style: {st["art_style"]}
- color_mood: {st["color_mood"]}
- line_style: {st["line_style"]}
- camera: {st["camera"]}

NUANCE / MOOD CHOICE (apply consistently):
{chr(10).join(nuance_lines)}

RULES TAMBAHAN NUANSA:
{nuance_rules}

RULES KETAT:
- Output harus 2 BAGIAN besar: part_no 1 dan 2.
- Masing-masing BAGIAN harus punya tepat 9 PANEL (panel_no 1..9).
- Konsistensi karakter wajib ketat (nama/ciri/outfit).
- Family-friendly.
- Setiap panel wajib punya:
  - panel_no (1..9)
  - panel_title
  - narration (1-2 kalimat)
  - dialogues (list max 2 baris; format "Nama: ...")
  - panel_context (visual wajib; jelas, konkret)
- BAGIAN 1 PANEL 1: harus berupa POSTER FILM + JUDUL KOMIK.
  - Komposisi poster: hero shot karakter utama, title besar, tagline singkat.
  - Tetap panel #1 dalam grid 3×3.

OUTPUT FORMAT (JSON):
{{
  "global": {{
    "comic_title": "...",
    "tagline": "...",
    "style": {{
      "style_id": "{sid}",
      "style_label": "{st["label"]}",
      "art_style": "{st["art_style"]}",
      "color_mood": "{st["color_mood"]}",
      "line_style": "{st["line_style"]}",
      "camera": "{st["camera"]}"
    }},
    "nuances": {{
      "selected_ids": {json.dumps(chosen_nuances)},
      "selected_labels": "{nuance_summary}"
    }},
    "characters": [
      {{
        "name": "...",
        "appearance": "...",
        "outfit": "...",
        "personality": "..."
      }}
    ]
  }},
  "parts": [
    {{
      "part_no": 1,
      "part_title": "...",
      "part_summary": "...",
      "panels": [ {{ "panel_no": 1, "panel_title": "...", "narration": "...", "dialogues": ["A: ..."], "panel_context": "..." }} ]
    }},
    {{
      "part_no": 2,
      "part_title": "...",
      "part_summary": "...",
      "panels": [ {{ "panel_no": 1, "panel_title": "...", "narration": "...", "dialogues": ["A: ..."], "panel_context": "..." }} ]
    }}
  ]
}}
""".strip()

    full_prompt = f"SYSTEM:\n{SYSTEM_PROMPT}\n\nUSER:\n{prompt}\n"
    logger.info("TEXT: build 2-part script via %s (style=%s, nuances=%s)", TEXT_MODEL, sid, chosen_nuances)

    def _call_text_model(prompt_text: str, *, temperature: float) -> str:
        data = vertex_generate_content(
            model=TEXT_MODEL,
            contents=[{"role": "user", "parts": [{"text": prompt_text}]}],
            generation_config={
                "temperature": float(temperature),
                "maxOutputTokens": int(TEXT_MAX_TOKENS),
                "candidateCount": 1,
                "responseMimeType": "application/json",
            },
            timeout_s=180,
        )
        return extract_text_from_response(data)

    raw_text = _call_text_model(full_prompt, temperature=0.35)

    try:
        script = safe_json_from_text(raw_text)
        validate_script_shape(script)
    except Exception as e1:
        logger.warning("TEXT: JSON parse/shape failed, attempting repair. err=%s", str(e1))
        repair_prompt = f"""
Kamu adalah "JSON Repair Bot".
TUGAS: Perbaiki JSON berikut agar valid JSON dan sesuai schema output yang diminta sebelumnya.

ATURAN KETAT:
- Output HARUS hanya JSON valid. Tidak boleh ada teks lain.
- Jangan menambah cerita baru. Hanya perbaiki sintaks JSON (koma, kutip, kurung, array/object).
- Pertahankan struktur yang diminta:
  - object root dengan "global" dan "parts"
  - "parts" harus 2 item, masing-masing punya part_no 1 dan 2
  - tiap part punya "panels" berisi 9 panel (panel_no 1..9)
  - tiap panel punya: panel_no, panel_title, narration, dialogues, panel_context

JSON_RUSAK:
{raw_text}
""".strip()
        repaired_text = _call_text_model(repair_prompt, temperature=0.0)
        script = safe_json_from_text(repaired_text)
        validate_script_shape(script)

    # Ensure nuance metadata consistent even if model deviates
    if isinstance(script.get("global"), dict):
        script["global"].setdefault("nuances", {})
        if isinstance(script["global"]["nuances"], dict):
            script["global"]["nuances"]["selected_ids"] = chosen_nuances
            script["global"]["nuances"]["selected_labels"] = nuance_summary

    return script


# ============================================================
# CONTINUITY SUMMARY
# ============================================================
def summarize_part_for_continuity(part: Dict[str, Any]) -> str:
    s = (part.get("part_summary") or "").strip()
    contexts: List[str] = []
    for p in (part.get("panels") or [])[:9]:
        c = (p.get("panel_context") or "").strip()
        if c:
            contexts.append(c)
    out = []
    if s:
        out.append(s)
    if contexts:
        out.append("Konteks visual penting: " + " | ".join(contexts[:6]))
    return (" ".join(out))[:1100]


# ============================================================
# BUILD IMAGE PROMPT (OPTION B: TEXT INSIDE IMAGE) + NUANCE
# ============================================================
def _dialogue_lines(dialogues: Any) -> List[str]:
    if not isinstance(dialogues, list):
        return []
    cleaned: List[str] = []
    for x in dialogues:
        s = str(x).strip()
        if s:
            cleaned.append(s)
    return cleaned[:2]


def _nuance_visual_rules(global_data: Dict[str, Any]) -> str:
    gnu = global_data.get("nuances") if isinstance(global_data.get("nuances"), dict) else {}
    ids = gnu.get("selected_ids") if isinstance(gnu, dict) else None
    chosen: List[str] = []
    if isinstance(ids, list):
        for x in ids:
            sx = str(x).strip()
            if sx and sx in COMIC_NUANCES and sx not in chosen:
                chosen.append(sx)
    if not chosen:
        chosen = list(DEFAULT_NUANCES)

    lines = ["NUANCE VISUAL + WRITING RULES (apply strongly):"]
    for nid in chosen:
        n = COMIC_NUANCES.get(nid) or {}
        lines.append(f"- {nid}: {n.get('label', nid)}")
    lines.append("")
    lines.append(
        "Enforce the selected nuance through: facial expressions, pacing, props, background mood, and wording in captions/bubbles."
    )
    return "\n".join(lines)


def build_image_prompt_3x3(global_data: Dict[str, Any], part: Dict[str, Any], prev_part_summary: str) -> str:
    style = global_data.get("style", {}) if isinstance(global_data.get("style"), dict) else {}
    characters = global_data.get("characters", [])
    if not isinstance(characters, list):
        characters = []

    comic_title = (global_data.get("comic_title") or "").strip() or "Judul Komik"
    tagline = (global_data.get("tagline") or "").strip()

    char_bible_lines = []
    for c in characters[:4]:
        if not isinstance(c, dict):
            continue
        char_bible_lines.append(
            f"- {c.get('name','Karakter')}: {c.get('appearance','')}; outfit: {c.get('outfit','')}; sifat: {c.get('personality','')}"
        )
    char_bible = "\n".join(char_bible_lines) if char_bible_lines else "- Buat karakter utama konsisten."

    panels_list = part.get("panels") or []
    panels_sorted = sorted(
        [p for p in panels_list if isinstance(p, dict)],
        key=lambda x: int(x.get("panel_no", 0) or 0),
    )

    panel_lines = []
    for panel in panels_sorted[:9]:
        pn = int(panel.get("panel_no") or 0)
        title = (panel.get("panel_title") or "").strip()
        narr = (panel.get("narration") or "").strip()
        dlgs = _dialogue_lines(panel.get("dialogues"))
        ctx = (panel.get("panel_context") or "").strip()

        dblock = "\n".join([f"- {d}" for d in dlgs]) if dlgs else "- (tanpa dialog)"
        panel_lines.append(
            f"""PANEL {pn}: {title}
VISUAL: {ctx}
NARASI (caption 1-2 kalimat, bahasa Indonesia): {narr}
DIALOG (speech bubbles, max 2):
{dblock}
""".strip()
        )

    part_no = int(part.get("part_no") or 1)
    part_title = (part.get("part_title") or "").strip()
    part_summary = (part.get("part_summary") or "").strip()

    poster_rules = f"""
POSTER RULE (ONLY for Part 1 Panel 1):
- It MUST look like a movie poster inside the top-left panel (panel 1).
- Render big readable title text: "{comic_title}"
- Render smaller readable tagline text: "{tagline}" (if empty, invent a short tagline).
- Typography: bold sans-serif, high contrast, clean, no gibberish.
""".strip()

    text_rules = """
TEXT RULES (CRITICAL):
- Render all written text in clear Indonesian, perfectly readable.
- Use large font sizes for phone portrait viewing.
- Use high-contrast caption boxes and speech bubbles.
- Avoid distorted letters, random symbols, or unreadable typography.
- Do NOT place text over faces; keep safe margins.
- For each panel:
  * 1 narration caption box (bottom or top) using the provided NARASI.
  * up to 2 speech bubbles using the provided DIALOG lines.
""".strip()

    layout_rules = f"""
LAYOUT / CANVAS (CRITICAL):
- Single image canvas MUST be portrait and phone-friendly (target aspect ratio {TARGET_AR}, like 1080×1620 or 1024×1536).
- Draw a perfect 3×3 grid of 9 equal panels.
- Thick straight white gutters.
- Each panel must be large and readable on a phone in portrait.
- Keep compositions simple, strong focal points.
""".strip()

    continuity = f"Previous part summary: {prev_part_summary}" if prev_part_summary else "Previous part summary: (first part)"
    nuance_rules = _nuance_visual_rules(global_data)

    return f"""
Create ONE high-quality COMIC PAGE as a portrait phone-friendly image.

{layout_rules}

STYLE (consistent):
- style_id: {style.get("style_id","")}
- art_style: {style.get("art_style","clean modern comic")}
- color_mood: {style.get("color_mood","cinematic warm")}
- line_style: {style.get("line_style","clean ink lines, sharp")}
- camera: {style.get("camera","simple cinematic framing")}

{nuance_rules}

CHARACTER BIBLE (keep consistent across all panels):
{char_bible}

STORY CONTINUITY:
{continuity}

TARGET PART:
Part {part_no}: {part_title}
Summary: {part_summary}

{poster_rules if part_no == 1 else ""}

{text_rules}

PANELS (reading order left-to-right, top-to-bottom):
{chr(10).join(panel_lines)}

QUALITY:
- Sharp, clean, no blur/no noise.
- Perfect grid alignment.
- Stable character faces/outfits across all panels.
""".strip()


def generate_3x3_grid_image(prompt: str) -> Image.Image:
    logger.info("IMAGE: calling %s (regional) [Option B text inside image]", IMAGE_MODEL)

    data = vertex_generate_content(
        model=IMAGE_MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config={
            "temperature": 0.0,
            "candidateCount": 1,
            "responseModalities": ["IMAGE"],
        },
        timeout_s=240,
    )

    imgs = extract_inline_images_from_response(data)
    if not imgs:
        txt = extract_text_from_response(data)
        raise RuntimeError(f"No image returned from model. Text response: {txt[:1200]}")

    mime, img_bytes = imgs[0]
    try:
        im = Image.open(BytesIO(img_bytes)).convert("RGB")
        return im
    except Exception as e:
        raise RuntimeError(f"Failed to decode image bytes (mime={mime}): {e}")


# ============================================================
# RENDER A PART
# ============================================================
def render_part_payload(script: Dict[str, Any], part_no: int, *, job_id: Optional[str] = None, style: Optional[str] = None) -> Dict[str, Any]:
    """
    Render a single part (9 panels in 3x3 grid).
    
    FLOW:
    1. Generate full 3x3 grid image from AI
    2. Split into 9 individual panels
    3. Upload each panel to GCS
    4. Return panel URLs for database storage
    
    Panel 1 (index 0) of Part 1 = Cover image
    """
    validate_script_shape(script)

    global_data = script.get("global", {}) if isinstance(script.get("global"), dict) else {}
    parts = script.get("parts", [])
    if not isinstance(parts, list) or len(parts) != 2:
        raise RuntimeError("Invalid script.parts")

    part = next((p for p in parts if isinstance(p, dict) and int(p.get("part_no") or 0) == int(part_no)), None)
    if not part:
        raise RuntimeError(f"part_no {part_no} not found in script")

    prev_part_summary = ""
    if int(part_no) == 2:
        prev_part = next((p for p in parts if isinstance(p, dict) and int(p.get("part_no") or 0) == 1), None)
        if prev_part:
            prev_part_summary = summarize_part_for_continuity(prev_part)

    img_prompt = build_image_prompt_3x3(global_data, part, prev_part_summary)
    grid_img = generate_3x3_grid_image(img_prompt)

    # Save full grid to local disk (for preview/debug)
    grid_path: Optional[Path] = None
    grid_gcs_url: Optional[str] = None
    if job_id:
        grid_path = _grid_png_path(job_id, int(part_no))
        try:
            grid_img.save(grid_path, "PNG")
        except Exception:
            logger.exception("Failed to save grid preview png: %s", str(grid_path))
            grid_path = None
        
        # Also upload full grid to GCS
        grid_gcs_url = upload_grid_to_gcs(job_id, int(part_no), grid_img)

    # Split grid into 9 panels
    grid_panels = split_grid_3x3(grid_img)
    panels_b64: List[str] = [b64_png(p) for p in grid_panels]
    
    # Upload all panels to GCS in PARALLEL
    if job_id:
        panel_urls = upload_panels_parallel(job_id, int(part_no), grid_panels, max_workers=4)
    else:
        panel_urls = [None] * len(grid_panels)
    
    logger.info(f"Rendered part {part_no}: {len([u for u in panel_urls if u])} panels uploaded to GCS")


    return {
        "part_no": int(part_no),
        "part": part,
        "grid": b64_png(grid_img),  # base64 for fallback/debug
        "grid_path": str(grid_path) if grid_path else None,
        "grid_gcs_url": grid_gcs_url,  # Full page GCS URL
        "panels": panels_b64,  # base64 panels (for backward compat)
        "panel_urls": panel_urls,  # GCS URLs for each panel
        "meta": {
            "project_id": PROJECT_ID,
            "vertex_location": VERTEX_LOCATION,
            "image_model": IMAGE_MODEL,
            "text_in_image": True,
            "target_ar": TARGET_AR,
            "target_canvas": TARGET_CANVAS,
        },
    }


# ============================================================
# READ-ALONG CLEAN TEXT (TTS)
# ============================================================
_TTS_STRIP_PATTERNS = [
    r"\bhalaman\s+\d+\b",
    r"\bbagian\s+\d+\b",
    r"\bpanel\s+\d+\b",
    r"\bnarasi\s*:\s*",
    r"\bdialog\s*:\s*",
]


def clean_tts_text(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    for pat in _TTS_STRIP_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    return s


def build_read_along_pages(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    18 pages aligned dengan panel.
    - 'text' = legacy/debug
    - 'tts_text' = bersih untuk dibacakan (narasi + dialog saja)
    """
    validate_script_shape(script)
    pages: List[Dict[str, Any]] = []

    global_data = script.get("global", {}) if isinstance(script.get("global"), dict) else {}
    title = (global_data.get("comic_title") or "").strip()

    parts = script.get("parts") or []
    parts_sorted = sorted([p for p in parts if isinstance(p, dict)], key=lambda x: int(x.get("part_no") or 0))

    page_no = 1
    for part in parts_sorted:
        pno = int(part.get("part_no") or 0)
        panels = part.get("panels") or []
        panels_sorted = sorted([p for p in panels if isinstance(p, dict)], key=lambda x: int(x.get("panel_no") or 0))

        for pan in panels_sorted:
            panel_no = int(pan.get("panel_no") or 0)
            panel_title = (pan.get("panel_title") or "").strip()
            narration = (pan.get("narration") or "").strip()

            dialogues = pan.get("dialogues") or []
            if not isinstance(dialogues, list):
                dialogues = [str(dialogues)]
            dlg_lines = [str(d).strip() for d in dialogues if str(d).strip()]
            dlg_join = " ".join(dlg_lines)

            # legacy/debug text (boleh ada label)
            legacy_chunks = []
            if page_no == 1 and title:
                legacy_chunks.append(f"Judul komik: {title}.")
            legacy_chunks.append(f"Halaman {page_no}.")
            legacy_chunks.append(f"Bagian {pno}, panel {panel_no}.")
            if panel_title:
                legacy_chunks.append(panel_title + ".")
            if narration:
                legacy_chunks.append("Narasi: " + narration)
            if dlg_join:
                legacy_chunks.append("Dialog: " + dlg_join)
            legacy_text = " ".join(legacy_chunks).strip()

            # clean TTS text (narasi + dialog saja)
            tts_chunks = []
            if page_no == 1 and title:
                tts_chunks.append(f"{title}.")
            if narration:
                tts_chunks.append(narration)
            if dlg_lines:
                tts_chunks.append(" ".join(dlg_lines))
            tts_text = clean_tts_text(" ".join(tts_chunks).strip())

            pages.append(
                {
                    "page_no": page_no,
                    "part_no": pno,
                    "panel_no": panel_no,
                    "panel_title": panel_title,
                    "text": legacy_text,
                    "tts_text": tts_text,
                }
            )
            page_no += 1

    return pages


# ============================================================
# JOB STORE (memory + disk persistence)
# ============================================================
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
JOB_TTL_SECONDS = 60 * 30  # 30 minutes


def _now() -> float:
    return time.time()


def cleanup_jobs() -> None:
    """
    Clean both in-memory and persisted job files that are older than TTL.
    ✅ FIX: juga hapus file preview grid png.
    """
    # 1) clean memory
    with JOBS_LOCK:
        dead: List[str] = []
        for jid, job in list(JOBS.items()):
            created = float(job.get("created_at") or 0)
            if created and (_now() - created) > JOB_TTL_SECONDS:
                dead.append(jid)

        for jid in dead:
            job = JOBS.pop(jid, None)
            if job:
                # remove pdf
                _safe_unlink(job.get("pdf_path"))

                # ✅ remove grid previews
                _cleanup_preview_files_from_job(job)

                # remove job json
                try:
                    _job_file(jid).unlink(missing_ok=True)
                except Exception:
                    pass

    # 2) clean disk files (in case server restarted and memory empty)
    try:
        for p in EXPORT_DIR.glob("job_*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                created = float((data or {}).get("created_at") or 0)
                if created and (_now() - created) > JOB_TTL_SECONDS:
                    # remove pdf if any
                    _safe_unlink((data or {}).get("pdf_path"))

                    # ✅ remove grid previews from disk job
                    _cleanup_preview_files_from_job(data or {})

                    p.unlink(missing_ok=True)
            except Exception:
                # if corrupted, remove it to avoid poisoning
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        # don't break app due to cleanup
        logger.exception("cleanup_jobs disk scan failed")


def _job_set(jid: str, patch: Dict[str, Any]) -> None:
    """
    Update job (memory) AND persist to disk. Also revives from disk if needed.
    """
    with JOBS_LOCK:
        job = JOBS.get(jid)
        if not job:
            disk_job = _load_job_from_disk(jid)
            if disk_job:
                JOBS[jid] = disk_job
                job = JOBS.get(jid)
        if not job:
            return
        job.update(patch)
        _save_job_to_disk(job)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    cleanup_jobs()

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job:
            return dict(job)

    disk_job = _load_job_from_disk(job_id)
    if disk_job:
        with JOBS_LOCK:
            JOBS[job_id] = disk_job
        return dict(disk_job)
    return None


def get_read(job_id: str) -> Optional[List[Dict[str, Any]]]:
    job = get_job(job_id)
    if not job:
        return None
    pages = job.get("read_pages") or []
    if not isinstance(pages, list):
        return []
    return pages


def _render_job_worker(job_id: str, script: Dict[str, Any]) -> None:
    """
    Render both parts in PARALLEL for ~50% faster processing.
    Uses ThreadPoolExecutor to render Part 1 and Part 2 simultaneously.
    """
    import concurrent.futures
    
    try:
        _job_set(job_id, {"status": "rendering_parallel", "error": None})
        logger.info(f"JOB {job_id}: Starting PARALLEL rendering of Part 1 and Part 2...")
        
        start_time = time.time()
        
        # Render Part 1 and Part 2 in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="render") as executor:
            future1 = executor.submit(render_part_payload, script, 1, job_id=job_id)
            future2 = executor.submit(render_part_payload, script, 2, job_id=job_id)
            
            # Wait for both to complete
            part1 = None
            part2 = None
            errors = []
            
            # Get Part 1 result
            try:
                part1 = future1.result(timeout=300)  # 5 min timeout per part
                _job_set(job_id, {"part1": part1})
                logger.info(f"JOB {job_id}: Part 1 completed")
            except Exception as e:
                errors.append(f"Part 1 failed: {e}")
                logger.exception(f"JOB {job_id}: Part 1 render failed")
            
            # Get Part 2 result
            try:
                part2 = future2.result(timeout=300)
                _job_set(job_id, {"part2": part2})
                logger.info(f"JOB {job_id}: Part 2 completed")
            except Exception as e:
                errors.append(f"Part 2 failed: {e}")
                logger.exception(f"JOB {job_id}: Part 2 render failed")
        
        elapsed = time.time() - start_time
        
        if errors:
            error_msg = "; ".join(errors)
            _job_set(job_id, {"status": "error", "error": error_msg})
            logger.error(f"JOB {job_id}: Parallel render failed in {elapsed:.1f}s - {error_msg}")
        else:
            _job_set(job_id, {"status": "done"})
            logger.info(f"JOB {job_id}: Parallel render DONE in {elapsed:.1f}s (both parts)")
            
    except Exception as e:
        logger.exception("JOB render failed: %s", job_id)
        _job_set(job_id, {"status": "error", "error": str(e)})


def start_render_all_job(script: Dict[str, Any], job_id: Optional[str] = None) -> str:
    """
    Create a job, precompute read-along pages, then render part1+part2 in background thread.
    Returns job_id.
    """
    cleanup_jobs()
    validate_script_shape(script)

    read_pages = build_read_along_pages(script)

    if not job_id:
        job_id = str(uuid.uuid4())
    
    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "created_at": _now(),
            "status": "queued",
            "error": None,
            "part1": None,
            "part2": None,
            "pdf_path": None,
            "script": script,
            "read_pages": read_pages,
        }
        _save_job_to_disk(JOBS[job_id])

    t = threading.Thread(target=_render_job_worker, args=(job_id, script), daemon=True)
    t.start()
    return job_id


# ============================================================
# PDF EXPORT — panel-by-panel (18 pages)
# ============================================================
def write_pdf_panel_by_panel(*, pdf_path: Path, panels_b64_ordered: List[str]) -> None:
    if not panels_b64_ordered:
        raise RuntimeError("No panels provided for PDF export")

    c = None

    for b64 in panels_b64_ordered:
        img_bytes = base64.b64decode(b64)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        w, h = img.size

        if c is None:
            c = canvas.Canvas(str(pdf_path), pagesize=(w, h))
        else:
            c.setPageSize((w, h))

        c.drawImage(
            ImageReader(img),
            0,
            0,
            width=w,
            height=h,
            preserveAspectRatio=True,
            mask="auto",
        )
        c.showPage()

    if c:
        c.save()


def ensure_job_pdf(job_id: str) -> Path:
    cleanup_jobs()
    job = get_job(job_id)
    if not job:
        raise RuntimeError("job_id not found (expired or invalid)")

    if job.get("status") != "done":
        raise RuntimeError(f"job status is '{job.get('status')}', not done")

    part1 = job.get("part1") or {}
    part2 = job.get("part2") or {}
    panels1 = part1.get("panels") or []
    panels2 = part2.get("panels") or []

    if len(panels1) != 9 or len(panels2) != 9:
        raise RuntimeError("Incomplete panels: expected 9 panels per part")

    existing = job.get("pdf_path")
    if existing:
        p = Path(existing)
        if p.exists():
            return p

    ordered_panels: List[str] = []
    ordered_panels.extend(panels1)
    ordered_panels.extend(panels2)

    pdf_path = EXPORT_DIR / f"nanobanana_comic_panels_{job_id}.pdf"
    write_pdf_panel_by_panel(pdf_path=pdf_path, panels_b64_ordered=ordered_panels)

    _job_set(job_id, {"pdf_path": str(pdf_path)})
    return pdf_path
