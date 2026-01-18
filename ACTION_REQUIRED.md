# Doku Payment Gateway Fix - Action Required

## 🚨 Current Status

**Error:** Still getting "Invalid Client-Id" from Doku Payment Gateway  
**Cause:** Cloud Run service is using wrong environment variable  
**Solution:** Update Cloud Run environment variable

---

## ✅ What We've Fixed (Local)

1. ✅ Updated `.env`: `DOKU_IS_PRODUCTION=false`
2. ✅ Updated `cloudbuild.yaml`: Added `DOKU_IS_PRODUCTION=false`
3. ✅ Added debug endpoint: `/api/v1/subscriptions/debug/doku-config`

---

## 🎯 ACTION REQUIRED: Update Cloud Run

### **RECOMMENDED: Use Google Cloud Console (No CLI needed)**

#### Step-by-Step Instructions:

1. **Open Cloud Run Console:**
   - Go to: https://console.cloud.google.com/run?project=nanobananacomic-482111
   - Click on service: `nanobanana-backend-us`

2. **Edit & Deploy New Revision:**
   - Click the **"EDIT & DEPLOY NEW REVISION"** button (top of page)

3. **Add Environment Variable:**
   - Scroll down to **"Variables & Secrets"** section
   - Under **"Environment Variables"**, click **"+ ADD VARIABLE"**
   - Enter:
     - **Name:** `DOKU_IS_PRODUCTION`
     - **Value:** `false`

4. **Deploy:**
   - Scroll to bottom
   - Click **"DEPLOY"** button
   - Wait 2-3 minutes for deployment

5. **Verify Deployment:**
   - Once deployed, test the debug endpoint:

   ```
   GET https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/debug/doku-config
   ```

   **Expected Response:**

   ```json
   {
     "ok": true,
     "data": {
       "DOKU_IS_PRODUCTION": false,
       "DOKU_CLIENT_ID": "BRN-0280-176576...",
       "base_url": "https://api-sandbox.doku.com",
       "environment": "Sandbox",
       "USE_MOCK_PAYMENT": false
     }
   }
   ```

6. **Test Purchase Endpoint:**

   ```
   POST https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/purchase

   {
       "packageId": 2,
       "payment_method": "DOKU"
   }
   ```

   **Should now return:**

   ```json
   {
     "ok": true,
     "message": "Transaction created successfully...",
     "data": {
       "payment_url": "https://sandbox.doku.com/checkout/..."
     }
   }
   ```

---

## 📋 Alternative Methods

See `UPDATE_CLOUD_RUN.md` for other deployment options:

- Option 2: Redeploy via GitHub/Cloud Build
- Option 3: Manual deployment via Cloud Build
- Option 4: Direct update via gcloud CLI

---

## 🔍 Verification Checklist

After updating Cloud Run:

- [ ] Debug endpoint shows `DOKU_IS_PRODUCTION: false`
- [ ] Debug endpoint shows `base_url: "https://api-sandbox.doku.com"`
- [ ] Debug endpoint shows `environment: "Sandbox"`
- [ ] Purchase endpoint returns payment URL (not error)
- [ ] Payment URL starts with `https://sandbox.doku.com/`

---

## 📞 If Still Not Working

1. **Check Cloud Run Logs:**
   - Console → Cloud Run → nanobanana-backend-us → LOGS
   - Look for Doku-related errors

2. **Verify Credentials:**
   - Ensure `BRN-0280-1765767732062` is valid sandbox Client ID
   - Contact Doku support if needed

3. **Try Mock Payment:**
   - Add environment variable: `USE_MOCK_PAYMENT=true`
   - This bypasses Doku API for testing

---

## 🎯 Next Steps After Fix

1. **Test full payment flow** in sandbox
2. **Document production credentials** for future
3. **Update monitoring** to track payment success rate
4. **Plan production migration** when ready

---

## 📝 Files Modified

- `.env` - Local environment (line 42)
- `cloudbuild.yaml` - Deployment config (line 43)
- `app/api/subscriptions.py` - Added debug endpoint (line 170)
- `DOKU_FIX_DOCUMENTATION.md` - Full documentation
- `UPDATE_CLOUD_RUN.md` - Deployment guide

---

## ⏱️ Estimated Time

- Cloud Console update: **3-5 minutes**
- Testing: **2 minutes**
- **Total: ~7 minutes**

---

**Start here:** https://console.cloud.google.com/run?project=nanobananacomic-482111
