"""
Eligibility Service for Student Funding Application Management System

Handles automatic eligibility determination for each funding stream based on policy rules.
"""

from decimal import Decimal
from django.utils import timezone
from api.models import PolicySetting, AuditLog
from django.contrib.auth import get_user_model

User = get_user_model()


class EligibilityService:
    """Service for determining student eligibility for funding streams."""

    @staticmethod
    def check_eligibility(submission):
        """
        Check eligibility for a submission against all applicable funding streams.
        
        Args:
            submission: FormSubmission object
            
        Returns:
            dict with eligibility results for each stream
        """
        results = {
            'eligible_streams': [],
            'ineligible_streams': [],
            'details': {},
            'timestamp': timezone.now().isoformat()
        }
        
        # Extract student data
        student = submission.student
        profile = student.profile if hasattr(student, 'profile') else None
        answers = {a.field.label.lower(): a.answer_text for a in submission.answers.all()}
        
        # Check each funding stream
        streams = ['PSSSP', 'UCEPP', 'DGGR']
        
        for stream in streams:
            eligibility_result = EligibilityService._check_stream_eligibility(
                stream, student, profile, answers, submission
            )
            
            if eligibility_result['eligible']:
                results['eligible_streams'].append(stream)
            else:
                results['ineligible_streams'].append(stream)
            
            results['details'][stream] = eligibility_result
        
        return results

    @staticmethod
    def _check_stream_eligibility(stream, student, profile, answers, submission):
        """
        Check eligibility for a specific funding stream.
        
        Args:
            stream: Funding stream name (PSSSP, UCEPP, DGGR)
            student: User object
            profile: User profile object
            answers: Dict of form answers
            submission: FormSubmission object
            
        Returns:
            dict with eligibility status and reasons
        """
        result = {
            'eligible': True,
            'reasons': [],
            'stream': stream
        }
        
        if stream == 'PSSSP':
            result = EligibilityService._check_psssp_eligibility(student, profile, answers)
        elif stream == 'UCEPP':
            result = EligibilityService._check_ucepp_eligibility(student, profile, answers)
        elif stream == 'DGGR':
            result = EligibilityService._check_dggr_eligibility(student, profile, answers)
        
        return result

    @staticmethod
    def _check_psssp_eligibility(student, profile, answers):
        """
        Check C-DFN PSSSP eligibility criteria:
        - Indian Act status verification
        - Enrollment status (full-time or part-time)
        - Program type eligibility
        - Not receiving NWT SFA
        """
        result = {
            'eligible': True,
            'reasons': [],
            'stream': 'PSSSP'
        }
        
        # Check Indian Act status
        if profile and not profile.indian_status:
            result['eligible'] = False
            result['reasons'].append('Indian Act status not verified')
        
        # Check enrollment status
        enrollment = answers.get('enrollmenttype', '').lower()
        if not enrollment or enrollment not in ['full-time', 'part-time', 'fulltime', 'parttime']:
            result['eligible'] = False
            result['reasons'].append('Enrollment status not specified or invalid')
        
        # Check program type
        program = answers.get('program', '').lower()
        if not program:
            result['eligible'] = False
            result['reasons'].append('Program information not provided')
        
        # Check NWT SFA eligibility (if eligible for NWT SFA, cannot use PSSSP)
        if profile and profile.is_sfa_active:
            result['eligible'] = False
            result['reasons'].append('Student is eligible for NWT SFA; PSSSP funding not applicable')
        
        return result

    @staticmethod
    def _check_ucepp_eligibility(student, profile, answers):
        """
        Check C-DFN UCEPP eligibility criteria:
        - Indian Act status verification
        - Upgrading program enrollment
        - Not receiving NWT SFA
        """
        result = {
            'eligible': True,
            'reasons': [],
            'stream': 'UCEPP'
        }
        
        # Check Indian Act status
        if profile and not profile.indian_status:
            result['eligible'] = False
            result['reasons'].append('Indian Act status not verified')
        
        # Check for upgrading program
        program_type = answers.get('programtype', '').lower()
        if program_type and 'upgrading' not in program_type and 'upgrade' not in program_type:
            result['eligible'] = False
            result['reasons'].append('UCEPP is only for upgrading programs')
        
        # Check NWT SFA eligibility
        if profile and profile.is_sfa_active:
            result['eligible'] = False
            result['reasons'].append('Student is eligible for NWT SFA; UCEPP funding not applicable')
        
        return result

    @staticmethod
    def _check_dggr_eligibility(student, profile, answers):
        """
        Check DGGR Bursaries eligibility criteria:
        - Beneficiary status verification
        - Enrollment status
        - Not receiving other land claim funding
        """
        result = {
            'eligible': True,
            'reasons': [],
            'stream': 'DGGR'
        }
        
        # Check Beneficiary status
        if profile and not profile.beneficiary_number:
            result['eligible'] = False
            result['reasons'].append('Beneficiary number not verified')
        
        # Check enrollment status
        enrollment = answers.get('enrollmenttype', '').lower()
        if not enrollment or enrollment not in ['full-time', 'part-time', 'fulltime', 'parttime']:
            result['eligible'] = False
            result['reasons'].append('Enrollment status not specified or invalid')
        
        # Check for other land claim funding
        other_funding = answers.get('receivingotherfunding', '').lower()
        if other_funding == 'yes':
            result['eligible'] = False
            result['reasons'].append('Student is receiving other land claim funding; DGGR funding not applicable')
        
        return result

    @staticmethod
    def log_eligibility_check(submission, eligibility_result, performed_by=None):
        """
        Log the eligibility check in the audit trail.
        
        Args:
            submission: FormSubmission object
            eligibility_result: Result dict from check_eligibility
            performed_by: User who performed the check (optional)
        """
        action = f"Eligibility Check: {', '.join(eligibility_result['eligible_streams'])} eligible"
        
        AuditLog.objects.create(
            action=action,
            performed_by=performed_by,
            role=performed_by.role if performed_by else 'system',
            application=None,  # Link to FormSubmission if needed
            details=str(eligibility_result)
        )

    @staticmethod
    def get_eligibility_policy_rules(stream):
        """
        Get the policy rules for a specific funding stream.
        
        Args:
            stream: Funding stream name
            
        Returns:
            dict of policy rules
        """
        rules = {}
        
        # Get all policy settings for this stream
        section_prefix = stream.lower()
        settings = PolicySetting.objects.filter(section__startswith=section_prefix)
        
        for setting in settings:
            rules[setting.field_key] = {
                'value': setting.value,
                'unit': setting.unit,
                'label': setting.field_label
            }
        
        return rules
