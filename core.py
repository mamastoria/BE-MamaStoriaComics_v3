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

import requests # For calling microservices




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
    # For local development, skip placeholder validation
    # if "NAMA_PROJECT" in pid.upper():
    #     raise RuntimeError(f"Invalid placeholder project id detected: {pid}")
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
    "BOOT >> project=%s location=%s text_model=%s image_model=%s",
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
    
    gcs_path = f"{GCS_PANEL_PREFIX}/{job_id}/part{part_no}_panel{panel_idx:02d}.png"
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
    max_workers: int = 9  # OPTIMIZED: Increased from 4 to 9 (one per panel)
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
# COMIC STYLES - Synced with production database
# ============================================================
# Style keys can be either string ID (e.g., "1", "2") or legacy keys (e.g., "modern_clean")
# Frontend sends numeric IDs from database, we map them to visual descriptors
COMIC_STYLES: Dict[str, Dict[str, str]] = {
    # === Database ID-based styles (from production) ===
    "1": {
        "label": "Realistic",
        "art_style": "photorealistic comic illustration, detailed faces, lifelike proportions, realistic lighting and shadows",
        "color_mood": "natural colors, realistic skin tones, subtle gradients, cinematic lighting",
        "line_style": "fine detailed lines, realistic textures, minimal outlines",
        "camera": "realistic perspective, natural composition, portrait-like framing",
        "notes": "Best for realistic storytelling, drama, and mature themes.",
    },
    "2": {
        "label": "Cartoon",
        "art_style": "classic cartoon style, exaggerated expressions, rounded shapes, bouncy proportions",
        "color_mood": "bright vibrant colors, flat shading, cheerful palette",
        "line_style": "bold clean outlines, smooth curves, thick strokes",
        "camera": "dynamic poses, exaggerated angles, fun compositions",
        "notes": "Perfect for comedy, children's stories, and lighthearted content.",
    },
    "3": {
        "label": "Semi-Realistic",
        "art_style": "semi-realistic illustration, stylized faces with realistic proportions, detailed backgrounds",
        "color_mood": "balanced colors, realistic lighting with artistic flair, soft shadows",
        "line_style": "medium weight lines, blend of realistic and stylized",
        "camera": "cinematic framing, balanced compositions, clear focal points",
        "notes": "Great balance between realism and stylization.",
    },
    "4": {
        "label": "Manga",
        "art_style": "Japanese manga style, expressive big eyes, dynamic speed lines, halftone shading",
        "color_mood": "black and white with screentones, high contrast, dramatic shadows",
        "line_style": "fine manga inking, varied line weight, detailed hair",
        "camera": "dramatic angles, action-ready panels, emotional close-ups",
        "notes": "Authentic manga look; great for action, romance, and drama.",
    },
    "5": {
        "label": "American Style",
        "art_style": "American comic book style, heroic proportions, dynamic poses, detailed musculature",
        "color_mood": "bold saturated colors, dramatic lighting, high contrast",
        "line_style": "bold ink outlines, classic crosshatching, strong shadows",
        "camera": "hero shots, dramatic low angles, action compositions",
        "notes": "Classic superhero comic aesthetic.",
    },
    "6": {
        "label": "Ghibli",
        "art_style": "Studio Ghibli inspired, soft watercolor feel, detailed backgrounds, warm nostalgic atmosphere",
        "color_mood": "soft pastel palette, warm golden lighting, dreamy atmosphere",
        "line_style": "gentle pencil-like lines, organic shapes, flowing hair",
        "camera": "wide scenic shots, peaceful compositions, nature-focused framing",
        "notes": "Perfect for magical, heartwarming family stories.",
    },
    "7": {
        "label": "Disney Style",
        "art_style": "Disney animation style, expressive characters, appealing design, magical feel",
        "color_mood": "vibrant rich colors, magical lighting, sparkle effects",
        "line_style": "smooth flowing lines, elegant curves, clean shapes",
        "camera": "cinematic framing, character-focused, emotional moments",
        "notes": "Magical fairy tale aesthetic, great for princess and adventure stories.",
    },
    "8": {
        "label": "Chibi Style",
        "art_style": "chibi/super-deformed style, oversized heads, tiny bodies, extremely cute expressions",
        "color_mood": "bright kawaii colors, pink and pastel palette, sparkles",
        "line_style": "simple clean lines, minimal details, rounded shapes",
        "camera": "cute poses, comedic angles, expressive reactions",
        "notes": "Super cute style for comedy and slice of life.",
    },
    "9": {
        "label": "Noir Style",
        "art_style": "film noir style, dramatic shadows, moody atmosphere, detective aesthetic",
        "color_mood": "black and white or sepia, heavy shadows, high contrast, dramatic lighting",
        "line_style": "bold shadows, stark contrasts, minimal mid-tones",
        "camera": "dutch angles, dramatic lighting, mysterious compositions",
        "notes": "Perfect for mystery and thriller stories.",
    },
    "10": {
        "label": "Watercolor Style",
        "art_style": "watercolor storybook illustration, soft washes, hand-painted feel, artistic textures",
        "color_mood": "pastel warm colors, soft gradients, paper texture visible",
        "line_style": "gentle sketch lines, painterly edges, flowing washes",
        "camera": "storybook framing, calm peaceful compositions",
        "notes": "Soft and emotional, perfect for family and bedtime stories.",
    },
    "11": {
        "label": "Pixel Art",
        "art_style": "retro pixel art style, 16-bit aesthetic, blocky shapes, nostalgic gaming look",
        "color_mood": "limited color palette, retro game colors, dithering patterns",
        "line_style": "pixelated edges, no anti-aliasing, sharp pixels",
        "camera": "side-scrolling game view, classic game compositions",
        "notes": "Nostalgic gaming aesthetic, great for adventure stories.",
    },
    "12": {
        "label": "Graffiti Style",
        "art_style": "urban graffiti art style, street art aesthetic, bold tags, spray paint effects",
        "color_mood": "vibrant neon colors, urban palette, spray paint gradients",
        "line_style": "bold graffiti outlines, dripping paint, raw edges",
        "camera": "street-level perspective, urban compositions, dynamic angles",
        "notes": "Edgy urban style, great for teen and street stories.",
    },
    "13": {
        "label": "Minimalist Style",
        "art_style": "minimalist illustration, simple shapes, clean design, essential elements only",
        "color_mood": "limited color palette, flat colors, lots of white space",
        "line_style": "simple thin lines, geometric shapes, clean edges",
        "camera": "clean compositions, focused framing, simple backgrounds",
        "notes": "Clean modern aesthetic, easy to read on mobile.",
    },
    "14": {
        "label": "Fantasy Style",
        "art_style": "epic fantasy illustration, magical atmosphere, detailed environments, mythical creatures",
        "color_mood": "rich jewel tones, magical glows, ethereal lighting",
        "line_style": "detailed linework, ornate patterns, flowing designs",
        "camera": "epic wide shots, dramatic landscapes, mystical framing",
        "notes": "Perfect for fantasy adventure and magical stories.",
    },
    "15": {
        "label": "Romance Style",
        "art_style": "shoujo manga romance style, beautiful characters, sparkly atmosphere, dreamy feel",
        "color_mood": "soft pink and pastel palette, rose petals, glowing lighting",
        "line_style": "delicate fine lines, flowing hair, soft features",
        "camera": "romantic close-ups, emotional moments, soft focus",
        "notes": "Perfect for love stories and romantic drama.",
    },
    "16": {
        "label": "Cartoon 3D",
        "art_style": "3D cartoon animation style, Pixar-like characters, rounded shapes, appealing design",
        "color_mood": "vibrant 3D lighting, soft subsurface scattering, cheerful colors",
        "line_style": "no outlines, 3D render with clean edges, smooth surfaces",
        "camera": "3D camera angles, cinematic depth of field, character focus",
        "notes": "Modern 3D animation look, family-friendly.",
    },
    # === Legacy keys for backward compatibility ===
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
        "notes": "Keren buat poster panel #1 yang 'buku cerita klasik'.",
    },
}
DEFAULT_STYLE_ID = "2"  # Cartoon as default (most versatile for family stories)


def get_style(style_id: Optional[str]) -> Tuple[str, Dict[str, str]]:
    """
    Get style configuration by ID or key.
    
    Args:
        style_id: Can be numeric ID from database (e.g., "1", "2", 1, 2) 
                  or legacy key (e.g., "modern_clean", "manga_bw")
    
    Returns:
        Tuple of (style_id, style_config_dict)
    """
    # Convert to string and strip whitespace
    sid = str(style_id or "").strip() or DEFAULT_STYLE_ID
    
    # Check if style exists
    if sid not in COMIC_STYLES:
        logger.warning(f"Style '{sid}' not found, falling back to default '{DEFAULT_STYLE_ID}'")
        sid = DEFAULT_STYLE_ID
    
    return sid, COMIC_STYLES[sid]


# ============================================================
# COMIC NUANCES / GENRES - Synced with production database
# ============================================================
# Genre keys can be either string ID (e.g., "1", "2") or legacy keys (e.g., "comedy")
# Frontend sends numeric IDs from database, we map them to labels and rules
COMIC_NUANCES: Dict[str, Dict[str, str]] = {
    # === Database ID-based genres (from production) ===
    "1": {
        "label": "Fiksi Keluarga",
        "description": "Cerita tentang keluarga, hubungan orangtua-anak, nilai-nilai keluarga",
    },
    "2": {
        "label": "Slice of Life",
        "description": "Cerita kehidupan sehari-hari yang relatable dan menghangatkan hati",
    },
    "3": {
        "label": "Komedi",
        "description": "Cerita lucu dengan humor visual dan dialog yang menghibur",
    },
    "4": {
        "label": "Petualangan",
        "description": "Cerita eksplorasi dengan tantangan dan tujuan yang seru",
    },
    "5": {
        "label": "Fabel",
        "description": "Cerita dengan karakter hewan yang mengajarkan nilai moral",
    },
    "6": {
        "label": "Fantasi",
        "description": "Cerita dengan elemen magis, dunia imajinatif, dan makhluk ajaib",
    },
    "7": {
        "label": "Misteri Ringan",
        "description": "Cerita dengan teka-teki dan petunjuk yang seru dipecahkan",
    },
    "8": {
        "label": "Drama Inspiratif",
        "description": "Cerita emosional dengan pesan moral dan inspirasi",
    },
    "9": {
        "label": "Edukasi",
        "description": "Cerita yang menyisipkan pelajaran dan fakta menarik",
    },
    "10": {
        "label": "Sejarah/Legenda",
        "description": "Cerita berdasarkan sejarah atau legenda lokal",
    },
    "11": {
        "label": "Superhero Keluarga",
        "description": "Cerita superhero yang family-friendly dengan nilai kepahlawanan",
    },
    "12": {
        "label": "Komik Kuliner & Lifestyle",
        "description": "Cerita tentang makanan, memasak, atau gaya hidup",
    },
    # === Legacy keys for backward compatibility ===
    "comedy": {"label": "Komedi"},
    "adventure": {"label": "Petualangan"},
    "education": {"label": "Edukasi"},
    "drama": {"label": "Drama"},
    "mystery": {"label": "Misteri"},
    "horror_light": {"label": "Horror Ringan"},
    "romance_light": {"label": "Romantis Ringan"},
    # === Mapping from database ID to legacy key for rules ===
    "family_fiction": {"label": "Fiksi Keluarga"},
    "slice_of_life": {"label": "Slice of Life"},
    "fable": {"label": "Fabel"},
    "fantasy": {"label": "Fantasi"},
    "history_legend": {"label": "Sejarah/Legenda"},
    "superhero_family": {"label": "Superhero Keluarga"},
    "culinary_lifestyle": {"label": "Komik Kuliner & Lifestyle"},
}
DEFAULT_NUANCES: List[str] = ["4"]  # Petualangan as default


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (label or "").lower())


def _match_label_to_key(label: Optional[str], mapping: Dict[str, Dict[str, str]]) -> Optional[str]:
    if not label:
        return None
    target = _normalize_label(label)
    if not target:
        return None
    for key, meta in mapping.items():
        mapped_label = _normalize_label(meta.get("label", ""))
        if not mapped_label:
            continue
        if mapped_label == target or target in mapped_label or mapped_label in target:
            return key
    return None


def map_style_id(style_id: Optional[str], style_name: Optional[str]) -> str:
    sid = str(style_id or "").strip()
    if sid in COMIC_STYLES:
        return sid
    matched = _match_label_to_key(style_name, COMIC_STYLES)
    if matched:
        return matched
    logger.warning("Style '%s' not mapped, falling back to default '%s'", style_name, DEFAULT_STYLE_ID)
    return DEFAULT_STYLE_ID


def map_nuance_ids(
    nuance_ids: Optional[List[str]] = None,
    nuance_names: Optional[List[str]] = None,
) -> List[str]:
    chosen: List[str] = []
    for nid in (nuance_ids or []):
        nid = str(nid or "").strip()
        if nid and nid in COMIC_NUANCES and nid not in chosen:
            chosen.append(nid)
    if not chosen and nuance_names:
        for name in nuance_names:
            matched = _match_label_to_key(name, COMIC_NUANCES)
            if matched and matched not in chosen:
                chosen.append(matched)
    if not chosen:
        chosen = list(DEFAULT_NUANCES)
    return chosen[:5]


def normalize_nuances(nuances: Optional[List[str]]) -> List[str]:
    return map_nuance_ids(nuance_ids=nuances)


def nuance_label_summary(nuances: List[str]) -> str:
    labels = []
    for nid in nuances:
        labels.append((COMIC_NUANCES.get(nid) or {}).get("label", nid))
    return ", ".join(labels)


def nuance_rules_text(nuances: List[str]) -> str:
    """Generate storytelling rules based on selected genres/nuances."""
    rules = []
    
    # Map database IDs to rule generators
    nuance_set = set(nuances)
    
    # Comedy rules (ID: 3 or legacy "comedy")
    if "3" in nuance_set or "comedy" in nuance_set:
        rules.append("- Sisipkan humor visual dan dialog singkat yang lucu (tanpa mengejek).")
    
    # Adventure rules (ID: 4 or legacy "adventure")
    if "4" in nuance_set or "adventure" in nuance_set:
        rules.append("- Pacing cepat, ada tantangan/tujuan kecil, rasa eksplorasi terasa.")
    
    # Education rules (ID: 9 or legacy "education")
    if "9" in nuance_set or "education" in nuance_set:
        rules.append("- Sisipkan pelajaran/fakta sederhana yang relevan di beberapa panel.")
    
    # Drama rules (ID: 8 or legacy "drama")
    if "8" in nuance_set or "drama" in nuance_set:
        rules.append("- Emosi & relasi terasa kuat; momen hening/haru diperjelas.")
    
    # Mystery rules (ID: 7 or legacy "mystery")
    if "7" in nuance_set or "mystery" in nuance_set:
        rules.append("- Tambahkan petunjuk kecil (clue) di panel_context; rasa misteri konsisten.")
    
    # Horror light rules (legacy only)
    if "horror_light" in nuance_set:
        rules.append("- Atmosfer spooky-cute, tanpa gore/trauma, tetap playful.")
    
    # Romance light rules (legacy only)
    if "romance_light" in nuance_set:
        rules.append("- Momen manis/awkward-cute, gesture halus, tetap family-friendly.")
    
    # Family Fiction rules (ID: 1)
    if "1" in nuance_set or "family_fiction" in nuance_set:
        rules.append("- Fokus pada hubungan keluarga yang hangat; nilai-nilai keluarga harus terasa.")
    
    # Slice of Life rules (ID: 2)
    if "2" in nuance_set or "slice_of_life" in nuance_set:
        rules.append("- Momen kehidupan sehari-hari yang relatable; detail kecil yang menghangatkan.")
    
    # Fable rules (ID: 5)
    if "5" in nuance_set or "fable" in nuance_set:
        rules.append("- Karakter hewan dengan sifat manusia; ada pesan moral jelas di akhir.")
    
    # Fantasy rules (ID: 6)
    if "6" in nuance_set or "fantasy" in nuance_set:
        rules.append("- Elemen magis dan dunia fantasi; visual yang imajinatif dan menakjubkan.")
    
    # History/Legend rules (ID: 10)
    if "10" in nuance_set or "history_legend" in nuance_set:
        rules.append("- Elemen sejarah/legenda yang akurat; kostum dan setting sesuai era.")
    
    # Superhero Family rules (ID: 11)
    if "11" in nuance_set or "superhero_family" in nuance_set:
        rules.append("- Aksi superhero yang family-friendly; nilai kepahlawanan dan keberanian.")
    
    # Culinary/Lifestyle rules (ID: 12)
    if "12" in nuance_set or "culinary_lifestyle" in nuance_set:
        rules.append("- Detail makanan/kuliner yang menggugah selera; visual masakan yang menarik.")
    
    if not rules:
        rules.append("- Nuansa harus terasa di narasi, dialog, pacing, dan visual.")
    
    return "\n".join(rules)


# ============================================================
# SYSTEM PROMPT (TEXT MODEL)
# ============================================================
SYSTEM_PROMPT = """
Kamu adalah editor buku cerita profesional.

Tugas:
- Ubah input user menjadi naskah buku cerita dalam 2 BAGIAN besar.
- Output JSON WAJIB memiliki object "global" dengan field WAJIB:
- comic_title: string judul buku cerita yang singkat, menarik, dan relevan
- Konsistensi karakter harus ketat.
- HINDARI deskripsi karakter yang mirip tokoh berhak cipta (misal: "robot kucing biru" yang mirip Doraemon). Gunakan deskripsi original.
- Setiap BAGIAN wajib tepat 9 PANEL.
- Family-friendly.
- Setiap panel wajib ada:
  panel_no, panel_title, narration, dialogues (max 2 baris), panel_context (visual wajib).
- Untuk BAGIAN 1 PANEL 1: Panel pembuka standar. Sertakan judul buku cerita di dalam panel ini dan jangan beri bubletext di panel ini.
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

    logger.info("VERTEX generateContent >> project=%s location=%s model=%s", PROJECT_ID, VERTEX_LOCATION, model)

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


def split_grid_3x3(img: Image.Image, use_margin: bool = False) -> List[Image.Image]:
    """
    Split a 3x3 grid image into 9 panels with uniform sizing.
    Remainder pixels are distributed so widths/heights stay aligned.
    """
    w, h = img.size

    base_cell_w = w // 3
    base_cell_h = h // 3
    remainder_w = w % 3
    remainder_h = h % 3

    # Distribute remainder pixels to the first columns/rows for perfect coverage
    col_widths = [base_cell_w + (1 if i < remainder_w else 0) for i in range(3)]
    row_heights = [base_cell_h + (1 if i < remainder_h else 0) for i in range(3)]

    margin_px = 8 if use_margin else 0

    panels: List[Image.Image] = []
    for row in range(3):
        for col in range(3):
            left = sum(col_widths[:col])
            right = left + col_widths[col]
            top = sum(row_heights[:row])
            bottom = top + row_heights[row]

            if margin_px:
                left += margin_px
                top += margin_px
                right -= margin_px
                bottom -= margin_px

            if left >= right or top >= bottom:
                # Clamp to avoid invalid crop when images are very small
                left = sum(col_widths[:col])
                right = left + col_widths[col]
                top = sum(row_heights[:row])
                bottom = top + row_heights[row]

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
Buat naskah buku cerita dari input user berikut.

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
- JIKA USER TIDAK MENYEBUT NAMA KARAKTER: Wajib gunakan nama Indonesia/Internasional yang kreatif.
- DESAIN KARAKTER: Wajib ORIGINAL. Jangan mendeskripsikan karakter mirip tokoh populer (seperti Doraemon, Upin Ipin, dll).
- KONSISTENSI VISUAL SUPER PENTING: Tulis deskripsi "appearance" dan "outfit" sengan SANGAT DETAIL.
  * Contoh: "Rambut spiky cokelat tua, mata bulat biru, kaos merah dengan garis kuning vertikal, celana pendek hitam."
  * Hindari deskripsi ambigua seperti "baju bola keren". Harus spesifik warnad an bentuknya.
- Family-friendly.
- Setiap panel wajib punya:
  - panel_no (1..9)
  - panel_title
  - narration (1-2 kalimat)
  - dialogues (list max 2 baris; format "Nama: ...")
  - panel_context (visual wajib; jelas, konkret)
- BAGIAN 1 PANEL 1: Panel pembuka standar (ukuran 1/9 grid).
  - Tampilkan JUDUL buku cerita di dalam panel ini dengan jelas.
  - Visual tetap menggambarkan adegan pembuka cerita.

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
    # Extract style from global_data - fallback to COMIC_STYLES if AI-generated style is incomplete
    raw_style = global_data.get("style", {}) if isinstance(global_data.get("style"), dict) else {}
    style_id = raw_style.get("style_id", "") or DEFAULT_STYLE_ID
    
    # If style_id exists in COMIC_STYLES, use the original definition (more reliable than AI output)
    if style_id in COMIC_STYLES:
        style = COMIC_STYLES[style_id].copy()
        style["style_id"] = style_id
        logger.info(f"IMAGE PROMPT: Using style '{style_id}' from COMIC_STYLES")
    else:
        # Fallback to AI-generated style or defaults
        style = raw_style if raw_style else COMIC_STYLES[DEFAULT_STYLE_ID].copy()
        style["style_id"] = style_id or DEFAULT_STYLE_ID
        logger.warning(f"IMAGE PROMPT: Style '{style_id}' not found, using fallback")
    
    characters = global_data.get("characters", [])
    if not isinstance(characters, list):
        characters = []

    comic_title = (global_data.get("comic_title") or "").strip() or "Judul buku cerita"
    tagline = (global_data.get("tagline") or "").strip()

    # Build detailed character bible for consistency
    char_bible_lines = []
    for c in characters[:4]:
        if not isinstance(c, dict):
            continue
        char_name = c.get('name', 'Karakter')
        char_appearance = c.get('appearance', '')
        char_outfit = c.get('outfit', '')
        char_personality = c.get('personality', '')
        char_bible_lines.append(
            f"- {char_name}: APPEARANCE: {char_appearance}; OUTFIT: {char_outfit}; PERSONALITY: {char_personality}"
        )
    char_bible = "\n".join(char_bible_lines) if char_bible_lines else "- Create visually consistent main characters."

    panels_list = part.get("panels") or []
    panels_sorted = sorted(
        [p for p in panels_list if isinstance(p, dict)],
        key=lambda x: int(x.get("panel_no", 0) or 0),
    )

    part_no = int(part.get("part_no") or 1)
    
    panel_lines = []
    for panel in panels_sorted[:9]:
        pn = int(panel.get("panel_no") or 0)
        title = (panel.get("panel_title") or "").strip()
        narr = (panel.get("narration") or "").strip()
        dlgs = _dialogue_lines(panel.get("dialogues"))
        ctx = (panel.get("panel_context") or "").strip()

        dblock = "\n".join([f"- {d}" for d in dlgs]) if dlgs else "- (no dialogue)"
        
        # SPECIAL: PART 1 PANEL 1 IS COVER/POSTER - NO BUBBLES
        # Standard panel processing (Part 1 Panel 1 handled same as others but with title)
        extra = ""
        if part_no == 1 and pn == 1:
            extra = f"TEXT INSTRUCTION: Render the story title '{comic_title}' clearly at the top."

        panel_lines.append(
            f"""PANEL {pn}: {title}
VISUAL: {ctx}
NARRATION (caption 1-2 sentences, in Indonesian): {narr}
DIALOGUE (speech bubbles, max 2):
{dblock}
{extra}
""".strip()
        )

    part_title = (part.get("part_title") or "").strip()
    part_summary = (part.get("part_summary") or "").strip()

    # Explicit pixel-perfect grid specification to remove ambiguity for the model
    CANVAS_WIDTH = 1080
    CANVAS_HEIGHT = 1620
    PANEL_WIDTH = CANVAS_WIDTH // 3  # 360px
    PANEL_HEIGHT = CANVAS_HEIGHT // 3  # 540px
    GUTTER_WIDTH = 0

    explicit_grid_spec = f"""
⚠️⚠️⚠️ GRID SPECIFICATION (ABSOLUTE - NO VARIATION) ⚠️⚠️⚠️

IMAGE CANVAS DIMENSIONS:
- Width: EXACTLY {CANVAS_WIDTH} pixels (1080px)
- Height: EXACTLY {CANVAS_HEIGHT} pixels (1620px)
- Aspect Ratio: {TARGET_AR} (2:3)

3×3 GRID LAYOUT:
- Rows: 3
- Columns: 3
- Total Panels: 9 (no more, no less)

EACH PANEL MUST BE:
- Width: EXACTLY {PANEL_WIDTH} pixels (1080÷3 = 360px per panel)
- Height: EXACTLY {PANEL_HEIGHT} pixels (1620÷3 = 540px per panel)
- Size: {PANEL_WIDTH}×{PANEL_HEIGHT} pixels EXACTLY
- Gutter/Border between panels: {GUTTER_WIDTH} pixels (FULL BLEED - panels touch edges)

VERIFICATION CHECKLIST (DO THIS BEFORE GENERATING):
✓ 3 columns × {PANEL_WIDTH}px = {3 * PANEL_WIDTH}px = {CANVAS_WIDTH}px (width matches? YES)
✓ 3 rows × {PANEL_HEIGHT}px = {3 * PANEL_HEIGHT}px = {CANVAS_HEIGHT}px (height matches? YES)
✓ All panels are identical size: {PANEL_WIDTH}×{PANEL_HEIGHT}px
✓ Panel 1 (top-left) = Panel 9 (bottom-right) in dimensions
✓ No merged panels, no variable sizes
✓ Image fills entire canvas (full bleed, no white borders)
✓ Thin black gridlines (1px) between panels only

FINAL OUTPUT CHECK (BEFORE SUBMITTING IMAGE):
- Count pixels: Top-left to top-right = {CANVAS_WIDTH}px? ✓
- Count pixels: Top-left to bottom-left = {CANVAS_HEIGHT}px? ✓
- Every panel corner to corner = {PANEL_WIDTH}×{PANEL_HEIGHT}? ✓
- If ANY answer is NO → REGENERATE with correct dimensions
""".strip()
    # SINGLE UNIFIED GRID RULE FOR ALL PARTS (1 and 2)
    grid_rules = """
GRID LAYOUT RULES (CRITICAL):
- The image MUST be a PERFECT 3x3 GRID of 9 EQUAL-SIZED PANELS.
- CRITICAL: Every panel MUST be exactly 1/3 width and 1/3 height of the page.
- DO NOT merge panels. DO NOT make Panel 1 larger.
- Layout MUST be identical for Part 1 and Part 2.
- ABSOLUTELY NO white borders or margins around the page edges.
- Full bleed: all panels must touch the edges of the image file.
""".strip()

    text_rules = """
TEXT RULES (CRITICAL):
- Render all written text in clear Indonesian, perfectly readable.
- TEXT MARGINS: Keep all text/bubbles at least 50 PIXELS AWAY from panel edges (Top, Bottom, Left, Right).
- BALANCED PLACEMENT: For titles and narration, CENTER them horizontally with EQUAL left/right margins.
- TOP GAP: Absolutely NO text touching the top edge. Leave a defined header space.
- Use large font sizes for phone portrait viewing.
- Use high-contrast caption boxes and speech bubbles.
- Avoid distorted letters, random symbols, or unreadable typography.
- Do NOT place text over faces.
- For each panel:
  * 1 narration caption box (bottom or top) using the provided NARRATION.
  * up to 2 speech bubbles using the provided DIALOGUE lines.

VISUAL SAFE AREA & FRAMING (CRITICAL - BALANCED MARGINS):
- BALANCED PADDING: Ensure EQUAL "breathing room" (empty space) on ALL 4 SIDES (Top, Bottom, Left, Right) between the subject and the panel borders.
- CENTER THE ACTION: Place main characters and text centrally to maintain this symmetry.
- DO NOT crowd the edges. If a character is on the left, balance the right side with background depth, but keep the SUBJECT with a buffer from the edge.
- PADDING SIZE: Maintain at least 15% clear background space from the panel edges for portraits.
- BACKGROUND EXTENSION: Background art MUST extend to the edges (full bleed), BUT important elements (faces, hands, text) MUST have this symmetrical safety margin.
- ERROR IF: Content feels "stuck" to one side or the top/bottom edges.
""".strip()

    layout_rules = f"""
{explicit_grid_spec}

LAYOUT / CANVAS (CRITICAL - MUST FOLLOW EXACTLY FOR ALL PARTS):
- Single image canvas MUST be portrait with exact aspect ratio {TARGET_AR} (like 1080x1620 or 1024x1536).
- Draw a PERFECT 3x3 grid of 9 EQUAL panels.
- PANELS MUST FILL THE ENTIRE CANVAS EDGE-TO-EDGE (FULL BLEED) - THIS APPLIES TO PART 1 AND PART 2 EQUALLY.
- ABSOLUTELY NO WHITE BORDERS, NO FRAMES, NO MARGINS around the outer edges of the image.
- The grid lines must be THIN BLACK lines (1-2px). Panel artwork MUST touch the very edge of the canvas.
- The image must look like a digital comic page, NOT a printed book scanned with white paper borders.
- Even if a panel contains a "poster" design, the artwork must extend fully to the panel edges with no internal margins.
- HOWEVER, Keep important TEXT and FACES inside the "Safe Zone" (center of the panel), away from the cut lines.
""".strip()

    # GRID ISOLATION RULES (CRITICAL)
    isolation_rules = """
GRID ISOLATION RULES (MANDATORY):
- CONTENT MUST NOT CROSS GRID LINES.
- Do NOT let Text, Speech Bubbles, or Characters cross from one panel to another.
- Each panel is a completely separate container.
- THE TITLE (if any) MUST BE FULLY INSIDE PANEL 1. Do not spread title across top panels.
- If text crosses a grid line, it will be cut in half and ruined.
- Keep all artwork strictly inside its 1/3 cell boundaries.
""".strip()

    # Character consistency rules - CRITICAL for multi-page comics
    character_consistency_rules = f"""
{isolation_rules}

CHARACTER CONSISTENCY (MANDATORY - HIGHEST PRIORITY):
- EVERY character MUST look EXACTLY THE SAME in EVERY panel they appear.
- Maintain IDENTICAL: face shape, eye color, hair color, hairstyle, skin tone, body type.
- Maintain IDENTICAL outfit/clothing unless explicitly stated to change.
- Characters should be immediately recognizable across all panels.
- Do NOT vary character appearances for "artistic" reasons.
- If a character appears in panel 1 and panel 9, they MUST look like the SAME person.
- Reference the CHARACTER BIBLE above for each character's fixed appearance.
""".strip()

    # STRICT 3x3 GRID REQUIREMENT - placed at the very beginning
    strict_3x3_opening = """
⚠️⚠️⚠️ MANDATORY GRID REQUIREMENT - READ THIS FIRST ⚠️⚠️⚠️
THIS IMAGE MUST BE A PERFECT 3x3 GRID OF 9 EQUAL-SIZED PANELS.
- 3 columns × 3 rows = 9 panels total
- Each panel is EXACTLY 1/3 width and 1/3 height
- ALL 9 panels MUST be the SAME SIZE - no exceptions
- Panel 1 is NOT bigger than other panels
- DO NOT merge any panels
- DO NOT create 2x2, 2x3, or any other layout
- ONLY 3x3 GRID IS ACCEPTABLE
""".strip()

    # Sacred character rules (prophets, companions, saints)
    sacred_character_rules = """
SACRED CHARACTER DEPICTION RULES (MANDATORY):
- For prophets (Nabi), companions of prophets (Sahabat Nabi), and saints (Orang Suci):
  * Their faces MUST be obscured/hidden with DIVINE LIGHT (bright white/golden glow)
  * Show their silhouette, body, and clothing clearly
  * Face area should emit radiant light that obscures facial features
  * Use soft, ethereal glow effect around the head/face region
  * Never show clear facial features for these sacred figures
- Examples of sacred figures: Prophet Muhammad, Prophet Ibrahim, Prophet Musa, Prophet Isa, Abu Bakar, Umar, Utsman, Ali, Khadijah, etc.
- When in doubt if a character is sacred, apply the light-obscured face treatment
""".strip()

    continuity = f"Previous part summary: {prev_part_summary}" if prev_part_summary else "Previous part summary: (first part)"
    nuance_rules = _nuance_visual_rules(global_data)

    # 3x3 reminder in the middle
    grid_reminder_mid = """
⚠️ REMINDER: 3x3 GRID CHECK ⚠️
Before proceeding, verify: Are you creating EXACTLY 9 equal-sized panels in a 3×3 grid?
If not, STOP and restart with the correct 3×3 layout.
""".strip()

    # 3x3 final check
    grid_final_check = """
⚠️⚠️⚠️ FINAL 3x3 GRID VERIFICATION ⚠️⚠️⚠️
Before finalizing the image, check:
□ Is the grid exactly 3 columns × 3 rows?
□ Are all 9 panels the SAME SIZE (each 1/3 × 1/3)?
□ Is Panel 1 the same size as Panel 9?
□ Are there no merged or larger panels?
If ANY answer is NO, the output is INVALID. Regenerate with correct 3×3 grid.
""".strip()

    return f"""
{strict_3x3_opening}

Create ONE high-quality COMIC PAGE as a portrait phone-friendly image.

{layout_rules}

{grid_reminder_mid}

{character_consistency_rules}

{sacred_character_rules}

STYLE (consistent across all panels):
- style_id: {style.get("style_id","")}
- art_style: {style.get("art_style","clean modern comic")}
- color_mood: {style.get("color_mood","cinematic warm")}
- line_style: {style.get("line_style","clean ink lines, sharp")}
- camera: {style.get("camera","simple cinematic framing")}

{nuance_rules}

CHARACTER BIBLE (MUST be followed exactly in every panel):
{char_bible}

STORY CONTINUITY:
{continuity}

TARGET PART:
Part {part_no}: {part_title}
Summary: {part_summary}

{grid_rules}

{text_rules}

PANELS (reading order left-to-right, top-to-bottom):
{chr(10).join(panel_lines)}

QUALITY REQUIREMENTS (MANDATORY):
- 2K ULTRA HD RESOLUTION, Extremely Detailed, Masterpiece.
- Sharp focus, high fidelity, 8k texture quality.
- PERFECT 3x3 grid alignment with edge-to-edge panels (FULL BLEED).
- ALL 9 PANELS MUST BE IDENTICAL SIZE (each exactly 1/3 width × 1/3 height).
- IDENTICAL character faces/outfits across all panels - this is CRITICAL.
- Consistent art style and color palette throughout.

ANTI-WHITE-BORDER CHECK (CRITICAL - APPLIES TO ALL PARTS):
- The ENTIRE canvas must be filled with colored artwork.
- There must be ZERO white/light pixels at any of the 4 edges (top, bottom, left, right).
- The panels must TOUCH the very edge of the image file.
- If you see any white/light margin or border in your output, you have FAILED the task.
- The image background color must extend to the edges - NO paper-white frames.

{grid_final_check}
""".strip()


def generate_3x3_grid_image(prompt: str) -> Image.Image:
    """Generate 3x3 grid image from AI model with timing logs."""
    ai_start = time.time()
    logger.info("IMAGE: calling %s (regional) [Option B text inside image]", IMAGE_MODEL)

    data = vertex_generate_content(
        model=IMAGE_MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config={
            "temperature": 0.0,
            "candidateCount": 1,
            "responseModalities": ["IMAGE"],
        },
        timeout_s=180,  # OPTIMIZED: Reduced from 240s to 180s
    )
    
    ai_elapsed = time.time() - ai_start
    logger.info(f"IMAGE: AI generation completed in {ai_elapsed:.1f}s")

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
# MICROSERVICE HELPER
# ============================================================
def call_smart_crop_service(grid_gcs_url: str, job_id: str, part_no: int) -> List[str]:
    """
    Call external Cloud Function to crop panels.
    Returns: List of GCS public URLs for the panels.
    """
    crop_start = time.time()
    
    # URL will be set via Environment Variable on deployment
    svc_url = _env("SMART_CROP_SERVICE_URL", "")
    
    if not svc_url:
        raise RuntimeError("Smart Crop Service URL not configured")
        
    payload = {
        "image_url": grid_gcs_url,
        "job_id": job_id,
        "part_no": part_no,
        "bucket_name": GCS_BUCKET_NAME
    }
    
    # OPTIMIZED: Reduced timeout from 300s to 120s
    resp = requests.post(svc_url, json=payload, timeout=120)
    resp.raise_for_status()
    
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Service returned error: {data.get('error')}")
    
    crop_elapsed = time.time() - crop_start
    logger.info(f"Smart Crop completed in {crop_elapsed:.1f}s for part {part_no}")
        
    return data.get("panel_urls", [])


# ============================================================
# RENDER A PART
# ============================================================
def render_part_payload(script: Dict[str, Any], part_no: int, *, job_id: Optional[str] = None, style: Optional[str] = None) -> Dict[str, Any]:
    """
    Render a single part (9 panels in 3x3 grid).
    
    FLOW (HYBRID + OPTIMIZED):
    1. Generate full 3x3 grid image from AI
    2. Try calling Smart Crop Microservice (OpenCV)
    3. If service fails/missing, fallback to Local Manual Crop
    4. Return panel URLs
    """
    part_start_time = time.time()
    ai_generate_ms = upload_grid_ms = smart_crop_ms = manual_crop_ms = upload_panels_ms = 0
    smart_crop_used = False
    logger.info(f"PART {part_no}: Starting render pipeline...")
    
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

    logger.info(f"PART {part_no}: Building image prompt...")
    img_prompt = build_image_prompt_3x3(global_data, part, prev_part_summary)
    
    # 1. Generate GRID Image
    logger.info(f"PART {part_no}: Generating 3x3 grid image via AI...")
    _t_ai = time.time()
    grid_img = generate_3x3_grid_image(img_prompt)
    ai_generate_ms = int((time.time() - _t_ai) * 1000)

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
        
        # Also upload full grid to GCS (Required for Smart Crop)
        _t_up_grid = time.time()
        grid_gcs_url = upload_grid_to_gcs(job_id, int(part_no), grid_img)
        upload_grid_ms = int((time.time() - _t_up_grid) * 1000)

    # 2. Crop Panels (Smart Service or Manual Fallback)
    panel_urls = []
    panels_b64 = [] # Will be populated only on fallback (or if we decide to download)
    
    smart_crop_success = False

    # TRY SMART CROP SERVICE
    if job_id and grid_gcs_url:
           try:
               _t_smart_crop = time.time()
               panel_urls = call_smart_crop_service(grid_gcs_url, job_id, int(part_no))
               smart_crop_ms = int((time.time() - _t_smart_crop) * 1000)
               logger.info(f"Smart Crop Success: Job {job_id} Part {part_no} -> {len(panel_urls)} panels.")
               smart_crop_success = True
               smart_crop_used = True
             
               # panels_b64 is left empty []. 
               # Frontend and PDF Generator must handle using URLs.
           except Exception as e:
               logger.warning(f"Smart Crop Service Failed/Skipped: {e}. Falling back to local manual crop.")
               smart_crop_success = False
    
    # FALLBACK: LOCAL MANUAL CROP
    if not smart_crop_success:
        logger.info(f"Performing Local Manual Crop (Fallback) for Job {job_id}")
        crop_start = time.time()
        grid_panels = split_grid_3x3(grid_img)
        manual_crop_ms = int((time.time() - crop_start) * 1000)
        panels_b64 = [b64_png(p) for p in grid_panels]  # Populate base64 for fallback
        logger.info(f"Local crop completed in {manual_crop_ms/1000:.1f}s")
        
        if job_id:
            upload_start = time.time()
            panel_urls = upload_panels_parallel(job_id, int(part_no), grid_panels, max_workers=9)  # OPTIMIZED: 9 workers
            upload_panels_ms = int((time.time() - upload_start) * 1000)
            logger.info(f"Panel upload completed in {upload_panels_ms/1000:.1f}s")
        else:
            panel_urls = [None] * len(grid_panels)
    
    # Log final timing summary
    part_elapsed = time.time() - part_start_time
    successful_panels = len([u for u in panel_urls if u])
    render_total_ms = int(part_elapsed * 1000)
    logger.info(
        {
            "event": "render_timings",
            "part_no": int(part_no),
            "job_id": job_id or "",
            "ai_generate_ms": ai_generate_ms,
            "upload_grid_ms": upload_grid_ms,
            "smart_crop_ms": smart_crop_ms,
            "manual_crop_ms": manual_crop_ms,
            "upload_panels_ms": upload_panels_ms,
            "render_total_ms": render_total_ms,
            "smart_crop_used": smart_crop_used,
            "successful_panels": successful_panels,
            "project_id": PROJECT_ID,
            "region": VERTEX_LOCATION,
        }
    )
    logger.info(f"PART {part_no}: COMPLETED in {part_elapsed:.1f}s ({successful_panels}/9 panels)")

    return {
        "part_no": int(part_no),
        "part": part,
        "grid": b64_png(grid_img),  # base64 for fallback/debug
        "grid_path": str(grid_path) if grid_path else None,
        "grid_gcs_url": grid_gcs_url,  # Full page GCS URL
        "panels": panels_b64,  # base64 panels (might be empty if smart crop used)
        "panel_urls": panel_urls,  # GCS URLs for each panel
        "render_time_seconds": round(part_elapsed, 1),  # ADDED: timing info
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
                legacy_chunks.append(f"Judul buku cerita: {title}.")
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
        logger.info(f"JOB {job_id}: Starting OPTIMIZED PARALLEL rendering of Part 1 and Part 2...")
        
        start_time = time.time()
        
        # OPTIMIZED: Render Part 1 and Part 2 in parallel with better timeout handling
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
    """
    Generate PDF from list of panels.
    Input `panels_b64_ordered` can be:
    - Base64 strings (Legacy)
    - HTTP URLs (New Microservice flow)
    """
    if not panels_b64_ordered:
        raise RuntimeError("No panels provided for PDF export")

    c = None

    for item in panels_b64_ordered:
        img_bytes = None
        
        # Check if URL
        if item.startswith("http://") or item.startswith("https://"):
            try:
                # Download image
                resp = requests.get(item, timeout=30)
                if resp.status_code == 200:
                    img_bytes = resp.content
                else:
                    logger.warning(f"PDF Gen: Failed to download panel {item}: {resp.status_code}")
                    continue
            except Exception as e:
                 logger.warning(f"PDF Gen: Error downloading panel {item}: {e}")
                 continue
        else:
            # Assume Base64
            try:
                img_bytes = base64.b64decode(item)
            except Exception:
               pass
            
        if not img_bytes:
            continue

        try:
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
        except Exception as e:
            logger.warning(f"PDF Gen: Failed to process image bytes: {e}")

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
