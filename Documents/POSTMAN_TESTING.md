# Postman API Testing Guide — Loan Management System

This guide outlines a step-by-step procedure to verify the entire system, including authentication, role assignments, KYC, credit scores, loan applications, status transitions, payments, and data-level authorization boundaries.

---

## Prerequisites
1. Ensure the Django server is running locally (e.g. `http://127.0.0.1:8000`).
2. Run migrations and the RBAC group initialization:
   ```bash
   python manage.py migrate
   python manage.py rbac
   ```
3. Create a Super Admin account:
   ```bash
   python manage.py createsuperuser
   ```
   *(Let's assume you set the username to `superadmin` and password to `SuperPass123`)*.

---

## Phase 1: Setup Testing Accounts

First, we will register 3 accounts in the system (a Borrower, a Manager, and a Loan Officer). Note that all new accounts registered via `/api/auth/register/` automatically default to the `BORROWER` role. We will promote them in Phase 2.

### 1.1 Register Manager Alice
* **POST** `http://127.0.0.1:8000/api/auth/register/`
* **Body (JSON)**:
  ```json
  {
    "username": "alice_manager",
    "email": "alice@lms.com",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!",
    "first_name": "Alice",
    "last_name": "Manager",
    "phone_number": "9000000001",
    "date_of_birth": "1990-01-01",
    "aadhar_number": "111122223333",
    "pan_number": "ABCDE1111F"
  }
  ```
* **Expected Response**: `201 Created`

### 1.2 Register Loan Officer Bob
* **POST** `http://127.0.0.1:8000/api/auth/register/`
* **Body (JSON)**:
  ```json
  {
    "username": "bob_officer",
    "email": "bob@lms.com",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!",
    "first_name": "Bob",
    "last_name": "Officer",
    "phone_number": "9000000002",
    "date_of_birth": "1992-02-02",
    "aadhar_number": "444455556666",
    "pan_number": "FGHIJ2222K"
  }
  ```
* **Expected Response**: `201 Created`

### 1.3 Register Borrower Charlie
* **POST** `http://127.0.0.1:8000/api/auth/register/`
* **Body (JSON)**:
  ```json
  {
    "username": "charlie_borrower",
    "email": "charlie@lms.com",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!",
    "first_name": "Charlie",
    "last_name": "Borrower",
    "phone_number": "9000000003",
    "date_of_birth": "1995-03-03",
    "aadhar_number": "777788889999",
    "pan_number": "LMNOP3333Q"
  }
  ```
* **Expected Response**: `201 Created`

---

## Phase 2: Role Assignments & Reporting Lines

Only the **Super Admin** or **Admin** can assign roles and set up reporting lines.

### 2.1 Login as Super Admin
* **POST** `http://127.0.0.1:8000/api/auth/login/`
* **Body (JSON)**:
  ```json
  {
    "username": "superadmin",
    "password": "SuperPass123"
  }
  ```
* **Expected Response**: `200 OK`. Copy the value of `"access"`.
* **Postman Setup**: In all subsequent requests for the Super Admin, go to the **Authorization** tab, select **Bearer Token**, and paste this access token.

### 2.2 Promote Alice to Manager
* **PATCH** `http://127.0.0.1:8000/api/auth/users/<alice_id>/assign-role/`
  *(Replace `<alice_id>` with Alice's user ID returned in her registration response)*
* **Headers**: `Authorization: Bearer <superadmin_access_token>`
* **Body (JSON)**:
  ```json
  {
    "role": "MANAGER"
  }
  ```
* **Expected Response**: `200 OK`

### 2.3 Promote Bob to Loan Officer & Assign to Manager Alice
* **PATCH** `http://127.0.0.1:8000/api/auth/users/<bob_id>/assign-role/`
* **Headers**: `Authorization: Bearer <superadmin_access_token>`
* **Body (JSON)**:
  ```json
  {
    "role": "LOAN_OFFICER",
    "manager": <alice_id>
  }
  ```
* **Expected Response**: `200 OK`

### 2.4 Assign Borrower Charlie to Loan Officer Bob
* **PATCH** `http://127.0.0.1:8000/api/auth/users/<charlie_id>/assign-role/`
* **Headers**: `Authorization: Bearer <superadmin_access_token>`
* **Body (JSON)**:
  ```json
  {
    "role": "BORROWER",
    "manager": <bob_id>
  }
  ```
* **Expected Response**: `200 OK`

---

## Phase 3: Setup Borrower Profile & Financials

Now, let's login as Borrower Charlie, fill out his borrower profile, and verify KYC & Credit Score.

### 3.1 Login as Borrower Charlie
* **POST** `http://127.0.0.1:8000/api/auth/login/`
* **Body (JSON)**:
  ```json
  {
    "username": "charlie_borrower",
    "password": "SecurePassword123!"
  }
  ```
* **Expected Response**: `200 OK`. Copy the `"access"` token.
* **Postman Setup**: Configure **Bearer Token** with Charlie's token for the next step.

### 3.2 Create Borrower Profile (Charlie)
* **POST** `http://127.0.0.1:8000/api/auth/borrower-profile/`
* **Headers**: `Authorization: Bearer <charlie_access_token>`
* **Body (JSON)**:
  ```json
  {
    "salary": "50000.00",
    "monthly_expenses": "15000.00",
    "employment_type": "SALARIED",
    "employer_name": "Tech Corp"
  }
  ```
* **Expected Response**: `201 Created`

---

## Phase 4: Staff Operations & Data-Level Boundaries

Now let's log in as staff members to verify KYC verification, credit score updates, and check that team boundaries prevent unauthorized edits.

### 4.1 Login as Loan Officer Bob
* **POST** `http://127.0.0.1:8000/api/auth/login/`
* **Body (JSON)**:
  ```json
  {
    "username": "bob_officer",
    "password": "SecurePassword123!"
  }
  ```
* **Expected Response**: `200 OK`. Copy Bob's `"access"` token.

### 4.2 Verify KYC for Borrower Charlie (Succeeds)
* **PUT** `http://127.0.0.1:8000/api/admin/verify-kyc/<charlie_profile_id>/`
  *(Replace `<charlie_profile_id>` with the ID of Charlie's borrower profile)*
* **Headers**: `Authorization: Bearer <bob_access_token>`
* **Body (JSON)**:
  ```json
  {
    "is_kyc_verified": true
  }
  ```
* **Expected Response**: `200 OK` (because Charlie reports to Bob).

### 4.3 Update Credit Score for Borrower Charlie (Succeeds)
* **POST** `http://127.0.0.1:8000/api/admin/update-credit-score/`
* **Headers**: `Authorization: Bearer <bob_access_token>`
* **Body (JSON)**:
  ```json
  {
    "borrower_profile": <charlie_profile_id>,
    "score": 750,
    "remarks": "Credit bureau score verified."
  }
  ```
* **Expected Response**: `201 Created` (because Charlie reports to Bob).

### 4.4 Data Boundary Check (Test Rejection)
1. Register a new borrower, **Daniel** (`daniel_borrower`), using `/api/auth/register/`.
2. Do **not** assign Daniel to Loan Officer Bob (keep him unassigned or assign to another manager/officer).
3. Attempt to update Daniel's credit score using **Bob's token**:
   * **POST** `http://127.0.0.1:8000/api/admin/update-credit-score/`
   * **Headers**: `Authorization: Bearer <bob_access_token>`
   * **Body (JSON)**:
     ```json
     {
       "borrower_profile": <daniel_profile_id>,
       "score": 800,
       "remarks": "Attemped out-of-team update."
     }
     ```
   * **Expected Response**: `400 Bad Request` with message: *"You are not authorized to update the credit score of this borrower..."* (This proves data-level authorization works!).

---

## Phase 5: Loan Applications & Lifecycle

### 5.1 Create Loan Type (Admin/Super Admin only)
* **POST** `http://127.0.0.1:8000/api/loans/types/`
* **Headers**: `Authorization: Bearer <superadmin_access_token>`
* **Body (JSON)**:
  ```json
  {
    "name": "PERSONAL_LOAN",
    "interest_type": "REDUCING_BALANCE",
    "interest_rate": "12.00",
    "min_amount": "10000.00",
    "min_tenure_months": 6,
    "max_tenure_months": 24
  }
  ```
* **Expected Response**: `201 Created`. Copy the `"id"` of the loan type.

### 5.2 Apply for a Loan (Borrower Charlie)
* **POST** `http://127.0.0.1:8000/api/loans/`
* **Headers**: `Authorization: Bearer <charlie_access_token>`
* **Body (JSON)**:
  ```json
  {
    "loan_type": <loan_type_id>,
    "amount_requested": "20000.00",
    "tenure_months": 12
  }
  ```
* **Expected Response**: `201 Created`. Copy the `"id"` of the created loan application. Status will default to `PENDING`.

### 5.3 Review the Loan (Loan Officer Bob)
* **PATCH** `http://127.0.0.1:8000/api/loans/<loan_id>/`
* **Headers**: `Authorization: Bearer <bob_access_token>`
* **Body (JSON)**:
  ```json
  {
    "status": "UNDER_REVIEW"
  }
  ```
* **Expected Response**: `200 OK`

### 5.4 Approve the Loan (Loan Officer Bob or Manager Alice)
* **PATCH** `http://127.0.0.1:8000/api/loans/<loan_id>/`
* **Headers**: `Authorization: Bearer <bob_access_token>`
* **Body (JSON)**:
  ```json
  {
    "status": "APPROVED"
  }
  ```
* **Expected Response**: `200 OK` (stamps `approved_by` and `approved_at`).

### 5.5 Disburse the Loan (Loan Officer Bob or Manager Alice)
* **PATCH** `http://127.0.0.1:8000/api/loans/<loan_id>/`
* **Headers**: `Authorization: Bearer <bob_access_token>`
* **Body (JSON)**:
  ```json
  {
    "status": "DISBURSED"
  }
  ```
* **Expected Response**: `200 OK` (stamps `disbursed_at`, marks loan `ACTIVE`, and **automatically generates the EMISchedule rows**).

---

## Phase 6: Amortization & Repayments

### 6.1 View EMI Amortization Schedule (Borrower Charlie)
* **GET** `http://127.0.0.1:8000/api/loans/<loan_id>/emi-schedule/`
* **Headers**: `Authorization: Bearer <charlie_access_token>`
* **Expected Response**: `200 OK`. Returns a list of 12 EMI installments. Note the `id` of the first installment (`emi_number`: 1) and its `emi_amount`.

### 6.2 Submit Payment for EMI 1 (Borrower Charlie)
* **POST** `http://127.0.0.1:8000/api/loans/payments/`
* **Headers**: `Authorization: Bearer <charlie_access_token>`
* **Body (JSON)**:
  ```json
  {
    "loan": <loan_id>,
    "emi_schedule": <emi_schedule_id_for_number_1>,
    "amount_paid": "1944.44"  // Must match exact emi_amount from schedule
  }
  ```
* **Expected Response**: `201 Created` (updates EMI status to `PAID`).

### 6.3 Verify Payment History List (Loan Officer Bob)
* **GET** `http://127.0.0.1:8000/api/loans/payments/history/`
* **Headers**: `Authorization: Bearer <bob_access_token>`
* **Expected Response**: `200 OK`. Bob should see Charlie's payment because Charlie belongs to his team. If another Loan Officer calls this, they won't see Charlie's payments.
