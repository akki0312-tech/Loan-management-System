# Loan Management System — Validation Summary

---

## 1. CustomUser (Registration & Profile Update)

### Field-Level & Serializer Validation
| Field | Validation / Rules | Mechanism |
|---|---|---|
| `username` | Min 3 characters, max 150, alphanumeric + underscores only, unique | Field constraints + DRF validators |
| `email` | Valid email format, unique | Field constraints + `UniqueValidator` |
| `password` | Min 8 chars, not fully numeric, not too common | Django Auth validators + serializer |
| `confirm_password` | Must match `password` | Object-level `validate()` |
| `phone_number` | Digits only, exactly 10 digits, unique | `validate_phone_number()` |
| `date_of_birth` | Age must be ≥ 18 (calculated against current system date) | `validate_date_of_birth()` |
| `aadhar_number` | Exactly 12 digits, no letters, unique (via hash check) | `validate_aadhar_number()` |
| `pan_number` | Must match uppercase alphanumeric regex `^[A-Z]{5}[0-9]{4}[A-Z]$`, unique (via hash check) | `validate_pan_number()` |
| `profile_picture` | Only JPEG/PNG allowed; size ≤ 5 MB; auto-resized to max 500x500 pixels (aspect-ratio preserved) via Pillow | `validate_profile_picture()` |

### Security & Data Encryption
> [!CAUTION]
> **Role escalation prevention** — The `role` field is completely ignored from the request body in registration. It is hardcoded to `BORROWER` in the registration serializer's `create()` method. Only authorized users can update roles through the separate role assignment API.

> [!CAUTION]
> `password` and raw input fields (`confirm_password`, `aadhar_number`, `pan_number`) are set to `write_only=True` so they never leak in any JSON API responses.

> [!IMPORTANT]
> **PII Encryption at Rest**:
> - Raw Aadhar and PAN numbers are encrypted using **Fernet (AES-128 key-based)** cryptography before saving to the DB.
> - Plain-text lookups on encrypted blobs are impossible. Hence, an **HMAC-SHA256 hash** of the Aadhar and PAN is created and stored in separate unique columns (`aadhar_hash`, `pan_hash`) for quick database uniqueness checks.
> - Retrieval fields (`aadhar_display`, `pan_display`) return masked values (e.g. `XXXX-XXXX-1234`) using custom serializing methods to prevent exposing full PII values to clients.

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
| `monthly_expenses` must be < `salary` (cannot spend more than monthly earnings) | `validate()` |

### Security
> [!CAUTION]
> `is_kyc_verified` is configured as a `read_only` field for borrowers. Only staff members with appropriate roles (Super Admin, Admin, Manager, Loan Officer) can modify KYC verification status via the dedicated staff-only KYC verification API.

---

## 3. CreditScoreHistory

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `score` | Range 300 – 900 | Field `min_value=300, max_value=900` |
| `remarks` | Cannot be blank — staff must explain the score update | `required=True, allow_blank=False` |

### Security & Hierarchical Integrity
> [!CAUTION]
> **Append-only enforcement** — No `UPDATE` or `DELETE` operations are allowed on this model to preserve audit logs.

> [!IMPORTANT]
> **Hierarchical Authorization Check**:
> - Enforced inside `CreditScoreHistorySerializer.validate()` based on reporting line manager relationships:
>   - **Super Admins & Admins** can update the credit score of any borrower.
>   - **Loan Officers** can only update scores of borrowers directly assigned to them (`borrower.manager == request.user`).
>   - **Managers** can only update scores of borrowers directly assigned to them OR assigned to Loan Officers reporting to them (`borrower.manager.manager == request.user`).
>   - **Borrowers** are blocked entirely.

---

## 4. Role Assignment (RoleAssignmentSerializer)

This serializer handles mapping users to roles and managing reporting lines.

### Validation Rules (validate())
- **Requesting user is Admin / Super Admin**:
  - Can assign any role to any user.
  - Can set any `manager` as long as that manager's role is `SUPER_ADMIN`, `ADMIN`, or `MANAGER`.
- **Requesting user is Manager**:
  - Can only assign/update roles for users whose current role is `BORROWER`.
  - Cannot promote a borrower to `SUPER_ADMIN`, `ADMIN`, or `MANAGER`.
  - Can only assign a borrower to a manager/officer if it is **themselves** OR a **Loan Officer reporting directly to them** (`new_manager.manager == request.user`).
- **Requesting user is Loan Officer / Borrower**:
  - Access is blocked entirely at the view level (`IsAdminManagerOrSuperAdmin` permission).

### Group Sync (update())
- When a user's role is updated, the database automatically:
  1. Clears all previous Django Group memberships (`Admins`, `Managers`, `Loan_Officers`, `Borrowers`).
  2. Adds the user to the Django Group corresponding to their new role.

---

## 5. LoanType

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `name` | Must be unique, one of: `PERSONAL_LOAN`, `HOME_LOAN`, `CAR_LOAN`, `EDUCATION_LOAN` | `ChoiceField` + `UniqueValidator` |
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
> Only `SUPER_ADMIN` and `ADMIN` can create, update, or delete a `LoanType` (enforced via view-level permissions).

---

## 6. Loan (Application & Status Updates)

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `amount_requested` | Must be > 0 | Field `min_value=0.01` |
| `tenure_months` | Must be ≥ 1 | Field `min_value=1` |

### Object-Level
| Rule | Where |
|---|---|
| `borrower.borrowerprofile.is_kyc_verified` must be `True` | `validate()` |
| `amount_requested` must be ≥ `loan_type.min_amount` | `validate()` |
| `tenure_months` must be within `loan_type.min_tenure_months` ↔ `loan_type.max_tenure_months` | `validate()` |
| User cannot apply if they already have an active/disbursed loan (`status__in=['APPROVED', 'DISBURSED', 'ACTIVE', 'OVERDUE']`) | `validate()` |

### Security & Integrity
> [!CAUTION]
> **Admin/Staff-only fields** — `approved_by`, `approved_at`, `disbursed_at`, `status`, and borrower relation must never be accepted from borrower input during creation.
> `interest_rate` and `interest_type` are snapshotted from `LoanType` on creation.

> [!IMPORTANT]
> **Status Transitions (State Machine)**:
> - Enforced inside `LoanSerializer.validate()` when status is updated. Only the following transitions are valid:
>   ```
>   PENDING → UNDER_REVIEW → APPROVED → DISBURSED → ACTIVE → CLOSED
>                          ↘ REJECTED             ↘ OVERDUE → DEFAULTED
>   CANCELLED ← only from PENDING or UNDER_REVIEW
>   ```
> - Changing loan status is restricted to authorized staff (`SUPER_ADMIN`, `ADMIN`, `MANAGER`, `LOAN_OFFICER`) or superusers.

---

## 7. EMISchedule

### Integrity
- Generated automatically when `Loan.status` transitions to `DISBURSED`.
- Read-only; `UPDATE` and `DELETE` requests are rejected.
- **Verification checks on generation**:
  - `principal_component + interest_component` must equal the calculated monthly `emi_amount` exactly.
  - The final outstanding balance must resolve to `0.00` after the final installment.
  - Installment numbers (`emi_number`) must be sequential from 1 to the requested tenure months without gaps.

---

## 8. Payment

### Field-Level
| Field | Validation | Type |
|---|---|---|
| `amount_paid` | Must be > 0 | Field `min_value=0.01` |

### Object-Level
| Rule | Where |
|---|---|
| `amount_paid` must exactly equal `emi_schedule.emi_amount` | `validate()` |
| `emi_schedule.status` must be `PENDING` or `OVERDUE` (cannot pay a paid EMI) | `validate()` |
| Previous installments must be paid first (no skipping due dates) | `validate()` |
| `loan.status` must be `ACTIVE` or `DISBURSED` | `validate()` |

### Integrity
- Payments are **append-only**; editing or deleting payment records is strictly prohibited.
- `UniqueValidator` is applied to `emi_schedule` to prevent duplicate payments for the same installment.

---

## Cross-Cutting Security Concerns

### Data-Level Authorization (Row-Level Security)
Enforced at the View level (`get_queryset()`):
- **Borrower**: Can see only their own profile, loans, EMIs, and payments.
- **Loan Officer**: Can see only borrowers assigned directly to them, along with their loans, EMIs, and payments.
- **Manager**: Can see only borrowers assigned directly to them or to Loan Officers reporting to them, along with their loans, EMIs, and payments.
- **Admin / Super Admin**: Can view all database records.

### Precision Enforcement
- Always use `DecimalField(max_digits=12, decimal_places=2)` for financial calculations to prevent floating-point rounding errors.
