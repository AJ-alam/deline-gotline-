import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import API from '../api/client';
import '../styles/auth.css';

interface Dependent {
  id: string;
  firstName: string;
  lastName: string;
  dob: string;
  relationship: string;
  treatyNum: string;
  disabilityStatus: string;
}

const SignUp: React.FC = () => {
  const navigate = useNavigate();
  const [dependents, setDependents] = useState<Dependent[]>([]);
  const [eligibility, setEligibility] = useState({
    q1: '', q2: '', q3: '', q4: '', q5: '', q6: ''
  });
  
  const [eligResult, setEligResult] = useState<{
    style: 'error' | 'success' | 'warning' | 'info';
    title: string;
    desc: string;
    isApproved: boolean;
  }>({
    style: 'info',
    title: 'Eligibility Incomplete',
    desc: 'Please answer all 6 questions above to determine your eligibility and proceed.',
    isApproved: false
  });

  const [showSFANote, setShowSFANote] = useState(false);

  const addDependent = () => {
    const newDep: Dependent = {
      id: `dep-${Date.now()}`,
      firstName: '',
      lastName: '',
      dob: '',
      relationship: '',
      treatyNum: '',
      disabilityStatus: ''
    };
    setDependents([...dependents, newDep]);
  };

  const removeDependent = (id: string) => {
    setDependents(dependents.filter(dep => dep.id !== id));
  };

  const handleEligChange = (name: string, value: string) => {
    setEligibility(prev => ({ ...prev, [name]: value }));
  };

  useEffect(() => {
    const { q1, q2, q3, q4, q5, q6 } = eligibility;

    let style: 'error' | 'success' | 'warning' | 'info' = 'info';
    let title = 'Eligibility Incomplete';
    let desc = 'Please answer all 6 questions above to determine your eligibility and proceed.';
    let isApproved = false;
    let sfaNote = false;

    // Rule out dealbreakers first
    if (q5 === 'no') {
      style = 'error';
      title = 'Intake Stopped - Institution Not Accredited';
      desc = 'Based on your answers, you do not qualify for DGG funding support at this time. DGG funding requires enrollment at an Accredited Institution. Please contact the DGG Education Department if you have questions.';
    } else if (q6 === 'no') {
      style = 'error';
      title = 'Intake Stopped - Program Requirements';
      desc = (q1 === 'yes' || q2 === 'yes')
        ? 'Based on your answers, you are not eligible for any funding administered by the DGG Education Department. You may wish to contact the Sahtu Dene Council to ask about other funding programs.'
        : 'Based on your answers, you do not qualify for DGG funding support at this time. Please contact the DGG Education Department if you have questions.';
    } else if (q1 === 'no' && q2 === 'no') {
      style = 'error';
      title = 'Intake Stopped';
      desc = 'Based on your answers, you do not qualify for DGG funding support at this time. Only registered Deline First Nation members or Deline Beneficiaries are eligible for these streams.';
    } else if (q1 && q2 && q3 && q4 && q5 === 'yes' && q6 === 'yes') {
      // Run advanced routing
      isApproved = true;
      if (q4 === 'nwt') {
        if (q2 === 'yes') {
          style = 'success';
          title = 'Action Required: DGGR Top-Up Funding';
          desc = 'Based on your status as an NWT resident and Délı̨nę Beneficiary, you qualify for **DGGR Top-Up Funding**. Your primary funding must be requested through GNWT SFA first.';
          if (q3 === 'no') sfaNote = true;
        } else {
          style = 'error';
          title = 'Intake Stopped';
          desc = 'Based on your answers, you do not qualify for DGG funding support at this time. Residents of the NWT who are not beneficiaries are generally expected to use GNWT SFA exclusively.';
          isApproved = false;
        }
      } else if (q4 === 'other' || q4 === 'outside') {
        if (q1 === 'yes') {
          style = 'success';
          title = 'Eligible: Federal PSSSP / UCEPP Funding';
          desc = `Because you live outside the NWT and are registered with the Délı̨nę First Nation, you qualify for the **Federal Post-Secondary Student Support Program (PSSSP)**. ${q2 === 'yes' ? 'You have also qualified for the DGGR Top-Up.' : ''}`;
        } else if (q2 === 'yes') {
          style = 'success';
          title = 'Eligible: DGGR Top-Up Only';
          desc = 'Because you are not registered with the Délı̨nę First Nation (Indian Act), you do not qualify for Federal PSSSP. However, as a Délı̨nę Beneficiary, you qualify for **DGGR Top-Up Funding**.';
        } else {
          style = 'error';
          title = 'Intake Stopped';
          desc = 'Based on your answers, you do not qualify for DGG funding support at this time.';
          isApproved = false;
        }
      }
    }

    setShowSFANote(sfaNote);
    setEligResult({ style, title, desc, isApproved });
  }, [eligibility]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
    beneficiaryNo: '',
    treatyNum: '',
    dob: '',
    phone: ''
  });

  const normalizeDate = (dateStr: string) => {
    if (!dateStr) return dateStr;
    // Cleanup slashes, dots, dashes and spaces
    const parts = dateStr.split(/[\/\-\.\s]+/).filter(Boolean);
    
    if (parts.length === 3) {
      let d, m, y;
      
      // Detect year position (start vs end)
      if (parts[0].length === 4) {
        // YYYY MM DD
        [y, m, d] = parts;
      } else if (parts[2].length === 4) {
        // DD MM YYYY (Standard for our placeholder)
        [d, m, y] = parts;
      } else {
        // Cannot reliably normalize (e.g. 05-06-07), return as is
        return dateStr;
      }

      // Format to ISO YYYY-MM-DD for backend
      const finalY = y;
      const finalM = m.padStart(2, '0');
      const finalD = d.padStart(2, '0');
      
      return `${finalY}-${finalM}-${finalD}`;
    }
    return dateStr;
  };

  const handleSignUp = async () => {
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      // Normalize DOB to YYYY-MM-DD
      const normalizedData = { 
        ...formData, 
        dob: normalizeDate(formData.dob) 
      };

      await API.register({
        ...normalizedData,
        eligibility
      });
      navigate('/signin');
    } catch (err: any) {
      if (err.data && typeof err.data === 'object' && !Array.isArray(err.data)) {
        // Extract first validation error if it's a field-level error
        const firstField = Object.keys(err.data)[0];
        const firstError = err.data[firstField];
        const errorMessage = Array.isArray(firstError) ? firstError[0] : String(firstError);
        setError(`${firstField.replace('_', ' ').toUpperCase()}: ${errorMessage}`);
      } else {
        setError(err.message || 'Registration failed');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const updateFormData = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="auth-root">
      <div className="page-layout">
        {/* Left Branding Panel */}
        <div className="left-panel">
          <div>
            <div className="brand-name">Deline Got'ı̨nę Government</div>
            <div className="brand-sub">Student Financial Support Program</div>
            <div className="left-headline" style={{ marginTop: '48px' }}>
              <h1 style={{ fontSize: '28px' }}>Your future <br/><span style={{ color: 'var(--admin-accent, #e5a662)' }}>Starts Here.</span></h1>
              <p style={{ fontSize: '13px' }}>Establish your student profile to access government funding streams, track payments, and verify your eligibility for academic awards.</p>
              
              <div className="create-title" style={{ marginTop: '40px', color: '#e5a662', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Setup Progress</div>
              <ul className="step-list" style={{ marginTop: '16px' }}>
                <li className="active">
                  <div className="step-num">1</div> 
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: '700' }}>Eligibility Check</div>
                    <div style={{ fontSize: '10px', opacity: 0.6 }}>Confirm program requirements</div>
                  </div>
                </li>
              </ul>
            </div>
          </div>

          <div className="left-footer">
             <div className="progress-dots">
               <span className="active"></span>
             </div>
             <p style={{ marginTop: '12px', color: 'rgba(255,255,255,0.4)', fontSize: '10px' }}>Secure Application Portal v2.0</p>
          </div>
        </div>

        {/* Right panel */}
        <div className="right-panel">
          <div className="step-indicator">Account Creation</div>
          <div className="form-title">Tell us about yourself</div>
          <div className="form-sub">Already have an account? <Link to="/signin">Sign in →</Link></div>

            {/* ── Eligibility Check Section ── */}
            <div className="section-divider" style={{ marginTop: 0 }}>Eligibility Check</div>
            <div className="elig-check-container" style={{ background: '#fafafa', border: '1px solid #ddd', padding: '16px', borderRadius: '3px', marginBottom: '20px' }}>
              <div className="checkbox-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11.5px', fontWeight: 600, color: '#333' }}>1. Are you registered under the Indian Act, with your status affiliated with the band formerly known as the Délı̨nę First Nation?</div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <label className="radio-label"><input type="radio" name="elig_q1" value="yes" checked={eligibility.q1 === 'yes'} onChange={(e) => handleEligChange('q1', e.target.value)} /> Yes</label>
                  <label className="radio-label"><input type="radio" name="elig_q1" value="no" checked={eligibility.q1 === 'no'} onChange={(e) => handleEligChange('q1', e.target.value)} /> No</label>
                </div>
              </div>

              <div className="checkbox-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11.5px', fontWeight: 600, color: '#333' }}>2. Are you a Délı̨nę Beneficiary? <span style={{ fontWeight: 400, fontSize: '10px', color: '#166534', cursor: 'help', textDecoration: 'underline' }} title="Délı̨nę Beneficiary means a person enrolled as a Délı̨nę participant in the enrolment register pursuant to Chapter 4 of the Sahtú Dene and Métis Comprehensive Land Claim Agreement.">[?] View Definition</span></div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <label className="radio-label"><input type="radio" name="elig_q2" value="yes" checked={eligibility.q2 === 'yes'} onChange={(e) => handleEligChange('q2', e.target.value)} /> Yes</label>
                  <label className="radio-label"><input type="radio" name="elig_q2" value="no" checked={eligibility.q2 === 'no'} onChange={(e) => handleEligChange('q2', e.target.value)} /> No</label>
                </div>
              </div>

              <div className="checkbox-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11.5px', fontWeight: 600, color: '#333' }}>3. Are you currently receiving GNWT Student Financial Assistance (SFA)?</div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <label className="radio-label"><input type="radio" name="elig_q3" value="yes" checked={eligibility.q3 === 'yes'} onChange={(e) => handleEligChange('q3', e.target.value)} /> Yes</label>
                  <label className="radio-label"><input type="radio" name="elig_q3" value="no" checked={eligibility.q3 === 'no'} onChange={(e) => handleEligChange('q3', e.target.value)} /> No</label>
                </div>
                {showSFANote && (
                  <div className="policy-note info animate-fade-in" style={{ fontSize: '9.5px', marginTop: '6px', borderLeftColor: '#3182ce' }}>
                    <strong>Note:</strong> As an NWT resident, you are expected to apply for GNWT SFA first. Since you are not receiving SFA, you will be required to upload proof of denial or context later.
                  </div>
                )}
              </div>

              <div className="checkbox-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11.5px', fontWeight: 600, color: '#333' }}>4. Where do you currently live?</div>
                <select className="field-select" style={{ width: 'auto', padding: '6px 24px 6px 8px' }} value={eligibility.q4} onChange={(e) => handleEligChange('q4', e.target.value)}>
                  <option value="">Select location...</option>
                  <option value="nwt">Northwest Territories</option>
                  <option value="other">Other Canadian province or territory</option>
                  <option value="outside">Outside Canada</option>
                </select>
              </div>

              <div className="checkbox-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11.5px', fontWeight: 600, color: '#333' }}>5. Are you enrolled in an Accredited Institution? <a href="https://www.canada.ca/en/employment-social-development/programs/designated-schools.html" target="_blank" rel="noopener noreferrer" style={{ fontWeight: 400, fontSize: '10px', color: '#1e40af', textDecoration: 'underline', marginLeft: '6px' }}>Check Federal Master List</a></div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <label className="radio-label"><input type="radio" name="elig_q5" value="yes" checked={eligibility.q5 === 'yes'} onChange={(e) => handleEligChange('q5', e.target.value)} /> Yes</label>
                  <label className="radio-label"><input type="radio" name="elig_q5" value="no" checked={eligibility.q5 === 'no'} onChange={(e) => handleEligChange('q5', e.target.value)} /> No</label>
                </div>
              </div>

              <div className="checkbox-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11.5px', fontWeight: 600, color: '#333' }}>6. Are you enrolled in an approved program that is at least 12 continuous weeks? <span style={{ fontWeight: 400, fontSize: '10px', color: '#166534', cursor: 'help', textDecoration: 'underline' }} title="Approved Program means a course of study that leads to a certificate, diploma, degree, trades or upgrading program; and at least 12 continuous weeks.">[?] View Definition</span></div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <label className="radio-label"><input type="radio" name="elig_q6" value="yes" checked={eligibility.q6 === 'yes'} onChange={(e) => handleEligChange('q6', e.target.value)} /> Yes</label>
                  <label className="radio-label"><input type="radio" name="elig_q6" value="no" checked={eligibility.q6 === 'no'} onChange={(e) => handleEligChange('q6', e.target.value)} /> No</label>
                </div>
              </div>

              <div className={`elig-result-box ${eligResult.style}`}>
                <strong className="elig-result-title">{eligResult.title}</strong>
                <span>{eligResult.desc}</span>
              </div>
            </div>

            {/* ── Form Content (Only enabled if approved) ── */}
            {eligResult.isApproved ? (
              <div className="animate-fade-in">
                <div className="section-divider">Basic Information</div>
                <div className="field-row">
                  <div className="field-group">
                    <label className="field-label">First Name <span className="required">*</span></label>
                    <input className="field-input" type="text" placeholder="Marie" value={formData.firstName} onChange={e => updateFormData('firstName', e.target.value)} />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Last Name <span className="required">*</span></label>
                    <input className="field-input" type="text" placeholder="Beaulieu" value={formData.lastName} onChange={e => updateFormData('lastName', e.target.value)} />
                  </div>
                </div>

                <div className="field-row">
                  <div className="field-group">
                    <label className="field-label">Date of Birth <span className="required">*</span></label>
                    <input 
                      className="field-input" 
                      type="text" 
                      placeholder="DD / MM / YYYY" 
                      value={formData.dob} 
                      onChange={e => updateFormData('dob', e.target.value)} 
                    />
                  </div>
                  <div className="field-group">
                    <label className="field-label">DGG Beneficiary # <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, fontSize: '9px', color: '#999' }}>(Optional)</span></label>
                    <input className="field-input" type="text" placeholder="e.g. DGG-00412" value={formData.beneficiaryNo} onChange={e => updateFormData('beneficiaryNo', e.target.value)} />
                  </div>
                </div>

                <div className="field-row">
                  <div className="field-group">
                    <label className="field-label">Email Address</label>
                    <input className="field-input" type="email" placeholder="e.g. marie@email.com" value={formData.email} onChange={e => updateFormData('email', e.target.value)} />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Phone Number <span className="required">*</span></label>
                    <input 
                      className="field-input" 
                      type="tel" 
                      placeholder="(867) 000-0000" 
                      value={formData.phone} 
                      onChange={e => updateFormData('phone', e.target.value)} 
                    />
                  </div>
                </div>

                {/* Dependents Section */}
                <div className="section-divider">Dependents</div>
                <div className="dependents-container">
                  {dependents.map((dep, index) => (
                    <div key={dep.id} className="dependent-card animate-slide-in">
                      <div className="dep-header">
                        <span>Dependent {index + 1}</span>
                        <button className="dep-remove" onClick={() => removeDependent(dep.id)} type="button">✕ Remove</button>
                      </div>
                      <div className="field-row">
                        <div className="field-group">
                          <label className="field-label">First Name <span className="required">*</span></label>
                          <input className="field-input" type="text" placeholder="First name" />
                        </div>
                        <div className="field-group">
                          <label className="field-label">Last Name <span className="required">*</span></label>
                          <input className="field-input" type="text" placeholder="Last name" />
                        </div>
                      </div>
                      <div className="field-row">
                        <div className="field-group">
                          <label className="field-label">Date of Birth <span className="required">*</span></label>
                          <input className="field-input" type="text" placeholder="DD / MM / YYYY" />
                        </div>
                        <div className="field-group">
                          <label className="field-label">Relationship <span className="required">*</span></label>
                          <select className="field-select">
                            <option value="">Select</option>
                            <option>Child</option>
                            <option>Spouse / Partner</option>
                            <option>Other</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="add-dep-btn" onClick={addDependent} type="button">+ Add Dependent</button>

                <div className="section-divider">Set Password</div>
                <div className="field-row">
                  <div className="field-group">
                    <label className="field-label">Password <span className="required">*</span></label>
                    <input className="field-input" type="password" placeholder="••••••••" value={formData.password} onChange={e => updateFormData('password', e.target.value)} />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Confirm Password <span className="required">*</span></label>
                    <input className="field-input" type="password" placeholder="••••••••" value={formData.confirmPassword} onChange={e => updateFormData('confirmPassword', e.target.value)} />
                  </div>
                </div>

                {error && <div style={{ color: '#ef4444', fontSize: '11px', marginTop: '12px', fontWeight: '600' }}>{error}</div>}

                <button 
                  className="btn-auth-primary" 
                  onClick={handleSignUp} 
                  disabled={isLoading || !eligResult.isApproved} 
                  type="button" 
                  style={{ marginTop: '24px', opacity: isLoading ? 0.7 : 1 }}
                >
                  {isLoading ? 'CREATING ACCOUNT...' : 'Create My Account \u00a0\u2192'}
                </button>
              </div>
            ) : (
              <div style={{ padding: '40px 20px', textAlign: 'center', background: '#f8fafc', border: '1px dashed #e2e8f0', borderRadius: '4px', marginTop: '20px' }}>
                <div style={{ fontSize: '24px', marginBottom: '12px' }}>🔒</div>
                <div style={{ fontSize: '12.5px', color: '#64748b', fontWeight: '500' }}>Account registration will unlock once eligibility is confirmed.</div>
                <div style={{ fontSize: '10.5px', color: '#94a3b8', marginTop: '4px' }}>Please complete the 6-question questionnaire above.</div>
              </div>
            )}

        </div>
      </div>
    </div>
  );
};

export default SignUp;
