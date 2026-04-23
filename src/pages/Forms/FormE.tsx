import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface ExpenseRow {
  id: string;
  description: string;
  amount: string;
  receiptAttached: boolean;
}

interface FormEProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
}

const FormE: React.FC<FormEProps> = ({ profile, onBack, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  
  // BUG 1: Connectivity & State
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    dob: '',
    treatyNumber: '',
    travelFrom: '',
    travelTo: '',
    travelDate: '',
    returnTravelDate: '',
    modeAir: true,
    modeLand: false,
    kmTraveled: '',
    vehicleDriver: '',
    declarationConfirmed: false,
    signature: ''
  });

  const [expenses, setExpenses] = useState<ExpenseRow[]>([
    { id: '1', description: '', amount: '', receiptAttached: false },
    { id: '2', description: '', amount: '', receiptAttached: false },
    { id: '3', description: '', amount: '', receiptAttached: false }
  ]);

  const [totalAmount, setTotalAmount] = useState(0);
  const [selectedReceipts, setSelectedReceipts] = useState<FileList | null>(null);

  // Auto-fill sync from profile
  useEffect(() => {
    if (profile) {
      setFormData(prev => ({
        ...prev,
        firstName: prev.firstName || profile.full_name?.split(' ')[0] || '',
        lastName: prev.lastName || profile.full_name?.split(' ').slice(1).join(' ') || '',
        dob: prev.dob || profile.dob || '',
        treatyNumber: prev.treatyNumber || profile.treaty_number || '',
        travelFrom: prev.travelFrom || profile.town_city || ''
      }));
    }
  }, [profile]);

  useEffect(() => {
    const total = expenses.reduce((sum, row) => {
      const val = parseFloat(row.amount) || 0;
      return sum + val;
    }, 0);
    setTotalAmount(total);
  }, [expenses]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleUpdateRow = (id: string, field: keyof ExpenseRow, value: any) => {
    setExpenses(expenses.map(e => e.id === id ? { ...e, [field]: value } : e));
  };

  const steps = [
    { id: 1, label: 'Student & Travel' },
    { id: 2, label: 'Expenses & Receipts' },
    { id: 3, label: 'Declaration & Office' }
  ];

  // BUG 5: Validation
  // Validation Logic
  const canGoNext = () => {
    if (currentStep === 1) {
      return !!(formData.firstName && formData.lastName && formData.travelFrom && formData.travelTo && formData.travelDate);
    }
    if (currentStep === 2) {
      return totalAmount > 0 && selectedReceipts && selectedReceipts.length > 0;
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      if (currentStep === 1) {
        setError('Please fill in all required travel information (Name, Destination, Departure Date).');
      } else if (currentStep === 2) {
        if (totalAmount <= 0) setError('Total claim amount must be greater than zero.');
        else if (!selectedReceipts || selectedReceipts.length === 0) setError('Please upload your boarding passes or travel receipts.');
        else setError('Please ensure all required fields in the expense list are filled.');
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
    if (!formData.declarationConfirmed || !formData.signature) {
      setError('Please sign and confirm the declaration.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      const answers = [
        { field_label: 'First Name', answer_text: formData.firstName },
        { field_label: 'Last Name', answer_text: formData.lastName },
        { field_label: 'DOB', answer_text: formData.dob },
        { field_label: 'Treaty Number', answer_text: formData.treatyNumber },
        { field_label: 'Traveling From', answer_text: formData.travelFrom },
        { field_label: 'Traveling To', answer_text: formData.travelTo },
        { field_label: 'Travel Date', answer_text: formData.travelDate },
        { field_label: 'Return Date', answer_text: formData.returnTravelDate },
        { field_label: 'Mode Air', answer_text: formData.modeAir ? 'Yes' : 'No' },
        { field_label: 'Mode Land', answer_text: formData.modeLand ? 'Yes' : 'No' },
        { field_label: 'Total KM', answer_text: formData.kmTraveled },
        { field_label: 'Vehicle/Driver', answer_text: formData.vehicleDriver },
        { field_label: 'Total Claim', answer_text: totalAmount.toString() },
        { field_label: 'Signature', answer_text: formData.signature }
      ];

      // Indexed answers
      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      // Add expense list as a JSON string in one field for reference
      submissionData.append(`answers[${answers.length}]field_label`, 'Expense List');
      submissionData.append(`answers[${answers.length}]answer_text`, JSON.stringify(expenses.filter(e => e.description && e.amount)));

      // Add receipts
      if (selectedReceipts) {
        for (let i = 0; i < selectedReceipts.length; i++) {
          submissionData.append(`answers[${answers.length + 1 + i}]field_label`, `Receipt ${i + 1}`);
          submissionData.append(`answers[${answers.length + 1 + i}]answer_file`, selectedReceipts[i]);
        }
      }

      await API.submitApplication({
        form_type: 'FormE',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit travel claim. Please try again.');
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
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Claim Submitted</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your travel reimbursement claim has been received. Please allow 10-15 business days for processing after all receipts are verified.
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
      title="Travel Reimbursement"
      subtitle={currentStep === 1 
        ? "Apply for coverage of travel to and from your educational institution." 
        : currentStep === 2
          ? "List all individual travel expenses. Receipts must be attached for each."
          : "Finalize your claim with supporting documentation."
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

      <div style={{ background: '#f7f7f7', border: '1px solid #e0e0e0', borderLeft: '3px solid #333', borderRadius: '3px', padding: '10px 12px', fontSize: '10px', color: '#444', lineHeight: '1.6', marginBottom: '12px', marginTop: '20px' }}>
        Use this form to apply for coverage of travel expenses to and from your educational institution. <strong>Receipts are mandatory.</strong>
      </div>

      {currentStep === 1 && (
        <div className="fade-in">
          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', marginBottom: '14px', padding: '16px' }}>
             <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '12px', textTransform: 'uppercase' }}>A. Student Information</div>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px' }}>
                <div>
                    <label className="field-label">First Name *</label>
                    <input className="field-input" value={formData.firstName} onChange={e => handleInputChange('firstName', e.target.value)} />
                </div>
                <div>
                    <label className="field-label">Last Name *</label>
                    <input className="field-input" value={formData.lastName} onChange={e => handleInputChange('lastName', e.target.value)} />
                </div>
                <div>
                    <label className="field-label">DOB *</label>
                    <input className="field-input" type="date" value={formData.dob} onChange={e => handleInputChange('dob', e.target.value)} />
                </div>
                <div>
                    <label className="field-label">Treaty # *</label>
                    <input className="field-input" value={formData.treatyNumber} onChange={e => handleInputChange('treatyNumber', e.target.value)} />
                </div>
             </div>
          </div>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', marginBottom: '14px', padding: '16px' }}>
             <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '12px', textTransform: 'uppercase' }}>B. Travel Information</div>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <div>
                    <label className="field-label">Traveling From *</label>
                    <input className="field-input" value={formData.travelFrom} onChange={e => handleInputChange('travelFrom', e.target.value)} placeholder="City, Prov" />
                </div>
                <div>
                    <label className="field-label">Traveling To *</label>
                    <input className="field-input" value={formData.travelTo} onChange={e => handleInputChange('travelTo', e.target.value)} placeholder="City, Prov" />
                </div>
             </div>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px' }}>
                <div>
                    <label className="field-label">Departure Date *</label>
                    <input className="field-input" type="date" value={formData.travelDate} onChange={e => handleInputChange('travelDate', e.target.value)} />
                </div>
                <div>
                    <label className="field-label">Return Date</label>
                    <input className="field-input" type="date" value={formData.returnTravelDate} onChange={e => handleInputChange('returnTravelDate', e.target.value)} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <label style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <input type="checkbox" checked={formData.modeAir} onChange={e => handleInputChange('modeAir', e.target.checked)} /> Air
                    </label>
                    <label style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <input type="checkbox" checked={formData.modeLand} onChange={e => handleInputChange('modeLand', e.target.checked)} /> Land
                    </label>
                </div>
                <div>
                    <label className="field-label">Total KM (if Land)</label>
                    <input className="field-input" type="number" value={formData.kmTraveled} onChange={e => handleInputChange('kmTraveled', e.target.value)} />
                </div>
             </div>
          </div>
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
           <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '16px', marginBottom: '14px' }}>
               <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '12px', textTransform: 'uppercase' }}>Expense Breakdown</div>
               <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr 1fr', gap: '10px', marginBottom: '10px', fontWeight: '600', fontSize: '10px' }}>
                   <div>Description</div>
                   <div>Amount ($)</div>
                   <div>Receipt?</div>
               </div>
               {expenses.map(row => (
                   <div key={row.id} style={{ display: 'grid', gridTemplateColumns: '3fr 1fr 1fr', gap: '10px', marginBottom: '8px' }}>
                       <input className="field-input" value={row.description} onChange={e => handleUpdateRow(row.id, 'description', e.target.value)} placeholder="e.g. Air Canada Flight" />
                       <input className="field-input" type="number" value={row.amount} onChange={e => handleUpdateRow(row.id, 'amount', e.target.value)} placeholder="0.00" />
                       <label style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                           <input type="checkbox" checked={row.receiptAttached} onChange={e => handleUpdateRow(row.id, 'receiptAttached', e.target.checked)} /> Yes
                       </label>
                   </div>
               ))}
               <div style={{ borderTop: '1px solid #eee', marginTop: '12px', paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                   <div style={{ fontWeight: '700', fontSize: '12px' }}>Total Requested:</div>
                   <div style={{ fontWeight: '700', fontSize: '14px', color: '#1a4aaa' }}>${totalAmount.toFixed(2)}</div>
               </div>
           </div>

           <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '16px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '4px' }}>Upload Receipts *</div>
                <div style={{ fontSize: '10px', color: '#666', marginBottom: '10px' }}>Select all photos/scans of travel receipts at once.</div>
                <input type="file" multiple onChange={e => setSelectedReceipts(e.target.files)} style={{ fontSize: '11px' }} />
           </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
           <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '16px', marginBottom: '14px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#111', marginBottom: '12px', textTransform: 'uppercase' }}>C. Declaration</div>
                <div style={{ background: '#f9f9f9', border: '1px solid #e0e0e0', borderRadius: '3px', padding: '12px 14px', fontSize: '10.5px', color: '#555', lineHeight: '1.7', marginBottom: '16px' }}>
                    I declare that the expenses incurred have been used for the purpose of traveling to and from my post-secondary institution. Any false information will result in the denial of reimbursement.
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: '#333', cursor: 'pointer', marginBottom: '16px' }}>
                   <input type="checkbox" checked={formData.declarationConfirmed} onChange={e => handleInputChange('declarationConfirmed', e.target.checked)} /> 
                   <span>I confirm the declaration <span style={{ color: '#cc0000' }}>*</span></span>
                </label>
                <div>
                   <label className="field-label">Student Signature (Full Name) *</label>
                   <input className="field-input" value={formData.signature} onChange={e => handleInputChange('signature', e.target.value)} placeholder="Type name to sign" />
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

export default FormE;
