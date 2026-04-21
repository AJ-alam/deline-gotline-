import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface FormGProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
}

const FormG: React.FC<FormGProps> = ({ profile, onBack, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // BUG 1: Connectivity & State
  const [formData, setFormData] = useState({
    fullName: '',
    dob: '',
    treatyNumber: '',
    sin: '',
    phone: '',
    email: '',
    city: '',
    province: '',
    postalCode: '',
    institution: '',
    program: '',
    completionDate: '',
    credential: 'Degree (Bachelors)',
    bankInstitution: '',
    bankTransit: '',
    bankAccount: '',
    releaseToOther: false,
    recipientName: '',
    recipientRelationship: '',
    signature: ''
  });

  const [selectedProof, setSelectedProof] = useState<File | null>(null);

  // Auto-fill sync from profile
  useEffect(() => {
    if (profile) {
      setFormData(prev => ({
        ...prev,
        fullName: prev.fullName || profile.full_name || '',
        email: prev.email || profile.email || '',
        phone: prev.phone || profile.phone || '',
        treatyNumber: prev.treatyNumber || profile.treaty_number || '',
        dob: prev.dob || profile.dob || '',
        city: prev.city || profile.town_city || '',
        province: prev.province || 'NT',
        postalCode: prev.postalCode || profile.postal_code || '',
        institution: prev.institution || profile.institute || profile.institution_name || '',
        program: prev.program || profile.program_credential || '',
        bankInstitution: prev.bankInstitution || profile.bank_name || '',
        bankTransit: prev.bankTransit || profile.transit_number || '',
        bankAccount: prev.bankAccount || profile.account_number || ''
      }));
    }
  }, [profile]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const steps = [
    { id: 1, label: 'Personal Info' },
    { id: 2, label: 'Graduation Details' },
    { id: 3, label: 'Banking & Release' },
    { id: 4, label: 'Declaration' }
  ];

  // BUG 5: Validation
  // Validation Logic
  const canGoNext = () => {
    if (currentStep === 1) {
      return !!(formData.fullName && formData.dob && formData.treatyNumber && formData.email && formData.city);
    }
    if (currentStep === 2) {
      return !!(formData.institution && formData.program && formData.completionDate && selectedProof);
    }
    if (currentStep === 3) {
      return !!(formData.bankInstitution && formData.bankTransit && formData.bankAccount);
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      if (currentStep === 1) {
        setError('Please fill in all required personal information (Name, DOB, Treaty #, and Address).');
      } else if (currentStep === 2) {
        if (!selectedProof) setError('Please upload your Proof of Completion / Certificate.');
        else setError('Please provide your Institution, Program name, and Completion Date.');
      } else if (currentStep === 3) {
        setError('Banking information (Institution, Transit, and Account #) is strictly required for this award.');
      }
      return;
    }
    setError(null);
    if (currentStep < 4) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
    else onBack();
  };

  // BUG 4: Connected Submission Flow
  const handleSubmit = async () => {
    if (!formData.signature) {
      setError('Student signature is required.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      const answers = [
        { field_label: 'Full Name', answer_text: formData.fullName },
        { field_label: 'Date of Birth', answer_text: formData.dob },
        { field_label: 'Treaty Number', answer_text: formData.treatyNumber },
        { field_label: 'SIN', answer_text: formData.sin },
        { field_label: 'Phone', answer_text: formData.phone },
        { field_label: 'Email', answer_text: formData.email },
        { field_label: 'City', answer_text: formData.city },
        { field_label: 'Province', answer_text: formData.province },
        { field_label: 'Postal Code', answer_text: formData.postalCode },
        { field_label: 'Institution', answer_text: formData.institution },
        { field_label: 'Program', answer_text: formData.program },
        { field_label: 'Completion Date', answer_text: formData.completionDate },
        { field_label: 'Credential', answer_text: formData.credential },
        { field_label: 'Bank Institution', answer_text: formData.bankInstitution },
        { field_label: 'Bank Transit', answer_text: formData.bankTransit },
        { field_label: 'Bank Account', answer_text: formData.bankAccount },
        { field_label: 'Recipient Name', answer_text: formData.releaseToOther ? formData.recipientName : 'Self' },
        { field_label: 'Recipient Relationship', answer_text: formData.releaseToOther ? formData.recipientRelationship : 'N/A' },
        { field_label: 'Student Signature', answer_text: formData.signature }
      ];

      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      if (selectedProof) {
        submissionData.append(`answers[${answers.length}]field_label`, 'Proof of Completion');
        submissionData.append(`answers[${answers.length}]answer_file`, selectedProof);
      }

      await API.submitApplication({
        form_type: 'FormG',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit graduation award application.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="wizard-root fade-in">
        <div className="wizard-shell" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div className="success-icon" style={{ margin: '0 auto 24px', width: '64px', height: '64px', border: '2px solid #38a169', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38a169' }}>
            <Icons.Check />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Application Received</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Congratulations on your graduation! Your award application is being processed. Payments are typically issued via direct deposit within 15 business days.
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
      title="Graduation Award"
      subtitle={currentStep === 1 
        ? "Verify your identity and mailing address for award processing." 
        : currentStep === 2
          ? "Tell us about your achievement and upload your proof of completion."
          : currentStep === 3
            ? "Provide your banking details for the award payment."
            : "Review and sign your application."
      }
      steps={steps}
      currentStep={currentStep}
      onStepClick={setCurrentStep}
      onBack={handleBack}
      onNext={handleNext}
      isLastStep={currentStep === 4}
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
            <div className="section-divider">Student Information</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label className="field-label">Full Legal Name *</label>
                  <input className="field-input" value={formData.fullName} onChange={e => handleInputChange('fullName', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Date of Birth *</label>
                  <input className="field-input" type="date" value={formData.dob} onChange={e => handleInputChange('dob', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Treaty / SCN # *</label>
                  <input className="field-input" value={formData.treatyNumber} onChange={e => handleInputChange('treatyNumber', e.target.value)} />
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Social Insurance #</label>
                  <input className="field-input" type="password" value={formData.sin} onChange={e => handleInputChange('sin', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Phone *</label>
                  <input className="field-input" value={formData.phone} onChange={e => handleInputChange('phone', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Email *</label>
                  <input className="field-input" type="email" value={formData.email} onChange={e => handleInputChange('email', e.target.value)} />
                </div>
            </div>
            
            <div className="section-divider">Current Mailing Address</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Town / City *</label>
                  <input className="field-input" value={formData.city} onChange={e => handleInputChange('city', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Province *</label>
                  <input className="field-input" value={formData.province} onChange={e => handleInputChange('province', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Postal Code *</label>
                  <input className="field-input" value={formData.postalCode} onChange={e => handleInputChange('postalCode', e.target.value)} />
                </div>
            </div>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '20px' }}>
            <div className="section-divider">Graduation Details</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                  <label className="field-label">Institution *</label>
                  <input className="field-input" value={formData.institution} onChange={e => handleInputChange('institution', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Program of Study *</label>
                  <input className="field-input" value={formData.program} onChange={e => handleInputChange('program', e.target.value)} />
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Completion Date *</label>
                  <input className="field-input" type="date" value={formData.completionDate} onChange={e => handleInputChange('completionDate', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Credential Earned *</label>
                  <select className="field-input" value={formData.credential} onChange={e => handleInputChange('credential', e.target.value)}>
                    <option>Certificate</option>
                    <option>Diploma</option>
                    <option>Degree (Bachelors)</option>
                    <option>Masters</option>
                    <option>Doctorate</option>
                  </select>
                </div>
            </div>
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
            <label className="field-label">Proof of Completion / Certificate *</label>
            <input type="file" onChange={e => setSelectedProof(e.target.files?.[0] || null)} />
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '20px' }}>
            <div className="section-divider">Banking Information</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Institution # *</label>
                  <input className="field-input" value={formData.bankInstitution} onChange={e => handleInputChange('bankInstitution', e.target.value)} maxLength={3} />
                </div>
                <div>
                  <label className="field-label">Transit # *</label>
                  <input className="field-input" value={formData.bankTransit} onChange={e => handleInputChange('bankTransit', e.target.value)} maxLength={5} />
                </div>
                <div>
                  <label className="field-label">Account # *</label>
                  <input className="field-input" value={formData.bankAccount} onChange={e => handleInputChange('bankAccount', e.target.value)} />
                </div>
            </div>
          </div>

          <div style={{ background: '#f8fafc', padding: '20px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', marginBottom: formData.releaseToOther ? '16px' : '0' }}>
              <input type="checkbox" checked={formData.releaseToOther} onChange={e => handleInputChange('releaseToOther', e.target.checked)} />
              <span style={{ fontSize: '13px', fontWeight: '600' }}>Payment goes to another person (Release of Funds)</span>
            </label>
            
            {formData.releaseToOther && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label className="field-label">Recipient Name *</label>
                  <input className="field-input" value={formData.recipientName} onChange={e => handleInputChange('recipientName', e.target.value)} />
                </div>
                <div>
                  <label className="field-label">Relationship *</label>
                  <input className="field-input" value={formData.recipientRelationship} onChange={e => handleInputChange('recipientRelationship', e.target.value)} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {currentStep === 4 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
            <div className="decl-panel" style={{ marginBottom: '20px' }}>
              I declare that the information provided is true and complete. I understand that any false information will result in the suspension of my graduation award.
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px' }}>
                <div>
                  <label className="field-label">Student Digital Signature *</label>
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

export default FormG;
