from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = "Initializes RBAC, creating groups and permissions for each model."

    def handle(self, *args, **options):
        # Define the default permissions for each group
        # Format: (app_label, model_name, permission_codename)
        groups_data = {
            "Admins": [
                # Can manage Loan Types (Products)
                ("loans", "loantype", "add_loantype"),
                ("loans", "loantype", "change_loantype"),
                ("loans", "loantype", "delete_loantype"),
                ("loans", "loantype", "view_loantype"),
                # Can view and edit user accounts (to assign roles/managers)
                ("accounts", "customuser", "view_customuser"),
                ("accounts", "customuser", "change_customuser"),
                # Can view and approve/disburse loans
                ("loans", "loan", "view_loan"),
                ("loans", "loan", "change_loan"),
            ],
            "Managers": [
                # Can view and change loans
                ("loans", "loan", "view_loan"),
                ("loans", "loan", "change_loan"),
                # Can view and change KYC / borrower profiles
                ("accounts", "borrowerprofile", "view_borrowerprofile"),
                ("accounts", "borrowerprofile", "change_borrowerprofile"),
                # Can view and update credit score histories
                ("accounts", "creditscorehistory", "view_creditscorehistory"),
                ("accounts", "creditscorehistory", "add_creditscorehistory"),
                # Can view EMI schedules and payment history
                ("loans", "emischedule", "view_emischedule"),
                ("loans", "payment", "view_payment"),
            ],
            "Loan_Officers": [
                # Can view and change loans
                ("loans", "loan", "view_loan"),
                ("loans", "loan", "change_loan"),
                # Can view and change KYC / borrower profiles
                ("accounts", "borrowerprofile", "view_borrowerprofile"),
                ("accounts", "borrowerprofile", "change_borrowerprofile"),
                # Can view and update credit score histories
                ("accounts", "creditscorehistory", "view_creditscorehistory"),
                ("accounts", "creditscorehistory", "add_creditscorehistory"),
                # Can view EMI schedules and payments
                ("loans", "emischedule", "view_emischedule"),
                ("loans", "payment", "view_payment"),
            ],
            "Borrowers": [
                # Borrowers can add (apply for) and view loans
                ("loans", "loan", "add_loan"),
                ("loans", "loan", "view_loan"),
                # Can view their own borrower profile and EMI schedules
                ("accounts", "borrowerprofile", "view_borrowerprofile"),
                ("loans", "emischedule", "view_emischedule"),
                # Can view and create payments
                ("loans", "payment", "add_payment"),
                ("loans", "payment", "view_payment"),
            ]
        }

        for group_name, perms in groups_data.items():
            # Get or create the group in the database
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {group_name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Group already exists: {group_name}"))

            # Clear existing permissions to prevent duplicate accumulation during re-runs
            group.permissions.clear()

            # Assign new permissions to the group
            for app_label, model_name, codename in perms:
                try:
                    # Fetch the content type of the target model
                    content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                    # Fetch the specific permission object
                    permission = Permission.objects.get(content_type=content_type, codename=codename)
                    group.permissions.add(permission)
                except (ContentType.DoesNotExist, Permission.DoesNotExist):
                    self.stdout.write(self.style.ERROR(
                        f"Permission '{codename}' for {app_label}.{model_name} not found."
                    ))

            self.stdout.write(self.style.SUCCESS(f"Configured permissions for group: {group_name}"))

        self.stdout.write(self.style.SUCCESS("RBAC initialization completed successfully!"))
