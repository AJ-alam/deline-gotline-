from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('student', 'Student'),
        ('director', 'Director'),
    )

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Personal Information (Extended)
    beneficiary_number = models.CharField(max_length=50, blank=True, null=True)
    treaty_number = models.CharField(max_length=50, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    preferred_name = models.CharField(max_length=255, blank=True, null=True)
    gender = models.CharField(max_length=50, blank=True, null=True)
    pronouns = models.CharField(max_length=50, blank=True, null=True)
    alternate_phone = models.CharField(max_length=20, blank=True, null=True)
    mailing_address = models.TextField(blank=True, null=True)
    num_dependents = models.IntegerField(default=0)
    dependent_ages = models.CharField(max_length=255, blank=True, null=True)
    disability_accommodation = models.TextField(blank=True, null=True)
    
    # Eligibility Identifiers (Extended)
    upi = models.CharField(max_length=100, blank=True, null=True) # Unique Personal Identifier
    financial_assistance_status = models.CharField(max_length=255, blank=True, null=True)
    
    # Banking Info (Extended)
    account_holder_name = models.CharField(max_length=255, blank=True, null=True)
    account_type = models.CharField(max_length=100, blank=True, null=True, default='Direct Deposit')
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    transit_number = models.CharField(max_length=10, blank=True, null=True)
    inst_number = models.CharField(max_length=10, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Eligibility Streams (Extended)
    primary_stream = models.CharField(max_length=100, blank=True, null=True)
    secondary_stream = models.CharField(max_length=100, blank=True, null=True)

    # Enrollment Information
    institution_name = models.CharField(max_length=255, blank=True, null=True)
    program_credential = models.CharField(max_length=255, blank=True, null=True)
    current_semester = models.CharField(max_length=100, blank=True, null=True)
    enrollment_status = models.CharField(max_length=50, blank=True, null=True) # e.g. Full-Time
    course_load = models.IntegerField(default=100)
    program_type = models.CharField(max_length=255, blank=True, null=True)
    expected_graduation_date = models.DateField(blank=True, null=True)
    years_in_program = models.CharField(max_length=100, blank=True, null=True) # e.g. Year 2 of 4
    institution_location = models.CharField(max_length=255, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.email} ({self.role})"
