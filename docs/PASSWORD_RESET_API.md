# Password Reset API Documentation

## Complete Password Reset Flow

The password reset feature consists of 3 endpoints that work together to securely reset user passwords.

---

## Endpoint 1: Send Reset Token

**URL:** `POST /api/v1/password/send-reset-token`

**Authentication:** Not required (public endpoint)

**Description:** Generates a 6-digit reset code, saves it to the database, and sends it to the user's email via Resend.

### Request

```json
{
  "email": "user@example.com"
}
```

### Response (Always Success for Security)

```json
{
  "ok": true,
  "message": "Reset code sent successfully to your email"
}
```

**Note:** Returns success message even if email doesn't exist (security feature to prevent user enumeration).

### Email Template

**Subject:** Password Reset Code

**Body:**

```
Password Reset Request

You have requested to reset your password. Use the code below:

┌─────────────┐
│   123456    │
└─────────────┘

This code will expire in 15 minutes.

If you didn't request this, please ignore this email and your password will remain unchanged.
```

### What Happens

1. ✅ Check if user exists by email
2. ✅ Generate 6-digit reset code
3. ✅ Save to `verification_code` field
4. ✅ Update `last_verification_sent_at` timestamp
5. ✅ Send formatted email via Resend API
6. ✅ Return success message

---

## Endpoint 2: Verify Reset Token (Optional)

**URL:** `POST /api/v1/password/verify-reset-token`

**Authentication:** Not required

**Description:** Validates the reset code before allowing password reset. This step is optional but recommended for better UX.

### Request

```json
{
  "email": "user@example.com",
  "reset_token": "123456"
}
```

### Response Success

```json
{
  "ok": true,
  "message": "Reset code verified. You can now reset your password."
}
```

### Response Error

**Invalid Code (400):**

```json
{
  "detail": "Invalid reset code"
}
```

**Expired Code (400):**

```json
{
  "detail": "Reset code expired"
}
```

### Validation Rules

- ✅ Code must match `verification_code` in database
- ✅ Code must not be expired (15 minutes from `last_verification_sent_at`)
- ✅ User must exist

---

## Endpoint 3: Reset Password

**URL:** `POST /api/v1/password/reset-password`

**Authentication:** Not required

**Description:** Resets the user's password using the verified reset code.

### Request

```json
{
  "email": "user@example.com",
  "reset_token": "123456",
  "new_password": "newSecurePassword123"
}
```

### Response Success

```json
{
  "ok": true,
  "message": "Password reset successfully"
}
```

### Response Error

**Invalid Code (400):**

```json
{
  "detail": "Invalid reset code"
}
```

**Expired Code (400):**

```json
{
  "detail": "Reset code expired"
}
```

### What Happens

1. ✅ Validate reset code matches
2. ✅ Check code expiry (15 minutes)
3. ✅ Hash new password
4. ✅ Update user password
5. ✅ Clear `verification_code` (prevent reuse)
6. ✅ Commit to database

---

## Complete Flow Example

### Step 1: Request Reset Code

```bash
curl -X POST https://your-api.com/api/v1/password/send-reset-token \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

**Response:**

```json
{
  "ok": true,
  "message": "Reset code sent successfully to your email"
}
```

### Step 2: User Receives Email

User checks email and gets code: `123456`

### Step 3: (Optional) Verify Code

```bash
curl -X POST https://your-api.com/api/v1/password/verify-reset-token \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "reset_token": "123456"
  }'
```

**Response:**

```json
{
  "ok": true,
  "message": "Reset code verified. You can now reset your password."
}
```

### Step 4: Reset Password

```bash
curl -X POST https://your-api.com/api/v1/password/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "reset_token": "123456",
    "new_password": "newSecurePassword123"
  }'
```

**Response:**

```json
{
  "ok": true,
  "message": "Password reset successfully"
}
```

---

## JavaScript Example

```javascript
// Step 1: Send reset code
async function sendResetCode(email) {
  const response = await fetch("/api/v1/password/send-reset-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  const result = await response.json();
  console.log(result.message);
  // Show "Check your email" message
}

// Step 2: Verify code (optional)
async function verifyResetCode(email, resetToken) {
  try {
    const response = await fetch("/api/v1/password/verify-reset-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, reset_token: resetToken }),
    });

    if (response.ok) {
      const result = await response.json();
      console.log("Code verified!");
      return true;
    } else {
      const error = await response.json();
      console.error(error.detail);
      return false;
    }
  } catch (error) {
    console.error("Verification failed:", error);
    return false;
  }
}

// Step 3: Reset password
async function resetPassword(email, resetToken, newPassword) {
  try {
    const response = await fetch("/api/v1/password/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        reset_token: resetToken,
        new_password: newPassword,
      }),
    });

    if (response.ok) {
      const result = await response.json();
      console.log("Password reset successfully!");
      // Redirect to login page
      return true;
    } else {
      const error = await response.json();
      console.error(error.detail);
      return false;
    }
  } catch (error) {
    console.error("Reset failed:", error);
    return false;
  }
}

// Usage
await sendResetCode("user@example.com");
// User enters code from email
const isValid = await verifyResetCode("user@example.com", "123456");
if (isValid) {
  await resetPassword("user@example.com", "123456", "newPassword123");
}
```

---

## Security Features

### 1. No User Enumeration

- ✅ Always returns success when sending reset code
- ✅ Doesn't reveal if email exists or not

### 2. Code Expiration

- ✅ Codes expire after 15 minutes
- ✅ Tracked via `last_verification_sent_at`

### 3. Single Use

- ✅ Code is cleared after successful password reset
- ✅ Prevents code reuse

### 4. Code Overwriting

- ✅ New reset request overwrites previous code
- ✅ Only latest code is valid

### 5. Password Hashing

- ✅ Passwords are hashed using bcrypt
- ✅ Never stored in plain text

---

## Database Fields

| Field                       | Type     | Description              |
| --------------------------- | -------- | ------------------------ |
| `verification_code`         | String   | 6-digit reset code       |
| `last_verification_sent_at` | DateTime | When code was sent (UTC) |
| `password`                  | String   | Hashed password          |

---

## Email Service Configuration

**Provider:** Resend (https://resend.com)

**Settings:**

- API Key: `re_hsvmU2Zv_EjdhcaWUC7aRuUgfjfinhfVq`
- From Email: `onboarding@resend.dev`
- API URL: `https://api.resend.com/emails`

**Recommendation:** Move to environment variables:

```python
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_EMAIL_FROM = os.getenv("RESEND_EMAIL_FROM", "noreply@yourdomain.com")
```

---

## Error Handling

### Common Errors

| Error                | Status | Cause                  | Solution                    |
| -------------------- | ------ | ---------------------- | --------------------------- |
| Invalid reset code   | 400    | Code doesn't match     | Request new code            |
| Reset code expired   | 400    | Code older than 15 min | Request new code            |
| User not found       | 200\*  | Email doesn't exist    | Returns success (security)  |
| Email sending failed | 200\*  | Resend API error       | Check logs, returns success |

\*Returns success for security reasons

---

## Testing

### Test Valid Flow

```bash
# 1. Send reset code
curl -X POST http://localhost:8080/api/v1/password/send-reset-token \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# 2. Check email for code (or check server logs)

# 3. Verify code
curl -X POST http://localhost:8080/api/v1/password/verify-reset-token \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "reset_token": "123456"
  }'

# 4. Reset password
curl -X POST http://localhost:8080/api/v1/password/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "reset_token": "123456",
    "new_password": "newPassword123"
  }'
```

### Test Invalid Code

```bash
curl -X POST http://localhost:8080/api/v1/password/verify-reset-token \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "reset_token": "999999"
  }'

# Expected: 400 - "Invalid reset code"
```

### Test Expired Code

```bash
# Wait 16 minutes after sending code, then verify
curl -X POST http://localhost:8080/api/v1/password/verify-reset-token \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "reset_token": "123456"
  }'

# Expected: 400 - "Reset code expired"
```

---

## Best Practices

1. ✅ **Always use HTTPS** in production
2. ✅ **Implement rate limiting** (max 3 requests per email per hour)
3. ✅ **Log all reset attempts** for security monitoring
4. ✅ **Notify users** when password is changed
5. ✅ **Use strong password validation** (min length, complexity)
6. ✅ **Clear sessions** after password reset
7. ✅ **Monitor email delivery** success rates

---

## Rate Limiting Recommendations

Prevent abuse with rate limits:

- **Per Email:** Max 3 reset requests per hour
- **Per IP:** Max 10 reset requests per hour
- **Global:** Monitor for unusual patterns

---

## Troubleshooting

### Email Not Received

1. Check spam/junk folder
2. Verify email address is correct
3. Check server logs for sending errors
4. Verify Resend API key is valid
5. Check Resend dashboard for delivery status

### Code Expired

- Codes expire after 15 minutes
- Request new code via `/send-reset-token`
- Previous code will be overwritten

### Email Sending Fails

**Common Causes:**

- Invalid Resend API key
- Rate limit exceeded
- Invalid sender email
- Network issues

**Solution:**

- Check server logs for detailed error
- Verify Resend account status
- Check API key permissions

---

## Related Endpoints

### Change Password (Authenticated)

**POST** `/api/v1/password/change-password`

For users who are logged in and know their current password.

**Request:**

```json
{
  "old_password": "currentPassword",
  "new_password": "newPassword123"
}
```

---

## Summary

✅ **3 Endpoints:** Send, Verify, Reset  
✅ **Email Integration:** Resend API  
✅ **Security:** No user enumeration, code expiry, single use  
✅ **Expiry:** 15 minutes  
✅ **Format:** 6-digit numeric code  
✅ **Validation:** Email format, password min 6 chars
