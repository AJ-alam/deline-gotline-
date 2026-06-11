"""
Duplicate Detection Service with Privacy Protection

Detects potential duplicate applicants using privacy-protected identifiers.
Uses SHA-256 hashing to ensure identifiers cannot be reversed.
"""

import hashlib
import logging
from django.utils import timezone
from api.models import AuditLog, DuplicateDetectionLog
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


class DuplicateDetectionService:
    """Service for detecting potential duplicate applicants with privacy protection."""
    
    @staticmethod
    def generate_privacy_protected_identifier(student_profile):
        """
        Generate a privacy-protected identifier using SHA-256 hashing.
        
        The identifier is based on:
        - Date of Birth
        - Last 4 digits of Beneficiary Number
        - Email address
        
        This creates a one-way hash that cannot be reversed.
        
        Args:
            student_profile: User profile object with DOB, beneficiary_number, email
            
        Returns:
            str: SHA-256 hash of the identifier components
        """
        # §6.3: identifier must be based on something that doesn't change between
        # accounts. Email is intentionally EXCLUDED — the whole purpose of this
        # check is detecting the same person who created two profiles with
        # DIFFERENT email addresses. Using email in the hash would make every
        # account unique regardless of the person.
        #
        # We combine: date_of_birth + full beneficiary_number + indian_status_number
        # All three together uniquely identify a person without being reversible.
        dob = str(student_profile.date_of_birth) if student_profile.date_of_birth else ''
        beneficiary = (student_profile.beneficiary_number or '').strip()
        # Indian Status / Treaty number stored in profile.indian_status
        indian_status = (student_profile.indian_status or '').strip()

        identifier_string = f"{dob}|{beneficiary}|{indian_status}".lower()

        # Hash using SHA-256 (one-way, cannot be reversed)
        identifier_hash = hashlib.sha256(identifier_string.encode()).hexdigest()

        return identifier_hash

    @staticmethod
    def check_for_duplicates(submission):
        """
        Check if a submission is a potential duplicate.
        
        Args:
            submission: FormSubmission object
            
        Returns:
            dict with duplicate detection results
        """
        result = {
            'is_flagged': False,
            'duplicate_count': 0,
            'message': 'No duplicates detected',
            'requires_review': False
        }
        
        try:
            # Generate privacy-protected identifier
            student = submission.student
            profile = student.profile if hasattr(student, 'profile') else None
            
            if not profile:
                return result
            
            identifier_hash = DuplicateDetectionService.generate_privacy_protected_identifier(profile)
            
            # Check for existing hashes
            existing_logs = DuplicateDetectionLog.objects.filter(
                identifier_hash=identifier_hash,
                is_confirmed_duplicate=False
            ).exclude(submission=submission)

            duplicate_count = existing_logs.count()

            if duplicate_count > 0:
                result['is_flagged'] = True
                result['duplicate_count'] = duplicate_count
                result['requires_review'] = True
                result['message'] = 'This application has been flagged for review'

            # Create or update detection log
            log, created = DuplicateDetectionLog.objects.get_or_create(
                submission=submission,
                defaults={
                    'identifier_hash': identifier_hash,
                    'is_flagged': result['is_flagged']
                }
            )
            
            if not created:
                log.identifier_hash = identifier_hash
                log.is_flagged = result['is_flagged']
                log.save()
            
            result['log_id'] = log.id
            
        except Exception as e:
            logger.error("Duplicate detection error for submission %s: %s", getattr(submission, 'id', '?'), e)
            result['error'] = str(e)
        
        return result

    @staticmethod
    def mark_as_legitimate(submission_id, reviewed_by, notes=''):
        """
        Mark a flagged submission as legitimate (not a duplicate).
        
        Args:
            submission_id: FormSubmission ID
            reviewed_by: User who reviewed the flag
            notes: Optional notes about the review
        """
        try:
            log = DuplicateDetectionLog.objects.get(submission_id=submission_id)
            log.is_flagged = False
            log.is_confirmed_duplicate = False
            log.reviewed_by = reviewed_by
            log.reviewed_at = timezone.now()
            log.notes = notes
            log.save()
            AuditLog.objects.create(
                action=f"Duplicate flag cleared for submission {submission_id}",
                performed_by=reviewed_by,
                role=getattr(reviewed_by, 'role', 'staff'),
                details=f"Submission {submission_id} — Notes: {notes}"
            )
            return True
        except DuplicateDetectionLog.DoesNotExist:
            return False

    @staticmethod
    def mark_as_confirmed_duplicate(submission_id, reviewed_by, notes=''):
        try:
            log = DuplicateDetectionLog.objects.get(submission_id=submission_id)
            log.is_flagged = True
            log.is_confirmed_duplicate = True
            log.reviewed_by = reviewed_by
            log.reviewed_at = timezone.now()
            log.notes = notes
            log.save()
            AuditLog.objects.create(
                action=f"Duplicate confirmed for submission {submission_id}",
                performed_by=reviewed_by,
                role=getattr(reviewed_by, 'role', 'staff'),
                details=f"Submission {submission_id} — Notes: {notes}"
            )
            return True
        except DuplicateDetectionLog.DoesNotExist:
            return False

    @staticmethod
    def get_flagged_submissions():
        """
        Get all flagged submissions awaiting review.
        
        Returns:
            QuerySet of DuplicateDetectionLog objects
        """
        return DuplicateDetectionLog.objects.filter(
            is_flagged=True,
            reviewed_at__isnull=True
        ).order_by('-created_at')

    @staticmethod
    def get_duplicate_status(submission_id):
        """
        Get the duplicate detection status for a submission.
        
        Args:
            submission_id: FormSubmission ID
            
        Returns:
            dict with status information
        """
        try:
            log = DuplicateDetectionLog.objects.get(submission_id=submission_id)
            return {
                'is_flagged': log.is_flagged,
                'is_confirmed_duplicate': log.is_confirmed_duplicate,
                'reviewed_by': log.reviewed_by.get_full_name() if log.reviewed_by else None,
                'reviewed_at': log.reviewed_at.isoformat() if log.reviewed_at else None,
                'notes': log.notes
            }
        except DuplicateDetectionLog.DoesNotExist:
            return {
                'is_flagged': False,
                'is_confirmed_duplicate': False,
                'reviewed_by': None,
                'reviewed_at': None,
                'notes': None
            }
