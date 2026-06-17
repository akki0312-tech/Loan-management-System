# Loan Management System — Complete Model Design

## Relationships Overview

```
CustomUser
    │
    ├──(OneToOne)──► BorrowerProfile
    │                       │
    │               (FK)──► CreditScoreHistory
    │
    └──(FK)──► Loan ──(FK)──► LoanType
                    │
                    ├──(FK)──► EMISchedule
                    │
                    └──(FK)──► Payment ──(FK)──► EMISchedule
```

---

## 1. CustomUser
> Extends Django's `AbstractUser`. Central auth model for all users.

| Field | Type | Notes |
|---|---|---|
| `username` | CharField | Inherited from AbstractUser |
| `password` | CharField | Inherited — hashed via PBKDF2 |
| `email` | EmailField | Inherited |
| `first_name` | CharField | Inherited |
| `last_name` | CharField | Inherited |
| `phone_number` | CharField | Unique |
| `date_of_birth` | DateField | For age eligibility checks |
| `aadhar` | CharField | Unique, KYC identity |
| `role` | CharField | `ADMIN` or `BORROWER` |
| `created_at` | DateTimeField | Auto set on creation |
| `updated_at` | DateTimeField | Auto updated |

**Constraints:**
- `role` must be either `ADMIN` or `BORROWER`
- Only `BORROWER` role can apply for loans
- Only `ADMIN` role can approve/reject loans

---

## 2. BorrowerProfile
> Extended financial identity for borrowers only. Admins do NOT have this.

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOneField | → `CustomUser` |
| `salary` | DecimalField | Monthly salary |
| `employment_type` | CharField | `SALARIED`, `SELF_EMPLOYED`, `BUSINESS` |
| `employer_name` | CharField | |
| `credit_score` | IntegerField | Latest value — kept in sync with `CreditScoreHistory` |
| `monthly_expenses` | DecimalField | Used for disposable income check |
| `is_kyc_verified` | BooleanField | Default `False` — must be `True` to apply for loan |
| `created_at` | DateTimeField | Auto set on creation |
| `updated_at` | DateTimeField | Auto updated |

**Constraints:**
- `is_kyc_verified` must be `True` before any loan application is allowed
- `credit_score` is always the latest value — never manually updated directly (goes through `CreditScoreHistory`)

---

## 3. CreditScoreHistory
> Immutable audit trail of every credit score change. Admin-driven.

| Field | Type | Notes |
|---|---|---|
| `borrower_profile` | ForeignKey | → `BorrowerProfile` |
| `score` | IntegerField | The score value at this point in time |
| `recorded_at` | DateTimeField | Auto timestamped |
| `updated_by` | ForeignKey | → `CustomUser` (Admin who made the change) |
| `remarks` | TextField | Why was it changed? Admin's note |

**Constraints:**
- Records are **never deleted or updated** — append-only
- `updated_by` must have `role = ADMIN`
- On insert → automatically sync `BorrowerProfile.credit_score` to latest value (via Django signals)

---

## 4. LoanType
> Master config table. Admin sets loan parameters here once. All loans reference this.

| Field | Type | Notes |
|---|---|---|
| `name` | CharField | `PERSONAL`, `HOME`, `CAR`, `EDUCATION` |
| `interest_type` | CharField | `FLAT` (Personal, Car) or `REDUCING_BALANCE` (Home, Education) |
| `interest_rate` | DecimalField | Annual rate e.g. `10.50` (%) |
| `min_amount` | DecimalField | Minimum loan amount allowed |
| `max_amount` | DecimalField | Maximum loan amount allowed |
| `min_tenure_months` | IntegerField | Minimum repayment period |
| `max_tenure_months` | IntegerField | Maximum repayment period |

**Constraints:**
- Changing `interest_rate` here does NOT affect existing loans (rate is snapshotted into `Loan` at application time)

---

## 5. Loan
> Core model. One record per loan application.

| Field | Type | Notes |
|---|---|---|
| `borrower` | ForeignKey | → `CustomUser` (role=BORROWER) |
| `loan_type` | ForeignKey | → `LoanType` |
| `amount_requested` | DecimalField | What borrower asked for |
| `interest_rate` | DecimalField | **SNAPSHOT** — copied from `LoanType` at application time |
| `interest_type` | CharField | **SNAPSHOT** — copied from `LoanType` at application time |
| `tenure_months` | IntegerField | Chosen by borrower (within LoanType min/max) |
| `status` | CharField | See lifecycle below |
| `approved_by` | ForeignKey | → `CustomUser` (Admin), nullable |
| `approved_at` | DateTimeField | Nullable |
| `disbursed_at` | DateTimeField | Nullable |
| `created_at` | DateTimeField | Auto set on creation |
| `updated_at` | DateTimeField | Auto updated |

**Status Lifecycle:**
```
PENDING → UNDER_REVIEW → APPROVED → DISBURSED → ACTIVE → CLOSED
                       ↘ REJECTED             ↘ OVERDUE → DEFAULTED

CANCELLED  ← only from PENDING or UNDER_REVIEW
```

**Constraints:**
- `borrower.borrowerprofile.is_kyc_verified` must be `True` to apply
- `amount_requested` must be within `LoanType.min_amount` and `LoanType.max_amount`
- `tenure_months` must be within `LoanType.min_tenure_months` and `LoanType.max_tenure_months`
- `approved_by` must have `role = ADMIN`
- `interest_rate` and `interest_type` are frozen at application time

---

## 6. EMISchedule
> Amortization table. Generated once when loan is DISBURSED. One row per installment.

| Field | Type | Notes |
|---|---|---|
| `loan` | ForeignKey | → `Loan` |
| `emi_number` | IntegerField | 1, 2, 3... up to `tenure_months` |
| `due_date` | DateField | When this EMI must be paid |
| `emi_amount` | DecimalField | Fixed — same every row |
| `principal_component` | DecimalField | Portion going to principal reduction |
| `interest_component` | DecimalField | Portion going to interest |
| `outstanding_balance` | DecimalField | Remaining principal after this payment |
| `status` | CharField | `PENDING`, `PAID`, `OVERDUE` |

**How principal/interest split works:**
- **FLAT:** Principal component = `amount / tenure`. Interest component = fixed. Same split every month.
- **REDUCING BALANCE:** Interest component decreases monthly. Principal component increases monthly. EMI total stays fixed.

**Constraints:**
- Generated automatically when `Loan.status` → `DISBURSED`
- Records are never manually created or edited
- `OVERDUE` set automatically when `due_date` is past and `status` is still `PENDING` (background scheduler)

---

## 7. Payment
> Immutable record of every EMI payment made by borrower.

| Field | Type | Notes |
|---|---|---|
| `loan` | ForeignKey | → `Loan` |
| `emi_schedule` | ForeignKey | → `EMISchedule` (exactly which installment) |
| `amount_paid` | DecimalField | Must equal `EMISchedule.emi_amount` exactly |
| `paid_at` | DateTimeField | Auto timestamped |

**Constraints:**
- `amount_paid` must exactly equal `emi_schedule.emi_amount` (no partial payments)
- Cannot pay an EMI that is already `PAID`
- Must pay EMIs in order (cannot skip emi_number 2 and pay emi_number 3)
- On successful payment → `EMISchedule.status` → `PAID`
- If all EMIs are `PAID` → `Loan.status` → `CLOSED`
- Records are **never deleted** — append-only audit trail

---

## Summary Table

| Model | Purpose | Key Relationship |
|---|---|---|
| `CustomUser` | Auth + identity for all users | Base model |
| `BorrowerProfile` | Financial profile for borrowers | OneToOne → CustomUser |
| `CreditScoreHistory` | Audit trail of score changes | FK → BorrowerProfile |
| `LoanType` | Master config (rates, limits) | Referenced by Loan |
| `Loan` | One loan application | FK → CustomUser, LoanType |
| `EMISchedule` | Monthly repayment schedule | FK → Loan |
| `Payment` | Actual payments made | FK → Loan, EMISchedule |

**Total: 7 models**
