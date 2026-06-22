# Implementation Plan: Role-Based Access Control (RBAC) & Data-Level Authorization

This document outlines the detailed strategy to design, build, and integrate Role-Based Access Control (RBAC) and data-level (row-level) authorization into the Loan Management System (LMS).

---

## Step 1: Identify Resources and Actions
Define the exact objects in our system and what actions can be performed on them by each role.

### 1.1 Key Roles
- **Admin**: System-wide configuration, managing interest rates, defining loan types, user deletion, and assigning managers.
- **Manager**: Oversees Loan Officers (employees) assigned under them, reviews escalated loans, and views department performance metrics.
- **Loan Officer (Employee)**: Conducts KYC verification, updates credit scores, reviews loan applications, and handles day-to-day operations.
- **Borrower**: Applies for loans, views own profiles, views own EMI schedules, and makes payments.

### 1.2 Resource Matrix
| Resource | Actions | Admin | Manager | Loan Officer | Borrower |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **LoanType** | Create, Update, Delete, View | Full | View Only | View Only | View Only |
| **Loan Application** | Apply (Create) | - | - | - | Own Only |
| **Loan Status** | Approve, Disburse, Reject | Full | Full (Escalated) | Own Assignment | - |
| **KYC Verification** | Verify, View Docs | Full | Assigned Team | Own Assignment | Own Only |
| **Credit Score** | Update, View History | Full | Assigned Team | Own Assignment | Own Only |
| **EMI Schedule** | Generate, View | Full | Assigned Team | Own Assignment | Own Only |
| **Payment** | Record, View History | Full | Assigned Team | Own Assignment | Own Only |
| **Employee (User)** | Create, Assign Manager, View | Full | Assigned Only | - | - |

---

## Step 2: Create Groups with Collection of Permissions
Use Django's built-in `Group` and `Permission` framework to bundle actions together.

### 2.1 Schema Extensions
To support employee-manager relationships and roles:
1. **Extend CustomUser**:
   - Add a self-referential foreign key `manager` (pointing to `CustomUser` with role `MANAGER` / `ADMIN`).
   - Update the `role` field choices to include: `[('ADMIN', 'Admin'), ('MANAGER', 'Manager'), ('LOAN_OFFICER', 'Loan Officer'), ('BORROWER', 'Borrower')]`.
2. **Django Groups**:
   - Create 4 corresponding Django Groups: `Admins`, `Managers`, `Loan_Officers`, `Borrowers`.

### 2.2 Permissions Mapping
Instead of checking raw role strings directly, we define and assign permission codenames:
- **`accounts.view_employee`**: View details of employees.
- **`accounts.manage_employee`**: Edit assignments, assign to managers.
- **`loans.add_loantype`**: Manage loan products.
- **`loans.approve_loan`**: Change loan status from PENDING to APPROVED/REJECTED.
- **`loans.disburse_loan`**: Change loan status from APPROVED to DISBURSED.
- **`accounts.verify_kyc`**: Access and complete KYC verification steps.

### 2.3 Initialization Script (Data Migration)
Create a Django data migration or custom management command that:
1. Creates the four Groups if they do not exist.
2. Fetches the defined permissions from Django's metadata.
3. Associates the permissions to their respective Groups.

---

## Step 3: Assign Users to Roles with API
Provide administrative API endpoints to manage user groups, roles, and reporting relationships.

### 3.1 Role Assignment Endpoint
* **Endpoint**: `POST /api/admin/users/{id}/assign-role/`
* **Access**: Restrict to Admins only.
* **Payload**:
  ```json
  {
    "role": "MANAGER" | "LOAN_OFFICER",
    "manager_id": 42
  }
  ```
* **Process**:
  1. Validates that the target user and manager exist.
  2. Updates the `role` field on the user profile.
  3. Updates the user's Group associations (removes old groups, adds new group).
  4. Sets the `manager` relation if provided.

### 3.2 Reporting Line Update Endpoint
* **Endpoint**: `PATCH /api/admin/employees/{id}/reporting-line/`
* **Access**: Restrict to Admins only.
* **Payload**:
  ```json
  {
    "manager_id": 42
  }
  ```
* **Process**: Re-assigns the employee to a different manager, maintaining clean hierarchy lines.

---

## Step 4: Permission Checks (DRF Custom Permissions)
Enforce access control policies at the Django REST Framework view level.

### 4.1 Custom Permission Classes
Implement reusable permission classes in a new file `lms/permissions.py`:
- **`HasGroupPermission`**: Inspects if the logged-in user belongs to the required group/group-permissions.
- **`IsLoanOfficer` / `IsManager` / `IsAdmin`**: Helper permission classes that check user roles/groups directly.

### 4.2 Application to Views
Integrate these permission classes into DRF ViewSets:
- **`LoanTypeDetailView`**: Apply `IsAdminOrReadOnly` so only admins can modify, but all authenticated users can view.
- **`kycView`**: Apply `HasGroupPermission` requiring `accounts.verify_kyc`.
- **`LoanListCreateView`**: Require `IsAuthenticated` for creation (borrowers applying), but restrict viewing lists based on roles.

---

## Step 5: Data Level Authorization (Row-Level Security)
Restrict data access dynamically based on ownership and reporting relationships.

### 5.1 Dynamic Queryset Filtering
Override the `get_queryset()` method inside DRF views to limit the rows returned:
1. **For Borrowers**:
   - `loans` queryset: `queryset.filter(borrower=request.user)`
   - `emi_schedule` queryset: `queryset.filter(loan__borrower=request.user)`
   - `payments` queryset: `queryset.filter(loan__borrower=request.user)`
2. **For Loan Officers (Employees)**:
   - `loans` queryset: `queryset.filter(assigned_officer=request.user)` (only loans they are assigned to review).
3. **For Managers**:
   - `employees` queryset: `queryset.filter(manager=request.user)` (only employees directly reporting to them).
   - `loans` queryset: `queryset.filter(assigned_officer__manager=request.user)` (loans managed by employees under their team).
4. **For Admins**:
   - Return all records (`queryset.all()`).

### 5.2 Object-Level Action Verification
Inside views/serializers, check user relationship before performing modifications (`has_object_permission`):
- A Manager can only approve/reject or review loan applications escalated by loan officers who report directly to them.
- A Loan Officer can only edit/verify KYC details for borrowers explicitly assigned to their pipeline.
- Verify relationship recursively: `if target_employee.manager != request.user: raise PermissionDenied()`.
