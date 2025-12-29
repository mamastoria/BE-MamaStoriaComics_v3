
import requests
import json
import sys

# URL Backend Anda
BASE_URL = "https://nanobanana-backend-1089713441636.asia-southeast2.run.app"

# Token dari login terakhir Anda (yang gagal di profile)
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsImV4cCI6MTc2NzAyMDQxNiwidHlwZSI6ImFjY2VzcyJ9.61j43ZWIJM-KgG-TqtiJAhnYFCe1vW87oL43-D3my1g"

def check_token():
    print("=== MULTI-STEP DIAGNOSTIC TOOL ===")
    
    # 1. Cek Endpoint Debug (Pastikan sudah deploy)
    debug_url = f"{BASE_URL}/api/v1/auth/debug-token"
    print(f"\n1. Menghubungi endpoint debug: {debug_url}")
    
    try:
        r = requests.post(debug_url, json={"token": TOKEN}, timeout=10)
        
        if r.status_code == 404:
            print("❌ GAGAL: Endpoint debug belum ditemukan.")
            print("   Tolong DEPLOY ulang kode backend (app/api/auth.py) ke Cloud Run.")
            return
            
        print(f"   Status Code: {r.status_code}")
        print("   Response Server:")
        try:
            print(json.dumps(r.json(), indent=2))
        except:
            print(r.text)
            
    except Exception as e:
        print(f"❌ Error koneksi: {e}")

    # 2. Cek Endpoint Profile (Validasi ulang kondisi error)
    print(f"\n2. Mencoba akses profile biasa...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/api/v1/profile", headers=headers)
        print(f"   Status: {r.status_code}")
        print(f"   Response: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_token()
