# Loan Management System (LMS) - API Testing Guide

This guide details how to run, configure, and test all current authentication, profile, and admin API endpoints using Postman.

---

## 1. Setup & Server Start

### A. Run Server
Run the following command in your terminal to start the Django development server:
```bash
..\.venv\Scripts\python.exe manage.py runserver
```
The base URL for all API requests will be:
`http://127.0.0.1:8000/api/`

### B. Create an Admin Account
To test the admin endpoints, you need an admin account. Run this command in a separate terminal:
```bash
..\.venv\Scripts\python.exe manage.py createsuperuser
```
Follow the prompts to create a username, email, and password.

---

## 2. Postman Headers & Authorization

For **protected endpoints**, you must include the access token in your request headers:
1. Copy the `access` token received from the **Login** response.
2. In Postman, go to the **Headers** tab of your request.
3. Add a header:
   * **Key:** `Authorization`
   * **Value:** `Bearer <your_copied_access_token>` (make sure there is a space between `Bearer` and the token).

---

## 3. API Endpoints Flow

### [POST] User Registration (Borrower)
Creates a new borrower user.
* **URL:** `http://127.0.0.1:8000/api/auth/register/`
* **Body (JSON):**
  ```json
  {
    "username": "rahul_sharma",
    "email": "rahul@example.com",
    "password": "Password123!",
    "confirm_password": "Password123!",
    "first_name": "Rahul",
    "last_name": "Sharma",
    "phone_number": "9876543210",
    "date_of_birth": "1998-08-23",
    "aadhar_number": "123456789012"
  }
  ```
* **Expected Response (201 Created):**
  ```json
  {
    "username": "rahul_sharma",
    "email": "rahul@example.com",
    "first_name": "Rahul",
    "last_name": "Sharma",
    "phone_number": "9876543210",
    "date_of_birth": "1998-08-23",
    "aadhar_number": "123456789012"
  }
  ```

---

### [POST] User Login (Obtain JWT)
Obtains token pair. The returned tokens contain custom claims (`username`, `email`, `role`).
* **URL:** `http://127.0.0.1:8000/api/auth/login/`
* **Body (JSON):**
  ```json
  {
    "username": "rahul_sharma",
    "password": "Password123!"
  }
  ```
* **Expected Response (200 OK):**
  ```json
  {
    "refresh": "eyJhbGciOi...",
    "access": "eyJhbGciOi..."
  }
  ```

---

### [POST] Token Refresh (Rotation)
Use the refresh token to obtain a brand new access and refresh token. The old refresh token will be blacklisted.
* **URL:** `http://127.0.0.1:8000/api/auth/token/refresh/`
* **Body (JSON):**
  ```json
  {
    "refresh": "<your_refresh_token_here>"
  }
  ```
* **Expected Response (200 OK):**
  ```json
  {
    "access": "new_access_token_here",
    "refresh": "new_refresh_token_here"
  }
  ```

---

### [GET] My User Profile (Protected)
Retrieves the logged-in user's details and nested borrower profile info.
* **URL:** `http://127.0.0.1:8000/api/auth/me/`
* **Headers:** `Authorization: Bearer <access_token>`
* **Expected Response (200 OK):**
  ```json
  {
    "id": 1,
    "username": "rahul_sharma",
    "email": "rahul@example.com",
    "first_name": "Rahul",
    "last_name": "Sharma",
    "phone_number": "9876543210",
    "date_of_birth": "1998-08-23",
    "aadhar_number": "123456789012",
    "role": "BORROWER",
    "borrower_profile": null
  }
  ```

---

### [PATCH] Update Borrower Financial Info (Protected)
Allows a logged-in user to fill out or update their salary, monthly expenses, and employment details.
* **URL:** `http://127.0.0.1:8000/api/auth/borrower-profile/`
* **Headers:** `Authorization: Bearer <access_token>`
* **Body (JSON):**
  ```json
  {
    "salary": "85000.00",
    "monthly_expenses": "25000.00",
    "employment_type": "SALARIED"
  }
  ```
* **Expected Response (200 OK):**
  ```json
  {
    "salary": "85000.00",
    "monthly_expenses": "25000.00",
    "credit_score": null,
    "employment_type": "SALARIED",
    "is_kyc_verified": false
  }
  ```

---

### [PATCH] Admin KYC Verification (Admin Only)
Admin changes a borrower's KYC verification status to `true`.
1. Log in with the **Admin** account details to get an Admin access token.
2. In the URL path, replace `<profile_id>` with the ID of the borrower profile you want to verify (e.g., `1`).
* **URL:** `http://127.0.0.1:8000/api/admin/verify-kyc/<profile_id>/`
* **Headers:** `Authorization: Bearer <admin_access_token>`
* **Body (JSON):**
  ```json
  {
    "is_kyc_verified": true
  }
  ```
* **Expected Response (200 OK):**
  ```json
  {
    "is_kyc_verified": true
  }
  ```

---

### [POST] Admin Credit Score Update (Admin Only)
Admin records a credit score history entry and updates the borrower's main profile credit score.
1. Log in with your **Admin** credentials to get an Admin token.
2. Provide the borrower profile ID in the body.
* **URL:** `http://127.0.0.1:8000/api/admin/update-credit-score/`
* **Headers:** `Authorization: Bearer <admin_access_token>`
* **Body (JSON):**
  ```json
  {
    "borrower_profile": 1,
    "score": 780,
    "remarks": "Verified active bank statements and clean repayment history."
  }
  ```
* **Expected Response (201 Created):**
  ```json
  {
    "id": 1,
    "borrower_profile": 1,
    "score": 780,
    "remarks": "Verified active bank statements and clean repayment history.",
    "recorded_at": "2026-06-18T13:20:00Z",
    "updated_by": 2,
    "updated_by_username": "admin_username"
  }
  ```
