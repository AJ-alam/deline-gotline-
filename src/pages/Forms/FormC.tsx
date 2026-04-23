import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface FormCProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
  onUpdateInfo?: () => void;
}

const FormC: React.FC<FormCProps> = ({ profile, onBack, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Form State for connectivity and Validation
  const [formData, setFormData] = useState({
    fullName: '',
    beneficiaryNumber: '',
    email: '',
    phone: '',
    institution: '',
    program: '',
    courseLoad: 'Full-Time',
    dependents: '0',
    signature: '',
    declarationConfirmed: false
  });

  const [selectedFiles, setSelectedFiles] = useState<Record<string, File | null>>({
    transcripts: null,
    enrollment: null
  });

  // Fix: Only auto-fill if the fields are currently empty to avoid overwriting user input during polling
  useEffect(() => {
    if (profile) {
      setFormData(prev => ({
        ...prev,
        fullName: prev.fullName || profile.full_name || '',
        beneficiaryNumber: prev.beneficiaryNumber || profile.beneficiary_number || '',
        email: prev.email || profile.email || '',
        phone: prev.phone || profile.phone || '',
        institution: prev.institution || profile.institution_name || '',
        program: prev.program || profile.program_credential || '',
        courseLoad: prev.courseLoad || profile.enrollment_status || 'Full-Time',
        dependents: prev.dependents || String(profile.num_dependents || '0')
      }));
    }
  }, [profile]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleFileChange = (field: string, file: File | null) => {
    setSelectedFiles(prev => ({ ...prev, [field]: file }));
  };

  const steps = [
    { id: 1, label: 'Information Review' },
    { id: 2, label: 'Documents & Declaration' }
  ];

  const canSubmit = () => {
    return (
      formData.declarationConfirmed && 
      formData.signature.trim() !== '' && 
      selectedFiles.transcripts && 
      selectedFiles.enrollment
    );
  };

  // BUG 4: Connected Submission Flow
  const handleSubmit = async () => {
    if (!canSubmit()) {
      setError('Please complete the declaration and upload all required documents.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      // Map JSON fields
      const answers = [
        { field_label: 'Full Name', answer_text: formData.fullName },
        { field_label: 'Beneficiary Number', answer_text: formData.beneficiaryNumber },
        { field_label: 'Institution', answer_text: formData.institution },
        { field_label: 'Program', answer_text: formData.program },
        { field_label: 'Course Load', answer_text: formData.courseLoad },
        { field_label: 'Dependents', answer_text: formData.dependents },
        { field_label: 'Signature', answer_text: formData.signature },
        { field_label: 'Declaration Confirmed', answer_text: 'Yes' },
        { field_label: 'Transcripts Uploaded', answer_text: 'File' },
        { field_label: 'Enrollment Proof Uploaded', answer_text: 'File' }
      ];

      // Append in indexed format for backend nested serializer
      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      // Special handling for files
      if (selectedFiles.transcripts) {
        submissionData.append(`answers[${answers.length - 2}]answer_file`, selectedFiles.transcripts);
      }
      if (selectedFiles.enrollment) {
        submissionData.append(`answers[${answers.length - 1}]answer_file`, selectedFiles.enrollment);
      }

      await API.submitApplication({
        form_type: 'FormC',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit renewal. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const canGoNext = () => {
    if (currentStep === 1) {
      return formData.fullName && formData.institution && formData.program;
    }
    if (currentStep === 2) {
      return formData.signature && selectedFiles.transcripts && selectedFiles.enrollment;
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      setError(currentStep === 1 
        ? 'Please fill in all required student and program information.' 
        : 'Please sign and upload your transcripts and proof of enrollment.'
      );
      return;
    }
    setError(null);
    if (currentStep < 2) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
    else onBack();
  };

  if (isSubmitted) {
    return (
      <div className="wizard-root fade-in">
        <div className="wizard-shell" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div className="success-icon" style={{ margin: '0 auto 24px', width: '64px', height: '64px', border: '2px solid #38a169', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38a169' }}>
            <Icons.Check />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Renewal Submitted</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your renewal has been received. We will verify your transcripts and next-semester enrollment shortly.
          </p>
          <button className="wizard-btn-next" style={{ margin: '0 auto' }} onClick={() => onComplete()}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <FormWizard
      title="Continuing Student"
      subtitle={currentStep === 1
        ? "Review your current enrollment on file and confirm accuracy."
        : "Upload required semester records and sign the declaration."
      }
      steps={steps}
      currentStep={currentStep}
      onStepClick={setCurrentStep}
      onBack={handleBack}
      onNext={handleNext}
      isLastStep={currentStep === 2}
      nextDisabled={!canGoNext() || isLoading}
      onSubmit={handleSubmit}
    >
      {error && (
        <div className="alert-box error fade-in" style={{ background: '#fff2f2', border: '1px solid #ffcccc', color: '#cc0000', padding: '12px 16px', borderRadius: '6px', marginBottom: '20px', fontSize: '13px' }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {currentStep === 1 && (
        <div className="fade-in">
          <div style={{ background: '#f0f4ff', border: '1px solid #c0ccf0', borderLeft: '3px solid #1a4aaa', borderRadius: '3px', padding: '10px 12px', fontSize: '10px', color: '#1a4aaa', lineHeight: '1.6', marginBottom: '12px' }}>
            <strong>Submit each semester to renew your funding.</strong> Your initial application must be on file. DGG will send enrollment verification to your registrar after receiving this form.
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', marginBottom: '14px', padding: '16px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
              1. Review Your Information</div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', background: '#f9f9f9', padding: '12px', borderRadius: '4px', border: '1px solid #eee', marginBottom: '20px' }}>
              <div>
                <label className="field-label" style={{ fontSize: '9px' }}>Full Name *</label>
                <input 
                  className="field-input" 
                  value={formData.fullName} 
                  onChange={(e) => handleInputChange('fullName', e.target.value)}
                  placeholder="Legal Name"
                  style={{ fontSize: '11px', background: '#fff' }}
                />
              </div>
              <div>
                <label className="field-label" style={{ fontSize: '9px' }}>Beneficiary # *</label>
                <input 
                  className="field-input" 
                  value={formData.beneficiaryNumber} 
                  onChange={(e) => handleInputChange('beneficiaryNumber', e.target.value)}
                  placeholder="DGG-XXXXX"
                  style={{ fontSize: '11px', background: '#fff' }}
                />
              </div>
              <div>
                <label className="field-label" style={{ fontSize: '9px' }}>Contact Email *</label>
                <input 
                  className="field-input" 
                  value={formData.email} 
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  placeholder="email@example.com"
                  style={{ fontSize: '11px', background: '#fff' }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr 1fr', gap: '12px' }}>
              <div>
                <label className="field-label">Institution *</label>
                <input 
                  className="field-input" 
                  value={formData.institution} 
                  onChange={(e) => handleInputChange('institution', e.target.value)}
                  placeholder="University Name"
                  required
                />
              </div>
              <div>
                <label className="field-label">Program *</label>
                <input 
                  className="field-input" 
                  value={formData.program} 
                  onChange={(e) => handleInputChange('program', e.target.value)}
                  placeholder="Degree Program"
                  required
                />
              </div>
              <div>
                <label className="field-label">Course Load *</label>
                <select 
                  className="field-input" 
                  value={formData.courseLoad}
                  onChange={(e) => handleInputChange('courseLoad', e.target.value)}
                  style={{ height: '36px', width: '100%' }}
                >
                  <option>Full-Time</option>
                  <option>Part-Time</option>
                </select>
              </div>
              <div>
                <label className="field-label">Dependents *</label>
                <input 
                  className="field-input" 
                  type="number"
                  value={formData.dependents} 
                  onChange={(e) => handleInputChange('dependents', e.target.value)}
                  min="0"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', marginBottom: '14px', padding: '16px' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
              2. Upload Required Documents</div>

            <div style={{ display: 'flex', gap: '20px' }}>
              <div style={{ flex: 1, background: '#fafafa', padding: '14px', border: '1px solid #ddd', borderRadius: '3px' }}>
                <div style={{ fontSize: '10.5px', fontWeight: '600', color: '#111', marginBottom: '4px' }}>Latest Transcripts *</div>
                <input type="file" onChange={(e) => handleFileChange('transcripts', e.target.files?.[0] || null)} style={{ fontSize: '10px' }} />
              </div>
              <div style={{ flex: 1, background: '#fafafa', padding: '14px', border: '1px solid #ddd', borderRadius: '3px' }}>
                <div style={{ fontSize: '10.5px', fontWeight: '600', color: '#111', marginBottom: '4px' }}>Enrollment Confirmation *</div>
                <input type="file" onChange={(e) => handleFileChange('enrollment', e.target.files?.[0] || null)} style={{ fontSize: '10px' }} />
              </div>
            </div>
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '16px' }}>
             <div style={{ background: '#f9f9f9', border: '1px solid #e0e0e0', borderRadius: '3px', padding: '12px 14px', fontSize: '10.5px', color: '#555', lineHeight: '1.7', marginBottom: '10px' }}>
                I declare that all information given on this application is true and complete.
             </div>
             <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: '#333', cursor: 'pointer', marginBottom: '12px' }}>
                <input 
                  type="checkbox" 
                  checked={formData.declarationConfirmed}
                  onChange={(e) => handleInputChange('declarationConfirmed', e.target.checked)}
                />
                <span>Confirm declaration <span style={{ color: '#cc0000' }}>*</span></span>
             </label>
             <div>
                <label className="field-label">Student Signature (Full Name) *</label>
                <input 
                  className="field-input" 
                  value={formData.signature}
                  onChange={(e) => handleInputChange('signature', e.target.value)}
                  placeholder="Type your name to sign"
                />
             </div>
          </div>
        </div>
      )}
    </FormWizard>
  );
};

const Icons = {
  Check: () => (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
  )
};

export default FormC;
