# notifications/tasks.py
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_payment_notification(payment_id, user_id):
    
    # Dispatch Notification (Mocking the Push Notification)
    print("\n" + "="*40)
    print(f"🔔 [MOCK PUSH NOTIFICATION]")
    print(f"To User ID: {user_id}")
    print(f"Message: Your payment (ID: {payment_id}) was successful!")
    print("="*40 + "\n")