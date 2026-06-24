# Loan Management System — API Reference

All API endpoints are prefixed with `/api/`.

## Access Legend
| Symbol | Meaning | Role Scope |
|---|---|---|
| 🌐 | Public | No authentication required |
| 👤 | Authenticated | Any authenticated user |
| 🟦 | Borrower | Scoped to the individual user's data |
| 🟨 | Staff | Loan Officers, Managers, Admins, and Super Admins |
| 🟥 | Admin | Admins and Super Admins only |

---

## 1. Authentication & Profile Management

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | 🌐 | Self-registration. Creates a new user with the `BORROWER` role. |
| `POST` | `/api/auth/login/` | 🌐 | Authenticates credentials and returns a pair of JWTs (`access` and `refresh`). |
| `POST` | `/api/auth/token/refresh/` | 🌐 | Refreshes the short-lived JWT access token using the valid refresh token. |
| `GET` | `/api/auth/me/` | 👤 | Returns basic details, decrypted/masked Aadhar/PAN info, profile picture, and role of the logged-in user. |
| `PATCH` | `/api/auth/profile-picture/` | 👤 | Uploads or replaces the logged-in user's profile picture. Validates image type (JPEG/PNG), file size (< 5MB), and auto-resizes to 500x500 pixels. |
| `GET` | `/api/auth/borrower-profile/` | 🟦 | Retrieves the logged-in borrower's financial profile. |
| `POST` | `/api/auth/borrower-profile/` | 🟦 | Creates a new financial profile (salary, monthly expenses, employer details) for the logged-in borrower. |

---

## 2. Staff Administration (KYC, Roles, and Credit Scores)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `PUT` | `/api/admin/verify-kyc/<int:pk>/` | 🟨 | Sets `is_kyc_verified = True` for the target `BorrowerProfile`. Restrained by data-level authorization reporting lines. |
| `POST` | `/api/admin/update-credit-score/` | 🟨 | Inserts a new credit score update record. Updates the borrower's main profile score. Restrained by reporting lines. |
| `PATCH` | `/api/auth/users/<int:pk>/assign-role/` | 🟨 | Promotes/updates user roles and assigns reporting managers. Managers can only assign borrowers to themselves or Loan Officers on their team. |

### Credit Score Update Payload (`POST /api/admin/update-credit-score/`)
```json
{
  "borrower_profile": 12,  // ID of the target BorrowerProfile
  "score": 750,            // Integer in range 300 - 900
  "remarks": "Verified credit score report via bureau check."
}
```

### Role Assignment Payload (`PATCH /api/auth/users/<int:pk>/assign-role/`)
```json
{
  "role": "LOAN_OFFICER", // Target user's new role choice
  "manager": 2           // ID of the user set as manager (must be ADMIN or MANAGER)
}
```

---

## 3. EMI Calculator (Public Tool)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/api/loans/emi-calculator/` | 🌐 | Stateless amortization schedule generator. Calculates installment values from input parameters. |

### Calculator Request Body
```json
{
  "loan_amount": 50000.00,
  "interest_rate": 12.00,
  "tenure_months": 6,
  "interest_type": "REDUCING_BALANCE"  // or "FLAT"
}
```

### Response Example
```json
{
  "monthly_emi": 8626.83
}
```

---

## 4. Loan Types (Master Config)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/loans/types/` | 👤 | Lists all available loan types (name, interest type, rate, limits). |
| `POST` | `/api/loans/types/` | 🟥 | Creates a new loan type configurator. |
| `GET` | `/api/loans/types/<int:pk>/` | 👤 | Retrieves details of a specific loan type configuration. |
| `PUT/PATCH` | `/api/loans/types/<int:pk>/` | 🟥 | Modifies loan type details (does not affect existing active loans). |
| `DELETE` | `/api/loans/types/<int:pk>/` | 🟥 | Deletes a loan type configuration. |

---

## 5. Loan Applications & Status Flow

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/loans/` | 👤 | Lists loans. Borrowers see own; Loan Officers see assigned borrowers; Managers see team assigned; Admins see all. |
| `POST` | `/api/loans/` | 🟦 | Applies for a loan. Borrower must be KYC verified and have no pending/active loan. Snapshots current interest parameters. |
| `GET` | `/api/loans/<int:pk>/` | 👤 | Retrieves details of a specific loan. Scoped to user visibility. |
| `PUT/PATCH` | `/api/loans/<int:pk>/` | 🟨 | Updates loan details. Staff use this to advance the loan's status in the state machine. |

### Loan Status Update transitions:
Staff must transition status along this path:
```
PENDING → UNDER_REVIEW → APPROVED → DISBURSED → ACTIVE → CLOSED
```
* Moving a status to `APPROVED` automatically timestamps `approved_by` and `approved_at`.
* Moving a status to `DISBURSED` automatically timestamps `disbursed_at` and generates the **complete monthly EMI schedule**.

---

## 6. EMI Schedules & Payments

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/api/loans/<int:loan_pk>/emi-schedule/` | 👤 | Returns all amortization installments (amount, principal/interest split, due date, outstanding, status). Scoped to user visibility. |
| `POST` | `/api/loans/payments/` | 🟦 | Submits a payment for the next pending EMI. Must be paid sequentially without skipping. |
| `GET` | `/api/loans/payments/history/` | 👤 | Lists payment transaction history. Scoped to user visibility. |

### Payment Submission Payload (`POST /api/loans/payments/`)
```json
{
  "loan": 3,               // ID of the target Loan
  "emi_schedule": 15,      // ID of the target EMISchedule row to pay
  "amount_paid": 8626.83   // Must match exact EMI installment amount
}
```
* Successful payment updates `EMISchedule.status` to `PAID`. 
* When the last EMI is paid, `Loan.status` is automatically closed (`CLOSED`).

---

## Endpoint List Summary

| Area | Endpoint URI | Methods | Role | Description |
|---|---|---|---|---|
| **Auth** | `/api/auth/register/` | `POST` | 🌐 | Borrower sign-up |
| **Auth** | `/api/auth/login/` | `POST` | 🌐 | Get auth token |
| **Auth** | `/api/auth/token/refresh/` | `POST` | 🌐 | Refresh access token |
| **Auth** | `/api/auth/me/` | `GET` | 👤 | View current user details |
| **Auth** | `/api/auth/profile-picture/` | `PATCH` | 👤 | Upload profile picture |
| **Profile** | `/api/auth/borrower-profile/` | `GET`, `POST` | 🟦 | Create/view borrower details |
| **KYC** | `/api/admin/verify-kyc/<int:pk>/` | `PUT` | 🟨 | Mark KYC as verified |
| **Score** | `/api/admin/update-credit-score/` | `POST` | 🟨 | Update borrower credit score |
| **Roles** | `/api/auth/users/<int:pk>/assign-role/` | `PATCH` | 🟨 | Assign user role & manager |
| **Calc** | `/api/loans/emi-calculator/` | `POST` | 🌐 | Stateless EMI calculations |
| **Loan Types**| `/api/loans/types/` | `GET`, `POST` | 👤/🟥 | List/create loan configurations |
| **Loan Types**| `/api/loans/types/<int:pk>/` | `GET`, `PUT`, `PATCH`, `DELETE` | 👤/🟥 | Manage loan configurations |
| **Loans** | `/api/loans/` | `GET`, `POST` | 👤/🟦 | Apply / view loan list |
| **Loans** | `/api/loans/<int:pk>/` | `GET`, `PUT`, `PATCH` | 👤/🟨 | Retrieve / update loan status |
| **Schedule** | `/api/loans/<int:loan_pk>/emi-schedule/` | `GET` | 👤 | View amortization list |
| **Payment** | `/api/loans/payments/` | `POST` | 🟦 | Pay an installment |
| **Payment** | `/api/loans/payments/history/` | `GET` | 👤 | View payment history |
