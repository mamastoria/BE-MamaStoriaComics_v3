
import cv2
import numpy as np
from PIL import Image
import os

def smart_panel_crop(image_path, output_dir="debug_output"):
    """
    Mendeteksi dan memotong panel komik 3x3 secara otomatis menggunakan OpenCV.
    Fallback ke metode manual jika gagal mendeteksi 9 panel.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Baca gambar
    img_cv = cv2.imread(image_path)
    if img_cv is None:
        print(f"Error: Tidak bisa membaca gambar {image_path}")
        return

    original_h, original_w = img_cv.shape[:2]
    
    # 2. Preprocessing: Grayscale & Thresholding
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Adaptive thresholding untuk mengatasi variasi pencahayaan/warna
    # Invert (binary_inv) agar garis panel (biasanya gelap) menjadi putih (terdeteksi)
    # Block size 11, C 2
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)

    # 3. Morphological Operations: Membersihkan noise
    # Kernel horizontal dan vertikal untuk mempertegas garis kotak
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1)) # Perkuat garis horizontal
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20)) # Perkuat garis vertikal
    
    # Gabungkan garis yang terputus-putus
    detect_h = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h, iterations=2)
    detect_v = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v, iterations=2)
    
    # Gabungkan kembali
    final_mask = cv2.addWeighted(detect_h, 0.5, detect_v, 0.5, 0)
    _, final_mask = cv2.threshold(final_mask, 0, 255, cv2.THRESH_BINARY) # Binarize lagi

    # Simpan mask untuk debug
    cv2.imwrite(f"{output_dir}/debug_mask.png", final_mask)

    # 4. Find Contours
    contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 5. Filter Contours (Cari kandidat panel)
    panel_rects = []
    min_area = (original_w * original_h) * 0.03 # Minimal 3% dari total area (agar tidak deteksi titik kecil)
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        
        # Validasi rasio aspek (panel biasanya kotak atau persegi panjang wajar)
        aspect_ratio = w / float(h)
        
        if area > min_area and 0.5 < aspect_ratio < 2.0:
            panel_rects.append((x, y, w, h))

    print(f"Deteksi awal menemukan {len(panel_rects)} kontur potensial.")

    # 6. Sorting Panel (Kiri ke Kanan, Atas ke Bawah)
    # Ini agak tricky karena urutan contours random.
    # Kita harus sort berdasarkan Y (baris), lalu X (kolom).
    
    # Toleransi baris (pixel) agar panel yang sedikit miring tetap dianggap satu baris
    ROW_TOLERANCE = 50 
    
    def sort_panels(rects):
        # Sort by Y first (top to bottom)
        rects.sort(key=lambda r: r[1])
        
        # Group into rows
        rows = []
        current_row = []
        last_y = -999
        
        for r in rects:
            y = r[1]
            if not current_row:
                current_row.append(r)
                last_y = y
            else:
                # Jika Y beda tipis, anggap satu baris
                if abs(y - last_y) < ROW_TOLERANCE:
                    current_row.append(r)
                else:
                    # Baris baru
                    # Sort row sebelumnya by X
                    current_row.sort(key=lambda x: x[0])
                    rows.append(current_row)
                    current_row = [r]
                    last_y = y
        
        if current_row:
            current_row.sort(key=lambda x: x[0])
            rows.append(current_row)
            
        # Flatten
        sorted_rects = [item for sublist in rows for item in sublist]
        return sorted_rects

    final_panels = sort_panels(panel_rects)
    
    # 7. Validasi: Apakah jumlahnya 9?
    if len(final_panels) == 9:
        print("✅ SUKSES: Mendeteksi tepat 9 panel secara otomatis (OpenCV).")
        method = "opencv"
    else:
        print(f"⚠️ PERINGATAN: Mendeteksi {len(final_panels)} panel (bukan 9). Fallback ke Manual Grid.")
        # Fallback logic: Buat rect manual seperti Pillow
        final_panels = []
        cell_w = original_w // 3
        cell_h = original_h // 3
        for r in range(3):
            for c in range(3):
                final_panels.append((c*cell_w, r*cell_h, cell_w, cell_h))
        method = "fallback_manual"

    # 8. Cropping & Saving
    pil_image = Image.open(image_path)
    # Margin opsional untuk membuang garis hitam (sedikit "zoom in" ke dalam panel)
    MARGIN_PCT = 0.02 # 2% crop kedalam
    
    for i, (x, y, w, h) in enumerate(final_panels):
        # Apply margin (hanya jika OpenCV, kalau manual pake margin manual)
        if method == "opencv":
            m_x = int(w * MARGIN_PCT)
            m_y = int(h * MARGIN_PCT)
            crop_rect = (x + m_x, y + m_y, x + w - m_x, y + h - m_y)
            
            # Draw rectangle on debug image
            cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(img_cv, str(i+1), (x+10, y+50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
        else:
            # Manual grid logic (sama kayak Pillow)
            crop_rect = (x, y, x + w, y + h) 
        
        # Crop PIL
        cropped = pil_image.crop(crop_rect)
        save_path = f"{output_dir}/panel_{i+1}_{method}.png"
        cropped.save(save_path)
        print(f"Saved: {save_path}")

    # Simpan outline visualisasi
    cv2.imwrite(f"{output_dir}/debug_detection.png", img_cv)
    print(f"Debug visual saved to {output_dir}/debug_detection.png")

if __name__ == "__main__":
    # Ganti dengan path gambar komik grid Anda yang ada di folder ini
    # Saya akan cari file PNG random di folder exports kalau ada
    target_img = "test_grid.png" 
    
    # Check if exists, if not finding in exports
    if not os.path.exists(target_img):
        # Try to find one in exports
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(".png") and "grid" in file:
                    target_img = os.path.join(root, file)
                    break
    
    if os.path.exists(target_img):
        print(f"Running test on: {target_img}")
        smart_panel_crop(target_img)
    else:
        print("No test image found. Please upload a 'grid' png image or rename one to test_grid.png")
