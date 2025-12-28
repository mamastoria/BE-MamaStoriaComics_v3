# Auto-Deploy Setup: GitHub → Cloud Run

Panduan lengkap untuk mengaktifkan auto-deploy dari GitHub ke Google Cloud Run.

## Prerequisites

- Repository GitHub: `mamastoria/BE-MamaStoriaComics_v3`
- GCP Project: `nanobananacomic-482111`
- Cloud Run Service: `nanobanana-backend`

---

## Step 1: Setup Workload Identity Federation (WIF)

Jalankan perintah berikut di Cloud Shell atau terminal lokal:

```bash
# Set variables
PROJECT_ID="nanobananacomic-482111"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-provider"
SERVICE_ACCOUNT="github-actions-sa"
GITHUB_REPO="mamastoria/BE-MamaStoriaComics_v3"

# 1. Enable required APIs
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID

# 2. Create Workload Identity Pool
gcloud iam workload-identity-pools create $POOL_NAME \
  --project=$PROJECT_ID \
  --location="global" \
  --display-name="GitHub Actions Pool"

# 3. Create Workload Identity Provider (for GitHub)
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_NAME \
  --project=$PROJECT_ID \
  --location="global" \
  --workload-identity-pool=$POOL_NAME \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# 4. Create Service Account for GitHub Actions
gcloud iam service-accounts create $SERVICE_ACCOUNT \
  --project=$PROJECT_ID \
  --display-name="GitHub Actions Service Account"

# 5. Grant permissions to Service Account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# 6. Allow GitHub to impersonate Service Account
gcloud iam service-accounts add-iam-policy-binding ${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com \
  --project=$PROJECT_ID \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"

# 7. Get the WIF Provider resource name (copy this for GitHub secrets)
echo "WIF_PROVIDER:"
echo "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"

echo ""
echo "WIF_SERVICE_ACCOUNT:"
echo "${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
```

---

## Step 2: Create Secrets in Secret Manager

```bash
# Store sensitive values in Secret Manager
echo -n "e68865f98e54264001d49d780a52e3e024e819bcbca523c91350a241dd51" | \
  gcloud secrets create SECRET_KEY --data-file=- --project=$PROJECT_ID

echo -n "a22e901209dbd89a1b9c95dc6c9fe3b1bf5ce88a1030d07a2970b63094cb32ddd" | \
  gcloud secrets create JWT_SECRET_KEY --data-file=- --project=$PROJECT_ID

echo -n "postgresql://postgres:Aihebat@1@/nanobanana_db?host=/cloudsql/nanobananacomic-482111:asia-southeast2:cloudsql-nanobanana-dev" | \
  gcloud secrets create DATABASE_URL --data-file=- --project=$PROJECT_ID

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding SECRET_KEY \
  --member="serviceAccount:nanobanana-comic-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding JWT_SECRET_KEY \
  --member="serviceAccount:nanobanana-comic-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding DATABASE_URL \
  --member="serviceAccount:nanobanana-comic-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

---

## Step 3: Add Secrets to GitHub Repository

1. Buka: https://github.com/mamastoria/BE-MamaStoriaComics_v3/settings/secrets/actions
2. Klik **"New repository secret"**
3. Tambahkan 2 secrets:

| Secret Name | Value |
|-------------|-------|
| `WIF_PROVIDER` | `projects/1089713441636/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | `github-actions-sa@nanobananacomic-482111.iam.gserviceaccount.com` |

---

## Step 4: Test Auto-Deploy

1. Commit dan push perubahan ke branch `main`
2. Buka: https://github.com/mamastoria/BE-MamaStoriaComics_v3/actions
3. Lihat workflow "Deploy to Cloud Run" berjalan

---

## Troubleshooting

### Error: "Unable to exchange token"
- Pastikan repository name di WIF binding sudah benar
- Pastikan WIF_PROVIDER format benar (dengan PROJECT_NUMBER, bukan PROJECT_ID)

### Error: "Permission denied on Cloud Run"
- Jalankan ulang perintah grant permissions di Step 1.5

---

## Alternative: Menggunakan Cloud Build Triggers

Jika WIF terlalu rumit, Anda bisa menggunakan Cloud Build Triggers yang lebih simple:

1. Buka: https://console.cloud.google.com/cloud-build/triggers?project=nanobananacomic-482111
2. Klik **"Connect Repository"** → Pilih GitHub → Authorize
3. Pilih repository `BE-MamaStoriaComics_v3`
4. Buat trigger:
   - Name: `deploy-on-push`
   - Event: Push to branch
   - Branch: `^main$`
   - Type: Cloud Build configuration file (yaml)
   - Location: `/cloudbuild.yaml`
