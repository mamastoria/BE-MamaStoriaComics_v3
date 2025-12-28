# Quick Test: Google OAuth

## Cara Cepat Test Google OAuth

### 1. Setup Environment Variables

Tambahkan ke `.env`:

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

### 2. Start Server

```bash
uvicorn app.main:app --reload
```

### 3. Test dengan Swagger UI

1. Buka: http://localhost:8000/docs
2. Cari endpoint: `POST /api/v1/auth/google/verify-token`
3. Klik "Try it out"
4. Masukkan test ID token (lihat cara dapat ID token di bawah)
5. Klik "Execute"

### 4. Cara Dapat Google ID Token untuk Testing

#### Option A: Google OAuth Playground (Recommended)

1. Buka: https://developers.google.com/oauthplayground/
2. Klik ⚙️ (Settings) di kanan atas
3. Check "Use your own OAuth credentials"
4. Masukkan Client ID dan Client Secret
5. Di Step 1: Select & authorize APIs
   - Pilih "Google OAuth2 API v2"
   - Check: `https://www.googleapis.com/auth/userinfo.email`
   - Check: `https://www.googleapis.com/auth/userinfo.profile`
   - Klik "Authorize APIs"
6. Login dengan Google account
7. Di Step 2: Exchange authorization code for tokens
   - Klik "Exchange authorization code for tokens"
8. Copy `id_token` dari response
9. Paste ke Swagger UI

#### Option B: Using curl

```bash
curl -X POST "http://localhost:8000/api/v1/auth/google/verify-token" \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "YOUR_GOOGLE_ID_TOKEN_HERE"
  }'
```

### 5. Expected Response

```json
{
  "ok": true,
  "message": "Google login successful",
  "data": {
    "user": {
      "id_users": 1,
      "full_name": "Your Name",
      "email": "your@email.com",
      "phone_number": "google_1234567890",
      "is_verified": true,
      "login_method": "google",
      "external_id": "1234567890",
      "profile_photo_path": "https://lh3.googleusercontent.com/...",
      "kredit": 0,
      "balance": 0,
      "publish_quota": 5
    },
    "tokens": {
      "access_token": "eyJ...",
      "refresh_token": "eyJ...",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
}
```

### 6. Test Login Kedua Kali

Gunakan ID token yang sama atau ID token baru dari Google account yang sama.
Backend akan mengenali user yang sudah ada dan langsung login (tidak create user baru).

---

## Troubleshooting

### Error: "Invalid Google token"

**Penyebab**: Client ID tidak sesuai atau token expired

**Solusi**:

1. Pastikan `GOOGLE_CLIENT_ID` di `.env` sama dengan yang digunakan untuk generate token
2. Generate token baru (token Google valid 1 jam)

### Error: "Failed to verify token"

**Penyebab**: Network issue atau Google API tidak bisa diakses

**Solusi**:

1. Check internet connection
2. Pastikan server bisa akses `https://www.googleapis.com`

---

## Next Steps

Setelah berhasil test:

1. ✅ Integrate dengan mobile app (Flutter, React Native)
2. ✅ Integrate dengan web app (React, Vue, Angular)
3. ✅ Test dengan multiple Google accounts
4. ✅ Test linking Google account ke existing user

Lihat `GOOGLE_OAUTH.md` untuk dokumentasi lengkap dan code examples.
