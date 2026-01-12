import sys
import os
from pathlib import Path
from io import BytesIO
from PIL import Image
from google.cloud import storage
import concurrent.futures

# Add parent directory to path to import core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import core

# Configuration
COMIC_ID = "149"
BUCKET_NAME = "nanobanana-storage"

def fix_comic_149():
    print(f"Starting Fix for Comic {COMIC_ID} (Cropping & Panel Upload)...")
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
    except Exception as e:
        print(f"Error initializing GCS client: {e}")
        print("Make sure you have Google Cloud credentials configured.")
        return

    for part_no in [1, 2]:
        print(f"\nProcessing Part {part_no}...")
        
        # Try to find the grid image
        # Possible paths based on core.py patterns
        possible_paths = [
            f"comics/{COMIC_ID}/grid/part{part_no}.png",
            f"comics/grids/{COMIC_ID}/part{part_no}.png",
            f"comics/grid/{COMIC_ID}/part{part_no}.png"
        ]
        
        grid_blob = None
        found_path = ""
        
        for path in possible_paths:
            blob = bucket.blob(path)
            if blob.exists():
                grid_blob = blob
                found_path = path
                break
        
        if not grid_blob:
            print(f"❌ Grid image for Part {part_no} NOT found in bucket.")
            print(f"Checked paths: {possible_paths}")
            continue
            
        print(f"✅ Found grid image at: gs://{BUCKET_NAME}/{found_path}")
        
        try:
            # Download Grid
            print("Downloading grid image...")
            img_bytes = grid_blob.download_as_bytes()
            grid_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            
            # Crop Panels (Manual Fallback Logic)
            print("Cropping into 9 panels (Manual 3x3 split)...")
            panels = core.split_grid_3x3(grid_img)
            
            if len(panels) != 9:
                print(f"❌ Error: Expected 9 panels, got {len(panels)}")
                continue
                
            # Upload Panels
            print(f"Uploading {len(panels)} panels to GCS...")
            # We use core.upload_panels_parallel which handles the correct path
            # It puts them in comics/panels/{job_id}/part{part_no}_panel{i}.png
            panel_urls = core.upload_panels_parallel(COMIC_ID, part_no, panels)
            
            cleaned_urls = [u for u in panel_urls if u]
            print(f"✅ Successfully uploaded {len(cleaned_urls)} panels.")
            # for u in cleaned_urls:
            #     print(f"  - {u}")
                
        except Exception as e:
            print(f"❌ Error processing Part {part_no}: {e}")
            import traceback
            traceback.print_exc()

    print("\n---------------------------------------------------")
    print("Fix complete. Check if panels appear in the App/Dashboard.")
    print("If successful, you can regenerate the video via the Admin Dashboard or API.")

if __name__ == "__main__":
    fix_comic_149()
