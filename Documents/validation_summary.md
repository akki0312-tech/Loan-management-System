# Loan Management System — Validation Summary

---

## 1. CustomUser (Registration)

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `username` | Min 3 chars, max 150, alphanumeric + underscores only, unique | Field + `validate_username()` |
| `email` | Valid email format, unique | Field + `UniqueValidator` |
| `password` | Min 8 chars, not fully numeric, not too common (Django validators) | Field + `validate()` |
| `confirm_password` | Must match `password` | Object-level `validate()` |
| `phone_number` | Digits only, 10 digits, unique | `validate_phone_number()` |
| `date_of_birth` | Age must be ≥ 18 | `validate_date_of_birth()` |
| `aadhar` | Exactly 12 digits, no letters, unique | `validate_aadhar()` |

### Security
> [!CAUTION]
> **Role escalation prevention** — `role` field must **never** be accepted from request body.
> It is hardcoded to `BORROWER` in `create()`. Even if a user sends `"role": "ADMIN"`, it is ignored.

> [!CAUTION]
> `password` must always be `write_only=True` — never returned in any API response.

> [!NOTE]
> `aadhar` is sensitive PII. Consider encrypting it at rest using `django-encrypted-model-fields`
> in a production system.

---

## 2. BorrowerProfile

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `salary` | Must be > 0 | Field `min_value=0.01` |
| `monthly_expenses` | Must be > 0 | Field `min_value=0.01` |
| `credit_score` | Range 300 – 900 (standard CIBIL range) | Field `min_value=300, max_value=900` |
| `employment_type` | Must be one of: `SALARIED`, `SELF_EMPLOYED`, `BUSINESS` | `ChoiceField` |

### Object-Level
| Rule | Where |
|---|---|
| `monthly_expenses` must be < `salary` (can't spend more than you earn) | `validate()` |

### Security
> [!CAUTION]
> `is_kyc_verified` must **never** be settable by the borrower themselves.
> Only an `ADMIN` can flip this to `True` via a dedicated admin-only endpoint.

---

## 3. CreditScoreHistory

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `score` | Range 300 – 900 | Field `min_value=300, max_value=900` |
| `remarks` | Cannot be blank — admin must explain the change | `required=True, allow_blank=False` |

### Security & Integrity
> [!CAUTION]
> **Append-only enforcement** — No `UPDATE` or `DELETE` allowed on this model ever.
> Enforce by overriding `update()` and `destroy()` in the ViewSet to raise `MethodNotAllowed`.

> [!CAUTION]
> `updated_by` must be verified as `role = ADMIN` in the serializer.
> Even if the FK resolves, check the role explicitly — don't rely on permissions alone.

### Signal-Driven
> [!IMPORTANT]
> On every new `CreditScoreHistory` record inserted → Django signal automatically
> updates `BorrowerProfile.credit_score` to the latest value.
> This sync must only happen via signal — never via manual field update.

---

## 4. LoanType

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `name` | Must be unique, one of: `PERSONAL`, `HOME`, `CAR`, `EDUCATION` | `ChoiceField` + `UniqueValidator` |
| `interest_rate` | Must be > 0, max 100 (%) | Field `min_value=0.01, max_value=100` |
| `interest_type` | Must be `FLAT` or `REDUCING_BALANCE` | `ChoiceField` |
| `min_amount` | Must be > 0 | Field `min_value=0.01` |
| `min_tenure_months` | Must be ≥ 1 | Field `min_value=1` |
| `max_tenure_months` | Must be ≥ 1 | Field `min_value=1` |

### Object-Level
| Rule | Where |
|---|---|
| `max_tenure_months` must be > `min_tenure_months` | `validate()` |

### Security
> [!CAUTION]
> Only `ADMIN` can create or modify `LoanType`. No borrower access at all.

---

## 5. Loan (Application)

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `amount_requested` | Must be > 0 | Field `min_value=0.01` |
| `tenure_months` | Must be ≥ 1 | Field `min_value=1` |

### Object-Level
| Rule | Where |
|---|---|
| `borrower.borrowerprofile.is_kyc_verified` must be `True` | `validate()` |
| `amount_requested` ≥ `loan_type.min_amount` | `validate()` |
| `tenure_months` within `loan_type.min_tenure_months` ↔ `max_tenure_months` | `validate()` |

### Security & Integrity
> [!CAUTION]
> **Admin-only fields** — `approved_by`, `approved_at`, `disbursed_at`, `status` must
> **never** be accepted from borrower input. These are set by the system or admin only.

> [!CAUTION]
> **Rate/type snapshot** — `interest_rate` and `interest_type` must be auto-copied from
> `LoanType` at the time of application inside `create()`. Never accepted from request body.

> [!IMPORTANT]
> **State machine enforcement** — Loan status can only move forward along valid transitions.
> Any attempt to set an invalid transition (e.g. `PENDING → CLOSED`) must be rejected.
> ```
> PENDING → UNDER_REVIEW → APPROVED → DISBURSED → ACTIVE → CLOSED
>                        ↘ REJECTED             ↘ OVERDUE → DEFAULTED
> CANCELLED ← only from PENDING or UNDER_REVIEW
> ```

> [!NOTE]
> **Consideration** — Should a borrower be allowed to have multiple ACTIVE loans simultaneously?
> If not, add a check: reject if borrower already has a loan with status `ACTIVE` or `DISBURSED`.

---

## 6. EMISchedule

### Integrity
> [!CAUTION]
> EMISchedule records are **never created by user input** — generated automatically
> when `Loan.status → DISBURSED`. The creation endpoint (if any) must be admin/system only.

> [!CAUTION]
> No `UPDATE` or `DELETE` allowed. Override `update()` and `destroy()` to raise `MethodNotAllowed`.

### Internal Integrity Checks (on generation)
| Rule |
|---|
| `principal_component + interest_component` must equal `emi_amount` exactly |
| `outstanding_balance` after the final EMI must equal `0.00` |
| `emi_number` must be sequential from 1 to `tenure_months` with no gaps |
| `due_date` must be exactly 1 month apart for each row |

---

## 7. Payment

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `amount_paid` | Must be > 0 | Field `min_value=0.01` |

### Object-Level
| Rule | Where |
|---|---|
| `amount_paid` must exactly equal `emi_schedule.emi_amount` | `validate()` |
| `emi_schedule.status` must be `PENDING` or `OVERDUE` (not already `PAID`) | `validate()` |
| All previous EMIs (`emi_number < current`) must be `PAID` — no skipping | `validate()` |
| `loan.status` must be `ACTIVE` — can't pay a `CLOSED` or `DEFAULTED` loan | `validate()` |

### Integrity
> [!CAUTION]
> **Append-only** — Payment records are never updated or deleted. Override accordingly.

> [!IMPORTANT]
> **Uniqueness** — Add a `unique=True` constraint or `UniqueValidator` on `emi_schedule`
> to prevent double-payment of the same EMI.

---

## Cross-Cutting Security Concerns

### Object-Level Permissions (Row-level security)
> [!IMPORTANT]
> These are enforced in **Views/ViewSets**, not serializers:
> - A borrower can only view/pay their **own** loans and EMIs
> - A borrower cannot access another borrower's data even if they know the ID
> - Enforce using `get_queryset()` filtered by `request.user`

### Decimal Precision
> [!IMPORTANT]
> **Never use `FloatField` for any monetary value.** Floating-point arithmetic causes rounding
> errors in financial calculations.
> Always use `DecimalField(max_digits=12, decimal_places=2)`.

### Write-Only Fields
The following fields must always have `write_only=True` and must **never** appear in any response:
- `password`
- `confirm_password`
- `aadhar` *(consider masking in read responses, e.g. `XXXX-XXXX-9012`)*

### Rate Limiting
> [!NOTE]
> Apply Django REST Framework's throttling on:
> - `POST /auth/login/` — prevent brute-force attacks
> - `POST /auth/register/` — prevent spam registrations

---

## Summary — Validation Layers

```
┌─────────────────────────────────────────────┐
│ Layer 1 — Field-level (automatic)           │
│  max_length, min_value, required, format     │
├─────────────────────────────────────────────┤
│ Layer 2 — validate_<field>() (per field)    │
│  uniqueness, format, range, age check        │
├─────────────────────────────────────────────┤
│ Layer 3 — validate() (cross-field)          │
│  password match, amount vs min, tenure range │
├─────────────────────────────────────────────┤
│ Layer 4 — create() / update() (business)   │
│  role hardcoding, field snapshotting,        │
│  state machine transitions                   │
├─────────────────────────────────────────────┤
│ Layer 5 — View permissions (row-level)      │
│  IsAdmin, IsBorrower, IsKYCVerified,         │
│  filtered querysets by request.user          │
└─────────────────────────────────────────────┘
```
