import functions_framework
import cv2
import numpy as np
import requests
import json
import os
from PIL import Image
from io import BytesIO
from google.cloud import storage

# Inisialisasi GCS Client (global agar reuse connection)
storage_client = storage.Client()

def download_image_as_cv2(url):
    """Download image from URL and convert to OpenCV format"""
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    
    # Read to PIL first to handle formats smoothly
    img_pil = Image.open(BytesIO(resp.content))
    img_pil = img_pil.convert("RGB") # Ensure RGB
    
    # Convert to Numpy/OpenCV
    img_np = np.array(img_pil)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    
    return img_cv, img_pil

def upload_to_gcs(bucket_name, blob_name, img_pil):
    """Upload PIL image directly to GCS and return public URL"""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    buf = BytesIO()
    img_pil.save(buf, format="PNG")
    blob.upload_from_string(buf.getvalue(), content_type="image/png")
    
    # Make public (optional, depending on your bucket policy)
    # blob.make_public() 
    # return blob.public_url
    
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

@functions_framework.http
def smart_crop(request):
    """HTTP Cloud Function entry point."""
    
    # CORS Headers
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600"
        }
        return ("", 204, headers)
    
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        req_json = request.get_json(silent=True)
        if not req_json or "image_url" not in req_json:
            return (json.dumps({"error": "Missing image_url"}), 400, headers)
        
        image_url = req_json.get("image_url")
        job_id = req_json.get("job_id", "temp_job")
        part_no = req_json.get("part_no", 1)
        bucket_name = req_json.get("bucket_name", "nanobanana-storage") # Default bucket
        
        print(f"Processing: Job={job_id}, Part={part_no}, URL={image_url}")

        # 1. Download & Prepare
        img_cv, img_pil = download_image_as_cv2(image_url)
        original_h, original_w = img_cv.shape[:2]
        
        panels_pil = []
        method = "manual"

        # 2. Try OpenCV Detection
        try:
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY_INV, 11, 2)
            
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
            kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
            detect_h = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h, iterations=2)
            detect_v = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v, iterations=2)
            final_mask = cv2.addWeighted(detect_h, 0.5, detect_v, 0.5, 0)
            _, final_mask = cv2.threshold(final_mask, 0, 255, cv2.THRESH_BINARY) 

            contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            panel_rects = []
            min_area = (original_w * original_h) * 0.03
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                ar = w / float(h)
                if area > min_area and 0.5 < ar < 2.0:
                    panel_rects.append((x, y, w, h))
            
            # Sort Logic
            if len(panel_rects) == 9:
                ROW_TOLERANCE = 50 
                panel_rects.sort(key=lambda r: r[1])
                rows = []
                current_row = []
                last_y = -999
                for r in panel_rects:
                    y = r[1]
                    if not current_row:
                        current_row.append(r)
                        last_y = y
                    else:
                        if abs(y - last_y) < ROW_TOLERANCE:
                            current_row.append(r)
                        else:
                            current_row.sort(key=lambda x: x[0])
                            rows.append(current_row)
                            current_row = [r]
                            last_y = y
                if current_row:
                    current_row.sort(key=lambda x: x[0])
                    rows.append(current_row)
                
                sorted_rects = [item for sublist in rows for item in sublist]
                
                if len(sorted_rects) == 9:
                    method = "opencv"
                    MARGIN_PCT = 0.02
                    for (x, y, w, h) in sorted_rects:
                        m_x = int(w * MARGIN_PCT)
                        m_y = int(h * MARGIN_PCT)
                        crop_rect = (x + m_x, y + m_y, x + w - m_x, y + h - m_y)
                        panels_pil.append(img_pil.crop(crop_rect))

        except Exception as e:
            print(f"OpenCV failed: {e}")
        
        # 3. Fallback Manual
        if method == "manual":
            print("Using Fallback Manual Crop")
            panels_pil = [] # Reset
            cell_w = img_pil.width // 3
            cell_h = img_pil.height // 3
            INNER_M = 0.035
            OUTER_M = 0.05
            for r in range(3):
                for c in range(3):
                    bl = c * cell_w
                    bt = r * cell_h
                    br = bl + cell_w
                    bb = bt + cell_h
                    
                    ml = OUTER_M if c == 0 else INNER_M
                    mt = OUTER_M if r == 0 else INNER_M
                    mr = OUTER_M if c == 2 else INNER_M
                    mb = OUTER_M if r == 2 else INNER_M
                    
                    l = bl + int(cell_w * ml)
                    t = bt + int(cell_h * mt)
                    ri = br - int(cell_w * mr)
                    bo = bb - int(cell_h * mb)
                    
                    # Safer crop
                    if l>=ri: l=bl
                    if t>=bo: t=bt
                    
                    panels_pil.append(img_pil.crop((l, t, ri, bo)))

        # 4. Upload Result Panels
        panel_urls = []
        for i, p_img in enumerate(panels_pil):
             # Format path: comics/panels/{job_id}/part{part_no}_panel{i}.png
            blob_path = f"comics/panels/{job_id}/part{part_no}_panel{i}.png"
            url = upload_to_gcs(bucket_name, blob_path, p_img)
            panel_urls.append(url)
            
        return (json.dumps({
            "ok": True,
            "method": method,
            "panel_urls": panel_urls
        }), 200, headers)

    except Exception as e:
        print(f"Global Error: {e}")
        return (json.dumps({"ok": False, "error": str(e)}), 500, headers)
