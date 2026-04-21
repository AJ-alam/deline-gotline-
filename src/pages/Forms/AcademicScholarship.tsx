import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface AcademicScholarshipProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
}

const AcademicScholarship: React.FC<AcademicScholarshipProps> = ({ profile, onBack, onComplete }) => {
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
    gpaAchieved: '',
    transcriptSubmitted: 'No',
    signature: '',
    declarationConfirmed: false
  });

  const [selectedTranscript, setSelectedTranscript] = useState<File | null>(null);

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

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const steps = [
    { id: 1, label: 'Program Info' },
    { id: 2, label: 'Achievements' },
    { id: 3, label: 'Declaration' }
  ];

  // BUG 5: Validation
  // Validation Logic
  const canGoNext = () => {
    if (currentStep === 1) {
      return !!(formData.studentName && formData.institution && formData.semester && formData.year);
    }
    if (currentStep === 2) {
      return !!(formData.gpaAchieved && (formData.transcriptSubmitted === 'Yes' || selectedTranscript));
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      if (currentStep === 1) {
        setError('Please fill in all required program information (Institution, Semester, and Year).');
      } else if (currentStep === 2) {
        if (!formData.gpaAchieved) setError('Please provide your GPA or Final Grade percentage.');
        else if (formData.transcriptSubmitted === 'No' && !selectedTranscript) setError('Please upload your official transcript.');
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
    if (!formData.signature || !formData.declarationConfirmed) {
      setError('Please sign and confirm the declaration.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      const answers = [
        { field_label: 'Student Name', answer_text: formData.studentName },
        { field_label: 'Student ID', answer_text: formData.studentId },
        { field_label: 'Educational Institution', answer_text: formData.institution },
        { field_label: 'Qualifying Semester', answer_text: formData.semester },
        { field_label: 'Academic Year', answer_text: formData.year },
        { field_label: 'GPA Achieved', answer_text: formData.gpaAchieved },
        { field_label: 'Transcript Status', answer_text: formData.transcriptSubmitted },
        { field_label: 'Digital Signature', answer_text: formData.signature }
      ];

      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      if (selectedTranscript) {
        submissionData.append(`answers[${answers.length}]field_label`, 'Official Transcript');
        submissionData.append(`answers[${answers.length}]answer_file`, selectedTranscript);
      }

      await API.submitApplication({
        form_type: 'Scholarship',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit scholarship application. Please try again.');
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
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Scholarship Application Submitted</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your achievement scholarship application has been received. Our team will verify your transcripts against the DGG Education Policy.
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
      title="Academic Achievement Scholarship"
      subtitle={currentStep === 1 
        ? "Confirm the qualifying semester and your educational institution." 
        : currentStep === 2
          ? "Report your academic achievements and provide supporting documentation."
          : "Finalize your scholarship application."
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
          <div className="policy-note info" style={{ marginBottom: 24, padding: '12px', background: '#f0f4ff', borderRadius: '4px', fontSize: '12px', color: '#1a44aa' }}>
            <strong>Award Criteria:</strong> GPA &ge; 80% = $1,000 | GPA 70\u201379.99% = $500.
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                   <label className="field-label">Student Name *</label>
                   <input className="field-input" value={formData.studentName} onChange={e => handleInputChange('studentName', e.target.value)} />
                </div>
                <div>
                   <label className="field-label">Student ID / Beneficiary #</label>
                   <input className="field-input" value={formData.studentId} onChange={e => handleInputChange('studentId', e.target.value)} />
                </div>
             </div>
             <div style={{ marginBottom: '12px' }}>
                <label className="field-label">Educational Institution *</label>
                <input className="field-input" value={formData.institution} onChange={e => handleInputChange('institution', e.target.value)} placeholder="e.g. University of Calgary" />
             </div>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                   <label className="field-label">Qualifying Semester *</label>
                   <select className="field-input" value={formData.semester} onChange={e => handleInputChange('semester', e.target.value)}>
                      <option>Fall</option>
                      <option>Winter</option>
                      <option>Spring/Summer</option>
                   </select>
                </div>
                <div>
                   <label className="field-label">Academic Year *</label>
                   <input className="field-input" value={formData.year} onChange={e => handleInputChange('year', e.target.value)} placeholder="e.g. 2025" />
                </div>
             </div>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px', marginBottom: '14px' }}>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                   <label className="field-label">GPA Achieved / Final Grade % *</label>
                   <input className="field-input" value={formData.gpaAchieved} onChange={e => handleInputChange('gpaAchieved', e.target.value)} placeholder="e.g. 85%" />
                </div>
                <div>
                   <label className="field-label">Transcripts Status *</label>
                   <select className="field-input" value={formData.transcriptSubmitted} onChange={e => handleInputChange('transcriptSubmitted', e.target.value)}>
                      <option value="No">Uploading now</option>
                      <option value="Yes">Already submitted earlier</option>
                   </select>
                </div>
             </div>
          </div>

          {formData.transcriptSubmitted === 'No' && (
             <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
                <label className="field-label">Official Transcript / Grades Letter *</label>
                <div style={{ fontSize: '10px', color: '#666', marginBottom: '8px' }}>Must show full name and institution name.</div>
                <input type="file" onChange={e => setSelectedTranscript(e.target.files?.[0] || null)} />
             </div>
          )}
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
             <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '4px', fontSize: '11px', lineHeight: '1.6', color: '#444', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
                 I confirm that the information provided is accurate. I understand that eligibility for the scholarship is subject to enrollment verification and meeting the DGG Education Policy requirements.
             </div>
             
             <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', marginBottom: '16px', cursor: 'pointer' }}>
                <input type="checkbox" checked={formData.declarationConfirmed} onChange={e => handleInputChange('declarationConfirmed', e.target.checked)} />
                <span>I confirm the declaration <span style={{ color: '#cc0000' }}>*</span></span>
             </label>

             <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px' }}>
                <div>
                   <label className="field-label">Digital Signature *</label>
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

export default AcademicScholarship;
