# 📡 Analisis Komunikasi Frontend ↔ Backend

Dokumen ini menganalisa bagaimana Frontend (Flutter) berkomunikasi dengan Backend (FastAPI).

---

## 🏗️ Arsitektur Komunikasi

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Flutter)                                   │
│                                                                              │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐               │
│   │  Screens     │ ──▶ │  Providers   │ ──▶ │ Repositories │               │
│   │  (UI)        │     │  (Riverpod)  │     │  (Retrofit)  │               │
│   └──────────────┘     └──────────────┘     └──────┬───────┘               │
│                                                     │                        │
│                                              ┌──────▼───────┐               │
│                                              │   Dio HTTP   │               │
│                                              │   Client     │               │
│                                              └──────┬───────┘               │
└──────────────────────────────────────────────────────┼──────────────────────┘
                                                       │
                                                       │ HTTPS
                                                       │
┌──────────────────────────────────────────────────────┼──────────────────────┐
│                         BACKEND (FastAPI)            │                       │
│                                                      ▼                       │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    Cloud Run (nanobanana-backend)                     │  │
│   │                                                                       │  │
│   │   main.py (Legacy AI Comic Generator)                                │  │
│   │      └─ /api/styles, /api/nuances, /api/script, /api/render_all     │  │
│   │                                                                       │  │
│   │   app/api/ (New FastAPI Routers)                                     │  │
│   │      ├─ auth.py       → /api/v1/auth/*                              │  │
│   │      ├─ comics.py     → /api/v1/comics/*                            │  │
│   │      ├─ master_data.py → /api/v1/styles, /api/v1/genres, etc       │  │
│   │      ├─ users.py      → /api/v1/users/*                             │  │
│   │      └─ ...                                                          │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Endpoint Mapping: Frontend ↔ Backend

### 1. Authentication (`auth_repository.dart` ↔ `auth.py`)

| Frontend Method | Backend Endpoint | Status |
|-----------------|------------------|--------|
| `login()` | `POST /api/login` | ⚠️ Mismatch |
| `verifyGoogleToken()` | `POST /api/v1/auth/google/verify-token` | ✅ Match |
| `logout()` | `POST /api/logout` | ⚠️ Mismatch |
| `refresh()` | `POST /api/refresh` | ⚠️ Mismatch |
| `updateFcmToken()` | `POST /api/user/update-fcm-token` | ⚠️ Mismatch |
| `updateCredit()` | `POST /api/api/profile/update-kredit` | ❌ Double /api |

**Backend yang Tersedia:**
```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/verify
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/user/update-fcm-token
POST /api/v1/auth/google/verify-token
```

---

### 2. Comics (`comic_repository.dart` ↔ `comics.py`)

| Frontend Method | Backend Endpoint | Status |
|-----------------|------------------|--------|
| `getComics()` | `GET /v1/comics` | ⚠️ Missing /api prefix |
| `submitStory()` | `POST /v1/comics/story-idea` | ⚠️ Missing /api prefix |
| `getDraftStatus()` | `GET /v1/comics/{id}/draft/status` | ⚠️ Missing /api |
| `getComic()` | `GET /v1/comics/show/{id}` | ⚠️ Missing /api |
| `likeStatus()` | `GET /v1/comics/{id}/likes/status` | ⚠️ Missing /api |
| `previewVideo()` | `GET /v1/comics/{id}/preview-video` | ⚠️ Missing /api |
| `read()` | `POST /v1/comics/{id}/track-read` | ⚠️ Missing /api |
| `like()` | `POST /v1/comics/{id}/likes` | ⚠️ Missing /api |
| `dislike()` | `DELETE /v1/comics/{id}/likes` | ⚠️ Missing /api |
| `getComments()` | `GET /v1/comics/{id}/review_comments` | ⚠️ Missing /api |
| `addComment()` | `POST /v1/comics/{id}/comments` | ⚠️ Missing /api |
| `deleteDraft()` | `DELETE /v1/drafts/{id}` | ⚠️ Missing /api |

**Backend yang Tersedia:**
```
GET  /api/v1/comics
GET  /api/v1/comics/{id}
POST /api/v1/comics/story-idea
PUT  /api/v1/comics/{id}/summary
PUT  /api/v1/comics/{id}/character
PUT  /api/v1/comics/{id}/backgrounds
GET  /api/v1/comics/drafts
POST /api/v1/comics/{id}/publish
POST /api/v1/comics/{id}/track-read
```

---

### 3. Master Data (`master_repository.dart` ↔ `master_data.py`)

| Frontend Method | Backend Endpoint | Status |
|-----------------|------------------|--------|
| `getList(genres)` | `GET /v1/genres` | ⚠️ Missing /api |
| `getList(styles)` | `GET /v1/styles` | ⚠️ Missing /api |
| `getList(chars)` | `GET /v1/chars` | ⚠️ Missing /api |
| `getList(bg)` | `GET /v1/bg` | ⚠️ Missing /api |

**Backend yang Tersedia:**
```
GET /api/v1/styles
GET /api/v1/genres
GET /api/v1/characters (alias: /api/v1/chars)
GET /api/v1/backgrounds (alias: /api/v1/bg)
```

---

### 4. Generate Comic (`generate_comic_repository.dart`)

| Frontend Method | Backend Endpoint | Status |
|-----------------|------------------|--------|
| `createIdea()` | `POST /v1/comics/story-idea` | ⚠️ Missing /api |
| `transcribeIdea()` | `POST /v1/comics/story-idea/transcribe` | ❓ Not found |
| `generateComic()` | `POST /v1/comics/{id}/drafts` | ❓ Not found |
| `editDraftText()` | `PUT /v1/{id}/summary` | ❌ Wrong path |
| `editCharacter()` | `PUT /v1/comics/{id}/characters` | ⚠️ Wrong endpoint |
| `editBackgrounds()` | `PUT /v1/comics/{id}/backgrounds` | ⚠️ Match |

---

### 5. Drafts (`draft_repository.dart`)

| Frontend Method | Backend Endpoint | Status |
|-----------------|------------------|--------|
| `list()` | `GET /v1/comics/drafts` | ⚠️ Missing /api |
| `single()` | `GET /v1/comics/{id}/draft/status` | ❓ Not found |
| `panels()` | `GET /v1/drafts/{id}/panels` | ❓ Not found |
| `publish()` | `POST /v1/comics/{id}/publish` | ⚠️ Missing /api |
| `media()` | `GET /v1/comics/exported-media/{id}` | ❓ Not found |

---

## ⚠️ Masalah yang Ditemukan

### 1. **Prefix Path Tidak Konsisten**

**Frontend menggunakan:**
- `/api/login` (tanpa v1)
- `/v1/comics` (tanpa /api)
- `/api/v1/auth/google/verify-token` (lengkap)

**Backend menggunakan:**
- `/api/v1/*` (konsisten)

**Solusi:** Standardisasi path di Frontend

---

### 2. **Endpoint yang Hilang di Backend**

| Endpoint | Dibutuhkan Untuk |
|----------|------------------|
| `POST /api/v1/comics/story-idea/transcribe` | Voice input |
| `POST /api/v1/comics/{id}/drafts` | Start generation |
| `GET /api/v1/comics/{id}/draft/status` | Cek status generation |
| `GET /api/v1/drafts/{id}/panels` | Get panel images |
| `GET /api/v1/comics/exported-media/{id}` | Get video/PDF |
| `GET /api/v1/comics/{id}/preview-video` | Video preview |
| `GET /api/v1/comics/{id}/likes/status` | Like status |
| `GET /api/v1/comics/{id}/review_comments` | Get comments |

---

### 3. **Response Format Berbeda**

**Frontend mengharapkan:**
```json
{
  "ok": true,
  "data": { ... },
  "message": "Success"
}
```

**Backend mengembalikan:**
```json
{
  "ok": true,
  "data": { ... }
}
// atau langsung data tanpa wrapper
```

---

## 🔧 Rekomendasi Perbaikan

### Prioritas 1: Fix Path Prefix di Frontend

```dart
// auth_repository.dart
@RestApi(baseUrl: '/api/v1/auth')  // Ubah dari '/api'
abstract class AuthRepository {
  @POST('/login')      // Jadi /api/v1/auth/login
  @POST('/logout')
  @POST('/refresh')
  // ...
}

// comic_repository.dart  
@RestApi(baseUrl: '/api/v1')  // Tambahkan /api
abstract class ComicRepository {
  @GET('/comics')      // Jadi /api/v1/comics
  // ...
}

// master_repository.dart
@RestApi(baseUrl: '/api/v1')  // Tambahkan /api
abstract class MasterRepository {
  @GET('/{path}')      // Jadi /api/v1/genres, etc
  // ...
}
```

### Prioritas 2: Tambah Endpoint yang Hilang di Backend

| File | Endpoint yang Perlu Ditambah |
|------|------------------------------|
| `comics.py` | `GET /{id}/draft/status` |
| `comics.py` | `GET /{id}/likes/status` |
| `comics.py` | `GET /{id}/preview-video` |
| `comics.py` | `POST /story-idea/transcribe` |
| `likes.py` | `GET /comics/{id}/likes/status` |
| `comments.py` | `GET /comics/{id}/review_comments` |

### Prioritas 3: Standardisasi Response Format

Semua endpoint harus mengembalikan:
```json
{
  "ok": true,
  "data": { ... },
  "message": "Optional message",
  "meta": {  // untuk pagination
    "current_page": 1,
    "total_pages": 10,
    "total": 100
  }
}
```

---

## 📋 Action Items

## 📋 Action Items
262: 
263: - [x] Update `auth_repository.dart` - fix baseUrl ke `/api/v1/auth`
264: - [x] Update `comic_repository.dart` - fix baseUrl ke `/api/v1`
265: - [x] Update `master_repository.dart` - fix baseUrl ke `/api/v1`
266: - [x] Update `generate_comic_repository.dart` - fix paths
267: - [x] Update `draft_repository.dart` - fix paths
268: - [x] Tambah endpoint `draft/status` di backend
269: - [x] Tambah endpoint `likes/status` di backend
270: - [x] Tambah endpoint `review_comments` di backend
271: - [x] Tambah endpoint `transcribe` di backend
272: - [x] Test semua endpoint dengan Postman/curl
273: - [x] Fix Database Connection di Cloud Run (Cloud SQL Python Connector)
274: 
275: ---
276: 
277: *Last Updated: 2024-12-29 11:30*

