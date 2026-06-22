import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Application
from notifications.models import Notification

logger = logging.getLogger(__name__)

# Pre-save signal to store the old status
@receiver(pre_save, sender=Application)
def capture_previous_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Application.objects.get(pk=instance.pk)
            instance._original_status = old_instance.status
        except Application.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None

# Post-save signal to create a notification if status has changed
@receiver(post_save, sender=Application)
def notify_status_change(sender, instance, created, **kwargs):
    # If the application was just created, we might send a "Submited" notification
    if created:
        Notification.objects.create(
            user=instance.student,
            title=f"Application Submitted: {instance.form_type}",
            message=f"Your {instance.form_type} has been successfully submitted and is awaiting staff review.",
            link=f"/dashboard/applications/{instance.id}"
        )
        return

    # Check for status change
    old_status = getattr(instance, '_original_status', None)
    new_status = instance.status

    if old_status != new_status:
        # Determine notification title and message based on the new status
        title = f"Application Status Updated: {instance.form_type}"
        message = ""

        if new_status == Application.Status.REVIEW:
            message = "Your application is now being reviewed by our staff."
        elif new_status == Application.Status.PENDING:
            message = "Your application has been reviewed and is now pending director approval."
        elif new_status == Application.Status.APPROVED:
            title = f"Application APPROVED: {instance.form_type}"
            message = f"Congratulations! Your application has been approved. {instance.decision_notes or ''}"
        elif new_status == Application.Status.DENIED:
            title = f"Application DENIED: {instance.form_type}"
            message = f"Unfortunately, your application was not approved at this time. Notes: {instance.decision_notes or ''}"
        elif new_status == Application.Status.WAITING_B:
            message = "Staff are currently processing your academic details (Form B)."
        else:
            message = f"The status of your application has been changed to {new_status}."

        Notification.objects.create(
            user=instance.student,
            title=title,
            message=message,
            link=f"/dashboard/applications/{instance.id}"
        )
        logger.info(f"Notification created for user {instance.student.email} on application {instance.id}")
