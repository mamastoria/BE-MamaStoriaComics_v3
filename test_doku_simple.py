import requests
import json

# Test simple GET request to check if credentials work at all
client_id = "BRN-0280-1765767732062"

print("Testing Doku API accessibility...")
print("=" * 60)

# Test 1: Sandbox endpoint
print("\n1. Testing SANDBOX endpoint...")
try:
    resp = requests.get("https://api-sandbox.doku.com", timeout=5)
    print("   Sandbox API reachable: YES (Status: {})".format(resp.status_code))
except Exception as e:
    print("   Sandbox API reachable: NO ({})".format(str(e)))

# Test 2: Production endpoint  
print("\n2. Testing PRODUCTION endpoint...")
try:
    resp = requests.get("https://api.doku.com", timeout=5)
    print("   Production API reachable: YES (Status: {})".format(resp.status_code))
except Exception as e:
    print("   Production API reachable: NO ({})".format(str(e)))

# Test 3: Check Client ID format
print("\n3. Checking Client ID format...")
print("   Client ID: {}".format(client_id))
print("   Length: {}".format(len(client_id)))
print("   Format: {}".format("BRN-XXXX-XXXXXXXXXXXXX"))
if client_id.startswith("BRN-"):
    print("   Prefix: VALID (BRN-)")
else:
    print("   Prefix: INVALID (should start with BRN-)")

# Test 4: Recommendation
print("\n" + "=" * 60)
print("RECOMMENDATION:")
print("=" * 60)
print("""
Karena Client ID dan Secret Key sudah dikonfirmasi benar,
tapi Doku API tetap reject dengan 'invalid_client_id', 
kemungkinan besar masalahnya adalah:

1. Account Doku belum diaktivasi/verified
2. Client ID tidak punya akses ke Checkout API
3. Ada whitelist IP yang perlu dikonfigurasi
4. Client ID untuk Production, bukan Sandbox

SOLUSI TERBAIK SAAT INI:
========================
1. Gunakan Mock Payment (sudah aktif) untuk development
2. Hubungi Doku Support untuk verifikasi account
3. Atau coba payment gateway alternatif (Midtrans/Xendit)

Mock Payment URL setelah deploy:
https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/mock-payment/{order_id}
""")
print("=" * 60)
