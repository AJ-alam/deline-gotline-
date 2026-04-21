from .models import Notification

def create_notification(user, title, message, link=None):
    """
    Creates a notification for a user.
    """
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link
    )
