# Task Konversi API Laravel ke Python - MamaStoria Comics

## 📋 Ringkasan Proyek

Konversi Backend API Laravel (PHP) ke Python FastAPI untuk aplikasi MamaStoria Comics - platform pembuatan komik dengan AI.

**CATATAN PENTING**: Worker, Job, Queue TIDAK perlu dikonversi. Hanya API CRUD biasa.

---

## 🎯 Teknologi Stack Python

### Framework & Core

-   **FastAPI** - Web framework modern untuk API
-   **SQLAlchemy** - ORM untuk database
-   **Pydantic** - Validasi data
-   **Alembic** - Database migrations
-   **PostgreSQL** - Database (sesuai production)

### Authentication & Security

-   **python-jose[cryptography]** - JWT tokens
-   **passlib[bcrypt]** - Password hashing
-   **python-multipart** - File uploads

### Google Cloud Integration

-   **google-cloud-storage** - GCS untuk file storage
-   **google-cloud-texttospeech** - Text to Speech
-   **google-cloud-speech** - Speech to Text
-   **google-auth** - Authentication

### External Services

-   **httpx** - HTTP client untuk API calls
-   **python-dotenv** - Environment variables
-   **firebase-admin** - Firebase notifications

---

## 📁 Struktur Database (54 Tabel)

### Core Tables

1. **users** - User accounts & profiles
2. **comics** - Comic data & metadata
3. **comic_panels** - Panel images & content
4. **comic_panel_ideas** - Draft panel ideas

### Master Data

5. **styles** - Visual styles
6. **genres** - Comic genres
7. **characters** - Character templates
8. **backgrounds** - Background templates
9. **asset_music** - Music assets

### Social Features

10. **comments** - Comic comments
11. **comic_user** - Likes (pivot)
12. **comic_views** - Read history

### Monetization

13. **subscriptions** - User subscriptions
14. **subscription_packages** - Subscription plans
15. **payment_transactions** - Payment records
16. **transactions** - General transactions
17. **creator_wallets** - Creator earnings
18. **wallet_transactions** - Wallet history
19. **withdrawal_requests** - Withdrawal requests

### Referral System

20. **referrals** - Referral records
21. **user_monthly_stats** - Monthly analytics

### Authentication

22. **personal_access_tokens** - API tokens
23. **password_resets** - Password reset tokens
24. **otp_requests** - OTP verification

### System

25. **notifications** - User notifications
26. **banners** - App banners
27. **banner_comic** - Banner-Comic pivot
28. **profile_updates_log** - Profile change log
29. **sessions** - User sessions
30. **cache** - Cache storage

---

## 🔑 Fitur Utama API

### 1. Authentication (`AuthController`)

-   ✅ Register dengan email/phone
-   ✅ Login (email/password)
-   ✅ Google OAuth (redirect & callback)
-   ✅ Google Token Verification (mobile)
-   ✅ OTP verification
-   ✅ Refresh token
-   ✅ Logout
-   ✅ Update FCM token

### 2. User Management (`UserEditController`, `ProfileController`)

-   ✅ Change password
-   ✅ Forgot password (send/verify/reset token)
-   ✅ Update profile (name, username, email)
-   ✅ Update profile photo
-   ✅ Update kredit (credits)
-   ✅ Get referral code
-   ✅ Get profile rating
-   ✅ Get update quota

### 3. Comics CRUD (`ComicController`)

-   ✅ List comics (public, pagination)
-   ✅ Show comic detail
-   ✅ Create story idea (step 1)
-   ✅ Update summary
-   ✅ Update characters (step 2)
-   ✅ Update backgrounds (step 3)
-   ✅ Generate draft (async)
-   ✅ Get draft status
-   ✅ Cancel draft generation
-   ✅ List drafts (user's drafts)
-   ✅ List completed panels
-   ✅ Publish comic
-   ✅ Track read
-   ✅ Get similar comics
-   ✅ Export PDF
-   ✅ Generate video
-   ✅ Download PDF/Video
-   ✅ Preview video

### 4. Master Data

-   ✅ Get styles
-   ✅ Get genres
-   ✅ Get characters
-   ✅ Get backgrounds

### 5. Social Features

-   ✅ Comments (list, create) - `CommentController`
-   ✅ Likes (list, create, delete, status) - `LikeController`
-   ✅ Read history - `HistoryController`

### 6. Subscriptions (`SubscriptionController`)

-   ✅ List packages
-   ✅ Get payment methods
-   ✅ Purchase subscription
-   ✅ Check subscription status
-   ✅ Payment history
-   ✅ Payment callback (webhook)

### 7. Monetization

-   ✅ Wallet info - `WalletController`
-   ✅ Withdrawal requests
-   ✅ Referral list - `ReferralController`

### 8. Notifications (`NotificationController`)

-   ✅ List notifications (paginated)
-   ✅ Unread count
-   ✅ Mark as read
-   ✅ Delete notification

### 9. Analytics (`AnalyticsController`)

-   ✅ Master dashboard
-   ✅ Daily stats
-   ✅ Monthly stats
-   ✅ Yearly stats
-   ✅ Transaction history

### 10. Banners (`BannerController`)

-   ✅ Show banner
-   ✅ Update banner

### 11. Drafts (`DraftController`)

-   ✅ Show draft
-   ✅ Delete draft

### 12. Speech-to-Text (`SpeechToTextController`)

-   ✅ Transcribe audio
-   ✅ Check transcription status

---

## 🚀 Step-by-Step Implementation Plan

### PHASE 1: Setup & Infrastructure (Hari 1-2)

#### Step 1.1: Project Initialization

```bash
# Create project structure
mkdir -p app/{api,core,models,schemas,services,utils}
touch app/__init__.py app/main.py
```

#### Step 1.2: Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary
pip install pydantic python-jose[cryptography] passlib[bcrypt]
pip install python-multipart python-dotenv httpx
pip install google-cloud-storage google-cloud-texttospeech
pip install google-cloud-speech google-auth firebase-admin
```

#### Step 1.3: Configuration (`app/core/config.py`)

-   Environment variables
-   Database settings
-   JWT settings
-   Google Cloud settings

#### Step 1.4: Database Connection (`app/core/database.py`)

-   SQLAlchemy engine
-   Session management
-   Base model

---

### PHASE 2: Models & Schemas (Hari 3-5)

#### Step 2.1: Create SQLAlchemy Models (`app/models/`)

Buat file untuk setiap model:

-   `user.py` - User model
-   `comic.py` - Comic model
-   `comic_panel.py` - ComicPanel model
-   `comment.py` - Comment model
-   `subscription.py` - Subscription models
-   `transaction.py` - Transaction models
-   `notification.py` - Notification model
-   `master_data.py` - Style, Genre, Character, Background
-   `banner.py` - Banner model

#### Step 2.2: Create Pydantic Schemas (`app/schemas/`)

Request & Response schemas untuk setiap endpoint

#### Step 2.3: Database Migrations

```bash
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

---

### PHASE 3: Core Services (Hari 6-8)

#### Step 3.1: Authentication Service (`app/services/auth_service.py`)

-   Password hashing
-   JWT token generation/validation
-   Google OAuth integration
-   OTP generation/verification

#### Step 3.2: Google Cloud Services (`app/services/`)

-   `google_storage_service.py` - File upload/download
-   `google_ai_service.py` - AI text generation
-   `text_to_speech_service.py` - TTS
-   `speech_to_text_service.py` - STT

#### Step 3.3: External Services

-   `fcm_service.py` - Firebase notifications
-   `doku_service.py` - Payment gateway

---

### PHASE 4: API Endpoints (Hari 9-15)

#### Step 4.1: Authentication Routes (`app/api/auth.py`)

```python
POST /register
POST /login
POST /verify
POST /resend-verification
GET /v1/auth/google/redirect
GET /v1/auth/google/callback
POST /v1/auth/google/verify-token
POST /refresh
POST /logout
```

#### Step 4.2: User Routes (`app/api/users.py`)

```python
GET /profile
POST /password/change-password
POST /password/send-reset-token
POST /password/verify-reset-token
POST /password/reset-password
POST /profile/update-details
POST /profile/update-photo
POST /profile/update-kredit
GET /profile/referral-code
GET /profile/rating
```

#### Step 4.3: Comics Routes (`app/api/comics.py`)

```python
GET /v1/comics
GET /v1/comics/show/{comic_id}
POST /v1/comics/story-idea
PUT /v1/{comic}/summary
PUT /v1/comics/{comic}/characters
PUT /v1/comics/{comic}/backgrounds
POST /v1/comics/{comic}/drafts
GET /v1/comics/{comic}/draft/status
POST /v1/comics/{comic_id}/drafts/cancel
GET /v1/comics/drafts
GET /v1/drafts/{comic}/panels
POST /v1/comics/{comic}/publish
POST /v1/comics/{id}/track-read
GET /v1/comics/{comic}/similar
POST /v1/comics/{comic}/exportPdf
POST /v1/comics/{comic}/export/video
```

#### Step 4.4: Social Routes

-   `app/api/comments.py` - Comments endpoints
-   `app/api/likes.py` - Likes endpoints
-   `app/api/history.py` - Read history

#### Step 4.5: Master Data Routes (`app/api/master_data.py`)

```python
GET /v1/styles
GET /v1/genres
GET /v1/characters
GET /v1/backgrounds
```

#### Step 4.6: Subscription Routes (`app/api/subscriptions.py`)

```python
GET /v1/subscriptions/packages
GET /v1/payment-methods
POST /v1/subscriptions/purchase
GET /v1/me/subscription
GET /v1/subscriptions/payment-history
POST /v1/subscriptions/payment-callback
```

#### Step 4.7: Other Routes

-   `app/api/notifications.py`
-   `app/api/analytics.py`
-   `app/api/wallet.py`
-   `app/api/banners.py`

---

### PHASE 5: Middleware & Utils (Hari 16-17)

#### Step 5.1: Authentication Middleware

-   JWT verification
-   User context injection

#### Step 5.2: Error Handling

-   Custom exceptions
-   Global exception handler

#### Step 5.3: Utilities

-   Response formatters
-   File validators
-   Pagination helpers

---

### PHASE 6: Testing & Documentation (Hari 18-20)

#### Step 6.1: API Testing

-   Test authentication flow
-   Test CRUD operations
-   Test file uploads

#### Step 6.2: API Documentation

-   FastAPI auto-generates Swagger docs
-   Add descriptions & examples

---

## 📝 Catatan Penting

### Yang TIDAK Perlu Dikonversi

❌ Worker processes (Laravel Horizon)
❌ Job queues (GenerateDraftJob, dll)
❌ Background job processing

### Yang Perlu Dikonversi

✅ Semua API endpoints
✅ Authentication & authorization
✅ Database models & relationships
✅ File upload/download
✅ External service integrations
✅ Business logic di controllers

---

## 🔧 Environment Variables

```env
# App
APP_NAME=MamaStoria
APP_ENV=production
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Google Cloud
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_BUCKET_NAME=your-bucket
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Firebase
FIREBASE_CREDENTIALS=/path/to/firebase-key.json

# DOKU Payment
DOKU_CLIENT_ID=your-client-id
DOKU_SECRET_KEY=your-secret
DOKU_IS_PRODUCTION=false
```

---

## 📦 File Structure

```
Python-MamaStoria-v2/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── comics.py
│   │   ├── comments.py
│   │   ├── likes.py
│   │   ├── subscriptions.py
│   │   ├── notifications.py
│   │   └── ...
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── comic.py
│   │   └── ...
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── comic.py
│   │   └── ...
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── google_storage_service.py
│   │   ├── google_ai_service.py
│   │   └── ...
│   └── utils/
│       ├── __init__.py
│       ├── responses.py
│       └── pagination.py
├── alembic/
├── tests/
├── .env
├── requirements.txt
└── README.md
```

---

## ✅ Checklist Konversi

### Setup

-   [ ] Project structure created
-   [ ] Dependencies installed
-   [ ] Environment configured
-   [ ] Database connected

### Models (30 models)

-   [ ] User
-   [ ] Comic
-   [ ] ComicPanel
-   [ ] Comment
-   [ ] Style, Genre, Character, Background
-   [ ] Subscription, SubscriptionPackage
-   [ ] PaymentTransaction, Transaction
-   [ ] Notification
-   [ ] Banner
-   [ ] (27 models lainnya...)

### API Endpoints (80+ endpoints)

-   [ ] Authentication (8 endpoints)
-   [ ] User Management (10 endpoints)
-   [ ] Comics CRUD (20 endpoints)
-   [ ] Social Features (8 endpoints)
-   [ ] Subscriptions (6 endpoints)
-   [ ] Master Data (4 endpoints)
-   [ ] Notifications (4 endpoints)
-   [ ] Analytics (5 endpoints)
-   [ ] (endpoints lainnya...)

### Services

-   [ ] Auth Service
-   [ ] Google Storage Service
-   [ ] Google AI Service
-   [ ] TTS Service
-   [ ] STT Service
-   [ ] FCM Service
-   [ ] DOKU Service

### Testing

-   [ ] Unit tests
-   [ ] Integration tests
-   [ ] API tests

---

**Estimasi Total**: 20 hari kerja
**Prioritas**: API CRUD > Authentication > File Upload > External Services
