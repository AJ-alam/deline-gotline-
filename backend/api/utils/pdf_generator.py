"""
PDF Generator for Form Templates
Generates downloadable PDF forms for students to fill out manually
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime


class FormPDFGenerator:
    """Generate PDF templates for forms"""
    
    @staticmethod
    def generate_form_template(form):
        """
        Generate a blank PDF template for a form
        
        Args:
            form: Form model instance
            
        Returns:
            BytesIO: PDF file buffer
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                               rightMargin=0.75*inch, leftMargin=0.75*inch,
                               topMargin=1*inch, bottomMargin=0.75*inch)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a365d'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        )
        
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=4,
            fontName='Helvetica-Bold'
        )
        
        instruction_style = ParagraphStyle(
            'Instruction',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#718096'),
            spaceAfter=8,
            fontName='Helvetica-Oblique'
        )
        
        # Add header
        elements.append(Paragraph("Délı̨nę Got'ı̨nę Government", title_style))
        elements.append(Paragraph("Education & Training Department", styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Add form title
        elements.append(Paragraph(form.title, heading_style))
        
        # Add description if available
        if form.description:
            elements.append(Paragraph(form.description, styles['Normal']))
            elements.append(Spacer(1, 0.2*inch))
        
        # Add instructions
        elements.append(Paragraph(
            "Instructions: Please complete all required fields marked with (*). "
            "Print clearly in black or blue ink. Attach all required documents.",
            instruction_style
        ))
        elements.append(Spacer(1, 0.2*inch))
        
        # Add student information section
        elements.append(Paragraph("Student Information", heading_style))
        
        student_fields = [
            ("Full Name*:", "_" * 60),
            ("Email Address*:", "_" * 60),
            ("Phone Number*:", "_" * 60),
            ("Beneficiary Number*:", "_" * 60),
            ("Date of Birth:", "_" * 60),
            ("Mailing Address:", "_" * 60),
        ]
        
        for label, line in student_fields:
            elements.append(Paragraph(label, label_style))
            elements.append(Paragraph(line, styles['Normal']))
            elements.append(Spacer(1, 0.15*inch))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Add form-specific fields
        if form.fields.exists():
            elements.append(Paragraph("Application Details", heading_style))
            
            for field in form.fields.all().order_by('order'):
                # Add field label
                required_marker = "*" if field.is_required else ""
                field_label = f"{field.label}{required_marker}:"
                elements.append(Paragraph(field_label, label_style))
                
                # Add help text if available
                if field.help_text:
                    elements.append(Paragraph(field.help_text, instruction_style))
                
                # Add appropriate input space based on field type
                if field.field_type == 'textarea':
                    # Multiple lines for textarea
                    for _ in range(4):
                        elements.append(Paragraph("_" * 90, styles['Normal']))
                        elements.append(Spacer(1, 0.1*inch))
                elif field.field_type == 'checkbox':
                    # Checkbox options
                    elements.append(Paragraph("☐ Yes    ☐ No", styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
                elif field.field_type == 'radio' and field.options:
                    # Radio button options
                    options_text = "    ".join([f"☐ {opt}" for opt in field.options])
                    elements.append(Paragraph(options_text, styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
                elif field.field_type == 'dropdown' and field.options:
                    # Dropdown options listed
                    options_text = "Options: " + ", ".join(field.options)
                    elements.append(Paragraph(options_text, instruction_style))
                    elements.append(Paragraph("_" * 60, styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
                elif field.field_type == 'file':
                    # File upload instruction
                    elements.append(Paragraph("☐ Document attached (please label clearly)", styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
                else:
                    # Single line for text, number, email, date
                    elements.append(Paragraph("_" * 60, styles['Normal']))
                    elements.append(Spacer(1, 0.1*inch))
                
                elements.append(Spacer(1, 0.15*inch))
        
        # Add signature section
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Declaration and Signature", heading_style))
        elements.append(Paragraph(
            "I declare that the information provided in this application is true and complete to the best of my knowledge. "
            "I understand that providing false information may result in the rejection of my application or termination of funding.",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.3*inch))
        
        # Signature table
        sig_data = [
            ["Applicant Signature:", "_" * 40, "Date:", "_" * 20],
        ]
        sig_table = Table(sig_data, colWidths=[1.5*inch, 3*inch, 0.6*inch, 1.4*inch])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        elements.append(sig_table)
        
        # Add footer
        elements.append(Spacer(1, 0.4*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y')} | "
            "For assistance, contact the Education & Training Department",
            footer_style
        ))
        
        # Build PDF
        doc.build(elements)
        
        # Get the value of the BytesIO buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf
    
    @staticmethod
    def generate_filled_form(submission):
        """
        Generate a PDF with pre-filled submission data
        
        Args:
            submission: FormSubmission model instance
            
        Returns:
            BytesIO: PDF file buffer
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                               rightMargin=0.75*inch, leftMargin=0.75*inch,
                               topMargin=1*inch, bottomMargin=0.75*inch)
        
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a365d'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        )
        
        # Add header
        elements.append(Paragraph("Délı̨nę Got'ı̨nę Government", title_style))
        elements.append(Paragraph("Education & Training Department", styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Add form title
        elements.append(Paragraph(submission.form.title, heading_style))
        elements.append(Paragraph(f"Submission ID: FS-{submission.id}", styles['Normal']))
        elements.append(Paragraph(
            f"Submitted: {submission.submitted_at.strftime('%B %d, %Y at %I:%M %p')}", 
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.2*inch))
        
        # Student information
        if submission.student:
            elements.append(Paragraph("Student Information", heading_style))
            student = submission.student
            profile = student.profile if hasattr(student, 'profile') else None
            
            student_data = [
                ["Full Name:", student.full_name or "—"],
                ["Email:", student.email or "—"],
                ["Phone:", profile.phone_number if profile else "—"],
                ["Beneficiary #:", profile.beneficiary_number if profile else "—"],
            ]
            
            student_table = Table(student_data, colWidths=[2*inch, 4.5*inch])
            student_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(student_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Submission answers
        elements.append(Paragraph("Application Responses", heading_style))
        
        for answer in submission.answers.all().order_by('field__order'):
            field_label = answer.field.label if answer.field else "Response"
            elements.append(Paragraph(f"<b>{field_label}:</b>", styles['Normal']))
            
            answer_text = answer.answer_text or "—"
            if answer.answer_file:
                answer_text += f" [File: {answer.answer_file.name}]"
            
            elements.append(Paragraph(answer_text, styles['Normal']))
            elements.append(Spacer(1, 0.15*inch))
        
        # Status information
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("Status Information", heading_style))
        
        status_data = [
            ["Status:", submission.get_status_display()],
            ["Amount:", f"${submission.amount}" if submission.amount else "—"],
        ]
        
        if submission.decided_by:
            status_data.append(["Decided By:", submission.decided_by.full_name])
        if submission.decided_at:
            status_data.append(["Decision Date:", submission.decided_at.strftime('%B %d, %Y')])
        
        status_table = Table(status_data, colWidths=[2*inch, 4.5*inch])
        status_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(status_table)
        
        # Build PDF
        doc.build(elements)
        
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf
