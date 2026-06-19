# Loans Module — README

The `loans` app handles everything related to the loan lifecycle: loan type management, loan applications, admin approvals, EMI schedule generation, and payment processing.

---

## Models

### `LoanType`
Defines the product catalogue of loan categories available in the system. Created and managed by admins only.

| Field | Type | Notes |
|---|---|---|
| `name` | CharField | Unique. One of: `PERSONAL_LOAN`, `HOME_LOAN`, `CAR_LOAN`, `EDUCATION_LOAN` |
| `interest_type` | CharField | `FLAT` or `REDUCING_BALANCE` |
| `interest_rate` | DecimalField | Annual rate in %, must be > 0 |
| `min_amount` | DecimalField | Minimum borrowable amount |
| `min_tenure_months` | IntegerField | Minimum loan tenure |
| `max_tenure_months` | IntegerField | Maximum loan tenure, must be > `min_tenure_months` |

### `Loan`
Represents a single loan application from a borrower.

| Field | Type | Notes |
|---|---|---|
| `borrower` | ForeignKey → CustomUser | Auto-set from `request.user` on creation |
| `loan_type` | ForeignKey → LoanType | Chosen by borrower |
| `amount_requested` | DecimalField | Must be ≥ `loan_type.min_amount` |
| `interest_rate` | DecimalField | **Snapshotted** from `LoanType` at application time — never changes |
| `interest_type` | CharField | **Snapshotted** from `LoanType` at application time — never changes |
| `tenure_months` | IntegerField | Must fall within `LoanType.min_tenure_months` ↔ `max_tenure_months` |
| `status` | CharField | Managed via state machine (see below) |
| `approved_by` | ForeignKey → CustomUser | Auto-set to admin on approval |
| `approved_at` | DateTimeField | Auto-stamped on approval |
| `disbursed_at` | DateTimeField | Auto-stamped on disbursement; triggers EMI generation |
| `created_at` | DateTimeField | Auto |
| `updated_at` | DateTimeField | Auto |

#### Loan Status State Machine

```
PENDING → UNDER_REVIEW → APPROVED → DISBURSED → ACTIVE → CLOSED
                       ↘ REJECTED              ↘ OVERDUE → DEFAULTED
CANCELLED ← (from PENDING or UNDER_REVIEW only)
```

Only admins can change a loan's status. Any invalid transition is rejected.

### `EMISchedule`
Auto-generated monthly EMI rows when a loan is marked `DISBURSED`. Never created or edited by users.

| Field | Type | Notes |
|---|---|---|
| `loan` | ForeignKey → Loan | |
| `emi_number` | IntegerField | Sequential from 1 to `tenure_months` |
| `due_date` | DateField | Exactly 1 month apart per row |
| `emi_amount` | DecimalField | Fixed for FLAT; same value for REDUCING_BALANCE (EMI is constant) |
| `principal_component` | DecimalField | Portion going to principal |
| `interest_component` | DecimalField | Portion going to interest |
| `outstanding_balance` | DecimalField | Remaining principal after this EMI. Final row = `0.00` |
| `status` | CharField | `PENDING`, `PAID`, or `OVERDUE` |

> **Integrity checks on generation:** `principal_component + interest_component = emi_amount` exactly. Final row `outstanding_balance = 0.00`.

### `Payment`
Records a borrower making a payment for one EMI. Append-only — no edits or deletes.

| Field | Type | Notes |
|---|---|---|
| `loan` | ForeignKey → Loan | |
| `emi_schedule` | OneToOneField → EMISchedule | Ensures one payment per EMI (no double-payment) |
| `amount_paid` | DecimalField | Must exactly match `emi_schedule.emi_amount` |
| `paid_at` | DateTimeField | Auto-set on creation |

---

## EMI Calculation Logic

### Flat Rate
```
Monthly EMI = (Principal + (Principal × Rate/100 × Tenure/12)) / Tenure
```
Interest is calculated once on the full principal and divided equally across all months.

### Reducing Balance
```
Monthly Rate (r) = Annual Rate / 100 / 12
Monthly EMI      = P × r × (1 + r)^n / ((1 + r)^n − 1)
```
Interest recalculates each month on the remaining outstanding balance — the principal portion grows over time.

Both formulas use `Decimal` arithmetic (never `float`) to avoid rounding errors in financial calculations.

---

## API Endpoints

Base prefix: `/api/`

### EMI Calculator (Public)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/loans/emi-calculator/` | ❌ Public | Calculate monthly EMI for any inputs |

### Loan Types

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/loans/types/` | ✅ Any user | List all loan types |
| `POST` | `/loans/types/` | 🔐 Admin | Create a new loan type |
| `GET` | `/loans/types/<pk>/` | ✅ Any user | Retrieve a specific loan type |
| `PUT/PATCH` | `/loans/types/<pk>/` | 🔐 Admin | Update a loan type |
| `DELETE` | `/loans/types/<pk>/` | 🔐 Admin | Delete a loan type |

### Loans

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/loans/` | ✅ Borrower | Apply for a loan |
| `GET` | `/loans/` | ✅ Any user | Borrowers see own loans; admins see all |
| `GET` | `/loans/<pk>/` | ✅ Any user | Retrieve a specific loan |
| `PATCH` | `/loans/<pk>/` | 🔐 Admin | Update loan status (state machine enforced) |

### EMI Schedule

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/loans/<loan_pk>/emi-schedule/` | ✅ Any user | View EMI schedule for a loan (borrowers see own only) |

### Payments

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/loans/payments/` | ✅ Borrower | Make a payment for an EMI |
| `GET` | `/loans/payments/history/` | ✅ Any user | Borrowers see own payments; admins see all |

---

## Request / Response Examples

### EMI Calculator
```http
POST /api/loans/emi-calculator/
Content-Type: application/json

{
  "loan_amount": "500000",
  "interest_rate": "12.00",
  "tenure_months": 24,
  "interest_type": "REDUCING_BALANCE"
}
```
**Response:**
```json
{
  "monthly_emi": 23537.46
}
```

### Create Loan Type (Admin)
```http
POST /api/loans/types/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "name": "PERSONAL_LOAN",
  "interest_type": "REDUCING_BALANCE",
  "interest_rate": "12.00",
  "min_amount": "10000.00",
  "min_tenure_months": 6,
  "max_tenure_months": 60
}
```

### Apply for a Loan (Borrower)
```http
POST /api/loans/
Authorization: Bearer <borrower_token>
Content-Type: application/json

{
  "loan_type": 1,
  "amount_requested": "500000.00",
  "tenure_months": 24
}
```
> `interest_rate`, `interest_type`, `borrower`, and `status` are all **auto-set by the system** — never accepted from the request body.

**Response:**
```json
{
  "id": 5,
  "borrower": 3,
  "loan_type": 1,
  "amount_requested": "500000.00",
  "interest_rate": "12.00",
  "interest_type": "REDUCING_BALANCE",
  "tenure_months": 24,
  "status": "PENDING",
  "approved_by": null,
  "approved_at": null,
  "disbursed_at": null,
  "created_at": "2026-06-19T10:30:00Z",
  "updated_at": "2026-06-19T10:30:00Z"
}
```

### Admin — Approve a Loan
```http
PATCH /api/loans/5/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "status": "APPROVED"
}
```
> `approved_by` and `approved_at` are auto-stamped on the server side.

### Admin — Disburse a Loan
```http
PATCH /api/loans/5/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "status": "DISBURSED"
}
```
> Automatically triggers EMI schedule generation for all `tenure_months` rows.

### View EMI Schedule
```http
GET /api/loans/5/emi-schedule/
Authorization: Bearer <token>
```
**Response:**
```json
[
  {
    "id": 1,
    "loan": 5,
    "emi_number": 1,
    "due_date": "2026-07-19",
    "emi_amount": "23537.46",
    "principal_component": "18537.46",
    "interest_component": "5000.00",
    "outstanding_balance": "481462.54",
    "status": "PENDING"
  },
  ...
]
```

### Make a Payment
```http
POST /api/loans/payments/
Authorization: Bearer <borrower_token>
Content-Type: application/json

{
  "loan": 5,
  "emi_schedule": 1,
  "amount_paid": "23537.46"
}
```
> After payment: EMI status → `PAID`. If all EMIs are paid, loan status → `CLOSED` automatically.

---

## Validation Rules

| Rule | Where Enforced |
|---|---|
| Borrower must have `is_kyc_verified = True` to apply | `LoanSerializer.validate()` |
| Borrower cannot have an active/pending loan when applying | `LoanSerializer.validate()` |
| `amount_requested` ≥ `loan_type.min_amount` | `LoanSerializer.validate()` |
| `tenure_months` within `min_tenure_months` ↔ `max_tenure_months` | `LoanSerializer.validate()` |
| Only admins can change loan status | `LoanSerializer.validate()` |
| Loan status transitions must follow the state machine | `LoanSerializer.validate()` |
| `interest_rate` and `interest_type` snapshotted at creation time | `LoanSerializer.create()` |
| EMI schedules are **read-only** — never created by user input | View permission |
| `amount_paid` must **exactly equal** `emi_schedule.emi_amount` | `PaymentSerializer.validate()` |
| EMI must not already be `PAID` | `PaymentSerializer.validate()` |
| All previous EMIs must be paid — no skipping allowed | `PaymentSerializer.validate()` |
| Loan must be `ACTIVE` or `OVERDUE` to accept payments | `PaymentSerializer.validate()` |
| Payment belongs to the correct loan | `PaymentSerializer.validate()` |
| Payments are **append-only** — no edits or deletes | Model design |
| `max_tenure_months` must be > `min_tenure_months` | `LoanTypeSerializer.validate()` |

---

## Row-Level Security

Borrowers can **only see their own data**. This is enforced via `get_queryset()` in every list view — not by serializer logic.

| View | Borrower sees | Admin sees |
|---|---|---|
| `GET /api/loans/` | Own loans only | All loans |
| `GET /api/loans/<pk>/emi-schedule/` | Own loan's EMIs only | Any loan's EMIs |
| `GET /api/loans/payments/history/` | Own payments only | All payments |

---

## Files

| File | Purpose |
|---|---|
| `models.py` | LoanType, Loan, EMISchedule, Payment models |
| `serializers.py` | Validation, state machine, snapshot logic, payment processing |
| `views.py` | All API views + `generate_emi_schedule()` utility function |
| `urls.py` | URL routing for this app |
| `migrations/` | Database migration history |
