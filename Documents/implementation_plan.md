# Authentication System Design — Loan Management System

## Overview

We are designing a **JWT-based authentication system** for a pure Django REST API backend.
Two roles exist: `ADMIN` and `BORROWER`. The system must securely handle registration,
login, logout, token refresh, and role-based access control.

---

## Tech Stack Choice

| Concern | Decision | Why |
|---|---|---|
| Framework | `djangorestframework` (DRF) | Industry standard for Django APIs |
| Auth Tokens | `djangorestframework-simplejwt` | Most widely used JWT library for DRF |
| Token Blacklisting | simplejwt's built-in `TokenBlacklist` app | Enables secure logout |

---

## Token Strategy

| Token | Lifetime | Purpose |
|---|---|---|
| **Access Token** | 30 minutes | Sent with every API request in `Authorization: Bearer <token>` header |
| **Refresh Token** | 7 days | Used only to get a new access token |

**Why short-lived access tokens?**
If an access token is stolen, it expires in 30 minutes. The refresh token is only sent to
one endpoint (`/auth/token/refresh/`), greatly reducing attack surface.

**Token Blacklisting:**
On logout, the refresh token is blacklisted in the DB so it cannot be used to generate
new access tokens — even if stolen.

---

## App Structure

We will create a dedicated `accounts` Django app to house all auth-related code.

```
accounts/
├── models.py         ← CustomUser model
├── serializers.py    ← Register, Login, User serializers
├── views.py          ← Auth endpoints
├── urls.py           ← URL routing
└── permissions.py    ← Custom permission classes (IsAdmin, IsBorrower)
```

---

## Endpoints

### Public Endpoints (No auth required)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register/` | Borrower self-registration |
| `POST` | `/auth/login/` | Login — returns access + refresh tokens |
| `POST` | `/auth/token/refresh/` | Exchange refresh token for new access token |

### Protected Endpoints (Auth required)

| Method | Endpoint | Who | Description |
|---|---|---|---|
| `POST` | `/auth/logout/` | Any authenticated user | Blacklists refresh token |
| `GET` | `/auth/me/` | Any authenticated user | Returns current user's profile |
| `PUT` | `/auth/change-password/` | Any authenticated user | Change own password |

---

## Registration Flow

Only **Borrowers can self-register**. Admins are created via Django's `createsuperuser`
command or manually by a super admin — **not** through a public API endpoint.

```
POST /auth/register/
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+919876543210",
  "date_of_birth": "1995-04-15",
  "aadhar": "1234-5678-9012"
}

→ 201 Created
{
  "message": "Registration successful",
  "user": { "id": 1, "username": "john_doe", "email": "...", "role": "BORROWER" }
}
```

**Validation rules:**
- `password` and `confirm_password` must match
- `password` must pass Django's built-in validators (min length 8, not common, not numeric only)
- `phone_number` must be unique
- `aadhar` must be unique
- `role` is **automatically set to `BORROWER`** — never accepted from request body
- `email` must be unique

---

## Login Flow

```
POST /auth/login/
{
  "username": "john_doe",   ← can also accept email
  "password": "SecurePass123!"
}

→ 200 OK
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 1,
    "username": "john_doe",
    "role": "BORROWER",
    "email": "john@example.com"
  }
}
```

---

## Logout Flow

```
POST /auth/logout/
Authorization: Bearer <access_token>
{
  "refresh": "eyJ..."
}

→ 205 Reset Content
{ "message": "Logged out successfully" }
```

The refresh token is added to simplejwt's `OutstandingToken` blacklist table.

---

## Token Refresh Flow

```
POST /auth/token/refresh/
{
  "refresh": "eyJ..."
}

→ 200 OK
{
  "access": "eyJ...(new token)"
}
```

---

## Custom Permission Classes

These will live in `accounts/permissions.py` and be reused across the entire project.

```python
# IsAdmin — only users with role=ADMIN
class IsAdmin(BasePermission): ...

# IsBorrower — only users with role=BORROWER
class IsBorrower(BasePermission): ...

# IsKYCVerified — borrower must have is_kyc_verified=True (used for loan APIs)
class IsKYCVerified(BasePermission): ...
```

---

## Security Measures

| Measure | Implementation |
|---|---|
| Password hashing | Django's default PBKDF2-SHA256 (built-in) |
| Token blacklisting on logout | `simplejwt.token_blacklist` app |
| Role enforcement | Custom permission classes on every view |
| Aadhar / phone uniqueness | DB-level unique constraints |
| Role cannot be set by user | `role` field excluded from RegisterSerializer write fields |
| Short-lived access tokens | 30-minute expiry |

---

## `settings.py` Configuration

```python
INSTALLED_APPS = [
    ...
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'accounts',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',  # default: all endpoints need auth
    ),
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,       # new refresh token issued on each refresh
    'BLACKLIST_AFTER_ROTATION': True,    # old refresh token blacklisted after rotation
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Login with email or username?**
> Currently designed to login with `username`. Should we also support logging in with `email`?
> This requires a custom authentication backend.

> [!IMPORTANT]
> **Q2 — Refresh token storage on the client?**
> The refresh token will be returned in the JSON response body. The client (e.g., frontend or Postman)
> is responsible for storing it. We are NOT using HttpOnly cookies since this is a pure API.
> Is that acceptable?

> [!NOTE]
> **Q3 — `ROTATE_REFRESH_TOKENS`?**
> With this enabled, every time a refresh token is used to get a new access token, a brand new
> refresh token is also issued (and the old one is blacklisted). This is more secure but means
> the client must store the latest refresh token each time. Should we keep this enabled?

---

## What We Are NOT Building (Kept Out of Scope)

- Password reset via email (requires email SMTP setup — can be added later)
- OTP-based login
- OAuth / Social login
- Session-based auth
