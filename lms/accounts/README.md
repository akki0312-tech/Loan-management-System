# Accounts Module — README

The `accounts` app handles everything related to users: registration, authentication, profile management, KYC verification, credit score tracking, and profile picture uploads.

---

## Models

### `CustomUser` (extends `AbstractUser`)
The core user model for the system.

| Field | Type | Notes |
|---|---|---|
| `username` | CharField | Unique, from AbstractUser |
| `email` | EmailField | Unique |
| `first_name` | CharField | Optional |
| `last_name` | CharField | Optional |
| `phone_number` | CharField | 10 digits, unique, optional |
| `date_of_birth` | DateField | Optional |
| `aadhar_number` | TextField | Encrypted ciphertext (Fernet AES-128) |
| `aadhar_hash` | CharField | HMAC-SHA256 of raw Aadhar, `unique=True` — used for uniqueness checks |
| `pan_number` | TextField | Encrypted ciphertext |
| `pan_hash` | CharField | HMAC-SHA256 of raw PAN, `unique=True` |
| `profile_picture` | ImageField | Stored in `media/profile_pictures/`, resized to max 500×500 by Pillow |
| `role` | CharField | `ADMIN` or `BORROWER` (default) |
| `created_at` | DateTimeField | Auto-set on create |
| `updated_at` | DateTimeField | Auto-set on update |

### `BorrowerProfile`
Extended financial profile for borrowers. Created lazily via `get_or_create` on first access.

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOneField → CustomUser | |
| `salary` | DecimalField | Must be > 0 |
| `monthly_expenses` | DecimalField | Must be > 0, must be < salary |
| `employment_type` | CharField | `SALARIED`, `SELF_EMPLOYED`, `BUSINESS` |
| `employer_name` | CharField | Optional |
| `credit_score` | IntegerField | Range 300–900, synced from `CreditScoreHistory` |
| `is_kyc_verified` | BooleanField | Default `False`. **Only admin can set to `True`** |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

### `CreditScoreHistory`
Append-only audit log of every credit score change.

| Field | Type | Notes |
|---|---|---|
| `borrower_profile` | ForeignKey → BorrowerProfile | |
| `score` | IntegerField | Range 300–900 |
| `remarks` | TextField | Mandatory — admin must explain the change |
| `recorded_at` | DateTimeField | Auto-set, never editable |
| `updated_by` | ForeignKey → CustomUser | Auto-set to the admin making the request |

> **Append-only rule:** No UPDATE or DELETE is ever allowed on this model.

---

## PII Security Architecture

Aadhar and PAN numbers are sensitive government IDs and are never stored as plain text.

### How it works (`accounts/encryption.py`)

```
User sends: "123456789012"
       │
       ├─► encrypt()   → "gAAAAABn..." stored in aadhar_number column
       └─► make_hash() → "a3f8b2c1..." stored in aadhar_hash column (unique=True)
```

| Operation | Method | Purpose |
|---|---|---|
| **Encrypt** | Fernet AES-128 (`cryptography` library) | Reversible — admin can decrypt to see real value |
| **Hash** | HMAC-SHA256 (`FIELD_HASH_KEY`) | Irreversible — used only for uniqueness checks |
| **Display** | `mask_aadhar()` / `mask_pan()` | Returns `XXXX-XXXX-9012` in API responses — real value never exposed |

Keys are configured in `settings.py` — **must be moved to environment variables before production.**

---

## API Endpoints

Base prefix: `/api/`

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register/` | ❌ Public | Register a new borrower |
| `POST` | `/auth/login/` | ❌ Public | Login, returns JWT access + refresh tokens |
| `POST` | `/auth/token/refresh/` | ❌ Public | Refresh an access token |

### User Profile

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/auth/me/` | ✅ Any user | View your own profile (Aadhar/PAN shown masked) |
| `PUT/PATCH` | `/auth/me/` | ✅ Any user | Update your own profile fields |
| `GET` | `/auth/borrower-profile/` | ✅ Borrower | View your financial profile |
| `PUT/PATCH` | `/auth/borrower-profile/` | ✅ Borrower | Update salary, expenses, employment info |
| `PATCH` | `/auth/profile-picture/` | ✅ Any user | Upload/replace profile picture (`multipart/form-data`) |

### Admin Only

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `PATCH` | `/admin/verify-kyc/<pk>/` | 🔐 Admin | Set `is_kyc_verified = true` for a borrower |
| `POST` | `/admin/update-credit-score/` | 🔐 Admin | Append a new credit score history record |

---

## Request / Response Examples

### Register
```http
POST /api/auth/register/
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123",
  "confirm_password": "SecurePass123",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "9876543210",
  "date_of_birth": "1995-06-15",
  "aadhar_number": "123456789012",
  "pan_number": "ABCDE1234F"
}
```

### Login
```http
POST /api/auth/login/
Content-Type: application/json

{
  "username": "john_doe",
  "password": "SecurePass123"
}
```
**Response:**
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>"
}
```
> Token payload contains: `username`, `email`, `role`

### View Profile — `GET /api/auth/me/`
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "9876543210",
  "date_of_birth": "1995-06-15",
  "aadhar_display": "XXXX-XXXX-9012",
  "pan_display": "XXXXX1234A",
  "profile_picture": "http://localhost:8000/media/profile_pictures/john.jpg",
  "role": "BORROWER",
  "borrower_profile": {
    "salary": "75000.00",
    "monthly_expenses": "20000.00",
    "credit_score": 720,
    "employment_type": "SALARIED",
    "is_kyc_verified": true
  }
}
```

### Upload Profile Picture
```http
PATCH /api/auth/profile-picture/
Authorization: Bearer <token>
Content-Type: multipart/form-data

profile_picture: <image file>
```
- Only **JPEG** and **PNG** accepted
- Max file size: **5 MB**
- Image is automatically **resized to 500×500** (aspect ratio preserved) using Pillow before saving

### Admin — Verify KYC
```http
PATCH /api/admin/verify-kyc/1/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "is_kyc_verified": true
}
```

### Admin — Update Credit Score
```http
POST /api/admin/update-credit-score/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "borrower_profile": 1,
  "score": 750,
  "remarks": "Salary increased, credit utilisation reduced."
}
```

---

## Validation Rules

| Field | Rule |
|---|---|
| `phone_number` | Exactly 10 digits, numeric only |
| `date_of_birth` | User must be ≥ 18 years old |
| `aadhar_number` | Exactly 12 digits, numeric only, unique (checked via hash) |
| `pan_number` | Format `ABCDE1234F` (5 letters + 4 digits + 1 letter), unique (checked via hash) |
| `password` | Must match `confirm_password` |
| `role` | **Never accepted from request body** — always hardcoded to `BORROWER` on registration |
| `is_kyc_verified` | **Never settable by borrower** — admin-only via dedicated endpoint |
| `salary` | Must be > 0 |
| `monthly_expenses` | Must be > 0, must be less than `salary` |
| `credit_score` | Range 300–900 |
| `CreditScoreHistory` | Append-only — no edits or deletes ever allowed |

---

## JWT Configuration

| Setting | Value |
|---|---|
| Access token lifetime | 15 minutes |
| Refresh token lifetime | 30 minutes |
| Token rotation | ✅ Enabled — a new refresh token is issued on every refresh |
| Blacklist after rotation | ✅ Enabled — old refresh tokens are invalidated immediately |
| Auth header | `Authorization: Bearer <token>` |

---

## Files

| File | Purpose |
|---|---|
| `models.py` | Database models — CustomUser, BorrowerProfile, CreditScoreHistory |
| `serializers.py` | Input validation, encryption, masking logic |
| `views.py` | API views — all auth, profile, admin actions |
| `urls.py` | URL routing for this app |
| `encryption.py` | All PII crypto utilities — encrypt, decrypt, hash, mask |
| `migrations/` | Database migration history |
