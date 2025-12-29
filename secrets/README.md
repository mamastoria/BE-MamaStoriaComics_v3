# 🔐 Secret Management

Dokumentasi untuk pengelolaan secrets menggunakan Google Cloud Secret Manager.

---

## ✅ Secrets yang Dibuat

| Secret Name | Deskripsi | Status |
|-------------|-----------|--------|
| `SECRET_KEY` | Flask/FastAPI secret key | ✅ Created |
| `JWT_SECRET_KEY` | JWT signing key | ✅ Created |
| `DATABASE_URL` | PostgreSQL connection string | ✅ Created |

---

## 🔗 Akses Secrets

### Service Account yang Memiliki Akses
```
nanobanana-comic-sa@nanobananacomic-482111.iam.gserviceaccount.com
```

### Cloud Run Services yang Menggunakan Secrets
- `nanobanana-backend` ✅
- `nanobanana-worker` ✅

---

## 📋 Commands Reference

### List All Secrets
```bash
gcloud secrets list --project=nanobananacomic-482111
```

### View Secret Value (untuk debugging)
```bash
gcloud secrets versions access latest --secret=SECRET_KEY --project=nanobananacomic-482111
```

### Create New Secret
```bash
echo "your-secret-value" | gcloud secrets create NEW_SECRET_NAME \
  --data-file=- \
  --replication-policy=automatic \
  --project=nanobananacomic-482111
```

### Update Secret (Add New Version)
```bash
echo "new-secret-value" | gcloud secrets versions add SECRET_NAME \
  --data-file=- \
  --project=nanobananacomic-482111
```

### Grant Access to Service Account
```bash
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:YOUR_SA@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=nanobananacomic-482111
```

### Update Cloud Run to Use Secrets
```bash
gcloud run services update SERVICE_NAME \
  --region asia-southeast2 \
  --project nanobananacomic-482111 \
  --update-secrets="ENV_VAR=SECRET_NAME:latest"
```

---

## 🔄 Secret Rotation

### Langkah Rotasi Secret

1. **Buat versi baru:**
   ```bash
   echo "new-secret-value" | gcloud secrets versions add SECRET_KEY \
     --data-file=- \
     --project=nanobananacomic-482111
   ```

2. **Deploy ulang Cloud Run** (untuk mengambil secret baru):
   ```bash
   gcloud run services update nanobanana-backend \
     --region asia-southeast2 \
     --project nanobananacomic-482111
   ```

3. **Disable versi lama** (opsional):
   ```bash
   gcloud secrets versions disable 1 --secret=SECRET_KEY \
     --project=nanobananacomic-482111
   ```

---

## 🛡️ Best Practices

1. **Jangan pernah** commit secrets ke Git
2. **Rotasi** secrets secara berkala (tiap 90 hari)
3. **Audit** akses secrets di Cloud Audit Logs
4. **Limit** akses hanya ke service account yang membutuhkan
5. **Gunakan** Secret Manager untuk SEMUA nilai sensitif

---

## 📊 Secrets vs Environment Variables

| Aspek | Env Variables | Secret Manager |
|-------|---------------|----------------|
| Keamanan | ⚠️ Bisa terekspos di logs | ✅ Encrypted at rest |
| Audit | ❌ Tidak ada | ✅ Cloud Audit Logs |
| Rotation | ⚠️ Manual redeploy | ✅ Versioned |
| Access Control | ❌ All or nothing | ✅ Fine-grained IAM |

---

## 🔗 Console Links

- **Secret Manager**: https://console.cloud.google.com/security/secret-manager?project=nanobananacomic-482111
- **IAM**: https://console.cloud.google.com/iam-admin/iam?project=nanobananacomic-482111
- **Audit Logs**: https://console.cloud.google.com/logs/query?project=nanobananacomic-482111

---

*Last Updated: 2024-12-28*
