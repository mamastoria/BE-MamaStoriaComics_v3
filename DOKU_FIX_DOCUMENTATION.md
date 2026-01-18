# Doku Payment Gateway Error - Fix Documentation

## Problem Summary

**Error Message:**

```json
{
  "detail": "Payment gateway error: Unknown error from Doku Payment Gateway. Status: 400, Response: {\"error\":{\"code\":\"invalid_client_id\",\"message\":\"Invalid Client-Id\",\"type\":\"invalid_request_error\"}}"
}
```

**Root Cause:**
The application was configured to use **production mode** (`DOKU_IS_PRODUCTION=true`) but was using **sandbox credentials** (`BRN-0280-1765767732062`). Doku's production API rejects sandbox credentials with an "Invalid Client-Id" error.

## What Was Changed

### File: `.env` (Line 42)

**Before:**

```bash
DOKU_IS_PRODUCTION=true
```

**After:**

```bash
DOKU_IS_PRODUCTION=false
```

This change ensures the application connects to Doku's **sandbox API** (`https://api-sandbox.doku.com`) instead of the production API (`https://api.doku.com`), which matches your sandbox credentials.

## How It Works

The Doku client initialization in `app/utils/doku.py` (lines 11-16):

```python
class DokuClient:
    def __init__(self):
        self.client_id = settings.DOKU_CLIENT_ID
        self.secret_key = settings.DOKU_SECRET_KEY
        self.is_production = settings.DOKU_IS_PRODUCTION
        self.base_url = "https://api.doku.com" if self.is_production else "https://api-sandbox.doku.com"
```

When `DOKU_IS_PRODUCTION=false`:

- Base URL: `https://api-sandbox.doku.com`
- Accepts sandbox credentials: `BRN-0280-1765767732062`

When `DOKU_IS_PRODUCTION=true`:

- Base URL: `https://api.doku.com`
- Requires production credentials (different from sandbox)

## Testing the Fix

### 1. Restart Your Application

If running locally:

```bash
# Stop the current server (Ctrl+C)
# Restart it
uvicorn app.main:app --reload
```

If deployed on Cloud Run, redeploy or restart the service to pick up the new environment variable.

### 2. Test the Purchase Endpoint

```bash
POST https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/purchase
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
    "packageId": 2,
    "payment_method": "DOKU"
}
```

**Expected Response (Success):**

```json
{
  "ok": true,
  "message": "Transaction created successfully. Please proceed to payment.",
  "data": {
    "invoice_number": "INV-XXXXXXXX-XXXXXXXXXX",
    "amount": 16500,
    "payment_url": "https://sandbox.doku.com/checkout/...",
    "package_name": "Basic"
  }
}
```

### 3. Verify the Payment URL

The `payment_url` in the response should start with:

- ✅ **Sandbox:** `https://sandbox.doku.com/...`
- ❌ **Production:** `https://checkout.doku.com/...`

## Next Steps for Production

When you're ready to go live with real payments:

### 1. Get Production Credentials from Doku

Contact Doku support to obtain:

- Production Client ID (format: `BRN-XXXX-XXXXXXXXXXXXX`)
- Production Secret Key (format: `SK-XXXXXXXXXXXXXXXXXX`)
- Production Notification Secret

### 2. Update `.env` for Production

```bash
DOKU_CLIENT_ID=YOUR_PRODUCTION_CLIENT_ID
DOKU_SECRET_KEY=YOUR_PRODUCTION_SECRET_KEY
DOKU_NOTIFICATION_SECRET=YOUR_PRODUCTION_NOTIFICATION_SECRET
DOKU_IS_PRODUCTION=true
```

### 3. Update Cloud Run Environment Variables

If deployed on Cloud Run, update the secrets/environment variables:

```bash
gcloud run services update nanobanana-backend \
  --update-env-vars DOKU_IS_PRODUCTION=true \
  --update-secrets DOKU_CLIENT_ID=doku-client-id:latest \
  --update-secrets DOKU_SECRET_KEY=doku-secret-key:latest
```

## Alternative: Use Mock Payment (Development Only)

For local development without Doku API calls, you can use the mock payment system:

**In `.env`:**

```bash
USE_MOCK_PAYMENT=true
```

This will generate a local payment page at:

```
http://localhost:8000/api/v1/mock-payment/INV-XXXXXXXX
```

Where you can simulate successful or failed payments without hitting Doku's API.

## Troubleshooting

### Still Getting "Invalid Client-Id"?

1. **Verify credentials are correct:**
   - Check with Doku dashboard that `BRN-0280-1765767732062` is a valid sandbox client ID
   - Ensure the secret key matches

2. **Check environment variable loading:**

   ```python
   # Add debug logging in app/utils/doku.py
   print(f"Doku Client ID: {self.client_id}")
   print(f"Is Production: {self.is_production}")
   print(f"Base URL: {self.base_url}")
   ```

3. **Restart the application** to ensure `.env` changes are loaded

4. **Check Cloud Run environment variables** if deployed (they override `.env`)

### Error: "Invalid Signature"

This means credentials are accepted but the signature calculation is wrong:

- Verify `DOKU_SECRET_KEY` matches exactly (no extra spaces)
- Check that `DOKU_NOTIFICATION_SECRET` is set correctly

## Summary

✅ **Fixed:** Changed `DOKU_IS_PRODUCTION=false` to match sandbox credentials  
✅ **Result:** Application now connects to sandbox API with sandbox credentials  
✅ **Next:** Test the purchase endpoint and verify payment URL generation

For production deployment, obtain production credentials from Doku and update the environment variables accordingly.
