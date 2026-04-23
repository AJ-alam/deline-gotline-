import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface FormFProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
}

const FormF: React.FC<FormFProps> = ({ profile, onBack, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // BUG 1: Connectivity & State
  const [formData, setFormData] = useState({
    orgName: '',
    supervisorTitle: '',
    studentName: '',
    placementStart: '',
    placementEnd: '',
    responsibilities: '',
    performance: '',
    signature: ''
  });

  // Auto-fill sync from profile
  useEffect(() => {
    if (profile) {
      setFormData(prev => ({
        ...prev,
        studentName: prev.studentName || profile.full_name || '',
        orgName: prev.orgName || profile.institute || profile.institution_name || ''
      }));
    }
  }, [profile]);

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const steps = [
    { id: 1, label: 'Employer & Info' },
    { id: 2, label: 'Performance & Roles' },
    { id: 3, label: 'Declaration' }
  ];

  // BUG 5: Validation
  // Validation Logic
  const canGoNext = () => {
    if (currentStep === 1) {
      return !!(formData.orgName && formData.supervisorTitle && formData.studentName && formData.placementStart);
    }
    if (currentStep === 2) {
      // Must provide sufficient detail
      return formData.responsibilities.length > 10 && formData.performance.length > 10;
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      if (currentStep === 1) {
        setError('Please fill in all required employer and student information.');
      } else if (currentStep === 2) {
        if (formData.responsibilities.length <= 10) setError('Please provide a more detailed description of roles/responsibilities.');
        else if (formData.performance.length <= 10) setError('Please provide a more detailed summary of work performance.');
      }
      return;
    }
    setError(null);
    if (currentStep < 3) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
    else onBack();
  };

  // BUG 4: Connected Submission Flow
  const handleSubmit = async () => {
    if (!formData.signature) {
      setError('Supervisor signature is required.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      const answers = [
        { field_label: 'Organization Name', answer_text: formData.orgName },
        { field_label: 'Supervisor Title', answer_text: formData.supervisorTitle },
        { field_label: 'Student Name', answer_text: formData.studentName },
        { field_label: 'Start Date', answer_text: formData.placementStart },
        { field_label: 'End Date', answer_text: formData.placementEnd },
        { field_label: 'Roles/Responsibilities', answer_text: formData.responsibilities },
        { field_label: 'Work Performance', answer_text: formData.performance },
        { field_label: 'Supervisor Signature', answer_text: formData.signature }
      ];

      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      await API.submitApplication({
        form_type: 'FormF',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit practicum report. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="wizard-root fade-in">
        <div className="wizard-shell" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div className="success-icon" style={{ margin: '0 auto 24px', width: '64px', height: '64px', border: '2px solid #1a4aaa', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a4aaa' }}>
            <Icons.Check />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Report Received</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            The supervisor's performance report has been submitted and linked to the student's file.
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
      title="Summer Student / Practicum Award"
      subtitle={currentStep === 1 
        ? "This form must be completed by the employer or supervisor to verify your placement." 
        : currentStep === 2
          ? "Detail the student's responsibilities and overall work performance."
          : "Finalize the supervisor's report."
      }
      steps={steps}
      currentStep={currentStep}
      onStepClick={setCurrentStep}
      onBack={handleBack}
      onNext={handleNext}
      isLastStep={currentStep === 3}
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
          <div className="policy-note info" style={{ marginBottom: 24, background: '#f0f4ff', borderLeftColor: '#1a4aaa', color: '#1a4aaa' }}>
            <strong>Supervisor Notice:</strong> This report is required to release the student's practicum or summer incentive award.
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '16px', marginBottom: '20px' }}>
            <div className="section-divider">Employer Information</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label className="field-label">Organization Name *</label>
                  <input className="field-input" value={formData.orgName} onChange={e => handleInputChange('orgName', e.target.value)} placeholder="e.g. DGG" />
                </div>
                <div>
                  <label className="field-label">Supervisor Title *</label>
                  <input className="field-input" value={formData.supervisorTitle} onChange={e => handleInputChange('supervisorTitle', e.target.value)} placeholder="e.g. Director of Operations" />
                </div>
            </div>
            
            <div className="section-divider">Student Information</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Student Full Name *</label>
                  <input className="field-input" value={formData.studentName} onChange={e => handleInputChange('studentName', e.target.value)} />
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px' }}>
                <div>
                  <label className="field-label">Placement Start Date *</label>
                  <input className="field-input" type="date" value={formData.placementStart} onChange={e => handleInputChange('placementStart', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Placement End Date *</label>
                  <input className="field-input" type="date" value={formData.placementEnd} onChange={e => handleInputChange('placementEnd', e.target.value)} />
                </div>
            </div>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '20px' }}>
              <label className="field-label">Roles and Responsibilities *</label>
              <textarea 
                className="field-input" 
                value={formData.responsibilities}
                onChange={e => handleInputChange('responsibilities', e.target.value)}
                placeholder="List the key tasks the student was responsible for..."
                style={{ width: '100%', height: '120px', padding: '12px', marginBottom: 20 }}
              />

              <label className="field-label">Work Performance Summary *</label>
              <textarea 
                className="field-input" 
                value={formData.performance}
                onChange={e => handleInputChange('performance', e.target.value)}
                placeholder="Describe the student's performance, attendance, and contributions..."
                style={{ width: '100%', height: '120px', padding: '12px' }}
              />
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
              <div className="decl-panel" style={{ background: '#f8fafc', marginBottom: '20px' }}>
                The employer confirms that the information provided is accurate and complete. Award is contingent on regular attendance and satisfactory performance.
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px' }}>
                <div>
                  <label className="field-label">Supervisor Digital Signature *</label>
                  <input className="field-input" value={formData.signature} onChange={e => handleInputChange('signature', e.target.value)} placeholder="Type supervisor's full legal name" />
                </div>
                <div>
                  <label className="field-label">Date</label>
                  <input className="field-input" disabled value={new Date().toLocaleDateString()} />
                </div>
              </div>
          </div>
        </div>
      )}
    </FormWizard>
  );
};

const Icons = {
  Check: () => (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
  )
};

export default FormF;
