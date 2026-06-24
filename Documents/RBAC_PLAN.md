# Implemented Plan: Role-Based Access Control (RBAC) & Data-Level Authorization

This document outlines the final implementation details and strategy used to integrate Role-Based Access Control (RBAC) and data-level (row-level) authorization into the Loan Management System (LMS).

---

## Step 1: Resource Mapping and Key Roles
Defined objects in our system and what actions can be performed on them by each role.

### 1.1 Key Roles
- **Super Admin**: Bypasses all permissions dynamically. Has full master access.
- **Admin**: System-wide configuration, managing loan types, user deletion, and assigning managers/roles globally.
- **Manager**: Oversees Loan Officers (employees) and Borrowers assigned under them, reviews escalated loans, and performs role/manager assignments for Borrowers.
- **Loan Officer**: Conducts KYC verification, updates credit scores, and reviews loan applications for borrowers directly assigned to them.
- **Borrower**: Applies for loans, views own profiles, views own EMI schedules, and submits payments.

### 1.2 Resource Matrix
| Resource | Actions | Super Admin / Admin | Manager | Loan Officer | Borrower |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **LoanType** | Create, Update, Delete, View | Full | View Only | View Only | View Only |
| **Loan Application** | Apply (Create) | - | - | - | Own Only |
| **Loan Status** | Approve, Disburse, Reject | Full | Full (Escalated/Team) | Own Assignment | - |
| **KYC Verification** | Verify, View Profile | Full | Assigned Team | Own Assignment | Own Only |
| **Credit Score** | Update, View History | Full | Assigned Team | Own Assignment | Own Only |
| **EMI Schedule** | Generate, View | Full | Assigned Team | Own Assignment | Own Only |
| **Payment** | Record, View History | Full | Assigned Team | Own Assignment | Own Only |
| **Employee (User)** | Create, Assign Manager, View | Full | Assigned Only (Borrowers) | - | - |

---

## Step 2: Django Groups & Permissions Setup
Used Django's built-in `Group` and `Permission` framework to bundle system permissions.

### 2.1 Schema Extensions
To support employee-manager relationships and roles:
1. **CustomUser Model**:
   - Added a self-referential foreign key `manager` (`models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')`).
   - Extended `role` choices to include: `[('SUPER_ADMIN', 'Super Admin'), ('ADMIN', 'Admin'), ('MANAGER', 'Manager'), ('LOAN_OFFICER', 'Loan Officer'), ('BORROWER', 'Borrower')]`.
2. **Django Groups**:
   - Four Django Groups configured: `Admins`, `Managers`, `Loan_Officers`, `Borrowers`.

### 2.2 Permissions Mapping & Initialization
We created a custom management command **`rbac.py`** under [accounts/management/commands/](file:///C:/Loan%20management%20System%20-%20Backend/lms/accounts/management/commands/):
- **Command**: `python manage.py rbac`
- **Actions**:
  1. Creates the Groups if they do not exist.
  2. Clears existing permissions for idempotency.
  3. Maps model permissions (e.g. `loans.add_loantype`, `accounts.verify_kyc`, `loans.change_loan`) to their respective Groups.

---

## Step 3: Role Assignment API
Provides administrative endpoints to manage user roles, groups, and reporting lines.

- **Endpoint**: `PATCH /api/auth/users/<int:pk>/assign-role/`
- **Access Check (`IsAdminManagerOrSuperAdmin`)**: Restricts access to Super Admins, Admins, and Managers.
- **Payload**:
  ```json
  {
    "role": "LOAN_OFFICER",
    "manager": 2
  }
  ```
- **Manager Assignment Guardrails**:
  - Enforced in `RoleAssignmentSerializer.validate()`:
    - Managers can only update assignments for users with the `BORROWER` role.
    - Managers cannot promote borrowers to Admin or Manager roles.
    - Managers can only assign borrowers to themselves or a Loan Officer who reports directly to them.
- **Group Synchronization**:
  - Synced inside `RoleAssignmentSerializer.update()`. Updates role field and moves user to corresponding Django permission Group.

---

## Step 4: Custom DRF Permission Classes
Enforces role checking at the Django REST Framework view level.

- **Permissions Location**: [accounts/permissions.py](file:///C:/Loan%20management%20System%20-%20Backend/lms/accounts/permissions.py)
- **Dynamic Role Check (`HasRole(*roles)`)**:
  - Custom factory returning a permission class checking user role in memory. Super Admins always bypass checks.
  - Used on staff endpoints: `kycView`, `CreditScoreUpdateView`, and status updates inside `LoanDetailView`.

---

## Step 5: Data-Level Authorization (Row-Level Security)
Restricts data visibility dynamically based on ownership and reporting relationships.

### 5.1 Dynamic Queryset Filtering
Overrode `get_queryset()` in `loans/views.py` (loans, payments, EMI schedules) and `accounts/views.py` (KYC profiles):
- **Borrowers**: Scoped to own records (`borrower=user`).
- **Loan Officers**: Scoped to assigned borrowers (`borrower__manager=user`).
- **Managers**: Scoped to direct reporting team (`Q(borrower__manager=user) | Q(borrower__manager__manager=user)`).
- **Admins & Super Admins**: Scoped to all records (`objects.all()`).

### 5.2 Serializer Validation Guardrails
- **Credit Score Updates**:
  - Enforced in `CreditScoreHistorySerializer.validate()`:
    - Loan Officers can only post updates for borrowers reporting directly to them.
    - Managers can only update borrowers reporting to them or their Loan Officers.
    - Admins/Super Admins have unrestricted access.
- **Loan Status Updates**:
  - Enforced in `LoanSerializer.validate()`:
    - Restricts loan status modification to authorized staff roles (`SUPER_ADMIN`, `ADMIN`, `MANAGER`, `LOAN_OFFICER`).
