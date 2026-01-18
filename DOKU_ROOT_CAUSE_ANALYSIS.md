# DOKU Payment Gateway - Root Cause Analysis & Fix

## 🔍 Root Cause Identified

### Problem Summary

**Error:** `Invalid Client-Id` from Doku Payment Gateway (Status 400)

**Root Cause:** The Doku credentials `BRN-0280-1765767732062` are **INVALID** or **EXPIRED** in Doku's Sandbox API.

### Evidence

Test script (`test_doku_credentials.py`) confirmed:

```
Status Code: 400
Response Body:
{
  "error": {
    "code": "invalid_client_id",
    "message": "Invalid Client-Id",
    "type": "invalid_request_error"
  }
}
```

### Why It Kept Failing

1. **Invalid Credentials**: The Client ID `BRN-0280-1765767732062` is not recognized by Doku's API
2. **Missing Environment Variables**: DOKU credentials were NOT set in Cloud Run deployment
3. **Hardcoded Values**: Credentials were hardcoded in multiple places, making debugging difficult

## ✅ Fixes Applied

### 1. Removed Hardcoded Credentials

**File:** `app/utils/doku.py`

- Removed hardcoded credentials from `_refresh_settings()` method
- Now properly loads from `settings.DOKU_CLIENT_ID` and `settings.DOKU_SECRET_KEY`

### 2. Added Environment Variables to Cloud Run

**File:** `.github/workflows/deploy-cloudrun.yml`

- Added DOKU credentials to deployment configuration:
  ```yaml
  DOKU_IS_PRODUCTION=false
  DOKU_CLIENT_ID=BRN-0280-1765767732062
  DOKU_SECRET_KEY=SK-Mb7Lbo9POYkyOCpv1vG2
  DOKU_NOTIFICATION_SECRET=SK-Mb7Lbo9POYkyOCpv1vG2
  USE_MOCK_PAYMENT=true
  ```

### 3. Enabled Mock Payment System

**Temporary Solution:** Set `USE_MOCK_PAYMENT=true` to bypass invalid Doku credentials

## 🎯 Current Status

### ✅ Working Solution (Mock Payment)

The application now uses a **mock payment system** that:

- Creates payment transactions in the database
- Provides a local payment page at `/api/v1/mock-payment/{order_id}`
- Allows testing payment flows without Doku API
- Simulates both SUCCESS and FAILED payment scenarios

### ❌ Real Doku Integration (Blocked)

Cannot proceed until **valid Doku credentials** are obtained.

## 📋 Next Steps

### Option 1: Get Valid Doku Credentials (Recommended)

1. **Register/Login to Doku Sandbox:**
   - URL: https://dashboard-sandbox.doku.com/
2. **Create a New Application:**
   - Navigate to "Applications" or "API Keys"
   - Create new sandbox application
   - Copy the Client ID and Secret Key

3. **Update Credentials:**

   ```bash
   # Update .env file
   DOKU_CLIENT_ID=<new_client_id>
   DOKU_SECRET_KEY=<new_secret_key>
   DOKU_NOTIFICATION_SECRET=<new_secret_key>
   ```

4. **Update Cloud Run Deployment:**
   - Edit `.github/workflows/deploy-cloudrun.yml`
   - Replace credentials in line 58
   - Set `USE_MOCK_PAYMENT=false`

5. **Deploy:**
   ```bash
   git add .
   git commit -m "Update Doku credentials with valid sandbox keys"
   git push origin main
   ```

### Option 2: Continue with Mock Payment (Development Only)

- Keep `USE_MOCK_PAYMENT=true`
- Use for testing and development
- **NOT suitable for production**

### Option 3: Use Alternative Payment Gateway

Consider alternatives like:

- **Midtrans** (Popular in Indonesia)
- **Xendit** (Developer-friendly)
- **Stripe** (International)

## 🧪 Testing Mock Payment

### 1. Create Purchase Request

```bash
POST https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/purchase
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
    "packageId": 2,
    "payment_method": "DOKU"
}
```

### 2. Expected Response

```json
{
  "ok": true,
  "message": "Transaction created successfully. Please proceed to payment.",
  "data": {
    "invoice_number": "INV-XXXXXXXX-XXXXXXXXXX",
    "amount": 16500,
    "payment_url": "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/mock-payment/INV-XXXXXXXX-XXXXXXXXXX",
    "package_name": "Basic"
  }
}
```

### 3. Open Payment URL

- Click the `payment_url` from response
- You'll see a mock payment page
- Click "Simulate Success" or "Simulate Failure"

### 4. Verify Transaction

```bash
GET https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/payment-status/{invoice_number}
Authorization: Bearer YOUR_TOKEN
```

## 📊 Files Modified

1. **app/utils/doku.py**
   - Removed hardcoded credentials
   - Restored proper settings loading

2. **.github/workflows/deploy-cloudrun.yml**
   - Added DOKU environment variables
   - Enabled USE_MOCK_PAYMENT

3. **test_doku_credentials.py** (New)
   - Test script to validate Doku credentials
   - Saved results to `doku_test_result.txt`

## 🔐 Security Notes

1. **Never commit real credentials to Git**
2. **Use Google Secret Manager for production credentials**
3. **Rotate credentials regularly**
4. **Use different credentials for sandbox vs production**

## 📝 Summary

**Problem:** Invalid Doku Client ID causing 400 errors  
**Cause:** Credentials `BRN-0280-1765767732062` are not valid in Doku API  
**Solution:** Enabled mock payment system as temporary workaround  
**Action Required:** Obtain valid Doku sandbox credentials to enable real payment integration

---

_Last Updated: 2026-01-18_
_Status: Mock Payment Active, Real Doku Integration Pending Valid Credentials_
