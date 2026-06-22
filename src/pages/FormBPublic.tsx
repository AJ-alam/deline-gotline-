/**
 * Public Form B — Enrollment Verification
 * Accessed by registrar via a token link (no login required).
 * GET  /api/forms/form-b/<token>/  → pre-filled data
 * POST /api/forms/form-b/<token>/  → submit response
 */
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../config/api';
import * as Ic from '../components/Icons';

const api = axios.create({ baseURL: API_BASE_URL });

const FormBPublic: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<any>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const [form, setForm] = useState({
    is_enrolled: true,
    enrollment_status: 'Full-time',
    course_load_percent: '',
    confirmed_program: '',
    confirmed_sem_start: '',
    confirmed_sem_end: '',
    official_tuition: '',
    registrar_name: '',
    registrar_title: '',
    registrar_notes: '',
  });

  useEffect(() => {
    if (!token) return;
    api.get(`/forms/form-b/${token}/`)
      .then(res => {
        const d = res.data;
        if (d.already_submitted) {
          setSubmitted(true);
          setSuccessMsg('This enrollment verification has already been submitted. Thank you.');
          setLoading(false);
          return;
        }
        setPrefill(d);
        setForm(prev => ({
          ...prev,
          confirmed_program: d.program || '',
          confirmed_sem_start: d.sem_start || '',
          confirmed_sem_end: d.sem_end || '',
        }));
        setLoading(false);
      })
      .catch(err => {
        setError(err.response?.data?.error || 'Invalid or expired link.');
        setLoading(false);
      });
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.registrar_name.trim()) {
      alert('Please enter your name before submitting.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post(`/forms/form-b/${token}/`, form);
      setSuccessMsg(res.data.message || 'Submitted successfully. Thank you.');
      setSubmitted(true);
    } catch (err: any) {
      alert(err.response?.data?.error || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 14px', border: '1px solid #e2e8f0',
    borderRadius: '6px', fontSize: '14px', boxSizing: 'border-box',
    fontFamily: 'inherit', marginTop: '4px',
  };
  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: '12px', fontWeight: '700',
    color: '#374151', marginBottom: '2px', marginTop: '16px',
  };

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f1f5f9' }}>
      <div style={{ fontSize: '16px', color: '#64748b' }}>Loading enrollment verification form…</div>
    </div>
  );

  if (error) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f1f5f9' }}>
      <div style={{ background: '#fff', padding: '40px', borderRadius: '12px', maxWidth: '480px', textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
        <div style={{ marginBottom: '16px', color: '#991b1b' }}><Ic.AlertTriangle size={48} /></div>
        <h2 style={{ color: '#991b1b', marginBottom: '12px' }}>Link Invalid or Expired</h2>
        <p style={{ color: '#64748b', lineHeight: '1.6' }}>{error}</p>
        <p style={{ color: '#64748b', fontSize: '13px', marginTop: '16px' }}>
          Please contact the DGG Education Department at <strong>director.education@gov.deline.ca</strong>
        </p>
      </div>
    </div>
  );

  if (submitted) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f1f5f9' }}>
      <div style={{ background: '#fff', padding: '48px', borderRadius: '12px', maxWidth: '520px', textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
        <div style={{ marginBottom: '20px', color: '#166534' }}><Ic.CheckCircle size={56} /></div>
        <h2 style={{ color: '#166534', marginBottom: '12px', fontSize: '22px' }}>Verification Submitted</h2>
        <p style={{ color: '#374151', lineHeight: '1.7', fontSize: '15px' }}>{successMsg}</p>
        <p style={{ color: '#64748b', fontSize: '13px', marginTop: '20px' }}>
          You may close this window.
        </p>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: '100vh', background: '#f1f5f9', padding: '32px 16px' }}>
      <div style={{ maxWidth: '680px', margin: '0 auto' }}>

        {/* Header */}
        <div style={{ background: '#1e293b', borderRadius: '12px 12px 0 0', padding: '28px 36px' }}>
          <h1 style={{ color: '#e5a662', margin: 0, fontSize: '20px', fontWeight: '800' }}>
            Délı̨nę Got'ı̨nę Government
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.6)', margin: '6px 0 0', fontSize: '13px' }}>
            Education &amp; Training Department — Enrollment Verification
          </p>
        </div>

        <div style={{ background: '#fff', borderRadius: '0 0 12px 12px', padding: '36px', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>

          <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '16px', marginBottom: '28px' }}>
            <p style={{ margin: 0, fontSize: '13px', color: '#1e40af', lineHeight: '1.6' }}>
              <strong>Dear Registrar,</strong><br />
              The DGG Student Funding Program requests your verification of the following student's enrollment.
              Please review the pre-filled information, make any corrections, and submit this form.
              Reference: <strong>{prefill?.reference}</strong>
            </p>
          </div>

          {/* Student info (read-only) */}
          <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#1e293b', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Student Information (Pre-filled)
          </h3>
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', marginBottom: '28px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              {[
                ['Student Name', prefill?.student_name],
                ['Institution', prefill?.institution],
                ['Program', prefill?.program],
                ['Semester Start', prefill?.sem_start],
                ['Semester End', prefill?.sem_end],
              ].map(([label, value]) => (
                <tr key={label as string}>
                  <td style={{ padding: '6px 0', color: '#64748b', width: '160px', fontWeight: '600' }}>{label}</td>
                  <td style={{ padding: '6px 0', color: '#1e293b' }}>{value || '—'}</td>
                </tr>
              ))}
            </table>
          </div>

          {/* Registrar form */}
          <form onSubmit={handleSubmit}>
            <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#1e293b', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Verification Details
            </h3>

            <label style={labelStyle}>Is this student currently enrolled in good standing? *</label>
            <div style={{ display: 'flex', gap: '24px', marginTop: '8px' }}>
              {[true, false].map(val => (
                <label key={String(val)} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
                  <input type="radio" name="is_enrolled" checked={form.is_enrolled === val}
                    onChange={() => setForm({ ...form, is_enrolled: val })} />
                  {val ? 'Yes — Enrolled' : 'No — Not Enrolled'}
                </label>
              ))}
            </div>

            <label htmlFor="fb-enrollmentStatus" style={labelStyle}>Enrollment Status *</label>
            <select id="fb-enrollmentStatus" style={inputStyle} value={form.enrollment_status}
              onChange={e => setForm({ ...form, enrollment_status: e.target.value })}>
              <option value="Full-time">Full-time</option>
              <option value="Part-time">Part-time</option>
              <option value="Co-op">Co-op / Work Term</option>
            </select>

            <label htmlFor="fb-courseLoad" style={labelStyle}>Course Load (%)</label>
            <input id="fb-courseLoad" style={inputStyle} type="number" min="0" max="100" placeholder="e.g. 100"
              value={form.course_load_percent}
              onChange={e => setForm({ ...form, course_load_percent: e.target.value })} />

            <label htmlFor="fb-confirmedProgram" style={labelStyle}>Confirmed Program Name *</label>
            <input id="fb-confirmedProgram" style={inputStyle} type="text" value={form.confirmed_program}
              onChange={e => setForm({ ...form, confirmed_program: e.target.value })} required />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <label htmlFor="fb-semStart" style={labelStyle}>Confirmed Semester Start *</label>
                <input id="fb-semStart" style={inputStyle} type="text" placeholder="YYYY-MM-DD" value={form.confirmed_sem_start}
                  onChange={e => setForm({ ...form, confirmed_sem_start: e.target.value })} required />
              </div>
              <div>
                <label htmlFor="fb-semEnd" style={labelStyle}>Confirmed Semester End *</label>
                <input id="fb-semEnd" style={inputStyle} type="text" placeholder="YYYY-MM-DD" value={form.confirmed_sem_end}
                  onChange={e => setForm({ ...form, confirmed_sem_end: e.target.value })} required />
              </div>
            </div>

            <label htmlFor="fb-officialTuition" style={labelStyle}>Official Tuition Amount (CAD $) *</label>
            <input id="fb-officialTuition" style={inputStyle} type="number" min="0" step="0.01" placeholder="e.g. 3500.00"
              value={form.official_tuition}
              onChange={e => setForm({ ...form, official_tuition: e.target.value })} required />

            <label htmlFor="fb-registrarNotes" style={labelStyle}>Additional Notes (optional)</label>
            <textarea id="fb-registrarNotes" style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
              placeholder="Any additional information relevant to this student's enrollment…"
              value={form.registrar_notes}
              onChange={e => setForm({ ...form, registrar_notes: e.target.value })} />

            <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#1e293b', margin: '28px 0 4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Registrar Signature
            </h3>

            <label htmlFor="fb-registrarName" style={labelStyle}>Your Full Name *</label>
            <input id="fb-registrarName" style={inputStyle} type="text" placeholder="e.g. Jane Smith"
              value={form.registrar_name}
              onChange={e => setForm({ ...form, registrar_name: e.target.value })} required />

            <label htmlFor="fb-registrarTitle" style={labelStyle}>Your Title / Position</label>
            <input id="fb-registrarTitle" style={inputStyle} type="text" placeholder="e.g. Registrar, Aurora College"
              value={form.registrar_title}
              onChange={e => setForm({ ...form, registrar_title: e.target.value })} />

            <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '8px', padding: '14px', margin: '24px 0' }}>
              <p style={{ margin: 0, fontSize: '12px', color: '#92400e', lineHeight: '1.6' }}>
                By submitting this form, you confirm that the information provided is accurate to the best of your knowledge.
                This verification will be used to determine the student's eligibility for educational funding.
              </p>
            </div>

            <button type="submit" disabled={submitting}
              style={{
                width: '100%', padding: '14px', background: submitting ? '#94a3b8' : '#1e293b',
                color: '#e5a662', border: 'none', borderRadius: '8px', fontSize: '15px',
                fontWeight: '800', cursor: submitting ? 'not-allowed' : 'pointer', letterSpacing: '0.5px',
              }}>
              {submitting ? 'Submitting…' : 'Submit Enrollment Verification →'}
            </button>
          </form>

          <p style={{ textAlign: 'center', fontSize: '11px', color: '#94a3b8', marginTop: '24px' }}>
            Questions? Contact the DGG Education Department at <strong>director.education@gov.deline.ca</strong>
          </p>
        </div>
      </div>
    </div>
  );
};

export default FormBPublic;
