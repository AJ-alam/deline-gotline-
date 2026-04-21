import uuid
from django.core.management.base import BaseCommand
from api.models import PolicySetting

class Command(BaseCommand):
    help = 'Seeds all default policy settings from the official DGG Funding Policy'

    def handle(self, *args, **options):
        self.stdout.write("Seeding DGG Policy Settings...")
        
        # Clear existing to ensure fresh start as requested
        # "Existing JSON policy data will be lost"
        PolicySetting.objects.all().delete()

        policies = [
            # SECTION: application_deadlines
            ('application_deadlines', 'fall_deadline', 'Fall Semester Deadline', 8, 'month'),
            ('application_deadlines', 'winter_deadline', 'Winter Semester Deadline', 12, 'month'),
            ('application_deadlines', 'spring_deadline', 'Spring Semester Deadline', 4, 'month'),
            ('application_deadlines', 'summer_deadline', 'Summer Semester Deadline', 6, 'month'),

            # SECTION: psssp_tuition
            ('psssp_tuition', 'max_per_semester', 'Max Tuition Bursary Per Semester', 5000, '$'),

            # SECTION: psssp_living
            ('psssp_living', 'fulltime_no_dependents', 'Full-Time, No Dependents (per month)', 1200, '$'),
            ('psssp_living', 'fulltime_with_dependents', 'Full-Time, With Dependents (per month)', 1700, '$'),
            ('psssp_living', 'parttime_no_dependents', 'Part-Time, No Dependents (per month)', 720, '$'),
            ('psssp_living', 'parttime_with_dependents', 'Part-Time, With Dependents (per month)', 1020, '$'),

            # SECTION: psssp_travel
            ('psssp_travel', 'max_trips_per_year', 'Max Trips Per Year', 2, 'trips'),
            ('psssp_travel', 'min_distance_km', 'Minimum Distance from Home (km)', 200, 'km'),
            ('psssp_travel', 'max_per_trip_no_dependents', 'Max Per Trip — No Dependents', 2000, '$'),
            ('psssp_travel', 'max_per_trip_with_dependents', 'Max Per Trip — With Dependents', 3500, '$'),

            # SECTION: psssp_graduation_travel
            ('psssp_graduation_travel', 'max_total', 'Max Total Bursary', 5000, '$'),
            ('psssp_graduation_travel', 'max_family_members', 'Max Family Members Covered', 2, 'people'),
            ('psssp_graduation_travel', 'max_hotel_per_night', 'Max Hotel Per Night', 350, '$'),
            ('psssp_graduation_travel', 'max_hotel_nights', 'Max Hotel Nights', 3, 'nights'),

            # SECTION: ucepp_tuition
            ('ucepp_tuition', 'max_per_semester', 'Max Tuition Bursary Per Semester', 2000, '$'),

            # SECTION: ucepp_living
            ('ucepp_living', 'fulltime_no_dependents', 'Full-Time, No Dependents (per month)', 700, '$'),
            ('ucepp_living', 'fulltime_with_dependents', 'Full-Time, With Dependents (per month)', 1000, '$'),
            ('ucepp_living', 'parttime_no_dependents', 'Part-Time, No Dependents (per month)', 420, '$'),
            ('ucepp_living', 'parttime_with_dependents', 'Part-Time, With Dependents (per month)', 600, '$'),

            # SECTION: dggr_tuition
            ('dggr_tuition', 'fulltime_per_semester', 'Full-Time Per Semester', 1500, '$'),
            ('dggr_tuition', 'parttime_per_semester', 'Part-Time Per Semester', 900, '$'),

            # SECTION: dggr_extra_tuition
            ('dggr_extra_tuition', 'annual_cap_all_students', 'Annual Cap (All Students Combined)', 36000, '$'),
            ('dggr_extra_tuition', 'threshold_per_semester', 'Tuition Threshold Per Semester to Qualify', 5000, '$'),
            ('dggr_extra_tuition', 'threshold_per_year', 'Tuition Threshold Per Year to Qualify', 15000, '$'),
            ('dggr_extra_tuition', 'max_percent_covered', 'Max % of Tuition Covered', 25, '%'),
            ('dggr_extra_tuition', 'max_per_semester', 'Max Bursary Per Semester', 4000, '$'),
            ('dggr_extra_tuition', 'max_per_year', 'Max Bursary Per Year', 12000, '$'),

            # SECTION: dggr_living
            ('dggr_living', 'fulltime_no_dependents', 'Full-Time, No Dependents (per month)', 700, '$'),
            ('dggr_living', 'fulltime_with_dependents', 'Full-Time, With Dependents (per month)', 950, '$'),
            ('dggr_living', 'parttime_no_dependents', 'Part-Time, No Dependents (per month)', 420, '$'),
            ('dggr_living', 'parttime_with_dependents', 'Part-Time, With Dependents (per month)', 570, '$'),

            # SECTION: dggr_practicum_award
            ('dggr_practicum_award', 'award_amount', 'Award Amount', 500, '$'),
            ('dggr_practicum_award', 'application_deadline_months', 'Application Deadline (months after placement)', 6, 'months'),

            # SECTION: dggr_grad_bursary
            ('dggr_grad_bursary', 'high_school_diploma', 'High School Diploma', 500, '$'),
            ('dggr_grad_bursary', 'certificate', 'Certificate', 1000, '$'),
            ('dggr_grad_bursary', 'trades_certificate', 'Trades Certificate of Qualification', 2000, '$'),
            ('dggr_grad_bursary', 'trades_journeyperson', 'Trades Journeyperson Licence', 3000, '$'),
            ('dggr_grad_bursary', 'diploma', 'Diploma', 2000, '$'),
            ('dggr_grad_bursary', 'pilot_licence', 'Professional Pilot Licence', 3000, '$'),
            ('dggr_grad_bursary', 'red_seal', 'Red Seal', 3000, '$'),
            ('dggr_grad_bursary', 'bachelors_degree', 'Bachelor\'s Degree', 3000, '$'),
            ('dggr_grad_bursary', 'masters_degree', 'Master\'s Degree', 5000, '$'),
            ('dggr_grad_bursary', 'doctorate', 'Doctorate (PhD)', 5000, '$'),
            ('dggr_grad_bursary', 'juris_doctor', 'Juris Doctor / Bachelor of Laws', 5000, '$'),
            ('dggr_grad_bursary', 'doctor_medicine_dental', 'Doctor of Medicine / Doctor of Dental Surgery', 5000, '$'),

            # SECTION: dggr_academic_scholarship
            ('dggr_academic_scholarship', 'high_threshold_percent', 'High Achievement Threshold', 80, '%'),
            ('dggr_academic_scholarship', 'high_achievement_award', 'High Achievement Award', 1000, '$'),
            ('dggr_academic_scholarship', 'mid_threshold_lower', 'Mid Achievement Lower Bound', 70, '%'),
            ('dggr_academic_scholarship', 'mid_threshold_upper', 'Mid Achievement Upper Bound', 79.99, '%'),
            ('dggr_academic_scholarship', 'mid_achievement_award', 'Mid Achievement Award', 500, '$'),

            # SECTION: dggr_hardship
            ('dggr_hardship', 'max_per_student', 'Maximum Per Student', 500, '$'),

            # SECTION: eligibility_rules
            ('eligibility_rules', 'min_program_weeks', 'Minimum Program Length', 12, 'weeks'),
            ('eligibility_rules', 'fulltime_min_load_percent', 'Full-Time Minimum Course Load', 60, '%'),
            ('eligibility_rules', 'fulltime_min_load_disability', 'Full-Time Min Load (with disability)', 40, '%'),
            ('eligibility_rules', 'parttime_max_load_percent', 'Part-Time Maximum Course Load', 59.99, '%'),
            ('eligibility_rules', 'parttime_max_load_disability', 'Part-Time Max Load (with disability)', 39.99, '%'),

            # SECTION: misconduct_rules
            ('misconduct_rules', 'suspension_misconduct_years', 'Suspension for Misconduct (academic years)', 1, 'years'),
            ('misconduct_rules', 'suspension_overpayment_years', 'Suspension for Overpayment Failure (academic years)', 1, 'years'),

            # SECTION: payment_schedule
            ('payment_schedule', 'tuition_payment_weeks_after_deadline', 'Tuition Payment — Weeks After Deadline', 4, 'weeks'),
            ('payment_schedule', 'living_payment_day_of_month', 'Monthly Living — Payment Day of Month', 1, 'day'),
            ('payment_schedule', 'other_bursary_max_processing_days', 'Other Bursaries — Max Processing (business days)', 15, 'days'),
        ]

        count = 0
        for section, key, label, value, unit in policies:
            PolicySetting.objects.get_or_create(
                section=section,
                field_key=key,
                defaults={
                    'field_label': label,
                    'value': value,
                    'unit': unit
                }
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"SUCCESS: Seeded {count} policy fields successfully."))
