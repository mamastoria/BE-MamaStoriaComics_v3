# 🌐 Cloud CDN Setup

Dokumentasi setup Cloud CDN + Load Balancer untuk NanoBanana Comic.

---

## 📊 Arsitektur

```
                    ┌─────────────────────────────────┐
                    │       Global HTTP(S)            │
                    │       Load Balancer             │
                    │       IP: 34.149.78.224         │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │         Cloud CDN               │
                    │    (Cache at Edge Locations)    │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
                    │      Backend Bucket             │
                    │   gs://nanobanana-storage       │
                    └─────────────────────────────────┘
```

---

## ✅ Komponen yang Dibuat

| Komponen | Nama | Status |
|----------|------|--------|
| Backend Bucket | `nanobanana-cdn-backend` | ✅ Created |
| URL Map | `nanobanana-cdn-urlmap` | ✅ Created |
| HTTP Proxy | `nanobanana-http-proxy` | ✅ Created |
| HTTPS Proxy | `nanobanana-https-proxy` | ✅ Created |
| Static IP | `nanobanana-cdn-ip` | ✅ 34.149.78.224 |
| SSL Certificate | `nanobanana-cdn-cert` | ⏳ Provisioning |
| HTTP Forwarding | `nanobanana-http-forwarding` | ✅ Created |
| HTTPS Forwarding | `nanobanana-https-forwarding` | ✅ Created |

---

## 🔗 URL Access

### Sementara (HTTP via IP):
```
http://34.149.78.224/comics/123/panel_1.webp
```

### Setelah DNS dikonfigurasi (HTTPS):
```
https://cdn.nanobananacomic.com/comics/123/panel_1.webp
```

### Direct Storage (Fallback):
```
https://storage.googleapis.com/nanobanana-storage/comics/123/panel_1.webp
```

---

## 🌍 Setup DNS (Opsional tapi Disarankan)

Untuk menggunakan custom domain `cdn.nanobananacomic.com`:

1. **Akses DNS Provider Anda** (Cloudflare, GoDaddy, Namecheap, dll)

2. **Tambahkan A Record:**
   ```
   Type: A
   Name: cdn
   Value: 34.149.78.224
   TTL: 300 (atau auto)
   ```

3. **Tunggu SSL Certificate Provisioning:**
   - Google akan otomatis provision SSL setelah DNS propagate
   - Biasanya 15-30 menit setelah DNS setup
   - Cek status: 
     ```bash
     gcloud compute ssl-certificates describe nanobanana-cdn-cert --global
     ```

---

## 📈 CDN Benefits

| Metric | Tanpa CDN | Dengan CDN | Improvement |
|--------|-----------|------------|-------------|
| Latency (Asia) | 50-100ms | 5-20ms | 5-10x faster |
| Latency (Global) | 200-500ms | 20-50ms | 10x faster |
| Bandwidth Cost | $0.12/GB | $0.02-0.06/GB | 50-80% cheaper |
| Origin Load | 100% | 10-30% | 70-90% reduction |

---

## 🔧 Cache Settings

Default cache settings:
- **Cache Mode**: Cache all static content
- **Default TTL**: 3600 seconds (1 hour)
- **Max TTL**: 86400 seconds (1 day)
- **Client TTL**: Browser respects Cache-Control header

### Custom Cache Control (di backend):
```python
# Set di response header saat upload
blob.cache_control = "public, max-age=86400"  # 1 day
blob.upload_from_string(content)
```

---

## 🔍 Verify CDN is Working

```bash
# Check cache status in response headers
curl -I http://34.149.78.224/test-image.webp

# Look for these headers:
# - Age: [seconds since cached]
# - X-GUploader-UploadID: [if from origin]
# - Via: [if from CDN edge]
```

---

## 📋 Commands Reference

```bash
# Check backend bucket status
gcloud compute backend-buckets describe nanobanana-cdn-backend

# Check SSL certificate status
gcloud compute ssl-certificates describe nanobanana-cdn-cert --global

# Check load balancer
gcloud compute forwarding-rules list --global

# Invalidate cache (if needed)
gcloud compute url-maps invalidate-cdn-cache nanobanana-cdn-urlmap --path="/*"

# Invalidate specific path
gcloud compute url-maps invalidate-cdn-cache nanobanana-cdn-urlmap --path="/comics/123/*"
```

---

## 💰 Estimated Cost

| Item | Unit | Price | Monthly Est. |
|------|------|-------|--------------|
| CDN Egress (Asia) | per GB | $0.02-0.06 | $10-30 |
| CDN Egress (Global) | per GB | $0.04-0.12 | $20-50 |
| Cache Fill (Origin) | per GB | $0.01 | $1-5 |
| HTTP(S) Requests | per 10K | $0.0075 | $5-15 |
| **Total** | | | **$20-100** |

*Depends on traffic volume*

---

## 🔄 Update Frontend to Use CDN

Di frontend, update base URL untuk gambar:

```dart
// lib/core/constants/environtments.dart

abstract class Env {
  // API Backend
  static const baseUrl = "https://nanobanana-backend-1089713441636.asia-southeast2.run.app";
  
  // CDN for images (use this for comic images)
  static const cdnUrl = "http://34.149.78.224";  // HTTP sementara
  // static const cdnUrl = "https://cdn.nanobananacomic.com";  // Setelah DNS setup
  
  // Fallback storage URL
  static const storageUrl = "https://storage.googleapis.com/nanobanana-storage";
}
```

---

*Last Updated: 2024-12-28*
