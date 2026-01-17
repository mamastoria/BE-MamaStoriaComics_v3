"""
Check Failed Comics - Detailed Analysis
Identifies patterns and root causes of comic generation failures
"""
import requests
import json

BASE_URL = "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1"

def get_all_comics():
    """Get all comics from API"""
    try:
        response = requests.get(f"{BASE_URL}/comics", params={"limit": 200})
        response.raise_for_status()
        data = response.json()
        # Check if data is list or dict
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("data", {}).get("comics", [])
        return []
    except Exception as e:
        print(f"Error fetching comics: {e}")
        import traceback
        traceback.print_exc()
        return []

def analyze_failed_comics():
    """Analyze failed comics to identify patterns"""
    
    print("\n" + "="*70)
    print("FAILED COMICS ANALYSIS")
    print("="*70 + "\n")
    
    comics = get_all_comics()
    
    if not comics:
        print("No comics data retrieved")
        return
    
    # Filter failed comics
    failed = [c for c in comics if c.get("draft_job_status") == "FAILED"]
    
    print(f"Total Comics: {len(comics)}")
    print(f"Failed Comics: {len(failed)}\n")
    
    if not failed:
        print("✅ No failed comics found!")
        return
    
    print("="*70)
    print("FAILED COMICS DETAILS:")
    print("="*70 + "\n")
    
    for i, comic in enumerate(failed, 1):
        print(f"{i}. Comic #{comic.get('comic_id')} - {comic.get('title', 'Untitled')}")
        print(f"   Status: {comic.get('draft_job_status')}")
        print(f"   Has Cover: {'✅' if comic.get('cover_url') else '❌'}")
        print(f"   Has Video: {'✅' if comic.get('preview_video_url') else '❌'}")
        print(f"   Locked By: {comic.get('locked_by', 'None')}")
        
        # Get detailed debug info
        try:
            debug_resp = requests.get(f"{BASE_URL}/jobs/debug/{comic.get('comic_id')}")
            if debug_resp.status_code == 200:
                debug = debug_resp.json()
                print(f"   Script Retries: {debug.get('script_retry_count', 0)}")
                print(f"   Image Retries: {debug.get('image_retry_count', 0)}")
                print(f"   Video Retries: {debug.get('video_retry_count', 0)}")
                
                if debug.get('last_error_message'):
                    print(f"   Last Error: {debug.get('last_error_message')}")
                if debug.get('last_error_at'):
                    print(f"   Error Time: {debug.get('last_error_at')}")
        except Exception as e:
            print(f"   (Could not fetch debug info: {e})")
        
        print()
    
    # Analyze patterns
    print("="*70)
    print("FAILURE PATTERNS:")
    print("="*70 + "\n")
    
    has_cover = sum(1 for c in failed if c.get('cover_url'))
    has_video = sum(1 for c in failed if c.get('preview_video_url'))
    locked = sum(1 for c in failed if c.get('locked_by'))
    
    print(f"✅ Has Cover Image: {has_cover}/{len(failed)}")
    print(f"✅ Has Video: {has_video}/{len(failed)}")
    print(f"🔒 Currently Locked: {locked}/{len(failed)}")
    
    # Failure stage analysis
    no_cover = len(failed) - has_cover
    cover_no_video = has_cover - has_video
    
    print(f"\n📊 Failure Stages:")
    print(f"   - Failed during image generation: {no_cover}")
    print(f"   - Failed during video generation: {cover_no_video}")
    print(f"   - Failed at other stage: {len(failed) - no_cover - cover_no_video}")
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS:")
    print("="*70 + "\n")
    
    if no_cover > 0:
        print(f"⚠️  {no_cover} comic(s) failed during IMAGE GENERATION")
        print("   → Check render worker logs")
        print("   → Verify DALL-E API quota/credits")
        print("   → Check image cropping process\n")
    
    if cover_no_video > 0:
        print(f"⚠️  {cover_no_video} comic(s) failed during VIDEO GENERATION")
        print("   → Check video worker service status")
        print("   → Verify FFmpeg installation")
        print("   → Check Cloud Tasks queue")
        print("   → Verify Google TTS API access\n")
    
    if locked > 0:
        print(f"⚠️  {locked} comic(s) still LOCKED (may be stuck)")
        print("   → Run unlock endpoint: POST /jobs/unlock-expired")
        print("   → Check worker health\n")
    
    print("💡 To retry failed comics:")
    print("   1. Fix the root cause issue")
    print("   2. Use: POST /jobs/retry/{comic_id}")
    print("   3. Or reset all: POST /jobs/reset-failed")
    print()

if __name__ == "__main__":
    analyze_failed_comics()
