import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface FormHProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
}

const FormH: React.FC<FormHProps> = ({ profile, onBack, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // BUG 1: Connectivity & State
  const [formData, setFormData] = useState({
    studentName: '',
    studentId: '',
    institution: '',
    semester: 'Fall',
    year: '',
    appealReason: '',
    policyReference: '',
    signature: ''
  });

  const [selectedEvidence, setSelectedEvidence] = useState<File[]>([]);

  // Auto-fill sync from profile
  useEffect(() => {
    if (profile) {
      setFormData(prev => ({
        ...prev,
        studentName: prev.studentName || profile.full_name || '',
        studentId: prev.studentId || profile.beneficiary_number || '',
        institution: prev.institution || profile.institute || profile.institution_name || '',
        year: prev.year || String(new Date().getFullYear())
      }));
    }
  }, [profile]);

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const steps = [
    { id: 1, label: 'Appeal Context' },
    { id: 2, label: 'Detailed Reason' },
    { id: 3, label: 'Support & Submission' }
  ];

  // BUG 5: Validation
  // Validation Logic
  const canGoNext = () => {
    if (currentStep === 1) {
      return !!(formData.studentName && formData.institution && formData.semester && formData.year);
    }
    if (currentStep === 2) {
      return formData.appealReason.length > 20;
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      if (currentStep === 1) {
        setError('Please fill in all required student and academic information (Institution, Semester, Year).');
      } else if (currentStep === 2) {
        setError('Please provide a detailed explanation for your appeal (minimum 20 characters).');
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
      setError('Electronic signature is required.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      const answers = [
        { field_label: 'Student Name', answer_text: formData.studentName },
        { field_label: 'Student ID', answer_text: formData.studentId },
        { field_label: 'Institution', answer_text: formData.institution },
        { field_label: 'Semester', answer_text: formData.semester },
        { field_label: 'Academic Year', answer_text: formData.year },
        { field_label: 'Reason for Appeal', answer_text: formData.appealReason },
        { field_label: 'Policy Reference', answer_text: formData.policyReference },
        { field_label: 'Electronic Signature', answer_text: formData.signature }
      ];

      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      selectedEvidence.forEach((file, index) => {
        submissionData.append(`answers[${answers.length + index}]field_label`, `Evidence Attachment ${index + 1}`);
        submissionData.append(`answers[${answers.length + index}]answer_file`, file);
      });

      await API.submitApplication({
        form_type: 'FormH',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to file appeal. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="wizard-root fade-in">
        <div className="wizard-shell" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div className="success-icon" style={{ margin: '0 auto 24px', width: '64px', height: '64px', border: '2px solid #e65100', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#e65100' }}>
            <Icons.Check />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Appeal Filed</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your appeal has been forwarded to the Education Director and Appeal Committee. Decisions are typically rendered within 30 days of receipt.
          </p>
          <button className="wizard-btn-next" style={{ margin: '0 auto', background: '#e65100' }} onClick={() => onComplete()}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <FormWizard
      title="Appeal Request"
      subtitle={currentStep === 1 
        ? "Clearly identify the decision you are appealing and the relevant academic context." 
        : currentStep === 2
          ? "Explain your situation and why you believe the original decision should be reconsidered."
          : "Attach evidence and submit your request for committee review."
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
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '20px' }}>
            <div className="section-divider">Student & Academic Context</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label className="field-label">Student Name *</label>
                  <input className="field-input" value={formData.studentName} onChange={e => handleInputChange('studentName', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Student ID *</label>
                  <input className="field-input" value={formData.studentId} onChange={e => handleInputChange('studentId', e.target.value)} />
                </div>
            </div>
            <div style={{ marginBottom: '12px' }}>
                <label className="field-label">Educational Institution *</label>
                <input className="field-input" value={formData.institution} onChange={e => handleInputChange('institution', e.target.value)} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Semester *</label>
                  <select className="field-input" value={formData.semester} onChange={e => handleInputChange('semester', e.target.value)}>
                    <option>Fall</option>
                    <option>Winter</option>
                    <option>Spring/Summer</option>
                  </select>
                </div>
                <div>
                  <label className="field-label">Academic Year *</label>
                  <input className="field-input" value={formData.year} onChange={e => handleInputChange('year', e.target.value)} placeholder="e.g. 2025-2026" />
                </div>
            </div>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '20px' }}>
            <label className="field-label">Detailed Reason for Appeal *</label>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '10px' }}>
                Explain why you believe the original decision was incorrect and what outcome you are requesting.
            </div>
            <textarea 
              className="field-input" 
              value={formData.appealReason}
              onChange={e => handleInputChange('appealReason', e.target.value)}
              placeholder="Provide a thorough explanation..."
              style={{ width: '100%', height: '160px', padding: '12px', marginBottom: '20px' }}
            />

            <label className="field-label">Policy Reference (Optional)</label>
            <input 
              className="field-input" 
              value={formData.policyReference}
              onChange={e => handleInputChange('policyReference', e.target.value)}
              placeholder="e.g. Section 4.2 - Eligibility requirements"
            />
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '20px' }}>
            <label className="field-label">Supporting Evidence (Transcripts, Letters, etc.)</label>
            <input type="file" multiple onChange={e => setSelectedEvidence(Array.from(e.target.files || []))} />
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
            <div className="decl-panel" style={{ marginBottom: '20px' }}>
              I confirm that the information provided is accurate and complete. I understand that appeal decisions are discretionary and subject to the DGG Education Policy.
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px' }}>
                <div>
                  <label className="field-label">Electronic Signature *</label>
                  <input className="field-input" value={formData.signature} onChange={e => handleInputChange('signature', e.target.value)} placeholder="Type name to sign" />
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

export default FormH;
