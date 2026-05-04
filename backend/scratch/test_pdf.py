import os
import sys
import django

# Setup Django
sys.path.append('c:/Users/Alam Jabbar/Downloads/projects/deline-gotline-/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from forms.models import Form
from api.utils.pdf_generator import FormPDFGenerator

def test_pdf():
    form = Form.objects.first()
    if not form:
        print("No form found")
        return
    
    try:
        pdf = FormPDFGenerator.generate_form_template(form)
        print(f"PDF generated successfully, size: {len(pdf)} bytes")
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf()
