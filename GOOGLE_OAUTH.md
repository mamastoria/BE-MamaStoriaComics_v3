# Google OAuth Integration Guide

## Overview

MamaStoria API sekarang mendukung **Google OAuth** untuk registrasi dan login pengguna. Ada 2 metode yang tersedia:

1. **Server-side OAuth Flow** - Untuk web applications
2. **Client-side Token Verification** - Untuk mobile apps (Recommended)

---

## Setup

### 1. Google Cloud Console Setup

1. Buka [Google Cloud Console](https://console.cloud.google.com/)
2. Pilih atau buat project
3. Enable **Google+ API**
4. Buat **OAuth 2.0 Client ID**:
   - Application type: Web application (untuk server-side) atau Android/iOS (untuk mobile)
   - Authorized redirect URIs: `http://localhost:8000/api/v1/auth/google/callback`

### 2. Environment Variables

Tambahkan ke file `.env`:

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

---

## API Endpoints

### 1. Server-side OAuth Flow (Web)

#### Step 1: Redirect to Google

```http
GET /api/v1/auth/google/redirect
```

**Response**: Redirect ke Google OAuth consent screen

#### Step 2: Handle Callback

```http
GET /api/v1/auth/google/callback?code={authorization_code}
```

**Response**:

```json
{
  "ok": true,
  "message": "Google login successful",
  "data": {
    "user": {
      "id_users": 1,
      "full_name": "John Doe",
      "email": "john@example.com",
      "phone_number": "google_1234567890",
      "is_verified": true,
      "login_method": "google",
      ...
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

---

### 2. Client-side Token Verification (Mobile - Recommended)

Untuk mobile apps, gunakan Google Sign-In SDK di client, lalu kirim ID token ke backend.

#### Verify Google ID Token

```http
POST /api/v1/auth/google/verify-token
Content-Type: application/json

{
  "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
}
```

**Response**:

```json
{
  "ok": true,
  "message": "Google login successful",
  "data": {
    "user": {
      "id_users": 1,
      "full_name": "John Doe",
      "email": "john@example.com",
      "phone_number": "google_1234567890",
      "is_verified": true,
      "login_method": "google",
      "external_id": "1234567890",
      "profile_photo_path": "https://lh3.googleusercontent.com/...",
      ...
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

---

## Implementation Examples

### Flutter/Dart (Mobile)

```dart
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

final GoogleSignIn _googleSignIn = GoogleSignIn(
  scopes: ['email', 'profile'],
);

Future<void> signInWithGoogle() async {
  try {
    // Sign in with Google
    final GoogleSignInAccount? account = await _googleSignIn.signIn();

    if (account == null) return; // User cancelled

    // Get authentication
    final GoogleSignInAuthentication auth = await account.authentication;

    // Send ID token to backend
    final response = await http.post(
      Uri.parse('http://localhost:8000/api/v1/auth/google/verify-token'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'id_token': auth.idToken,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final accessToken = data['data']['tokens']['access_token'];
      final user = data['data']['user'];

      // Save token and user data
      print('Login successful: ${user['full_name']}');
    }
  } catch (error) {
    print('Error: $error');
  }
}
```

### JavaScript (Web)

```javascript
// Using Google Sign-In JavaScript Library
function onSignIn(googleUser) {
  const id_token = googleUser.getAuthResponse().id_token;

  fetch("http://localhost:8000/api/v1/auth/google/verify-token", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      id_token: id_token,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.ok) {
        const accessToken = data.data.tokens.access_token;
        const user = data.data.user;

        // Save token and user data
        localStorage.setItem("access_token", accessToken);
        console.log("Login successful:", user.full_name);
      }
    })
    .catch((error) => console.error("Error:", error));
}
```

### Python (Testing)

```python
import requests

# Verify Google ID token
response = requests.post(
    'http://localhost:8000/api/v1/auth/google/verify-token',
    json={
        'id_token': 'your-google-id-token-here'
    }
)

if response.status_code == 200:
    data = response.json()
    access_token = data['data']['tokens']['access_token']
    user = data['data']['user']
    print(f"Login successful: {user['full_name']}")
else:
    print(f"Error: {response.json()['detail']}")
```

---

## User Flow

### New User (First Time Google Login)

1. User clicks "Sign in with Google"
2. User authorizes the app on Google
3. Backend receives Google ID token
4. Backend verifies token with Google
5. Backend creates new user with:
   - `full_name` from Google
   - `email` from Google
   - `external_id` = Google user ID
   - `login_method` = "google"
   - `is_verified` = true (trust Google verification)
   - `phone_number` = placeholder (can be updated later)
   - `profile_photo_path` = Google profile picture
6. Backend returns JWT tokens
7. User is logged in

### Existing User (Return Login)

1. User clicks "Sign in with Google"
2. Backend finds user by `external_id` (Google ID)
3. Backend returns JWT tokens
4. User is logged in

### Link Google to Existing Account

If a user already exists with the same email:

1. Backend finds user by email
2. Backend links Google account by setting `external_id`
3. Backend updates `login_method` to "google"
4. User can now login with Google

---

## Security Notes

1. **ID Token Verification**: Backend verifies ID token dengan Google untuk memastikan authenticity
2. **Email Verification**: Email dari Google sudah terverifikasi, jadi `is_verified` langsung `true`
3. **No Password**: User yang login via Google tidak memiliki password
4. **Phone Number**: Phone number adalah placeholder, user bisa update nanti jika diperlukan

---

## Testing

### Using Swagger UI

1. Buka `http://localhost:8000/docs`
2. Cari endpoint `/api/v1/auth/google/verify-token`
3. Klik "Try it out"
4. Masukkan Google ID token
5. Klik "Execute"

### Get Test ID Token

Untuk testing, gunakan Google OAuth Playground:

1. Buka https://developers.google.com/oauthplayground/
2. Pilih "Google OAuth2 API v2"
3. Select scopes: `email`, `profile`, `openid`
4. Authorize APIs
5. Exchange authorization code for tokens
6. Copy `id_token` untuk testing

---

## Troubleshooting

### Error: "Invalid Google token"

- Pastikan `GOOGLE_CLIENT_ID` di `.env` sesuai dengan client ID di Google Cloud Console
- Pastikan ID token belum expired (valid 1 jam)
- Pastikan ID token dari client yang benar

### Error: "Failed to exchange authorization code"

- Pastikan `GOOGLE_CLIENT_SECRET` benar
- Pastikan `GOOGLE_REDIRECT_URI` sesuai dengan yang terdaftar di Google Cloud Console

### User Created with Placeholder Phone Number

- Ini normal untuk Google OAuth users
- User bisa update phone number nanti via `/api/v1/users/profile`

---

## Next Steps

Setelah Google OAuth berjalan:

1. ✅ User bisa register/login dengan Google
2. ✅ User data otomatis terisi dari Google
3. ✅ Profile picture otomatis dari Google
4. ⏳ User bisa update phone number jika diperlukan
5. ⏳ User bisa link multiple login methods (Google + phone/email)

---

## API Summary

| Endpoint                           | Method | Purpose               | Use Case       |
| ---------------------------------- | ------ | --------------------- | -------------- |
| `/api/v1/auth/google/redirect`     | GET    | Initiate OAuth flow   | Web apps       |
| `/api/v1/auth/google/callback`     | GET    | Handle OAuth callback | Web apps       |
| `/api/v1/auth/google/verify-token` | POST   | Verify ID token       | Mobile apps ⭐ |

**Recommended**: Use `/google/verify-token` for mobile apps (Flutter, React Native, etc.)
