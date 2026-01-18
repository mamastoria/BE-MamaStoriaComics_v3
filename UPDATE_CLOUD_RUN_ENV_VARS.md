# Manual Update Cloud Run Environment Variables

## Problem

Meskipun deployment sudah success, environment variables di Cloud Run TIDAK otomatis ter-update dari perubahan di deploy-cloudrun.yml.

Cloud Run mempertahankan env vars yang sudah ada kecuali di-update secara eksplisit.

## Solution

Update manual environment variables menggunakan gcloud command:

```bash
gcloud run services update nanobanana-backend-us \
  --region us-central1 \
  --project nanobananacomic-482111 \
  --update-env-vars "DOKU_IS_PRODUCTION=true,USE_MOCK_PAYMENT=false"
```

## Full Command (All DOKU vars)

```bash
gcloud run services update nanobanana-backend-us \
  --region us-central1 \
  --project nanobananacomic-482111 \
  --update-env-vars "DOKU_IS_PRODUCTION=true,DOKU_CLIENT_ID=BRN-0280-1765767732062,DOKU_SECRET_KEY=SK-Mb7Lbo9POYkyOCpv1vG2,DOKU_NOTIFICATION_SECRET=SK-Mb7Lbo9POYkyOCpv1vG2,USE_MOCK_PAYMENT=false"
```

## Alternative: Via Console

1. Go to: https://console.cloud.google.com/run/detail/us-central1/nanobanana-backend-us/variables?project=nanobananacomic-482111
2. Click "EDIT & DEPLOY NEW REVISION"
3. Go to "VARIABLES & SECRETS" tab
4. Update:
   - DOKU_IS_PRODUCTION = true
   - USE_MOCK_PAYMENT = false
5. Click "DEPLOY"

## Verify After Update

```bash
curl https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/debug/doku-config
```

Should show:

```json
{
  "ok": true,
  "data": {
    "DOKU_IS_PRODUCTION": true,
    "base_url": "https://api.doku.com",
    "USE_MOCK_PAYMENT": false
  }
}
```
