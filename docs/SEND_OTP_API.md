# Send OTP API Documentation

## Endpoint: Send OTP to Email

**URL:** `POST /api/v1/users/send-otp`

**Authentication:** Not required (public endpoint)

**Description:** Generates a 6-digit OTP verification code, saves it to the database, and sends it to the user's email address via Resend email service.

---

## Request

### Headers

```http
Content-Type: application/json
```

### Body

```json
{
  "email": "user@example.com"
}
```

### Parameters

| Field   | Type              | Required | Description          | Validation         |
| ------- | ----------------- | -------- | -------------------- | ------------------ |
| `email` | String (EmailStr) | Yes      | User's email address | Valid email format |

---

## Response

### Success Response (200 OK)

```json
{
  "ok": true
}
```

### Failure Response (200 OK)

```json
{
  "ok": false
}
```

**Note:** Returns `false` if:

- User with email doesn't exist
- Email sending failed
- Any other error occurred

For security reasons, the API doesn't reveal whether the user exists or not.

---

## How It Works

1. **User Lookup:** Checks if user exists by email
2. **Generate OTP:** Creates 6-digit random verification code
3. **Save to Database:**
   - Stores code in `user.verification_code`
   - Updates `user.last_verification_sent_at` with current timestamp
4. **Send Email:** Sends formatted email with OTP via Resend API
5. **Return Status:** Returns `true` if successful, `false` otherwise

---

## Email Template

The OTP email sent to users looks like this:

**Subject:** Your Verification Code

**Body:**

```html
Verification Code Your verification code is: ┌─────────────┐ │ 123456 │
└─────────────┘ This code will expire in 15 minutes. If you didn't request this
code, please ignore this email.
```

---

## OTP Details

- **Format:** 6-digit numeric code
- **Expiry:** 15 minutes from generation
- **Storage:** Saved in `users.verification_code` field
- **Timestamp:** `users.last_verification_sent_at` tracks when code was sent

---

## Security Features

1. ✅ **No User Enumeration:** Returns same response whether user exists or not
2. ✅ **Time-Limited:** OTP expires after 15 minutes
3. ✅ **Single Active Code:** New OTP overwrites previous one
4. ✅ **Error Hiding:** Doesn't expose internal errors to client

---

## Example Usage

### cURL

```bash
curl -X POST https://your-api.com/api/v1/users/send-otp \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

**Response:**

```json
{ "ok": true }
```

### JavaScript/Fetch

```javascript
const response = await fetch("https://your-api.com/api/v1/users/send-otp", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    email: "user@example.com",
  }),
});

const result = await response.json();

if (result.ok) {
  console.log("OTP sent successfully!");
  // Show OTP input form
} else {
  console.log("Failed to send OTP");
  // Show error message
}
```

### Python/Requests

```python
import requests

url = "https://your-api.com/api/v1/users/send-otp"
payload = {"email": "user@example.com"}

response = requests.post(url, json=payload)
result = response.json()

if result.get("ok"):
    print("OTP sent successfully!")
else:
    print("Failed to send OTP")
```

---

## Complete Verification Flow

### Step 1: Send OTP

```bash
POST /api/v1/users/send-otp
{
  "email": "user@example.com"
}

Response: {"ok": true}
```

### Step 2: User Receives Email

User gets email with 6-digit code (e.g., `123456`)

### Step 3: Verify OTP

```bash
POST /api/v1/users/check-verification-code
{
  "email": "user@example.com",
  "verification_code": "123456"
}

Response: {
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

---

## Error Handling

### User Not Found

```json
{
  "ok": false
}
```

**Note:** Same response as email sending failure (security feature)

### Email Sending Failed

```json
{
  "ok": false
}
```

**Server Logs:**

```
Failed to send OTP email: [error details]
```

### Invalid Email Format

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting Recommendations

⚠️ **Important:** Implement rate limiting to prevent abuse:

- **Per Email:** Max 3 requests per 15 minutes
- **Per IP:** Max 10 requests per hour
- **Global:** Monitor for unusual patterns

Example rate limit response:

```json
{
  "ok": false,
  "message": "Too many requests. Please try again later."
}
```

---

## Database Fields

| Field                       | Type     | Description                       |
| --------------------------- | -------- | --------------------------------- |
| `verification_code`         | String   | 6-digit OTP code                  |
| `last_verification_sent_at` | DateTime | Timestamp when OTP was sent (UTC) |

---

## Email Service Configuration

**Provider:** Resend (https://resend.com)

**Configuration:**

- API Key: Stored in code (should be moved to environment variables)
- From Address: `onboarding@resend.dev`
- API Endpoint: `https://api.resend.com/emails`

**Recommendation:** Move to environment variables:

```python
RESEND_KEY = os.getenv("RESEND_API_KEY")
RESEND_EMAIL_FROM = os.getenv("RESEND_EMAIL_FROM", "noreply@yourdomain.com")
```

---

## Testing

### Test with Valid Email

```bash
curl -X POST http://localhost:8080/api/v1/users/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "existing@example.com"}'

# Expected: {"ok": true}
# Check email inbox for OTP
```

### Test with Non-Existent Email

```bash
curl -X POST http://localhost:8080/api/v1/users/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "nonexistent@example.com"}'

# Expected: {"ok": false}
```

### Test with Invalid Email Format

```bash
curl -X POST http://localhost:8080/api/v1/users/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "invalid-email"}'

# Expected: 422 Validation Error
```

---

## Related Endpoints

### Check Verification Code

**POST** `/api/v1/users/check-verification-code`

Verifies if OTP is valid.

**Request:**

```json
{
  "email": "user@example.com",
  "verification_code": "123456"
}
```

**Response:**

```json
{
  "ok": true,
  "message": "Verification code is valid",
  "data": {...}
}
```

---

## Use Cases

1. ✅ **Email Verification:** Verify user email after registration
2. ✅ **Password Reset:** Send OTP for password reset flow
3. ✅ **Two-Factor Authentication:** Add extra security layer
4. ✅ **Account Recovery:** Verify user identity
5. ✅ **Login Verification:** Passwordless login via OTP

---

## Best Practices

1. ✅ **Always use HTTPS** in production
2. ✅ **Implement rate limiting** to prevent abuse
3. ✅ **Log failed attempts** for security monitoring
4. ✅ **Clear OTP after successful verification** (optional)
5. ✅ **Use environment variables** for sensitive config
6. ✅ **Monitor email delivery** success rates

---

## Troubleshooting

### OTP Not Received

1. Check spam/junk folder
2. Verify email address is correct
3. Check server logs for email sending errors
4. Verify Resend API key is valid
5. Check Resend dashboard for delivery status

### OTP Expired

- OTP expires after 15 minutes
- Request new OTP by calling `/send-otp` again
- Previous OTP will be overwritten

### Email Sending Fails

**Common Causes:**

- Invalid Resend API key
- Rate limit exceeded on Resend
- Invalid sender email address
- Network connectivity issues

**Solution:**

- Check server logs for detailed error
- Verify Resend account status
- Check API key permissions
