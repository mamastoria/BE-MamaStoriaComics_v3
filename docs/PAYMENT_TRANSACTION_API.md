# PaymentTransaction API Documentation

## Model: PaymentTransaction

Tabel `payment_transactions` menyimpan semua transaksi pembayaran dari payment gateway (Doku).

### Field List

| Field              | Type       | Nullable | Description                                                       | Auto-filled              |
| ------------------ | ---------- | -------- | ----------------------------------------------------------------- | ------------------------ |
| `id`               | Integer    | No       | Primary key, auto-increment                                       | ✅ Auto                  |
| `user_id`          | Integer    | No       | Foreign key ke `users.id_users`                                   | ✅ From auth             |
| `subscription_id`  | Integer    | Yes      | Foreign key ke `subscriptions.id` (diisi setelah payment success) | ✅ After payment         |
| `invoice_number`   | String     | No       | Nomor invoice unik (format: INV-XXXXX-timestamp)                  | ✅ Auto-generated        |
| `amount`           | BigInteger | No       | Jumlah pembayaran (dalam satuan terkecil, misal: cents/rupiah)    | ✅ From package          |
| `payment_method`   | String     | Yes      | Metode pembayaran (qris, gopay, dana, bni_va, dll)                | ⚠️ Optional input        |
| `status`           | String     | No       | Status transaksi: `pending`, `success`, `failed`, `expired`       | ✅ Default: pending      |
| `payment_url`      | Text       | Yes      | URL untuk checkout payment dari Doku                              | ✅ From Doku API         |
| `doku_order_id`    | String     | Yes      | Order ID dari Doku (sama dengan invoice_number)                   | ✅ Auto-generated        |
| `doku_response`    | Text       | Yes      | JSON response lengkap dari Doku callback (untuk audit trail)      | ✅ From callback         |
| `type_transaction` | String     | Yes      | Tipe transaksi: `subscription`, `topup`, dll                      | ✅ Set to 'subscription' |
| `expires_at`       | DateTime   | Yes      | Waktu kadaluarsa pembayaran (24 jam dari pembuatan)               | ✅ Auto: now + 24h       |
| `created_at`       | DateTime   | No       | Waktu pembuatan record                                            | ✅ Auto                  |
| `updated_at`       | DateTime   | No       | Waktu update terakhir                                             | ✅ Auto                  |

---

## API Endpoints

### 1. Create Payment Transaction

**Endpoint:** `POST /api/v1/subscriptions/purchase`

**Authentication:** Required (Bearer token)

**Request Body:**

```json
{
  "packageId": 1, // Required (atau gunakan packageSlug)
  "packageSlug": "credits-20", // Alternative dari packageId
  "paymentMethod": "qris" // Optional: qris, gopay, dana, ovo, bni_va, bri_va, bca_va, mandiri_va
}
```

**Response (201 Created):**

```json
{
  "ok": true,
  "message": "Transaction created successfully. Please proceed to payment.",
  "data": {
    "invoice_number": "INV-A1B2C3D4-1704067200",
    "amount": 50000,
    "payment_url": "https://sandbox.doku.com/checkout/...",
    "package_name": "Credits 20"
  }
}
```

**What Gets Saved:**

```json
{
  "id": 123, // Auto-increment
  "user_id": 456, // From current_user
  "subscription_id": null, // Null until payment success
  "invoice_number": "INV-A1B2C3D4-1704067200", // Auto-generated
  "amount": 50000, // From package.price
  "payment_method": "qris", // From request body
  "status": "pending", // Default
  "payment_url": "https://sandbox.doku.com/...", // From Doku API
  "doku_order_id": "INV-A1B2C3D4-1704067200", // Same as invoice_number
  "doku_response": null, // Filled on callback
  "type_transaction": "subscription", // Fixed value
  "expires_at": "2026-01-02T07:00:00Z", // Now + 24 hours
  "created_at": "2026-01-01T07:00:00Z", // Auto
  "updated_at": "2026-01-01T07:00:00Z" // Auto
}
```

---

### 2. Payment Callback (Webhook from Doku)

**Endpoint:** `POST /api/v1/subscriptions/payment-callback`

**Authentication:** None (validated via Doku signature)

**Request Body (from Doku):**

```json
{
  "order": {
    "invoice_number": "INV-A1B2C3D4-1704067200"
  },
  "transaction": {
    "status": "SUCCESS" // or "FAILED", "EXPIRED"
  }
}
```

**What Gets Updated:**

```json
{
  "status": "success", // Updated from "pending"
  "subscription_id": 789, // Created/updated subscription
  "doku_response": "{\"order\":{...},\"transaction\":{...}}" // Full callback payload
}
```

**Side Effects:**

- ✅ Create/update `Subscription` record
- ✅ Add `publish_quota` to user
- ✅ Add `bonus_credits` to user

---

### 3. Get Payment History

**Endpoint:** `GET /api/v1/subscriptions/payment-history?page=1&per_page=20`

**Authentication:** Required

**Response:**

```json
{
  "ok": true,
  "data": [
    {
      "id": 123,
      "invoice_number": "INV-A1B2C3D4-1704067200",
      "amount": 50000,
      "status": "success",
      "payment_method": "qris",
      "created_at": "2026-01-01T07:00:00Z",
      "package_name": "Credits 20"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

---

## Field Validation Summary

### ✅ Automatically Handled (No Input Required)

- `id` - Auto-increment
- `user_id` - From authentication
- `subscription_id` - Filled after payment success
- `invoice_number` - Auto-generated UUID format
- `doku_order_id` - Same as invoice_number
- `amount` - From selected package
- `status` - Default "pending", updated via callback
- `payment_url` - From Doku API response
- `doku_response` - From Doku callback
- `type_transaction` - Set to "subscription"
- `expires_at` - Auto-calculated (now + 24h)
- `created_at` - Auto timestamp
- `updated_at` - Auto timestamp

### ⚠️ Optional User Input

- `payment_method` - User can select payment method (optional)

### 🔒 Never Directly Settable by User

- `status` - Only updated via payment callback
- `doku_response` - Only from Doku webhook
- `subscription_id` - Only after successful payment

---

## Database Migration

Migration file created: `2026_01_01_0725-9e2e96e7d089_add_type_transaction_and_expires_at_to_.py`

**To apply migration:**

```bash
# Local development
python -m alembic upgrade head

# Production (auto-patched on startup)
# The app will automatically add missing columns on startup via app/main.py
```

---

## Status Flow

```
pending → success → subscription created + credits added
        ↓
        failed (no action)
        ↓
        expired (no action)
```

---

## Notes

1. **Invoice Number Format:** `INV-{8-char-hex}-{unix-timestamp}`
2. **Payment Expiration:** 24 hours from creation (standard Doku policy)
3. **Type Transaction:** Currently only "subscription", can be extended for "topup", "commission", etc.
4. **Doku Response:** Stored as JSON string for audit trail and debugging
5. **Auto-Patch:** Missing columns are automatically added on app startup for backward compatibility
