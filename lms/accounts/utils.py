import threading
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

def _send_email_thread(subject, message, recipient_list):
    """
    Function meant to be run in a separate thread.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Email '{subject}' sent successfully to {recipient_list}")
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}. Error: {str(e)}")

def send_login_notification(user_email, username, ip_address=None):
    """
    Asynchronously sends a login notification email to the user.
    """
    if not user_email:
        return

    subject = "New Login to Your LMS Account"
    
    current_time = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"Hello {username},\n\n"
    message += f"We noticed a new login to your account on {current_time} (UTC).\n"
    if ip_address:
        message += f"IP Address: {ip_address}\n"
    message += "\nIf this was you, you can safely ignore this email.\n"
    message += "If you did not initiate this login, please contact support immediately.\n\n"
    message += "Thanks,\nLMS Team"
    
    # Start a new thread to send the email asynchronously
    email_thread = threading.Thread(
        target=_send_email_thread,
        args=(subject, message, [user_email])
    )
    email_thread.daemon = True # Allow the program to exit even if this thread is running
    email_thread.start()
