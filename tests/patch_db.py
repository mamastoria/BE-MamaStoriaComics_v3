
import requests
import os

BASE_URL = os.getenv("API_BASE_URL", "https://nanobanana-backend-1089713441636.us-central1.run.app")

print(f"Triggering DB Patch at {BASE_URL}...")

try:
    resp = requests.post(f"{BASE_URL}/api/v1/admin/db-patch-timing", timeout=30)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Failed: {e}")
