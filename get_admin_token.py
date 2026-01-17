#!/usr/bin/env python3
"""
Generate JWT token untuk admin login
"""
import requests
import json

API_BASE = "http://127.0.0.1:8002/api/v1"

# Admin credentials
PHONE = "+6281234567890"
PASSWORD = "admin123"

print("🔐 Generating JWT Token for Admin...\n")

try:
    # Login request
    login_data = {
        "username": PHONE,
        "password": PASSWORD
    }
    
    response = requests.post(
        f"{API_BASE}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}\n")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        
        print("✅ Token Generated Successfully!\n")
        print("=" * 80)
        print("JWT TOKEN:")
        print("=" * 80)
        print(token)
        print("=" * 80)
        
        print("\n📋 How to use this token:\n")
        print("1. Add to Authorization header:")
        print(f'   Authorization: Bearer {token}\n')
        
        print("2. Example curl command:")
        print(f'   curl -X GET "http://127.0.0.1:8002/api/v1/admin/db/tables" \\')
        print(f'        -H "Authorization: Bearer {token}"\n')
        
        print("3. Save token for later use:")
        with open("admin_token.txt", "w") as f:
            f.write(token)
        print("   ✅ Token saved to: admin_token.txt\n")
        
    else:
        print("❌ Login failed!")
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
