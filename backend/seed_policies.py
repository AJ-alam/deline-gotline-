import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import PolicySetting

def seed_policies():
    print("Seeding DGG Post-Secondary Funding Policies...")
    
    policies = [
        # 🅐 Program 1: C-DFN PSSSP Bursaries
        ('psssp_rates', 'tuition_cap', 'PSSSP Tuition Cap (Per Semester)', 5000, 'per semester'),
        ('psssp_rates', 'living_full_no_dep', 'Living (Full-Time, No Dependents)', 1200, 'per month'),
        ('psssp_rates', 'living_full_with_dep', 'Living (Full-Time, With Dependents)', 1700, 'per month'),
        ('psssp_rates', 'living_part_no_dep', 'Living (Part-Time, No Dependents)', 720, 'per month'),
        ('psssp_rates', 'living_part_with_dep', 'Living (Part-Time, With Dependents)', 1020, 'per month'),
        ('psssp_rates', 'travel_no_dep', 'Travel Assistance (No Dependents)', 2000, 'max per trip'),
        ('psssp_rates', 'travel_with_dep', 'Travel Assistance (With Dependents)', 3500, 'max per trip'),
        
        # 🅑 Program 2: C-DFN UCEPP Bursaries
        ('ucepp_rates', 'tuition_cap', 'UCEPP Tuition Cap (Per Semester)', 2000, 'per semester'),
        ('ucepp_rates', 'living_full_no_dep', 'Living (Full-Time, No Dependents)', 700, 'per month'),
        ('ucepp_rates', 'living_full_with_dep', 'Living (Full-Time, With Dependents)', 1000, 'per month'),
        ('ucepp_rates', 'living_part_no_dep', 'Living (Part-Time, No Dependents)', 420, 'per month'),
        ('ucepp_rates', 'living_part_with_dep', 'Living (Part-Time, With Dependents)', 600, 'per month'),
        
        # 🅒 Program 3: DGGR Bursaries
        ('dggr_rates', 'tuition_full', 'DGGR Top-up (Full-Time)', 1500, 'per semester'),
        ('dggr_rates', 'tuition_part', 'DGGR Top-up (Part-Time)', 900, 'per semester'),
        ('dggr_rates', 'living_full_no_dep', 'Living (Full-Time, No Dependents)', 700, 'per month'),
        ('dggr_rates', 'living_full_with_dep', 'Living (Full-Time, With Dependents)', 950, 'per month'),
        ('dggr_rates', 'living_part_no_dep', 'Living (Part-Time, No Dependents)', 420, 'per month'),
        ('dggr_rates', 'living_part_with_dep', 'Living (Part-Time, With Dependents)', 570, 'per month'),
        ('dggr_rates', 'summer_practicum_award', 'Summer/Practicum Award', 500, 'flat'),
        ('dggr_rates', 'hardship_max', 'Hardship Bursary Max', 500, 'max'),
        
        # C2 — DGGR Extra Tuition Bursary
        ('dggr_extra_tuition', 'trigger_semester', 'Extra Tuition Trigger (Semester)', 5000, '$'),
        ('dggr_extra_tuition', 'trigger_year', 'Extra Tuition Trigger (Year)', 15000, '$'),
        ('dggr_extra_tuition', 'pool_cap_year', 'Total Relief Pool Cap (Year)', 36000, '$'),
        ('dggr_extra_tuition', 'relief_percent', 'Relief Percentage (of tuition)', 0.25, 'decimal'),
        ('dggr_extra_tuition', 'relief_max_semester', 'Relief Max (Per Semester)', 4000, 'max $'),
        ('dggr_extra_tuition', 'relief_max_year', 'Relief Max (Per Year)', 12000, 'max $'),
        
        # C5 — DGGR Grad Bursary
        ('dggr_grad_bursary', 'high_school', 'High School Diploma', 500, '$'),
        ('dggr_grad_bursary', 'certificate', 'Certificate', 1000, '$'),
        ('dggr_grad_bursary', 'trades_cert', 'Trades Cert of Qualification', 2000, '$'),
        ('dggr_grad_bursary', 'diploma', 'Diploma', 2000, '$'),
        ('dggr_grad_bursary', 'trades_journeyperson', 'Trades Journeyperson Licence', 3000, '$'),
        ('dggr_grad_bursary', 'pilot_licence', 'Professional Pilot Licence', 3000, '$'),
        ('dggr_grad_bursary', 'red_seal', 'Red Seal', 3000, '$'),
        ('dggr_grad_bursary', 'bachelors', 'Bachelors Degree', 3000, '$'),
        ('dggr_grad_bursary', 'masters', 'Masters Degree', 5000, '$'),
        ('dggr_grad_bursary', 'doctorate', 'Doctorate (PhD)', 5000, '$'),
        ('dggr_grad_bursary', 'juris_doctor', 'Juris Doctor / LLB', 5000, '$'),
        ('dggr_grad_bursary', 'md_dds', 'MD or DDS', 5000, '$'),
        
        # C6 — DGGR Academic Achievement Scholarship
        ('dggr_scholarship', 'gpa_80_plus', 'Achievement (80% or higher)', 1000, '$ per semester'),
        ('dggr_scholarship', 'gpa_70_79', 'Achievement (70% – 79.99%)', 500, '$ per semester'),
        
        # System Config
        ('system_config', 'travel_claim_days', 'Travel Claim Submission Deadline', 30, 'days'),
        ('system_config', 'grad_bursary_expiry_months', 'Grad Bursary Deadline', 6, 'months'),
        ('system_config', 'scholarship_expiry_months', 'Scholarship Deadline', 6, 'months'),
        ('application_deadlines', 'fall_deadline', 'Fall Deadline Month', 8, 'month'),
        ('application_deadlines', 'winter_deadline', 'Winter Deadline Month', 12, 'month'),
        ('application_deadlines', 'spring_deadline', 'Spring Deadline Month', 4, 'month'),
        ('application_deadlines', 'summer_deadline', 'Summer Deadline Month', 6, 'month'),
    ]
    
    # First, clear existing policies if they are in the wrong format or redundant
    # We use update_or_create to preserve existing IDs if possible
    for section, key, label, val, unit in policies:
        PolicySetting.objects.update_or_create(
            section=section,
            field_key=key,
            defaults={
                'field_label': label,
                'value': val,
                'unit': unit
            }
        )
        print(f"  [+] {section}.{key} -> {val} {unit}")
        
    print("Policy seeding complete.")

if __name__ == "__main__":
    seed_policies()
