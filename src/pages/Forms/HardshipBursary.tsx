import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface HardshipBursaryProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
}

const HardshipBursary: React.FC<HardshipBursaryProps> = ({ profile, onBack, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // BUG 1: Connectivity & State
  const [formData, setFormData] = useState({
    studentName: '',
    studentId: '',
    institution: '',
    hardshipDescription: '',
    othersAttempted: '',
    signature: '',
    isCompliant: true
  });

  const [expenses, setExpenses] = useState([{ id: Date.now(), purpose: '', amount: 0 }]);

  // Fix: Only auto-fill if the fields are currently empty to avoid overwriting user input during polling
  useEffect(() => {
    if (profile) {
      setFormData(prev => ({
        ...prev,
        studentName: prev.studentName || profile.full_name || '',
        studentId: prev.studentId || profile.beneficiary_number || ''
      }));
    }
  }, [profile]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const addExpense = () => {
    setExpenses([...expenses, { id: Date.now(), purpose: '', amount: 0 }]);
  };

  const removeExpense = (id: number) => {
    if (expenses.length > 1) setExpenses(expenses.filter(e => e.id !== id));
  };

  const updateExpense = (id: number, field: string, value: string | number) => {
    setExpenses(expenses.map(e => e.id === id ? { ...e, [field]: value } : e));
  };

  const totalAmount = expenses.reduce((sum, e) => sum + (Number(e.amount) || 0), 0);

  const steps = [
    { id: 1, label: 'Student Info' },
    { id: 2, label: 'Emergency Case' },
    { id: 3, label: 'Fund Breakdown' },
    { id: 4, label: 'Declaration' }
  ];

  // BUG 5: Validation
  // Validation Logic
  const canGoNext = () => {
    if (currentStep === 1) {
      return !!(formData.studentName && formData.institution && formData.isCompliant);
    }
    if (currentStep === 2) {
      return formData.hardshipDescription.length > 20 && formData.othersAttempted.length > 10;
    }
    if (currentStep === 3) {
      return totalAmount > 0 && totalAmount <= 500 && expenses.every(e => e.purpose && e.amount > 0);
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      if (currentStep === 1) {
        setError('Please fill in student details and confirm reporting compliance.');
      } else if (currentStep === 2) {
        if (formData.hardshipDescription.length <= 20) setError('Please provide a more detailed description of the hardship (min 20 chars).');
        else if (formData.othersAttempted.length <= 10) setError('Please provide more detail on other supports you have attempted.');
      } else if (currentStep === 3) {
        if (totalAmount <= 0) setError('Please list at least one emergency expense.');
        else if (totalAmount > 500) setError('The Hardship Bursary has a strict limit of $500.00.');
        else setError('Please ensure all expense rows have both a purpose and a valid amount.');
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
        { field_label: 'Student Name', answer_text: formData.studentName },
        { field_label: 'Student ID', answer_text: formData.studentId },
        { field_label: 'Institution', answer_text: formData.institution },
        { field_label: 'Hardship Description', answer_text: formData.hardshipDescription },
        { field_label: 'Others Attempted', answer_text: formData.othersAttempted },
        { field_label: 'Total Requested', answer_text: `$${totalAmount.toFixed(2)}` },
        { field_label: 'Expense Breakdown', answer_text: JSON.stringify(expenses.map(e => ({ purpose: e.purpose, amount: e.amount }))) },
        { field_label: 'Digital Signature', answer_text: formData.signature }
      ];

      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      await API.submitApplication({
        form_type: 'Hardship',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit hardship application.');
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
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Emergency Request Logged</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your hardship application is marked for priority review. An education officer will contact you within 48 hours.
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
      title="Emergency Hardship Bursary (Last Resort)"
      subtitle={currentStep === 1 
        ? "Verify your current academic status and identity." 
        : currentStep === 2
          ? "Describe the emergency and explain what other supports you have attempted."
          : currentStep === 3
            ? "Provide a breakdown of the immediate financial need ($500 limit)."
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
          <div className="policy-note warn" style={{ marginBottom: 24, padding: '12px', background: '#fffbeb', borderRadius: '4px', borderLeft: '4px solid #f59e0b', color: '#92400e' }}>
            <strong>Last Resort Notice:</strong> Hardship support is for short-term emergencies only.
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                   <label className="field-label">Student Full Name *</label>
                   <input className="field-input" value={formData.studentName} onChange={e => handleInputChange('studentName', e.target.value)} />
                </div>
                <div>
                   <label className="field-label">Student ID / Beneficiary #</label>
                   <input className="field-input" value={formData.studentId} onChange={e => handleInputChange('studentId', e.target.value)} />
                </div>
             </div>
             <div style={{ marginBottom: '16px' }}>
                <label className="field-label">Educational Institution *</label>
                <input className="field-input" value={formData.institution} onChange={e => handleInputChange('institution', e.target.value)} placeholder="e.g. University of Calgary" />
             </div>
             <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px' }}>
                <input type="checkbox" checked={formData.isCompliant} onChange={e => handleInputChange('isCompliant', e.target.checked)} />
                <span>I am currently active in my program and compliant with reporting.</span>
             </label>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
             <label className="field-label">Nature of Hardship *</label>
             <textarea 
               className="field-input" 
               value={formData.hardshipDescription}
               onChange={e => handleInputChange('hardshipDescription', e.target.value)}
               placeholder="What happened, when, and immediate impact..."
               style={{ width: '100%', height: '120px', padding: '12px', marginBottom: 20 }}
             />

             <label className="field-label">Other Supports Attempted *</label>
             <div style={{ fontSize: '11px', color: '#666', marginBottom: '8px' }}>
                e.g. food banks, family support, campus emergency funds.
             </div>
             <textarea 
               className="field-input" 
               value={formData.othersAttempted}
               onChange={e => handleInputChange('othersAttempted', e.target.value)}
               placeholder="How have you tried to resolve this already?"
               style={{ width: '100%', height: '100px', padding: '12px' }}
             />
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
            <div className="section-divider">Fund Breakdown (Max $500)</div>
            <table style={{ width: '100%', marginBottom: '16px' }}>
               <thead>
                  <tr style={{ textAlign: 'left', fontSize: '11px', color: '#666' }}>
                     <th>Expense / Purpose</th>
                     <th style={{ width: '120px' }}>Amount ($)</th>
                     <th style={{ width: '40px' }}></th>
                  </tr>
               </thead>
               <tbody>
                  {expenses.map((exp) => (
                    <tr key={exp.id}>
                      <td style={{ padding: '4px' }}>
                        <input className="field-input" value={exp.purpose} onChange={e => updateExpense(exp.id, 'purpose', e.target.value)} placeholder="e.g. Utilities" />
                      </td>
                      <td style={{ padding: '4px' }}>
                        <input className="field-input" type="number" value={exp.amount || ''} onChange={e => updateExpense(exp.id, 'amount', e.target.value)} placeholder="0.00" />
                      </td>
                      <td>
                        <button className="btn-icon" onClick={() => removeExpense(exp.id)}>\u00d7</button>
                      </td>
                    </tr>
                  ))}
               </tbody>
            </table>
            <button className="btn-ghost" style={{ fontSize: '11px' }} onClick={addExpense}>+ Add Row</button>

            <div style={{ marginTop: 24, padding: '16px', borderRadius: '4px', background: totalAmount > 500 ? '#fef2f2' : '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
               <span style={{ fontSize: '14px', fontWeight: '700' }}>Total Requested:</span>
               <span style={{ fontSize: '20px', fontWeight: '800', color: totalAmount > 500 ? '#dc2626' : '#1e293b' }}>
                 ${totalAmount.toFixed(2)}
               </span>
            </div>
          </div>
        </div>
      )}

      {currentStep === 4 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '20px' }}>
             <div className="decl-panel" style={{ marginBottom: '20px' }}>
                I confirm that the information provided is accurate and complete. I understand that hardship support is discretionary and considered a last resort.
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

export default HardshipBursary;
