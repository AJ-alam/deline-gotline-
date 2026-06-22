import React, { useState, useEffect } from 'react';
import API from '../api/client';
import '../styles/profile.css';
import * as Ic from '../components/Icons';

interface StudentProfileProps {
  profile?: any;
}

const StudentProfile: React.FC<StudentProfileProps> = ({ profile: initialProfile }) => {
  const [profile, setProfile] = useState<any>(initialProfile);
  const [activeModal, setActiveModal] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editData, setEditData] = useState<any>({});
  const [documents, setDocuments] = useState<any[]>([]);
  const [showUPi, setShowUPi] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [hasFormA, setHasFormA] = useState(false);
  const [isCheckingFormA, setIsCheckingFormA] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [userResp, docsResp, subsResp, appsResp] = await Promise.all([
          API.getMe(),
          API.getUserDocuments(),
          API.getSubmissions(),
          API.getApplications()
        ]);
        setProfile(userResp);
        setDocuments(Array.isArray(docsResp) ? docsResp : []);

        const subs = Array.isArray(subsResp) ? subsResp : ((subsResp as any)?.results || []);
        const apps = Array.isArray(appsResp) ? appsResp : ((appsResp as any)?.results || []);
        const merged = [...subs, ...apps];
        
        const formA = merged.find((a: any) => {
          const title = (a.form_title || a.form_type || '').toLowerCase();
          return title.includes('admission') || title.includes('form a') || title.includes('psssp');
        });
        setHasFormA(!!formA && formA.status !== 'rejected');
      } catch (err) {
        console.error('Failed to fetch profile data:', err);
      } finally {
        setIsCheckingFormA(false);
      }
    };
    fetchData();
  }, []);

  const handleEditClick = (type: string) => {
    const data = { ...profile };
    // Pre-split the full name for the personal info modal to ensure smooth editing
    if (type === 'personal') {
      const parts = (data.full_name || '').split(' ');
      data._firstName = parts[0] || '';
      data._lastName = parts.slice(1).join(' ') || '';
    }
    setEditData(data);
    setActiveModal(type);
  };

  const closeModal = () => setActiveModal(null);

  // FIX: use functional updater so each keystroke always
  // builds on the latest state, never a stale closure snapshot.
  const updateField = (field: string, value: any) =>
    setEditData((prev: any) => ({ ...prev, [field]: value }));

  const handleSave = async () => {
    setIsUpdating(true);
    try {
      const dataToSave = { ...editData };
      if (activeModal === 'personal') {
        dataToSave.full_name = `${dataToSave._firstName || ''} ${dataToSave._lastName || ''}`.trim();
        // Clean up temporary fields
        delete dataToSave._firstName;
        delete dataToSave._lastName;
      }
      const updated = await API.updateMe(dataToSave);
      setProfile(updated);
      setActiveModal(null);
    } catch (err: any) {
      console.error('Save failed details:', err);
      alert(err.message || 'Update failed');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, category: string = 'Profile Upload') => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so the same file can be re-selected
    e.target.value = '';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', file.name);
    formData.append('category', category);

    setIsUploading(true);
    setUploadMessage(null);
    try {
      await API.uploadUserDocument(formData);
      setUploadMessage('Document uploaded successfully');
      // Refresh documents
      const docsResp = await API.getUserDocuments();
      setDocuments(Array.isArray(docsResp) ? docsResp : []);
    } catch (err: any) {
      console.error('Upload failed details:', err);
      const errorMsg = err.message || 'Unknown error';
      const errorData = err.data ? JSON.stringify(err.data) : '';
      setUploadMessage(`Upload failed: ${errorMsg} ${errorData}`);
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadMessage(null), 3000);
    }
  };

  // Profile completeness logic
  const getCompleteness = () => {
    if (!profile) return 0;
    const fields = [
      profile.full_name, profile.email, profile.phone, profile.dob,
      profile.bank_name, profile.account_number, profile.transit_number,
      profile.institution_name, profile.program_credential, profile.beneficiary_number
    ];
    const completed = fields.filter(f => f && String(f).trim() !== '').length;
    return Math.round((completed / fields.length) * 100);
  };

  const completeness = getCompleteness();

  const isDocVerified = (cat: string) => {
    return documents.some(d => (d.category || '').toLowerCase().includes(cat.toLowerCase()));
  };

  const renderField = (label: string, value: any, span: number = 1, sensitivity: 'standard' | 'high' | 'extreme' = 'standard') => (
    <div className={`profile-field span-${span}`}>
      <div className="p-label">{label}</div>
      <div className={`p-val ${sensitivity !== 'standard' ? `st-${sensitivity}` : ''}`}>
        {value || <span className="p-val muted">Not entered</span>}
      </div>
    </div>
  );

  const getStudentId = () => {
    if (profile?.beneficiary_number) return profile.beneficiary_number;
    if (profile?.id) return `DGG-${new Date().getFullYear()}-${profile.id.toString().padStart(4, '0')}`;
    return 'Pending';
  };

  if (!profile) return <div style={{ padding: '40px', textAlign: 'center' }}>Loading profile record...</div>;

  return (
    <div className="profile-container fade-in" style={{ paddingBottom: '60px' }}>
      
      {/* ── FORM A STATUS ALERT ── */}
      {!hasFormA && !isCheckingFormA && (
        <div className="alert-banner info" style={{ marginBottom: '20px', background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af' }}>
          <Ic.Info size={16} />
          <div>
            <strong>Action Recommended:</strong> Please complete your <strong>Admission Application</strong> to automatically fill your profile details.
            <span className="alert-banner-link" onClick={() => window.location.href='/dashboard/admission'}> Start Application...</span>
          </div>
        </div>
      )}

      {/* ── COMPLETENESS HEADER ── */}
      <div className="completeness-wrap">
        <div className="completeness-header">
          <div className="completeness-label">Profile Completeness</div>
          <div className="completeness-pct">{completeness}%</div>
        </div>
        <div className="bar-track">
          <div className="bar-fill" style={{ width: `${completeness}%` }}></div>
        </div>
        <div className="completeness-items">
          <div className={`ci ${profile.dob ? 'done' : 'missing'}`}>Personal info</div>
          <div className={`ci ${profile.beneficiary_number ? 'done' : 'missing'}`}>Eligibility IDs</div>
          <div className={`ci ${profile.account_number ? 'done' : 'missing'}`}>Banking Details</div>
          <div className={`ci ${documents.length > 0 ? 'partial' : 'missing'}`}>Documents ({documents.length} uploaded)</div>
          <div className={`ci ${profile.institution_name ? 'done' : 'missing'}`}>Enrollment info</div>
          <div className={`ci ${profile.mailing_address ? 'done' : 'missing'}`}>Mail Cheque</div>
        </div>
      </div>

      {/* ── ACTION ALERT ── */}
      {(!profile.account_number || !profile.bank_name) && (
        <div className="alert-banner warn">
          <Ic.AlertTriangle size={16} />
          <div>
            <strong>Action required:</strong> Your banking details are incomplete. Payments cannot be processed until valid banking information is verified. 
            <span className="alert-banner-link" onClick={() => handleEditClick('banking')}> Add Banking Info...</span>
          </div>
        </div>
      )}

      {/* ── SECTION 1: PERSONAL INFORMATION ── */}
      <div className="profile-section">
        <div className="profile-section-header">
          <div className="profile-section-title">Personal Information</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="sensitivity-tag st-standard">STANDARD SENSITIVITY</span>
            <button className="section-edit-btn" onClick={() => handleEditClick('personal')}>
              {hasFormA ? 'Edit Additional Info' : 'Edit'}
            </button>
          </div>
        </div>
        <div className="profile-grid-4">
          {renderField('Legal First Name', profile.full_name?.split(' ')[0])}
          {renderField('Legal Last Name', profile.full_name?.split(' ').slice(1).join(' '))}
          {renderField('Preferred Name', profile.preferred_name)}
          {renderField('Date of Birth', profile.dob)}
          {renderField('Gender', profile.gender)}
          {renderField('Pronouns', profile.pronouns)}
          {renderField('Phone Number', profile.phone)}
          {renderField('Email Address', profile.email)}
          {renderField('Alternate Phone', profile.alternate_phone)}
          {renderField('Mailing Address', profile.mailing_address, 2)}
          {renderField('Town / City', profile.town_city)}
          {renderField('Postal Code', profile.postal_code)}
          {renderField('Number of Dependents', profile.num_dependents)}
          {renderField('Dependent Ages', profile.dependent_ages)}
          {renderField('Disability Accommodation', profile.disability_accommodation, 2)}
        </div>
      </div>

      {/* ── SECTION 2: ELIGIBILITY IDENTIFIERS ── */}
      <div className="profile-section">
        <div className="profile-section-header">
          <div className="profile-section-title">Eligibility Identifiers</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="sensitivity-tag st-high">HIGH SENSITIVITY</span>
            {hasFormA ? (
              <span className="p-val muted" style={{ fontSize: '11px', color: '#64748b' }}>Sourced from Admission Application</span>
            ) : (
              <button className="section-edit-btn" onClick={() => handleEditClick('eligibility')}>Edit</button>
            )}
          </div>
        </div>
        <div className="info-bar">
          These fields are derived from your signup eligibility answers and verified by DGG staff. Do not alter without uploading supporting documentation.
        </div>
        <div className="profile-grid-4">

          {/* Q1 — Indian Act registration */}
          <div className="profile-field">
            <div className="p-label">Indian Act Registration (Q1)</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.is_indian_act_registered === null || profile.is_indian_act_registered === undefined
                ? <span className="p-val muted">Not answered</span>
                : profile.is_indian_act_registered
                  ? <><span style={{ color: '#166534', fontWeight: 700 }}>Yes — Registered</span><span className="status-pill verified">✓</span></>
                  : <span style={{ color: '#991b1b', fontWeight: 700 }}>No — Not registered</span>
              }
            </div>
          </div>

          {/* Q2 — Délınę Beneficiary */}
          <div className="profile-field">
            <div className="p-label">Délı̨nę Beneficiary Status (Q2)</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.is_deline_beneficiary === null || profile.is_deline_beneficiary === undefined
                ? <span className="p-val muted">Not answered</span>
                : profile.is_deline_beneficiary
                  ? <><span style={{ color: '#166534', fontWeight: 700 }}>Yes — Beneficiary</span><span className="status-pill verified">✓</span></>
                  : <span style={{ color: '#991b1b', fontWeight: 700 }}>No — Not a beneficiary</span>
              }
            </div>
          </div>

          {/* Q3 — SFA status */}
          <div className="profile-field">
            <div className="p-label">GNWT Student Financial Assistance (Q3)</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {!profile.financial_assistance_status
                ? <span className="p-val muted">Not answered</span>
                : profile.financial_assistance_status === 'SFA Active'
                  ? <><span style={{ color: '#92400e', fontWeight: 700 }}>Yes — Receiving SFA</span><span className="status-pill" style={{ background: '#fef3c7', color: '#92400e' }}>ACTIVE</span></>
                  : <><span style={{ color: '#166534', fontWeight: 700 }}>No — Not receiving SFA</span><span className="status-pill verified">✓</span></>
              }
            </div>
          </div>

          {/* Q4 — Residence */}
          <div className="profile-field">
            <div className="p-label">Province / Territory of Residence (Q4)</div>
            <div className="p-val">
              {!profile.province_of_residence
                ? <span className="p-val muted">Not answered</span>
                : profile.province_of_residence === 'nwt'
                  ? 'Northwest Territories'
                  : profile.province_of_residence === 'other'
                    ? 'Other Canadian Province / Territory'
                    : 'Outside Canada'
              }
            </div>
          </div>

          {/* Beneficiary # */}
          <div className="profile-field">
            <div className="p-label">Deline Beneficiary #</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.beneficiary_number || <span className="p-val muted" style={{ fontSize: '10px' }}>NOT PROVIDED</span>}
              {profile.beneficiary_number && <span className="status-pill verified">✓ VERIFIED</span>}
            </div>
          </div>

          <div className="profile-field">
            <div className="p-label">System Student ID</div>
            <div className="p-val" style={{ fontWeight: '700', color: '#1e293b' }}>
              {getStudentId()}
            </div>
          </div>

          {/* Treaty # */}
          <div className="profile-field">
            <div className="p-label">Indian Status / Treaty #</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.treaty_number || <span className="p-val muted">PENDING</span>}
              {profile.treaty_number && <span className="status-pill verified">✓ VERIFIED</span>}
            </div>
          </div>

          {/* Funding streams */}
          <div className="profile-field">
            <div className="p-label">Primary Funding Stream</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.primary_stream
                ? <><span style={{ fontWeight: 700 }}>{profile.primary_stream}</span><span className="status-pill verified">ASSIGNED</span></>
                : <span className="p-val muted">Not determined</span>
              }
            </div>
          </div>

          <div className="profile-field">
            <div className="p-label">Secondary Funding Stream</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.secondary_stream
                ? <><span style={{ fontWeight: 700 }}>{profile.secondary_stream}</span><span className="status-pill verified">ASSIGNED</span></>
                : <span className="p-val muted">None</span>
              }
            </div>
          </div>

          {/* UPi */}
          <div className="profile-field span-2">
            <div className="p-label">Unique Personal Identifier (UPi)</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div className="p-val st-extreme" style={{ fontFamily: 'monospace', letterSpacing: '2px' }}>
                {showUPi ? (profile.upi || 'NOT ISSUED') : '••••••••••••'}
              </div>
              <button className="section-edit-btn" style={{ padding: '2px 8px' }} onClick={() => setShowUPi(!showUPi)}>
                {showUPi ? 'Hide' : 'Reveal'}
              </button>
            </div>
          </div>

        </div>
      </div>

      {/* ── SECTION 3: BANKING & PAYMENT DETAILS ── */}
      <div className="profile-section">
        <div className="profile-section-header">
          <div className="profile-section-title">Banking & Payment Details</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="sensitivity-tag st-high">HIGH SENSITIVITY</span>
            <span className={`status-pill ${profile.account_number ? 'verified' : 'required'}`}>
              {profile.account_number ? '✓ COMPLETE' : '! INCOMPLETE'}
            </span>
            {hasFormA ? (
              <span className="p-val muted" style={{ fontSize: '11px', color: '#64748b' }}>Sourced from Admission Application</span>
            ) : (
              <button className="section-edit-btn" onClick={() => handleEditClick('banking')}>ADD / UPDATE</button>
            )}
          </div>
        </div>
        <div className="info-bar warn">
          All payments are by direct deposit only; a void cheque is required for verification. Banking details are encrypted and never shared with third parties.
        </div>
        <div className="profile-grid-4">
          {renderField('Financial Institution', profile.bank_name)}
          {renderField('Account Holder Name', profile.account_holder_name || profile.full_name)}
          {renderField('Account Type', profile.account_type || 'Direct Deposit')}
          {renderField('Transit Number (5 Digits)', profile.transit_number)}
          {renderField('Institution Number (3 Digits)', profile.inst_number)}
          {renderField('Account Number', profile.account_number ? `••••${profile.account_number.slice(-4)}` : null)}
          <div className="profile-field span-4">
            <div className="p-label">Void Cheque</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className={`status-pill ${isDocVerified('cheque') ? 'verified' : 'required'}`}>
                {isDocVerified('cheque') ? 'UPLOADED' : 'REQUIRED'}
              </span>
              <span className="p-val muted" style={{ fontSize: '11px' }}>
                {isDocVerified('cheque')
                  ? `File on record: ${documents.find(d => (d.category || '').toLowerCase().includes('cheque'))?.name || 'void cheque'}`
                  : 'No file uploaded'}
              </span>
              <label className="section-edit-btn" style={{ cursor: 'pointer' }}>
                {isUploading ? 'Uploading...' : (isDocVerified('cheque') ? 'Replace Void Cheque' : 'Upload Void Cheque')}
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={(e) => handleFileUpload(e, 'Void Cheque')}
                  style={{ display: 'none' }}
                  disabled={isUploading}
                />
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* ── SECTION 4: ENROLLMENT INFORMATION ── */}
      <div className="profile-section">
        <div className="profile-section-header">
          <div className="profile-section-title">Enrollment Information</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="sensitivity-tag st-standard">STANDARD SENSITIVITY</span>
            {hasFormA ? (
              <span className="p-val muted" style={{ fontSize: '11px', color: '#64748b' }}>Sourced from Admission Application</span>
            ) : (
              <button className="section-edit-btn" onClick={() => handleEditClick('enrollment')}>Edit</button>
            )}
          </div>
        </div>
        <div className="info-bar" style={{ background: '#eff6ff', color: '#1e40af' }}>
          Enrollment details from your institution (confirmed via enrollment verification) determine eligibility transitions and payment calculations. Updates to this area may trigger an enrollment status review.
        </div>
        <div className="profile-grid-4">
          {renderField('Institution / Institute', profile.institute || profile.institution_name, 2)}
          {renderField('Program / Credential', profile.program_credential, 2)}
          {renderField('Current Semester', profile.current_semester)}
          <div className="profile-field">
            <div className="p-label">Enrollment Status</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="p-val" style={{ color: '#166534' }}>{profile.enrollment_status || 'NOT SET'}</span>
              <span className="status-pill verified">✓ CONFIRMED</span>
            </div>
          </div>
          {renderField('Course Load %', `${profile.course_load || 0}%`, 1)}
          {renderField('Program Type', profile.program_type)}
          {renderField('Expected Graduation', profile.expected_graduation_date)}
          {renderField('Period in program', profile.years_in_program)}
          {renderField('Institution Location', profile.institution_location)}
        </div>
      </div>

      {/* ── DOCUMENTS UPLOAD AREA ── */}
      <div className="profile-section">
        <div className="profile-section-header">
          <div className="profile-section-title">Documents & File Upload</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
             <label className="btn-auth-primary" style={{ cursor: 'pointer', padding: '6px 14px', fontSize: '11px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
               {isUploading ? 'Uploading...' : '+ Upload Document'}
               <input type="file" onChange={handleFileUpload} style={{ display: 'none' }} disabled={isUploading} />
             </label>
          </div>
        </div>
        {uploadMessage && (
          <div style={{ 
            fontSize: '11px', 
            padding: '8px 12px', 
            borderRadius: '4px', 
            marginBottom: '12px',
            background: uploadMessage.includes('success') ? '#f0fdf4' : '#fef2f2',
            color: uploadMessage.includes('success') ? '#166534' : '#991b1b',
            border: `1px solid ${uploadMessage.includes('success') ? '#bbf7d0' : '#fecaca'}`
          }}>
            {uploadMessage}
          </div>
        )}
        <div className="info-bar">
          Uploaded documents are reviewed by eligibility verification and award claims. Staff will review submitted documents manually; keep files under 10MB (PDF, JPG, PNG).
        </div>
        
        {documents.map((doc, i) => (
          <div key={i} className="doc-row">
            <div>
              <div className="doc-name">{doc.name}</div>
              <div className="doc-meta">{doc.category || 'General Document'} · Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className={`db-badge ${doc.is_verified ? 'db-verified' : 'db-uploaded'}`}>
                {doc.is_verified ? '✓ VERIFIED' : 'PENDING REVIEW'}
              </span>
              <a href={doc.file_url || doc.file} target="_blank" rel="noopener noreferrer" className="section-edit-btn" style={{ padding: '4px 10px', textDecoration: 'none' }}>View</a>
            </div>
          </div>
        ))}
        {documents.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: '#64748b', fontSize: '12px', border: '1px dashed #e2e8f0', borderRadius: '8px' }}>
            No documents uploaded yet.
          </div>
        )}
      </div>

      {/* ── MODALS ── */}
      {activeModal === 'personal' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={closeModal}>✕</button>
            <h3>Personal Information</h3>
            <p className="modal-sub">Basic student identity and contact information.</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              {!hasFormA && (
                <>
                  <div><label className="p-label" htmlFor="sp-firstName">Legal First Name</label><input id="sp-firstName" className="field-input" type="text" value={editData._firstName || ''} onChange={e => updateField('_firstName', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-lastName">Legal Last Name</label><input id="sp-lastName" className="field-input" type="text" value={editData._lastName || ''} onChange={e => updateField('_lastName', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-preferredName">Preferred Name</label><input id="sp-preferredName" className="field-input" type="text" value={editData.preferred_name || ''} onChange={e => updateField('preferred_name', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-dob">Date of Birth</label><input id="sp-dob" className="field-input" type="date" value={editData.dob || ''} onChange={e => updateField('dob', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-gender">Gender</label><input id="sp-gender" className="field-input" type="text" value={editData.gender || ''} onChange={e => updateField('gender', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-phone">Phone</label><input id="sp-phone" className="field-input" type="text" value={editData.phone || ''} onChange={e => updateField('phone', e.target.value)} /></div>
                  <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-mailingAddress">Mailing Address</label><textarea id="sp-mailingAddress" className="field-input" style={{ height: '60px' }} value={editData.mailing_address || ''} onChange={e => updateField('mailing_address', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-townCity">Town / City</label><input id="sp-townCity" className="field-input" type="text" value={editData.town_city || ''} onChange={e => updateField('town_city', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-postalCode">Postal Code</label><input id="sp-postalCode" className="field-input" type="text" value={editData.postal_code || ''} onChange={e => updateField('postal_code', e.target.value)} /></div>
                  <div><label className="p-label" htmlFor="sp-numDependents">Number of Dependents</label><input id="sp-numDependents" className="field-input" type="number" min="0" value={editData.num_dependents ?? ''} onChange={e => updateField('num_dependents', e.target.value === '' ? null : Number(e.target.value))} /></div>
                </>
              )}
              <div><label className="p-label" htmlFor="sp-pronouns">Pronouns</label><input id="sp-pronouns" className="field-input" type="text" value={editData.pronouns || ''} onChange={e => updateField('pronouns', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-altPhone">Alt Phone</label><input id="sp-altPhone" className="field-input" type="text" value={editData.alternate_phone || ''} onChange={e => updateField('alternate_phone', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-dependentAges">Dependent Ages</label><input id="sp-dependentAges" className="field-input" type="text" value={editData.dependent_ages || ''} onChange={e => updateField('dependent_ages', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-disability">Disability Accommodation</label><textarea id="sp-disability" className="field-input" style={{ height: '60px' }} value={editData.disability_accommodation || ''} onChange={e => updateField('disability_accommodation', e.target.value)} /></div>
            </div>
            {!hasFormA && (
              <div style={{ marginTop: '20px', padding: '12px', background: '#f8fafc', borderRadius: '6px', fontSize: '11px', color: '#64748b', border: '1px solid #e2e8f0' }}>
                <strong>Tip:</strong> You can also fill these details automatically by completing the <strong>Admission Application</strong>.
              </div>
            )}
            <button className="btn-auth-primary" style={{ width: '100%', marginTop: '16px' }} onClick={handleSave} disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
          </div>
        </div>
      )}

      {activeModal === 'banking' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={closeModal}>✕</button>
            <h3>Banking & Payment Details</h3>
            <p className="modal-sub">Electronic funds transfer (EFT) routing information.</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-bankName">Financial Institution</label><input id="sp-bankName" className="field-input" type="text" value={editData.bank_name || ''} onChange={e => updateField('bank_name', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-transitNumber">Transit # (5 digits)</label><input id="sp-transitNumber" className="field-input" type="text" maxLength={5} value={editData.transit_number || ''} onChange={e => updateField('transit_number', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-instNumber">Inst # (3 digits)</label><input id="sp-instNumber" className="field-input" type="text" maxLength={3} value={editData.inst_number || ''} onChange={e => updateField('inst_number', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-accountNumber">Account Number</label><input id="sp-accountNumber" className="field-input" type="text" value={editData.account_number || ''} onChange={e => updateField('account_number', e.target.value)} /></div>
            </div>
            <button className="btn-auth-primary" style={{ width: '100%' }} onClick={handleSave} disabled={isUpdating}>{isUpdating ? 'Saving Details...' : 'Save Banking Record'}</button>
          </div>
        </div>
      )}

      {activeModal === 'enrollment' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={closeModal}>✕</button>
            <h3>Enrollment Information</h3>
            <p className="modal-sub">Current academic placement and program details.</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-institute">Institution / Institute</label><input id="sp-institute" className="field-input" type="text" value={editData.institute || editData.institution_name || ''} onChange={e => { updateField('institute', e.target.value); updateField('institution_name', e.target.value); }} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-programCredential">Program / Credential</label><input id="sp-programCredential" className="field-input" type="text" value={editData.program_credential || ''} onChange={e => updateField('program_credential', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-currentSemester">Current Semester</label><input id="sp-currentSemester" className="field-input" type="text" value={editData.current_semester || ''} onChange={e => updateField('current_semester', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-enrollmentStatus">Enrollment Status</label><input id="sp-enrollmentStatus" className="field-input" type="text" value={editData.enrollment_status || ''} onChange={e => updateField('enrollment_status', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-courseLoad">Course Load %</label><input id="sp-courseLoad" className="field-input" type="number" value={editData.course_load || 100} onChange={e => updateField('course_load', parseInt(e.target.value))} /></div>
              <div><label className="p-label" htmlFor="sp-expectedGraduation">Expected Graduation</label><input id="sp-expectedGraduation" className="field-input" type="date" value={editData.expected_graduation_date || ''} onChange={e => updateField('expected_graduation_date', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-programType">Program Type</label><input id="sp-programType" className="field-input" type="text" value={editData.program_type || ''} onChange={e => updateField('program_type', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-yearsInProgram">Period in Program</label><input id="sp-yearsInProgram" className="field-input" type="text" value={editData.years_in_program || ''} onChange={e => updateField('years_in_program', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-institutionLocation">Institution Location</label><input id="sp-institutionLocation" className="field-input" type="text" value={editData.institution_location || ''} onChange={e => updateField('institution_location', e.target.value)} /></div>
            </div>
            <button className="btn-auth-primary" style={{ width: '100%' }} onClick={handleSave} disabled={isUpdating}>{isUpdating ? 'Updating Record...' : 'Save Enrollment'}</button>
          </div>
        </div>
      )}
      
      {activeModal === 'eligibility' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={closeModal}>✕</button>
            <h3>Eligibility Identifiers</h3>
            <p className="modal-sub">Signup answers are read-only. Beneficiary # and Treaty # can be updated with documentation.</p>
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '12px', marginBottom: '16px', fontSize: '11px', color: '#64748b' }}>
              <strong>From signup answers (read-only):</strong>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                <div><span style={{ fontWeight: 600 }}>Q1 — Indian Act:</span> {editData.is_indian_act_registered === true ? 'Yes' : editData.is_indian_act_registered === false ? 'No' : 'Not answered'}</div>
                <div><span style={{ fontWeight: 600 }}>Q2 — Beneficiary:</span> {editData.is_deline_beneficiary === true ? 'Yes' : editData.is_deline_beneficiary === false ? 'No' : 'Not answered'}</div>
                <div><span style={{ fontWeight: 600 }}>Q3 — SFA:</span> {editData.financial_assistance_status || 'Not answered'}</div>
                <div><span style={{ fontWeight: 600 }}>Q4 — Residence:</span> {editData.province_of_residence === 'nwt' ? 'NWT' : editData.province_of_residence === 'other' ? 'Other Province/Territory' : editData.province_of_residence === 'outside' ? 'Outside Canada' : 'Not answered'}</div>
                <div><span style={{ fontWeight: 600 }}>Primary Stream:</span> {editData.primary_stream || 'Not determined'}</div>
                <div><span style={{ fontWeight: 600 }}>Secondary Stream:</span> {editData.secondary_stream || 'None'}</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              <div><label className="p-label" htmlFor="sp-beneficiaryNumber">Beneficiary # <span style={{ color: '#64748b', fontWeight: 400 }}>(editable)</span></label><input id="sp-beneficiaryNumber" className="field-input" type="text" value={editData.beneficiary_number || ''} onChange={e => updateField('beneficiary_number', e.target.value)} /></div>
              <div><label className="p-label" htmlFor="sp-treatyNumber">Treaty # <span style={{ color: '#64748b', fontWeight: 400 }}>(editable)</span></label><input id="sp-treatyNumber" className="field-input" type="text" value={editData.treaty_number || ''} onChange={e => updateField('treaty_number', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label" htmlFor="sp-upi">UPi <span style={{ color: '#64748b', fontWeight: 400 }}>(staff-issued)</span></label><input id="sp-upi" className="field-input" type="text" value={editData.upi || ''} onChange={e => updateField('upi', e.target.value)} /></div>
            </div>
            <button className="btn-auth-primary" style={{ width: '100%' }} onClick={handleSave} disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Identifiers'}</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default StudentProfile;
