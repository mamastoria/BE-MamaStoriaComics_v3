# Check Verification Code API Documentation

## Endpoint: Check Verification Code

**URL:** `POST /api/v1/users/check-verification-code`

**Authentication:** Not required (public endpoint)

**Description:** Verifies if a verification code is valid for a given email address. Useful for email verification, password reset verification, or any other verification flow.

---

## Request

### Headers

```http
Content-Type: application/json
```

### Body

```json
{
  "email": "user@example.com",
  "verification_code": "123456"
}
```

### Parameters

| Field               | Type              | Required | Description               | Validation           |
| ------------------- | ----------------- | -------- | ------------------------- | -------------------- |
| `email`             | String (EmailStr) | Yes      | User's email address      | Valid email format   |
| `verification_code` | String            | Yes      | 6-digit verification code | Exactly 6 characters |

---

## Response

### Success Response (200 OK)

```json
{
  "ok": true,
  "message": "Verification code is valid",
  "data": {
    "user_id": 123,
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_verified": true
  }
}
```

### Error Responses

#### User Not Found (404)

```json
{
  "detail": "User not found"
}
```

#### Invalid Verification Code (400)

```json
{
  "detail": "Invalid verification code"
}
```

#### Verification Code Expired (400)

```json
{
  "detail": "Verification code expired"
}
```

---

## How It Works

1. **User Lookup:** Finds user by email address
2. **Code Validation:** Checks if `verification_code` matches `user.verification_code` in database
3. **Expiry Check:** Verifies code was sent within last 15 minutes (based on `last_verification_sent_at`)
4. **Return User Info:** If valid, returns basic user information

---

## Code Expiration

- **Expiry Time:** 15 minutes from `last_verification_sent_at`
- **Timezone:** UTC

---

## Use Cases

1. **Email Verification:** Verify user email after registration
2. **Password Reset:** Confirm reset code before allowing password change
3. **Two-Factor Authentication:** Validate 2FA codes
4. **Account Recovery:** Verify user identity for account recovery

---

## Example Usage

### cURL

```bash
curl -X POST https://your-api.com/api/v1/users/check-verification-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "verification_code": "123456"
  }'
```

### JavaScript/Fetch

```javascript
const response = await fetch(
  "https://your-api.com/api/v1/users/check-verification-code",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: "user@example.com",
      verification_code: "123456",
    }),
  }
);

const result = await response.json();

if (result.ok) {
  console.log("Code is valid!", result.data);
} else {
  console.error("Invalid code");
}
```

### Python/Requests

```python
import requests

url = "https://your-api.com/api/v1/users/check-verification-code"
payload = {
    "email": "user@example.com",
    "verification_code": "123456"
}

response = requests.post(url, json=payload)
result = response.json()

if result.get("ok"):
    print("Code is valid!", result["data"])
else:
    print("Invalid code:", result.get("detail"))
```

---

## Related Endpoints

### Send Verification Code

**POST** `/api/v1/password/send-reset-token`

Sends a new verification code to user's email.

**Request:**

```json
{
  "email": "user@example.com"
}
```

**Response:**

```json
{
  "ok": true,
  "message": "Reset code sent successfully to your email"
}
```

---

## Database Fields Used

| Field                       | Table   | Description                                     |
| --------------------------- | ------- | ----------------------------------------------- |
| `email`                     | `users` | User's email address (unique)                   |
| `verification_code`         | `users` | 6-digit code stored in database                 |
| `last_verification_sent_at` | `users` | Timestamp when code was sent (for expiry check) |

---

## Security Notes

1. ✅ **Rate Limiting Recommended:** Implement rate limiting to prevent brute force attacks
2. ✅ **Code Expiry:** Codes expire after 15 minutes
3. ✅ **Single Use:** Consider clearing code after successful verification
4. ⚠️ **No Authentication Required:** This is a public endpoint (by design for verification flows)

---

## Flow Diagram

```
User Request
    ↓
Check if user exists (by email)
    ↓
Validate verification_code matches
    ↓
Check if code expired (15 min)
    ↓
Return user info (success)
```

---

## Testing

### Valid Code Test

```bash
# 1. Send verification code
curl -X POST https://your-api.com/api/v1/password/send-reset-token \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# 2. Check the code (get from email or logs)
curl -X POST https://your-api.com/api/v1/users/check-verification-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "verification_code": "123456"
  }'
```

### Invalid Code Test

```bash
curl -X POST https://your-api.com/api/v1/users/check-verification-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "verification_code": "999999"
  }'
# Expected: 400 Bad Request - "Invalid verification code"
```

### Expired Code Test

```bash
# Wait 16 minutes after sending code, then check
curl -X POST https://your-api.com/api/v1/users/check-verification-code \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "verification_code": "123456"
  }'
# Expected: 400 Bad Request - "Verification code expired"
```
