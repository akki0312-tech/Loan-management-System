# Loan Management System — API Reference

## Access Legend
| Symbol | Meaning |
|---|---|
| 🌐 | Public — no auth required |
| 👤 | Any authenticated user |
| 🟦 | BORROWER only |
| 🟥 | ADMIN only |
| 🟦🟥 | Both, but scoped differently |

---

## 1. Authentication

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/auth/register/` | 🌐 | Borrower self-registration. Role hardcoded to BORROWER. |
| `POST` | `/auth/login/` | 🌐 | Login with username + password. Returns access + refresh tokens. |
| `POST` | `/auth/token/refresh/` | 🌐 | Exchange refresh token for a new access token. |
| `POST` | `/auth/logout/` | 👤 | Blacklists the refresh token. Effectively ends the session. |
| `GET` | `/auth/me/` | 👤 | Returns the currently authenticated user's basic info + role. |
| `PUT` | `/auth/change-password/` | 👤 | Change own password. Requires current password + new password confirmation. |

---

## 2. EMI Calculator

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/calculator/emi/` | 🌐 | Calculate EMI from custom inputs. No auth required. No data saved. Pure computation. |

### Request Body
```json
{
  "principal": 100000,
  "interest_rate": 10.5,
  "tenure_months": 12,
  "interest_type": "FLAT"   // or "REDUCING_BALANCE"
}
```

### Response
```json
{
  "emi_amount": 9541.67,
  "total_interest": 10500.00,
  "total_payment": 110500.00,
  "amortization_table": [
    {
      "emi_number": 1,
      "emi_amount": 9541.67,
      "principal_component": 8333.33,
      "interest_component": 1208.33,
      "outstanding_balance": 91666.67
    }
    // ... one entry per month
  ]
}
```

### Validations
| Field | Rule |
|---|---|
| `principal` | Must be > 0 |
| `interest_rate` | Must be > 0, max 100 |
| `tenure_months` | Must be ≥ 1 |
| `interest_type` | Must be `FLAT` or `REDUCING_BALANCE` |

> **Note:** This endpoint is completely stateless — nothing is saved to the DB.
> Anyone (unauthenticated users, borrowers, admins) can use it freely.
> Useful for borrowers to explore loan options before applying.

---

## 3. Borrower Profile

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/borrower/profile/` | 🟦 | Create own financial profile (salary, employment, etc.) after registration. |
| `GET` | `/borrower/profile/` | 🟦 | View own profile. |
| `PUT` | `/borrower/profile/` | 🟦 | Update own profile (salary, employer, expenses, etc.) |
| `GET` | `/admin/borrowers/` | 🟥 | List all borrowers with their profiles. Supports filtering/search. |
| `GET` | `/admin/borrowers/{id}/` | 🟥 | View a specific borrower's full profile. |
| `PATCH` | `/admin/borrowers/{id}/verify-kyc/` | 🟥 | Set `is_kyc_verified = True` for a borrower. One-way action — cannot un-verify. |

> **Note:** `is_kyc_verified` can only be set by admin. Borrower cannot touch this field.

---

## 3. Credit Score

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/admin/borrowers/{id}/credit-score/` | 🟥 | Add a new credit score entry for a borrower. Auto-updates `BorrowerProfile.credit_score`. Requires remarks. |
| `GET` | `/admin/borrowers/{id}/credit-score/` | 🟥 | View full credit score history for a specific borrower. |
| `GET` | `/borrower/credit-score/` | 🟦 | View own credit score history. |

> **Integrity:** No `PUT`, `PATCH`, or `DELETE` on credit score history — append-only.

---

## 4. Loan Types

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/loan-types/` | 👤 | List all available loan types with their rates and tenure limits. |
| `GET` | `/loan-types/{id}/` | 👤 | View details of a specific loan type. |
| `POST` | `/admin/loan-types/` | 🟥 | Create a new loan type (PERSONAL, HOME, CAR, EDUCATION). |
| `PUT` | `/admin/loan-types/{id}/` | 🟥 | Update a loan type's parameters (rate changes do NOT affect existing loans). |
| `DELETE` | `/admin/loan-types/{id}/` | 🟥 | Delete a loan type. Only allowed if no loans reference it. |

---

## 5. Loan Applications

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/loans/` | 🟦 | Apply for a loan. Borrower must be KYC verified. Interest rate + type auto-snapshotted. Status set to PENDING. |
| `GET` | `/loans/` | 🟦🟥 | **BORROWER:** sees only their own loans. **ADMIN:** sees all loans. Supports filtering by status. |
| `GET` | `/loans/{id}/` | 🟦🟥 | **BORROWER:** own loan only. **ADMIN:** any loan. Full details including status. |
| `DELETE` | `/loans/{id}/` | 🟦 | Cancel a loan application. Only allowed if status is `PENDING` or `UNDER_REVIEW`. |

### Admin Loan Actions

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `PATCH` | `/admin/loans/{id}/review/` | 🟥 | Move loan from `PENDING` → `UNDER_REVIEW`. Signals admin is looking at it. |
| `PATCH` | `/admin/loans/{id}/approve/` | 🟥 | Move from `UNDER_REVIEW` → `APPROVED`. Sets `approved_by` + `approved_at`. |
| `PATCH` | `/admin/loans/{id}/reject/` | 🟥 | Move from `UNDER_REVIEW` → `REJECTED`. Requires a rejection reason. |
| `PATCH` | `/admin/loans/{id}/disburse/` | 🟥 | Move from `APPROVED` → `DISBURSED` → `ACTIVE`. Sets `disbursed_at`. **Auto-generates the full EMI schedule.** |

> **State machine:** Status can only move forward along valid transitions. Invalid transitions return `400 Bad Request`.

---

## 6. EMI Schedule

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/loans/{id}/emi-schedule/` | 🟦🟥 | **BORROWER:** own loan only. **ADMIN:** any loan. Returns full amortization table — every EMI with due date, amount, principal/interest split, outstanding balance, and status. |

> **Integrity:** EMI schedule is read-only. No `POST`, `PUT`, or `DELETE` allowed.
> Generated automatically on disbursement — never manually.

---

## 7. Payments

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/loans/{id}/payments/` | 🟦 | Pay the next due EMI. Borrower submits which `emi_schedule` they are paying. Amount must exactly match EMI amount. Must pay in order — no skipping. |
| `GET` | `/loans/{id}/payments/` | 🟦🟥 | **BORROWER:** own loan only. **ADMIN:** any loan. Full payment history with timestamps. |

> **On successful payment:**
> 1. `EMISchedule.status` → `PAID`
> 2. Check if all EMIs are `PAID` → if yes, `Loan.status` → `CLOSED`

> **Integrity:** Payment records are append-only. No `PUT`, `PATCH`, or `DELETE`.

---

## 8. Dashboard / Summary

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/admin/dashboard/` | 🟥 | System-wide stats: total loans by status, total disbursed amount, pending applications, defaulted loans. |
| `GET` | `/borrower/dashboard/` | 🟦 | Personal summary: active loans, next EMI due date + amount, total outstanding balance, credit score. |

---

## Complete Endpoint Count

| Feature Area | Public | Borrower | Admin | Total |
|---|---|---|---|---|
| Auth | 3 | 3 | 0 | 6 |
| EMI Calculator | 1 | 0 | 0 | 1 |
| Borrower Profile | 0 | 3 | 3 | 6 |
| Credit Score | 0 | 1 | 2 | 3 |
| Loan Types | 0 | 2* | 3 | 5 |
| Loan Applications | 0 | 3 | 4 | 7 |
| EMI Schedule | 0 | 1 | 1 | 1 |
| Payments | 0 | 2 | 1 | 2 |
| Dashboard | 0 | 1 | 1 | 2 |
| **Total** | **4** | **16** | **15** | **33** |

*Loan type list/detail is available to all authenticated users.

---

## URL Structure Summary

```
/auth/
  register/
  login/
  logout/
  token/refresh/
  me/
  change-password/

/calculator/
  emi/                    ← public, no auth needed

/borrower/
  profile/
  credit-score/
  dashboard/

/loan-types/
  {id}/

/loans/
  {id}/
    emi-schedule/
    payments/

/admin/
  dashboard/
  borrowers/
    {id}/
      verify-kyc/
      credit-score/
  loan-types/
    {id}/
  loans/
    {id}/
      review/
      approve/
      reject/
      disburse/
```
