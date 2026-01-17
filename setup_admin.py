#!/usr/bin/env python3
"""
Setup script to create admin user
Runs independently without requiring Cloud SQL Proxy
"""
import subprocess
import json
import sys

# Admin credentials
PHONE = "0811814563"
PASSWORD = "admin123"
FULL_NAME = "Founder Mamastoria"
BACKEND_URL = "https://nanobanana-backend-1089713441636.us-central1.run.app"

print("🔐 Creating Admin User via Backend API...")
print(f"   Phone: {PHONE}")
print(f"   Name: {FULL_NAME}")
print(f"   Password: {PASSWORD}\n")

# Build URL with query parameters
url = f"{BACKEND_URL}/api/v1/setup/create-initial-admin"
params = {
    "phone_number": PHONE,
    "password": PASSWORD,
    "full_name": FULL_NAME
}

# Build query string
query_string = "&".join([f"{k}={v}" for k, v in params.items()])
full_url = f"{url}?{query_string}"

try:
    # Use curl via PowerShell
    cmd = [
        "powershell",
        "-Command",
        f"$response = Invoke-WebRequest -Uri '{full_url}' -Method POST -ErrorAction Stop; $response.Content"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if result.returncode == 0:
        print("✅ Admin user created successfully!\n")
        print("=" * 80)
        print("CREDENTIALS:")
        print("=" * 80)
        print(f"Phone: {PHONE}")
        print(f"Password: {PASSWORD}")
        print(f"Name: {FULL_NAME}")
        print("=" * 80)
        print("\n📱 You can now login with these credentials")
        print(f"🌐 Backend: {BACKEND_URL}")
        
        # Try to parse response
        try:
            response_json = json.loads(result.stdout)
            print(f"\n📋 Response: {json.dumps(response_json, indent=2)}")
        except:
            print(f"\n📋 Response: {result.stdout}")
    else:
        print(f"❌ Failed to create admin user")
        print(f"Error: {result.stderr}")
        sys.exit(1)
        
except subprocess.TimeoutExpired:
    print("❌ Request timed out")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
