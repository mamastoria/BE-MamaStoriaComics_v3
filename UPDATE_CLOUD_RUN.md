# How to Update Cloud Run Environment Variables

## Problem

The Cloud Run service `nanobanana-backend-us` is still using `DOKU_IS_PRODUCTION=true` (or it's not set, defaulting to the hardcoded value in `config.py`). We need to set it to `false` to use sandbox mode.

## ✅ What We've Done

1. ✅ Updated local `.env` file: `DOKU_IS_PRODUCTION=false`
2. ✅ Updated `cloudbuild.yaml` to include `DOKU_IS_PRODUCTION=false` for future deployments

## 🚀 Choose Your Solution

### **Option 1: Update via Google Cloud Console (Easiest - No CLI Required)**

1. **Open Google Cloud Console:**
   - Go to: https://console.cloud.google.com/run
   - Select project: `nanobananacomic-482111`
   - Region: `us-central1`

2. **Find Your Service:**
   - Click on `nanobanana-backend-us`

3. **Edit Configuration:**
   - Click **"EDIT & DEPLOY NEW REVISION"** button at the top

4. **Add Environment Variable:**
   - Scroll to **"Variables & Secrets"** section
   - Click **"+ ADD VARIABLE"**
   - Name: `DOKU_IS_PRODUCTION`
   - Value: `false`

5. **Deploy:**
   - Click **"DEPLOY"** at the bottom
   - Wait 2-3 minutes for deployment to complete

6. **Verify:**
   - Test the purchase endpoint again

---

### **Option 2: Redeploy via GitHub (If you have CI/CD setup)**

If your repository is connected to Cloud Build:

1. **Commit the changes:**

   ```bash
   git add .env cloudbuild.yaml
   git commit -m "Fix: Set DOKU_IS_PRODUCTION to false for sandbox mode"
   git push origin main
   ```

2. **Cloud Build will automatically:**
   - Build new Docker image
   - Deploy to Cloud Run with `DOKU_IS_PRODUCTION=false`

3. **Monitor deployment:**
   - Go to: https://console.cloud.google.com/cloud-build/builds
   - Wait for build to complete (usually 3-5 minutes)

---

### **Option 3: Manual Deployment via Cloud Build**

If you have `gcloud` CLI installed:

```bash
# Navigate to project directory
cd "c:\Users\shwen\Documents\DATA TPA\New folder\BE-MamaStoriaComics_v3"

# Submit build to Cloud Build
gcloud builds submit --config cloudbuild.yaml --project=nanobananacomic-482111
```

This will:

- Build the Docker image
- Deploy to Cloud Run with the updated environment variables from `cloudbuild.yaml`

---

### **Option 4: Direct Update via gcloud CLI (Fastest)**

If you have `gcloud` CLI installed:

```bash
gcloud run services update nanobanana-backend-us \
  --region=us-central1 \
  --update-env-vars DOKU_IS_PRODUCTION=false \
  --project=nanobananacomic-482111
```

This updates the running service immediately without rebuilding.

---

## 📋 After Updating

### 1. Verify the Environment Variable

Check if the variable is set correctly:

**Via Cloud Console:**

- Go to Cloud Run → `nanobanana-backend-us` → **VARIABLES** tab
- Look for `DOKU_IS_PRODUCTION` = `false`

**Via API (test endpoint):**
Create a debug endpoint to check:

```python
@router.get("/debug/doku-config")
async def debug_doku_config():
    from app.core.config import settings
    return {
        "DOKU_IS_PRODUCTION": settings.DOKU_IS_PRODUCTION,
        "DOKU_CLIENT_ID": settings.DOKU_CLIENT_ID[:10] + "...",  # Partial for security
        "base_url": "https://api.doku.com" if settings.DOKU_IS_PRODUCTION else "https://api-sandbox.doku.com"
    }
```

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

**Expected Success Response:**

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

**Key Check:** The `payment_url` should start with `https://sandbox.doku.com/...`

---

## 🔍 Troubleshooting

### Still Getting "Invalid Client-Id"?

1. **Check if variable was applied:**
   - Cloud Run → Service → Variables tab
   - Ensure `DOKU_IS_PRODUCTION=false` is listed

2. **Check service logs:**

   ```
   Cloud Console → Cloud Run → nanobanana-backend-us → LOGS
   ```

   Look for startup logs showing Doku configuration

3. **Force new revision:**
   - Sometimes Cloud Run caches environment
   - Edit & deploy a new revision even without code changes

### Deployment Takes Too Long?

- Normal deployment: 2-5 minutes
- If stuck > 10 minutes, check Cloud Build logs
- May need to check Cloud SQL connection

---

## 📝 Summary

**Recommended Approach:**

1. Use **Option 1** (Cloud Console) - easiest, no CLI needed
2. Takes ~3 minutes total
3. Test immediately after deployment

**For Future:**

- `cloudbuild.yaml` is now updated
- Any new deployment will include `DOKU_IS_PRODUCTION=false`
- When ready for production, update both `.env` and `cloudbuild.yaml` to `true` with production credentials

---

## 🎯 Quick Checklist

- [ ] Update Cloud Run environment variable `DOKU_IS_PRODUCTION=false`
- [ ] Wait for deployment to complete
- [ ] Test purchase endpoint
- [ ] Verify payment URL uses sandbox domain
- [ ] Document production credentials for future use
