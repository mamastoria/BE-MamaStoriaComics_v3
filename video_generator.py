"""
Cinematic Video Generator Service
Creates professional storytelling videos from comic panels with narration.

Features:
- Ken Burns effect (zoom/pan animation)
- Smooth fade transitions between panels
- Text-to-Speech narration
- Cinematic letterboxing (optional)
- Background music support
- 9:16 vertical format for mobile

Dependencies:
- ffmpeg (must be installed)
- google-cloud-texttospeech (for TTS)
- PIL (for image processing)
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO

logger = logging.getLogger("video_generator")

# Video settings
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280  # 9:16 aspect ratio for mobile
VIDEO_FPS = 30
PANEL_DURATION = 4.0  # seconds per panel (will be adjusted based on narration)
TRANSITION_DURATION = 0.5  # fade duration
MIN_PANEL_DURATION = 3.0
MAX_PANEL_DURATION = 8.0

# Ken Burns effect settings
ZOOM_FACTOR_MIN = 1.0
ZOOM_FACTOR_MAX = 1.15  # 15% zoom
PAN_STRENGTH = 0.05  # 5% pan


def check_ffmpeg() -> bool:
    """Check if ffmpeg is installed."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def generate_tts_audio(
    text: str,
    output_path: str,
    language_code: str = "id-ID",
    voice_name: str = "id-ID-Wavenet-D",  # MALE, Deep & Dramatic
) -> Optional[float]:
    """
    Generate TTS audio using Google Cloud Text-to-Speech.
    Returns audio duration in seconds, or None if failed.
    """
    try:
        from google.cloud import texttospeech
        
        client = texttospeech.TextToSpeechClient()
        
        # Use SSML for better intonation control
        ssml_text = f"<speak><p>{text}</p></speak>"
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.85,  # Slower pace for storytelling
            pitch=-2.0,          # Deeper voice for dramatic effect
            volume_gain_db=0.0
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        with open(output_path, "wb") as out:
            out.write(response.audio_content)
        
        # Get audio duration using ffprobe
        duration = get_audio_duration(output_path)
        logger.info(f"Generated TTS audio: {output_path} ({duration:.1f}s)")
        return duration
        
    except Exception as e:
        logger.warning(f"TTS generation failed: {e}")
        return None


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return PANEL_DURATION


def download_image(url: str, output_path: str) -> bool:
    """Download image from URL to local path."""
    try:
        import requests
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return False


def prepare_panel_image(
    input_path: str,
    output_path: str,
    target_width: int = VIDEO_WIDTH,
    target_height: int = VIDEO_HEIGHT
) -> bool:
    """
    Prepare panel image for video:
    - Resize to fit target dimensions
    - Add padding if needed
    - Apply slight vignette for cinematic look
    """
    try:
        from PIL import Image, ImageFilter, ImageDraw
        
        img = Image.open(input_path).convert("RGB")
        original_w, original_h = img.size
        
        # Calculate scaling to fill frame
        scale_w = target_width / original_w
        scale_h = target_height / original_h
        scale = max(scale_w, scale_h) * 1.15  # Scale up for Ken Burns room
        
        new_w = int(original_w * scale)
        new_h = int(original_h * scale)
        
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Center crop to target size
        left = (new_w - target_width) // 2
        top = (new_h - target_height) // 2
        img_cropped = img_resized.crop((left, top, left + target_width, top + target_height))
        
        img_cropped.save(output_path, "PNG", quality=95)
        return True
        
    except Exception as e:
        logger.warning(f"Failed to prepare image: {e}")
        # Fallback: just copy the file
        shutil.copy(input_path, output_path)
        return True


def create_ken_burns_filter(
    panel_index: int,
    duration: float,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT
) -> str:
    """
    Create FFmpeg filter for Ken Burns effect (zoom + pan).
    Alternates between different motion patterns for variety.
    """
    patterns = [
        # Zoom in from center
        {"start_zoom": 1.0, "end_zoom": 1.12, "start_x": 0.5, "start_y": 0.5, "end_x": 0.5, "end_y": 0.5},
        # Zoom out with slight pan right
        {"start_zoom": 1.15, "end_zoom": 1.0, "start_x": 0.45, "start_y": 0.5, "end_x": 0.55, "end_y": 0.5},
        # Pan left to right
        {"start_zoom": 1.1, "end_zoom": 1.1, "start_x": 0.3, "start_y": 0.5, "end_x": 0.7, "end_y": 0.5},
        # Pan top to bottom
        {"start_zoom": 1.1, "end_zoom": 1.1, "start_x": 0.5, "start_y": 0.35, "end_x": 0.5, "end_y": 0.65},
        # Zoom in with pan to bottom-right
        {"start_zoom": 1.0, "end_zoom": 1.15, "start_x": 0.4, "start_y": 0.4, "end_x": 0.6, "end_y": 0.6},
    ]
    
    p = patterns[panel_index % len(patterns)]
    
    # Calculate zoom and position expressions
    # t = current time, d = duration
    zoom_expr = f"{p['start_zoom']}+({p['end_zoom']}-{p['start_zoom']})*time/{duration}"
    x_expr = f"(iw-iw/zoom)/2+({p['start_x']}-0.5)*iw*(1-time/{duration})+({p['end_x']}-0.5)*iw*time/{duration}"
    y_expr = f"(ih-ih/zoom)/2+({p['start_y']}-0.5)*ih*(1-time/{duration})+({p['end_y']}-0.5)*ih*time/{duration}"
    
    return f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={int(duration*VIDEO_FPS)}:s={width}x{height}:fps={VIDEO_FPS}"


def generate_cinematic_video(
    panels: List[Dict[str, Any]],
    output_path: str,
    background_music_path: Optional[str] = None,
    with_narration: bool = True,
    with_letterbox: bool = True
) -> bool:
    """
    Generate a cinematic video from comic panels.
    
    Args:
        panels: List of panel data with keys:
            - image_url: URL or local path to panel image
            - narration: Text for TTS narration
            - dialogue: Optional dialogue text
        output_path: Output video file path
        background_music_path: Optional background music file
        with_narration: Whether to generate TTS narration
        with_letterbox: Whether to add cinematic letterbox bars
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"generate_cinematic_video called with {len(panels)} panels, output_path={output_path}")
    
    # Check FFmpeg
    if not check_ffmpeg():
        logger.error("FFmpeg not installed or not found in PATH!")
        # Try to check what's available
        try:
            # import shutil  <-- Removed to prevent shadowing global import
            ffmpeg_path = shutil.which("ffmpeg")
            logger.error(f"shutil.which('ffmpeg') returned: {ffmpeg_path}")
        except Exception as e:
            logger.error(f"Could not check ffmpeg path: {e}")
        return False
    
    logger.info("FFmpeg check passed")
    
    work_dir = tempfile.mkdtemp(prefix="comic_video_")
    logger.info(f"Working directory created: {work_dir}")
    
    # Initialize variable to prevent UnboundLocalError
    final_with_audio = None
    concatenated_video = None
    
    try:
        # Step 1: Download and prepare panel images
        logger.info("Step 1: Preparing panel images...")
        panel_files = []
        panel_durations = []
        audio_files = []
        
        for i, panel in enumerate(panels):
            # Download/copy image
            img_url = panel.get("image_url", "")
            img_path = os.path.join(work_dir, f"panel_{i:02d}_raw.png")
            prepared_path = os.path.join(work_dir, f"panel_{i:02d}.png")
            
            if img_url.startswith("http"):
                if not download_image(img_url, img_path):
                    logger.warning(f"Skipping panel {i}: download failed")
                    continue
            elif os.path.exists(img_url):
                shutil.copy(img_url, img_path)
            else:
                logger.warning(f"Skipping panel {i}: invalid image path")
                continue
            
            # Prepare image for video
            prepare_panel_image(img_path, prepared_path)
            panel_files.append(prepared_path)
            
            # Step 2: Generate narration audio
            duration = PANEL_DURATION
            if with_narration:
                narration_text = panel.get("narration", "")
                dialogue = panel.get("dialogue", [])
                if isinstance(dialogue, list):
                    dialogue_text = " ".join([d.get("text", "") for d in dialogue if isinstance(d, dict)])
                else:
                    dialogue_text = str(dialogue) if dialogue else ""
                
                full_text = f"{narration_text} {dialogue_text}".strip()
                
                if full_text:
                    audio_path = os.path.join(work_dir, f"narration_{i:02d}.mp3")
                    audio_duration = generate_tts_audio(full_text, audio_path)
                    
                    if audio_duration:
                        # Add buffer after narration
                        duration = max(MIN_PANEL_DURATION, min(MAX_PANEL_DURATION, audio_duration + 1.0))
                        audio_files.append(audio_path)
                    else:
                        audio_files.append(None)
                else:
                    audio_files.append(None)
            else:
                audio_files.append(None)
            
            panel_durations.append(duration)
            logger.info(f"Panel {i}: duration={duration:.1f}s")
        
        if not panel_files:
            logger.error("No valid panels to process!")
            return False
        
        # Step 3: Create individual panel videos with Ken Burns effect
        logger.info("Step 2: Creating panel videos with Ken Burns effect...")
        panel_videos = []
        
        for i, (panel_path, duration) in enumerate(zip(panel_files, panel_durations)):
            panel_video = os.path.join(work_dir, f"panel_video_{i:02d}.mp4")
            
            # Ken Burns filter
            kb_filter = create_ken_burns_filter(i, duration)
            
            # Add letterbox bars if requested
            if with_letterbox:
                letterbox_filter = f",drawbox=x=0:y=0:w=iw:h=ih*0.05:c=black:t=fill,drawbox=x=0:y=ih*0.95:w=iw:h=ih*0.05:c=black:t=fill"
            else:
                letterbox_filter = ""
            
            # Add subtle vignette for cinematic look
            vignette_filter = ",vignette=PI/4"
            
            # Combine filters
            full_filter = f"{kb_filter}{letterbox_filter}{vignette_filter}"
            
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", panel_path,
                "-filter_complex", full_filter,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                panel_video
            ]
            
            
            logger.info(f"Generating panel {i} video (Duration: {duration}s)")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                stderr_head = result.stderr[:500]
                stderr_tail = result.stderr[-500:] if len(result.stderr) > 500 else ""
                logger.warning(f"Panel {i} video creation failed with Ken Burns.\nCMD: {' '.join(cmd)}\nSTDERR Head: {stderr_head}\nSTDERR Tail: {stderr_tail}")
                
                # FALLBACK: Generate static video without Ken Burns
                logger.info(f"Retrying Panel {i} with static video fallback...")
                
                # Letterbox only if requested
                filters = []
                if with_letterbox:
                    filters.append(f"drawbox=x=0:y=0:w=iw:h=ih*0.05:c=black:t=fill,drawbox=x=0:y=ih*0.95:w=iw:h=ih*0.05:c=black:t=fill")
                
                # Ensure dimensions are even
                filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
                
                filter_str = ",".join(filters) if filters else "null"
                
                cmd_fallback = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", panel_path,
                    "-vf", filter_str,
                    "-t", str(duration),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    panel_video
                ]
                
                res_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=60)
                if res_fallback.returncode != 0:
                     logger.error(f"Panel {i} static fallback also failed: {res_fallback.stderr}")
                     continue
                
                logger.info(f"Panel {i} generated successfully using fallback.")

            panel_videos.append(panel_video)
        
        if not panel_videos:
            logger.error("No panel videos created!")
            return False
        
        # Step 4: Concatenate videos with fade transitions
        logger.info("Step 3: Concatenating videos with transitions...")
        
        # Create concat filter with xfade transitions
        concat_file = os.path.join(work_dir, "concat_list.txt")
        
        # Build complex filter for xfade transitions
        inputs = " ".join([f"-i {v}" for v in panel_videos])
        
        # Calculate xfade offsets
        filter_parts = []
        current_offset = 0
        
        for i in range(len(panel_videos) - 1):
            if i == 0:
                filter_parts.append(f"[0][1]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={panel_durations[0] - TRANSITION_DURATION}[v01]")
                current_offset = panel_durations[0] - TRANSITION_DURATION
            else:
                prev = f"v{i-1:02d}{i:02d}" if i > 1 else "v01"
                next_label = f"v{i:02d}{i+1:02d}"
                current_offset += panel_durations[i] - TRANSITION_DURATION
                filter_parts.append(f"[{prev}][{i+1}]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={current_offset}[{next_label}]")
        
        if len(panel_videos) == 1:
            # Single panel, no transition needed
            concatenated_video = panel_videos[0]
        else:
            concatenated_video = os.path.join(work_dir, "concatenated.mp4")
            final_label = f"v{len(panel_videos)-2:02d}{len(panel_videos)-1:02d}" if len(panel_videos) > 2 else "v01"
            
            filter_complex = ";".join(filter_parts)
            
            cmd = ["ffmpeg", "-y"]
            for v in panel_videos:
                cmd.extend(["-i", v])
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", f"[{final_label}]",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                concatenated_video
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.warning(f"Concatenation failed, using simple concat: {result.stderr[:500]}")
                # Fallback to simple concat
                with open(concat_file, "w") as f:
                    for v in panel_videos:
                        f.write(f"file '{v}'\n")
                
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file,
                    "-c", "copy",
                    concatenated_video
                ]
                subprocess.run(cmd, capture_output=True, timeout=300)
        
        # Step 5: Add audio (narration + optional background music)
        logger.info("Step 4: Adding audio...")
        
        # Define final_with_audio path early to prevent UnboundLocalError
        final_with_audio = os.path.join(work_dir, "final_with_audio.mp4")
        
        # Concatenate all narration audio files
        valid_audio = [(f, d) for f, d in zip(audio_files, panel_durations) if f]
        
        if valid_audio and concatenated_video and os.path.exists(concatenated_video):
            # Create audio with correct timing
            audio_concat = os.path.join(work_dir, "narration_full.mp3")
            
            # Use silence between narrations to match panel timing
            audio_parts = []
            current_time = 0
            
            for i, (audio_path, duration) in enumerate(zip(audio_files, panel_durations)):
                if audio_path:
                    audio_parts.append(audio_path)
                
                # Add silence to fill remaining time for this panel
                audio_duration = get_audio_duration(audio_path) if audio_path else 0
                silence_duration = duration - audio_duration
                
                if silence_duration > 0.1:
                    silence_file = os.path.join(work_dir, f"silence_{i:02d}.mp3")
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-i", f"anullsrc=r=44100:cl=stereo",
                        "-t", str(silence_duration),
                        "-c:a", "libmp3lame",
                        silence_file
                    ], capture_output=True, timeout=30)
                    if audio_path:
                        audio_parts.append(silence_file)
            
            # Concat audio parts
            if audio_parts:
                audio_list_file = os.path.join(work_dir, "audio_list.txt")
                with open(audio_list_file, "w") as f:
                    for ap in audio_parts:
                        f.write(f"file '{ap}'\n")
                
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", audio_list_file,
                    "-c:a", "libmp3lame",
                    audio_concat
                ], capture_output=True, timeout=120)
            
            # Combine video with audio
            
            if os.path.exists(audio_concat):
                cmd = [
                    "ffmpeg", "-y",
                    "-i", concatenated_video,
                    "-i", audio_concat,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-shortest",
                    final_with_audio
                ]
                
                if background_music_path and os.path.exists(background_music_path):
                    # Mix narration with background music
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", concatenated_video,
                        "-i", audio_concat,
                        "-i", background_music_path,
                        "-filter_complex",
                        "[1:a]volume=1.0[narr];[2:a]volume=0.15[music];[narr][music]amix=inputs=2:duration=shortest[aout]",
                        "-map", "0:v:0",
                        "-map", "[aout]",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-shortest",
                        final_with_audio
                    ]
                
                subprocess.run(cmd, capture_output=True, timeout=300)
                
                if os.path.exists(final_with_audio):
                    shutil.copy(final_with_audio, output_path)
                else:
                    if concatenated_video and os.path.exists(concatenated_video):
                        shutil.copy(concatenated_video, output_path)
            else:
                if concatenated_video and os.path.exists(concatenated_video):
                    shutil.copy(concatenated_video, output_path)
        else:
            if concatenated_video and os.path.exists(concatenated_video):
                shutil.copy(concatenated_video, output_path)
        
        logger.info(f"Video generated successfully: {output_path}")
        return True
        
    except Exception as e:
        logger.exception(f"Video generation failed: {e}")
        return False
    
    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(work_dir)
        except Exception:
            pass


def generate_video_for_comic(
    comic_id: int,
    panels: List[Dict[str, Any]],
    output_dir: str = None,
    upload_to_gcs: bool = True
) -> Optional[str]:
    """
    High-level function to generate video for a comic.
    
    Args:
        comic_id: Comic ID
        panels: List of panel data
        output_dir: Output directory (default: temp dir)
        upload_to_gcs: Whether to upload to Google Cloud Storage
        
    Returns:
        GCS URL of video if upload_to_gcs=True, else local path. None if failed.
    """
    # Use temp directory to avoid disk space issues on Cloud Run
    work_dir = tempfile.mkdtemp(prefix=f"comic_video_{comic_id}_")
    output_path = os.path.join(work_dir, f"comic_{comic_id}_cinematic.mp4")
    
    # Default background music
    bg_music_path = Path(__file__).parent / "assets" / "music" / "dramatic.mp3"
    
    try:
        success = generate_cinematic_video(
            panels=panels,
            output_path=output_path,
            background_music_path=str(bg_music_path) if bg_music_path.exists() else None,
            with_narration=True,
            with_letterbox=True
        )
        
        if not success or not os.path.exists(output_path):
            logger.error(f"Video generation failed for comic {comic_id}")
            return None
        
        if upload_to_gcs:
            # Upload to Google Cloud Storage
            try:
                from app.services.google_storage_service import GoogleStorageService
                
                gcs_service = GoogleStorageService()
                gcs_path = f"comics/videos/{comic_id}/cinematic.mp4"
                
                # Read video file and upload
                with open(output_path, "rb") as f:
                    video_content = f.read()
                
                video_url = gcs_service.upload_file(
                    file_content=video_content,
                    destination_path=gcs_path,
                    content_type="video/mp4",
                    make_public=True
                )
                
                logger.info(f"Video uploaded to GCS: {video_url}")
                return video_url
                
            except Exception as upload_err:
                logger.exception(f"Failed to upload video to GCS: {upload_err}")
                # Return local path as fallback
                return output_path
        else:
            return output_path
            
    except Exception as e:
        logger.exception(f"Video generation error for comic {comic_id}: {e}")
        return None
        
    finally:
        # Cleanup temp directory
        try:
            if upload_to_gcs and os.path.exists(work_dir):
                shutil.rmtree(work_dir)
        except Exception:
            pass


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate cinematic video from comic panels")
    parser.add_argument("--panels-json", required=True, help="JSON file with panel data")
    parser.add_argument("--output", required=True, help="Output video path")
    parser.add_argument("--no-narration", action="store_true", help="Skip TTS narration")
    parser.add_argument("--no-letterbox", action="store_true", help="Skip letterbox bars")
    
    args = parser.parse_args()
    
    with open(args.panels_json, "r") as f:
        panels = json.load(f)
    
    success = generate_cinematic_video(
        panels=panels,
        output_path=args.output,
        with_narration=not args.no_narration,
        with_letterbox=not args.no_letterbox
    )
    
    sys.exit(0 if success else 1)
