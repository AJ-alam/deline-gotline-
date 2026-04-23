import React, { useState, useEffect } from 'react';
import API from '../../api/client';
import FormWizard from '../../components/Forms/FormWizard';
import '../../styles/forms.css';

interface FormDProps {
  profile?: any;
  onBack: () => void;
  onComplete: () => void;
  onNavigate: (view: string) => void;
}

const FormD: React.FC<FormDProps> = ({ profile, onBack, onComplete, onNavigate }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  // Selection state
  const [categories, setCategories] = useState({
    drop: false,
    withdraw: false,
    school: false,
    dependents: false,
    contact: false,
    sfa: false,
    other: false
  });

  const [details, setDetails] = useState({
    status: '',
    effDate: '',
    reason: '',
    institution: '',
    program: '',
    dependentCount: '',
    dependentAges: '',
    address: '',
    phone: '',
    email: '',
    sfaStatus: '',
    declarationConfirmed: false
  });

  const [selectedFiles, setSelectedFiles] = useState<Record<string, File | null>>({
    enrollmentDoc: null,
    sfaLetter: null
  });

  // Auto-fill sync from profile
  useEffect(() => {
    if (profile) {
      setDetails(prev => ({
        ...prev,
        phone: prev.phone || profile.phone || '',
        email: prev.email || profile.email || '',
        address: prev.address || profile.mailing_address || '',
        dependentCount: prev.dependentCount || String(profile.num_dependents || ''),
        dependentAges: prev.dependentAges || profile.dependent_ages || '',
        institution: prev.institution || profile.institute || profile.institution_name || '',
        program: prev.program || profile.program_credential || '',
        status: prev.status || profile.enrollment_status || '',
        sfaStatus: prev.sfaStatus || profile.financial_assistance_status || ''
      }));
    }
  }, [profile]);

  const handleToggleCategory = (cat: keyof typeof categories) => {
    setCategories(prev => ({ ...prev, [cat]: !prev[cat] }));
  };

  const steps = [
    { id: 1, label: 'What changed?' },
    { id: 2, label: 'Details of the change' },
    { id: 3, label: 'Review & Impact Summary' }
  ];

  // BUG 5: Validation
  const canGoNext = () => {
    if (currentStep === 1) {
      return Object.values(categories).some(v => v);
    }
    if (currentStep === 2) {
      return details.effDate && details.reason;
    }
    return true;
  };

  const handleNext = () => {
    if (!canGoNext()) {
      setError(currentStep === 1 ? 'Please select at least one change category.' : 'Please provide an effective date and a description of the change.');
      return;
    }
    setError(null);

    if (currentStep === 1) {
      // HANDLE REDIRECTIONS
      // Priority 1: Changed schools or programs -> New Application
      if (categories.school) {
        onNavigate('formA');
        return;
      }
      
      // Priority 2: Profile related changes (Address, Dependents, SFA)
      // Only redirect if no "Internal" categories (drop, withdraw, other) are selected
      const hasInternal = categories.drop || categories.withdraw || categories.other;
      const hasRedirect = categories.contact || categories.dependents || categories.sfa;
      
      if (hasRedirect && !hasInternal) {
        onNavigate('profile');
        return;
      }
      
      // Otherwise continue to Step 2
      setCurrentStep(2);
    } else if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
    else onBack();
  };

  // BUG 4: Connected Submission Flow
  const handleSubmit = async () => {
    if (!details.declarationConfirmed) {
      setError('Please confirm the declaration before submitting.');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const submissionData = new FormData();
      
      const answers = [
        { field_label: 'Change Categories', answer_text: Object.entries(categories).filter(([_, v]) => v).map(([k]) => k).join(', ') },
        { field_label: 'Effective Date', answer_text: details.effDate },
        { field_label: 'Reason for Change', answer_text: details.reason },
        { field_label: 'New Status', answer_text: details.status },
        { field_label: 'New Institution', answer_text: details.institution },
        { field_label: 'New Program', answer_text: details.program },
        { field_label: 'Dependent Change', answer_text: `Count: ${details.dependentCount}, Ages: ${details.dependentAges}` },
        { field_label: 'Contact Info Change', answer_text: `Address: ${details.address}, Phone: ${details.phone}, Email: ${details.email}` },
        { field_label: 'SFA Status', answer_text: details.sfaStatus },
        { field_label: 'Impact Summary', answer_text: getImpactText() }
      ];

      answers.forEach((ans, i) => {
        submissionData.append(`answers[${i}]field_label`, ans.field_label);
        submissionData.append(`answers[${i}]answer_text`, ans.answer_text);
      });

      if (selectedFiles.enrollmentDoc) {
          submissionData.append('answers[10]field_label', 'Enrollment Document');
          submissionData.append('answers[10]answer_file', selectedFiles.enrollmentDoc);
      }
      if (selectedFiles.sfaLetter) {
          submissionData.append('answers[11]field_label', 'SFA Letter');
          submissionData.append('answers[11]answer_file', selectedFiles.sfaLetter);
      }

      await API.submitApplication({
        form_type: 'FormD',
        form_data: submissionData
      });
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit change report. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const getImpactText = () => {
    let summary = `You reported a change effective ${details.effDate || "[No Date Selected]"}. `;
    if (categories.drop || categories.withdraw) {
      summary += "Reducing your course load or withdrawing will immediately affect your living allowance. Staff will recalculate your eligibility. If an overpayment has already been issued, you will be notified of the repayment process.";
    } else if (categories.school) {
      summary += "Your school or program change will be reviewed to ensure the new program is eligible for funding. Tuition payments may be redirected.";
    } else if (categories.dependents) {
      summary += "Your dependent update may result in an adjustment to your monthly allowance starting from the reported effective date.";
    } else {
      summary += "DGG staff will review your report and update your profile. You will receive an email once the changes have been processed.";
    }
    return summary;
  };

  if (isSubmitted) {
    return (
      <div className="wizard-root fade-in">
        <div className="wizard-shell" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div className="success-icon" style={{ margin: '0 auto 24px', width: '64px', height: '64px', border: '2px solid #38a169', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38a169' }}>
            <Icons.Check />
          </div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Change Reported</h2>
          <p style={{ fontSize: '14px', color: '#4a5568', lineHeight: '1.6', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your change of information has been submitted. A counselor will review the impact on your funding and contact you if further action is needed.
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
      title="Change of Information"
      subtitle={currentStep === 1
        ? "Something changed in your school or life? Pick the categories that apply."
        : currentStep === 2
          ? "Provide the specific details for the changes you selected."
          : "Review the potential impact on your funding before finalizing."
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

      <div style={{ background: '#fff8f0', border: '1px solid #ffcc80', borderLeft: '3px solid #e65100', borderRadius: '3px', padding: '10px 12px', fontSize: '10px', color: '#7a4a00', lineHeight: '1.6', marginBottom: '12px', marginTop: '20px' }}>
        <strong>Submit immediately whenever any information changes.</strong> Failing to report enrollment changes (e.g. dropping to part-time) can result in overpayments you will be required to repay.
      </div>

      <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '20px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ flex: 1, textAlign: 'center', fontSize: '11px', fontWeight: '700', color: currentStep === 1 ? '#111' : '#aaa', borderBottom: `3px solid ${currentStep === 1 ? '#111' : '#eee'}`, paddingBottom: '10px' }}>1. What changed?</div>
        <div style={{ flex: 1, textAlign: 'center', fontSize: '11px', fontWeight: '700', color: currentStep === 2 ? '#111' : '#aaa', borderBottom: `3px solid ${currentStep === 2 ? '#111' : '#eee'}`, paddingBottom: '10px' }}>2. Details of the change</div>
        <div style={{ flex: 1, textAlign: 'center', fontSize: '11px', fontWeight: '700', color: currentStep === 3 ? '#111' : '#aaa', borderBottom: `3px solid ${currentStep === 3 ? '#111' : '#eee'}`, paddingBottom: '10px' }}>3. Review & Impact Summary</div>
      </div>

      {currentStep === 1 && (
        <div className="fade-in">
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#111', marginBottom: '8px' }}>Something changed in my school or life.</div>
          <p style={{ fontSize: '12px', color: '#666', marginBottom: '20px' }}>Pick one or more categories that apply to your current situation:</p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
            <CategoryCard 
              active={categories.drop} 
              onClick={() => handleToggleCategory('drop')} 
              label="Dropped / added courses (load changed)" 
              sub="Staff will be notified and your funding will be recalculated."
            />
            <CategoryCard 
              active={categories.withdraw} 
              onClick={() => handleToggleCategory('withdraw')} 
              label="Withdrew from my program (temp/perm)" 
              sub="Reporting a temporary or permanent withdrawal from study."
            />
            <CategoryCard 
              active={categories.school} 
              onClick={() => handleToggleCategory('school')} 
              label="Changed schools or programs" 
              sub="Policy requires a new application for program changes. Redirects to main application."
            />
            <CategoryCard 
              active={categories.dependents} 
              onClick={() => handleToggleCategory('dependents')} 
              label="My dependents changed" 
              sub="Add or remove dependents from your file. Redirects to Profile."
            />
            <CategoryCard 
              active={categories.contact} 
              onClick={() => handleToggleCategory('contact')} 
              label="Address or contact info changes" 
              sub="Update your residential address or phone. Redirects to Profile."
            />
            <CategoryCard 
              active={categories.sfa} 
              onClick={() => handleToggleCategory('sfa')} 
              label="SFA status changed" 
              sub="Updating your SFA / 3rd party funding status. Redirects to Profile."
            />
            <CategoryCard 
              active={categories.other} 
              onClick={() => handleToggleCategory('other')} 
              label="Something else happened" 
              sub="Describe an unusual situation to your Student Support Worker."
              span2 
            />
          </div>

          {(categories.contact || categories.dependents || categories.sfa) && (
            <div className="fade-in" style={{ padding: '16px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '12px', marginBottom: '12px' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <span style={{ fontSize: '20px' }}>ℹ️</span>
                <div style={{ fontSize: '11.5px', color: '#0369a1', fontWeight: '500' }}>
                   <strong>Note:</strong> Redirection to your Profile will occur upon clicking "Next Step".
                </div>
              </div>
            </div>
          )}

          {categories.school && (
            <div className="fade-in" style={{ padding: '16px', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '12px', marginBottom: '12px' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <span style={{ fontSize: '20px' }}>⚠️</span>
                <div style={{ fontSize: '11.5px', color: '#9a3412', fontWeight: '500' }}>
                   <strong>Action Required:</strong> A new application is required for school changes. You will be moved to the Admission Application.
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {currentStep === 2 && (
        <div className="fade-in">
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#111', marginBottom: '8px' }}>Details of the change.</div>
          <p style={{ fontSize: '12px', color: '#666', marginBottom: '20px' }}>Please provide the key details for each category you selected.</p>

          {(categories.drop || categories.withdraw) && (
            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', marginBottom: '16px', overflow: 'hidden' }}>
              <div style={{ background: '#f8f9fa', borderBottom: '1px solid #eee', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#1a4a8a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px' }}>🎓</span> Enrollment & Course Load
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>New Status</div>
                    <select value={details.status} onChange={e => setDetails({ ...details, status: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }}>
                      <option value="">Select status</option>
                      <option>Full-Time (Enrolled in 3+ courses)</option>
                      <option>Part-Time (Enrolled in 1-2 courses)</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Enrollment verification</div>
                    <input type="file" onChange={e => setSelectedFiles({ ...selectedFiles, enrollmentDoc: e.target.files?.[0] || null })} style={{ fontSize: '11px', color: '#555' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {categories.withdraw && (
            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', marginBottom: '16px', overflow: 'hidden' }}>
              <div style={{ background: '#fff1f2', borderBottom: '1px solid #fecaca', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#991b1b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px' }}>🛑</span> Program Withdrawal
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Withdrawal Status <span style={{ color: '#cc0000' }}>*</span></div>
                    <select value={details.status} onChange={e => setDetails({ ...details, status: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }}>
                      <option value="">Select status</option>
                      <option>Withdrawn (Temporary / Medical Leave)</option>
                      <option>Withdrawn (Permanent / Terminated)</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Withdrawal Date <span style={{ color: '#cc0000' }}>*</span></div>
                    <input type="date" value={details.effDate} onChange={e => setDetails({ ...details, effDate: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                </div>
                <div>
                   <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Reason for Withdrawal <span style={{ color: '#cc0000' }}>*</span></div>
                   <textarea rows={2} value={details.reason} onChange={e => setDetails({ ...details, reason: e.target.value })} placeholder="Please explain why you are withdrawing..." style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px', fontFamily: 'inherit' }}></textarea>
                </div>
              </div>
            </div>
          )}

          {categories.school && (
            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', marginBottom: '16px', overflow: 'hidden' }}>
              <div style={{ background: '#f8f9fa', borderBottom: '1px solid #eee', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#1a4a8a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px' }}>🏫</span> School or Program Change
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>New Institution Name</div>
                    <input type="text" value={details.institution} onChange={e => setDetails({ ...details, institution: e.target.value })} placeholder="e.g., Aurora College" style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>New Program of Study</div>
                    <input type="text" value={details.program} onChange={e => setDetails({ ...details, program: e.target.value })} placeholder="e.g., Business Administration" style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {categories.dependents && (
            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', marginBottom: '16px', overflow: 'hidden' }}>
              <div style={{ background: '#f8f9fa', borderBottom: '1px solid #eee', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#1a4a8a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px' }}>👥</span> Dependents Changed
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>New Total Count</div>
                    <input type="number" value={details.dependentCount} onChange={e => setDetails({ ...details, dependentCount: e.target.value })} min="0" style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Ages of Dependents</div>
                    <input type="text" value={details.dependentAges} onChange={e => setDetails({ ...details, dependentAges: e.target.value })} placeholder="e.g., 4, 7, 12" style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {categories.contact && (
            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', marginBottom: '16px', overflow: 'hidden' }}>
              <div style={{ background: '#f8f9fa', borderBottom: '1px solid #eee', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#1a4a8a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px' }}>🏠</span> Address or Contact Details
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ marginBottom: '12px' }}>
                  <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>New Primary Address</div>
                  <textarea rows={2} value={details.address} onChange={e => setDetails({ ...details, address: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px', fontFamily: 'inherit' }}></textarea>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Phone Number</div>
                    <input type="text" value={details.phone} onChange={e => setDetails({ ...details, phone: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Email (if changed)</div>
                    <input type="email" value={details.email} onChange={e => setDetails({ ...details, email: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {categories.sfa && (
            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', marginBottom: '16px', overflow: 'hidden' }}>
              <div style={{ background: '#f8f9fa', borderBottom: '1px solid #eee', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#1a4a8a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px' }}>💰</span> SFA / Other Funding Status
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Current SFA Status</div>
                    <select value={details.sfaStatus} onChange={e => setDetails({ ...details, sfaStatus: e.target.value })} style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }}>
                      <option value="">Select</option>
                      <option>Now receiving SFA</option>
                      <option>Stopped receiving SFA</option>
                      <option>Receiving other 3rd party funding</option>
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>New Letter (Optional)</div>
                    <input type="file" onChange={e => setSelectedFiles({ ...selectedFiles, sfaLetter: e.target.files?.[0] || null })} style={{ fontSize: '11px', color: '#555' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden' }}>
            <div style={{ background: '#f8f9fa', borderBottom: '1px solid #eee', padding: '12px 16px', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#333' }}>Timing & Context</div>
            <div style={{ padding: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Effective Date of Change <span style={{ color: '#cc0000' }}>*</span></div>
                  <input type="date" value={details.effDate} onChange={e => setDetails({ ...details, effDate: e.target.value })} style={{ width: '100%', maxWidth: '260px', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px' }} />
                </div>
                <div>
                  <div style={{ fontSize: '9px', fontWeight: '600', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Please describe what happened in your own words. <span style={{ color: '#cc0000' }}>*</span></div>
                  <textarea rows={3} value={details.reason} onChange={e => setDetails({ ...details, reason: e.target.value })} placeholder="e.g., I dropped Nursing 201 due to personal reasons, which changes my status to part-time." style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px', fontFamily: 'inherit' }}></textarea>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {currentStep === 3 && (
        <div className="fade-in">
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#111', marginBottom: '8px' }}>Review and Impact Summary.</div>
          <p style={{ fontSize: '12px', color: '#666', marginBottom: '20px' }}>Please read the following policy summary before submitting.</p>

          <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '24px', marginBottom: '16px' }}>
            <div style={{ background: '#f0f7ff', border: '1px solid #cce3ff', borderLeft: '4px solid #1a73e8', borderRadius: '4px', padding: '20px', lineHeight: '1.6', color: '#0b4c9e', fontSize: '12.5px' }}>
              <strong>Impact Estimate:</strong> <span>{getImpactText()}</span>
            </div>

            <div style={{ marginTop: '24px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', cursor: 'pointer' }}>
                <input 
                    type="checkbox" 
                    checked={details.declarationConfirmed}
                    onChange={e => setDetails({ ...details, declarationConfirmed: e.target.checked })}
                    style={{ width: '20px', height: '20px', flexShrink: 0, marginTop: '2px' }} 
                />
                <span style={{ fontSize: '12px', color: '#111', lineHeight: '1.5' }}>
                  <strong>Declaration:</strong> I confirm that the information provided is correct and complete. I understand that reporting this change may trigger a <strong>recalculation of my funding</strong> from the effective date provided, and may result in an <strong>overpayment</strong> that I will be required to repay.
                </span>
              </label>
            </div>
          </div>
        </div>
      )}
    </FormWizard>
  );
};

const CategoryCard: React.FC<{ 
  active: boolean; 
  onClick: () => void; 
  label: string; 
  sub: string; 
  span2?: boolean 
}> = ({ active, onClick, label, sub, span2 }) => (
  <div
    onClick={onClick}
    className={`selection-card ${active ? 'active' : ''}`}
    style={{
      border: `2px solid ${active ? '#1e40af' : '#e2e8f0'}`,
      borderRadius: '12px',
      padding: '20px',
      cursor: 'pointer',
      background: active ? '#eff6ff' : '#fff',
      display: 'flex',
      gap: '16px',
      alignItems: 'flex-start',
      gridColumn: span2 ? 'span 2' : 'auto',
      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
      boxShadow: active ? '0 4px 6px -1px rgba(30, 64, 175, 0.1), 0 2px 4px -1px rgba(30, 64, 175, 0.06)' : 'none',
      position: 'relative',
      overflow: 'hidden'
    }}
  >
    {active && <div style={{ position: 'absolute', top: '0', right: '0', background: '#1e40af', color: '#fff', padding: '4px 12px', fontSize: '10px', fontWeight: '800', borderBottomLeftRadius: '8px' }}>SELECTED</div>}
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: '14px', fontWeight: '800', color: active ? '#1e3a8a' : '#1e293b', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '11.5px', color: active ? '#3b82f6' : '#64748b', lineHeight: '1.4', fontWeight: '500' }}>{sub}</div>
    </div>
  </div>
);

const Icons = {
  Check: () => (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
  )
};

export default FormD;
