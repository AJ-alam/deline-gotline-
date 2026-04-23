"""
Duplicate Detection Service with Privacy Protection

Detects potential duplicate applicants using privacy-protected identifiers.
Uses SHA-256 hashing to ensure identifiers cannot be reversed.
"""

import hashlib
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from api.models import AuditLog
from django.contrib.auth import get_user_model

User = get_user_model()


class DuplicateDetectionLog(models.Model):
    """Model for tracking duplicate detection activities."""
    
    submission_id = models.IntegerField()  # FormSubmission ID
    identifier_hash = models.CharField(max_length=64, db_index=True)  # SHA-256 hash
    is_flagged = models.BooleanField(default=False)
    is_confirmed_duplicate = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['identifier_hash', 'is_flagged']),
        ]
    
    def __str__(self):
        return f"Duplicate Check for Submission {self.submission_id}"


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
        # Extract components
        dob = str(student_profile.date_of_birth) if student_profile.date_of_birth else ''
        beneficiary = student_profile.beneficiary_number or ''
        email = student_profile.user.email if hasattr(student_profile, 'user') else ''
        
        # Get last 4 of beneficiary number
        beneficiary_last4 = beneficiary[-4:] if len(beneficiary) >= 4 else beneficiary
        
        # Create identifier string
        identifier_string = f"{dob}|{beneficiary_last4}|{email}".lower()
        
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
                is_confirmed_duplicate=False  # Don't count confirmed duplicates
            ).exclude(submission_id=submission.id)
            
            duplicate_count = existing_logs.count()
            
            # Flag if duplicates found
            if duplicate_count > 0:
                result['is_flagged'] = True
                result['duplicate_count'] = duplicate_count
                result['requires_review'] = True
                result['message'] = f'This application has been flagged for review'
            
            # Create or update detection log
            log, created = DuplicateDetectionLog.objects.get_or_create(
                submission_id=submission.id,
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
            # Log error but don't fail the submission
            print(f"Duplicate detection error: {str(e)}")
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
            
            # Log in audit trail
            AuditLog.objects.create(
                action=f"Duplicate flag cleared for submission {submission_id}",
                performed_by=reviewed_by,
                role=reviewed_by.role if hasattr(reviewed_by, 'role') else 'staff',
                details=f"Notes: {notes}"
            )
            
            return True
        except DuplicateDetectionLog.DoesNotExist:
            return False

    @staticmethod
    def mark_as_confirmed_duplicate(submission_id, reviewed_by, notes=''):
        """
        Mark a flagged submission as a confirmed duplicate.
        
        Args:
            submission_id: FormSubmission ID
            reviewed_by: User who reviewed the flag
            notes: Optional notes about the review
        """
        try:
            log = DuplicateDetectionLog.objects.get(submission_id=submission_id)
            log.is_flagged = True
            log.is_confirmed_duplicate = True
            log.reviewed_by = reviewed_by
            log.reviewed_at = timezone.now()
            log.notes = notes
            log.save()
            
            # Log in audit trail
            AuditLog.objects.create(
                action=f"Duplicate confirmed for submission {submission_id}",
                performed_by=reviewed_by,
                role=reviewed_by.role if hasattr(reviewed_by, 'role') else 'staff',
                details=f"Notes: {notes}"
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
