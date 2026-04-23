import React, { useState, useEffect } from 'react';
import API from '../api/client';
import '../styles/profile.css';

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

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [userResp, docsResp] = await Promise.all([
          API.getMe(),
          API.getUserDocuments()
        ]);
        setProfile(userResp);
        setDocuments(Array.isArray(docsResp) ? docsResp : []);
      } catch (err) {
        console.error('Failed to fetch profile data:', err);
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

  // ✅ FIX: use functional updater so each keystroke always
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', file.name);
    formData.append('category', 'Profile Upload');

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

  if (!profile) return <div style={{ padding: '40px', textAlign: 'center' }}>Loading profile record...</div>;

  return (
    <div className="profile-container fade-in" style={{ paddingBottom: '60px' }}>
      
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
          <span>⚠️</span>
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
            <button className="section-edit-btn" onClick={() => handleEditClick('personal')}>Edit</button>
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
            <button className="section-edit-btn" onClick={() => handleEditClick('eligibility')}>Edit</button>
          </div>
        </div>
        <div className="info-bar">
          These fields are verified by DGG staff against official registries. Do not alter them without uploading supporting documentation; changes larger than once per year require DFN authorization.
        </div>
        <div className="profile-grid-4">
          <div className="profile-field">
            <div className="p-label">Deline Beneficiary #</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.beneficiary_number || 'PENDING'}
              {profile.beneficiary_number && <span className="status-pill verified">✓ VERIFIED</span>}
            </div>
          </div>
          <div className="profile-field">
            <div className="p-label">Indian Status / Treaty #</div>
            <div className="p-val" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {profile.treaty_number || 'PENDING'}
              {profile.treaty_number && <span className="status-pill verified">✓ VERIFIED</span>}
            </div>
          </div>
          {renderField('Primary Funding Source', profile.primary_stream, 2)}
          
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
          {renderField('Replacement Financial Assistance', profile.financial_assistance_status, 2)}
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
            <button className="section-edit-btn" onClick={() => handleEditClick('banking')}>ADD / UPDATE</button>
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
                {isDocVerified('cheque') ? 'File on record: void_cheque.pdf' : 'No file uploaded'}
              </span>
              <button className="section-edit-btn" onClick={() => window.location.href='/dashboard/documents'}>Upload Void Cheque</button>
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
            <button className="section-edit-btn" onClick={() => handleEditClick('enrollment')}>Edit</button>
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
              <a href={doc.file} target="_blank" rel="noopener noreferrer" className="section-edit-btn" style={{ padding: '4px 10px', textDecoration: 'none' }}>View</a>
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
              <div><label className="p-label">Legal First Name</label><input className="field-input" type="text" value={editData._firstName || ''} onChange={e => updateField('_firstName', e.target.value)} /></div>
              <div><label className="p-label">Legal Last Name</label><input className="field-input" type="text" value={editData._lastName || ''} onChange={e => updateField('_lastName', e.target.value)} /></div>
              <div><label className="p-label">Preferred Name</label><input className="field-input" type="text" value={editData.preferred_name || ''} onChange={e => updateField('preferred_name', e.target.value)} /></div>
              <div><label className="p-label">Date of Birth</label><input className="field-input" type="date" value={editData.dob || ''} onChange={e => updateField('dob', e.target.value)} /></div>
              <div><label className="p-label">Gender</label><input className="field-input" type="text" value={editData.gender || ''} onChange={e => updateField('gender', e.target.value)} /></div>
              <div><label className="p-label">Pronouns</label><input className="field-input" type="text" value={editData.pronouns || ''} onChange={e => updateField('pronouns', e.target.value)} /></div>
              <div><label className="p-label">Phone</label><input className="field-input" type="text" value={editData.phone || ''} onChange={e => updateField('phone', e.target.value)} /></div>
              <div><label className="p-label">Alt Phone</label><input className="field-input" type="text" value={editData.alternate_phone || ''} onChange={e => updateField('alternate_phone', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Mailing Address</label><textarea className="field-input" style={{ height: '60px' }} value={editData.mailing_address || ''} onChange={e => updateField('mailing_address', e.target.value)} /></div>
              <div><label className="p-label">Town / City</label><input className="field-input" type="text" value={editData.town_city || ''} onChange={e => updateField('town_city', e.target.value)} /></div>
              <div><label className="p-label">Postal Code</label><input className="field-input" type="text" value={editData.postal_code || ''} onChange={e => updateField('postal_code', e.target.value)} /></div>
            </div>
            <button className="btn-auth-primary" style={{ width: '100%' }} onClick={handleSave} disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Changes'}</button>
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
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Financial Institution</label><input className="field-input" type="text" value={editData.bank_name || ''} onChange={e => updateField('bank_name', e.target.value)} /></div>
              <div><label className="p-label">Transit # (5 digits)</label><input className="field-input" type="text" maxLength={5} value={editData.transit_number || ''} onChange={e => updateField('transit_number', e.target.value)} /></div>
              <div><label className="p-label">Inst # (3 digits)</label><input className="field-input" type="text" maxLength={3} value={editData.inst_number || ''} onChange={e => updateField('inst_number', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Account Number</label><input className="field-input" type="text" value={editData.account_number || ''} onChange={e => updateField('account_number', e.target.value)} /></div>
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
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Institution / Institute</label><input className="field-input" type="text" value={editData.institute || editData.institution_name || ''} onChange={e => { updateField('institute', e.target.value); updateField('institution_name', e.target.value); }} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Program / Credential</label><input className="field-input" type="text" value={editData.program_credential || ''} onChange={e => updateField('program_credential', e.target.value)} /></div>
              <div><label className="p-label">Current Semester</label><input className="field-input" type="text" value={editData.current_semester || ''} onChange={e => updateField('current_semester', e.target.value)} /></div>
              <div><label className="p-label">Enrollment Status</label><input className="field-input" type="text" value={editData.enrollment_status || ''} onChange={e => updateField('enrollment_status', e.target.value)} /></div>
              <div><label className="p-label">Course Load %</label><input className="field-input" type="number" value={editData.course_load || 100} onChange={e => updateField('course_load', parseInt(e.target.value))} /></div>
              <div><label className="p-label">Expected Graduation</label><input className="field-input" type="date" value={editData.expected_graduation_date || ''} onChange={e => updateField('expected_graduation_date', e.target.value)} /></div>
              <div><label className="p-label">Program Type</label><input className="field-input" type="text" value={editData.program_type || ''} onChange={e => updateField('program_type', e.target.value)} /></div>
              <div><label className="p-label">Period in Program</label><input className="field-input" type="text" value={editData.years_in_program || ''} onChange={e => updateField('years_in_program', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Institution Location</label><input className="field-input" type="text" value={editData.institution_location || ''} onChange={e => updateField('institution_location', e.target.value)} /></div>
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
            <p className="modal-sub">Government identity and program eligibility markers.</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              <div><label className="p-label">Beneficiary #</label><input className="field-input" type="text" value={editData.beneficiary_number || ''} onChange={e => updateField('beneficiary_number', e.target.value)} /></div>
              <div><label className="p-label">Treaty #</label><input className="field-input" type="text" value={editData.treaty_number || ''} onChange={e => updateField('treaty_number', e.target.value)} /></div>
              <div><label className="p-label">UPi</label><input className="field-input" type="text" value={editData.upi || ''} onChange={e => updateField('upi', e.target.value)} /></div>
              <div><label className="p-label">Primary Funding Source</label><input className="field-input" type="text" value={editData.primary_stream || ''} onChange={e => updateField('primary_stream', e.target.value)} /></div>
              <div style={{ gridColumn: 'span 2' }}><label className="p-label">Financial Asst. Status</label><input className="field-input" type="text" value={editData.financial_assistance_status || ''} onChange={e => updateField('financial_assistance_status', e.target.value)} /></div>
            </div>
            <button className="btn-auth-primary" style={{ width: '100%' }} onClick={handleSave} disabled={isUpdating}>{isUpdating ? 'Saving...' : 'Save Identifiers'}</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default StudentProfile;
