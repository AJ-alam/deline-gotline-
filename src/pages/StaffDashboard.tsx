import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api/client';
import { jsPDF } from 'jspdf';
import * as XLSX from 'xlsx';
import '../styles/staff.css';

// Admin Icons
const AdminIcons = {
  Dashboard: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="7" height="9" x="3" y="3" rx="1" /><rect width="7" height="5" x="14" y="3" rx="1" /><rect width="7" height="9" x="14" y="12" rx="1" /><rect width="7" height="5" x="3" y="16" rx="1" /></svg>
  ),
  Apps: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14.5 2 14.5 7.5 20 7.5" /></svg>
  ),
  Policy: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" /></svg>
  ),
  Reports: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83" /><path d="M22 12A10 10 0 0 0 12 2v10z" /></svg>
  ),
  Director: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
  ),
  ChevronLeft: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
  )
};

type ViewMode = 'dashboard' | 'applications' | 'detail' | 'policy' | 'reports' | 'director' | 'payments' | 'director-queue' | 'director-detail' | 'appeals';

const StaffDashboard: React.FC = () => {
  const [role, setRole] = useState<'ssw' | 'director'>(
    (localStorage.getItem('dgg_role')?.toLowerCase() === 'director') ? 'director' : 'ssw'
  );
  const [currentView, setCurrentView] = useState<ViewMode>(role === 'director' ? 'director-queue' : 'dashboard');
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [reportFundingType, setReportFundingType] = useState('all');
  const [reportSubFilter, setReportSubFilter] = useState('students');
  const [showFinanceModal, setShowFinanceModal] = useState(false);
  const [financeEmail, setFinanceEmail] = useState('finance@organization.com');
  const [isExporting, setIsExporting] = useState(false);
  const navigate = useNavigate();

  const [applications, setApplications] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payments, setPayments] = useState<any[]>([]);
  const [appeals, setAppeals] = useState<any[]>([]);
  const [userData, setUserData] = useState<any>(null);

  const fetchApplications = async () => {
    try {
      const resp = await API.getSubmissions() as any;
      setApplications(Array.isArray(resp) ? resp : []);
      
      const stats = await API.getDashboardStats() as any;
      setBackendStats(stats || null);

      const notifs = await API.getNotifications() as any;
      setNotifications(Array.isArray(notifs) ? notifs : []);

      // Verify role from profile to ensure absolute sync
      const me = await API.getMe() as any;
      setUserData(me);
      const mappedRole = me.role?.toLowerCase();

      if (mappedRole === 'director' && role !== 'director') {
        setRole('director');
        localStorage.setItem('dgg_role', 'director');
      } else if ((mappedRole === 'admin' || mappedRole === 'ssw') && role !== 'ssw') {
        setRole('ssw');
        localStorage.setItem('dgg_role', 'admin');
      }
    } catch (err: any) {
      console.error('Data sync failed:', err);
      // If it's a 401, the Axios interceptor will handle redirect
      setError(err.message || 'Failed to sync with database');
    } finally {
      setIsLoading(false);
    }
  };

  // ── FORCE STOP LOADER AFTER 3 SECONDS FOR UI RESPONSIVENESS ──
  useEffect(() => {
    const timer = setTimeout(() => {
      if (isLoading) setIsLoading(false);
    }, 3000);
    return () => clearTimeout(timer);
  }, [isLoading]);

  // ── POLLING FOR REAL-TIME UPDATES ──
  useEffect(() => {
    fetchApplications();
    const interval = setInterval(fetchApplications, 5000); // 5-second polling
    return () => clearInterval(interval);
  }, [reportFundingType]); // Re-fetch when funding type filter changes

  useEffect(() => {
    const fetchFinanceConfig = async () => {
      try {
        const settings = await API.getPolicySettings() as any;
        const config = settings.find((s: any) => s.section === 'system_config' && s.field_key === 'finance_email');
        if (config) setFinanceEmail(config.unit || 'finance@organization.com');
      } catch (e) {}
    };
    fetchFinanceConfig();
  }, []);

  const handleExcelExport = () => {
    setIsExporting(true);
    try {
      const exportData = payments.map(p => ({
        'Student ID': `DGG-${p.user.toString().padStart(5, '0')}`,
        'Student Full Name': userData?.full_name || 'Student', 
        'Funding Type': (p.payment_type || '').includes('DGGR') ? 'DGGR' : ((p.payment_type || '').includes('UCEPP') ? 'UCEPP' : 'CDFN'),
        'Approved Amount': parseFloat(p.amount),
        'Approval Date': new Date(p.date_issued).toLocaleDateString(),
        'Quarter': `Q${Math.floor(new Date(p.date_issued).getMonth() / 3) + 1}`,
        'Payment Status': p.status.toUpperCase()
      }));

      const worksheet = XLSX.utils.json_to_sheet(exportData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Approved Payments");
      XLSX.writeFile(workbook, `Approved_Payments_Report_${new Date().toISOString().split('T')[0]}.xlsx`);
      setShowFinanceModal(true);
    } catch (err) {
      alert("Export failed");
    } finally {
      setIsExporting(false);
    }
  };

  const [backendStats, setBackendStats] = useState<any>(null);

  const getStats = () => {
    if (!backendStats) return { totalApps: 0, approvedAmount: 0, underReview: 0, activeStudents: 0, pssspCount: 0, otherCount: 0, pssspPercent: 0, livingApps: 0, travelApps: 0, scholarshipApps: 0 };
    
    return { 
      totalApps: backendStats.total_submissions || 0, 
      approvedAmount: backendStats.total_funding_approved || 0, 
      underReview: (backendStats.submissions_by_status?.pending || 0) + (backendStats.submissions_by_status?.reviewed || 0) + (backendStats.submissions_by_status?.forwarded || 0), 
      activeStudents: backendStats.total_students || 0, 
      pssspCount: backendStats.submissions_by_form?.['FormA'] || 0, 
      otherCount: (backendStats.total_submissions || 0) - (backendStats.submissions_by_form?.['FormA'] || 0), 
      pssspPercent: (backendStats.total_submissions || 0) > 0 ? ((backendStats.submissions_by_form?.['FormA'] || 0) / backendStats.total_submissions) * 100 : 0, 
      livingApps: backendStats.submissions_by_status?.pending || 0, 
      travelApps: backendStats.submissions_by_form?.['FormE'] || 0, 
      scholarshipApps: backendStats.submissions_by_form?.['scholarship'] || 0 
    };
  };

  const stats = getStats();

  const [staffNote, setStaffNote] = useState('');

  const handleDecision = async (status: 'accepted' | 'rejected' | 'forwarded') => {
    if (!selectedAppId) return;
    const currentApp = applications.find(a => String(a.id) === String(selectedAppId));
    
    // Immutable storage: Capture auto-calculated total at time of approval
    let amountToSave = currentApp?.amount || 0;
    if (status === 'accepted') {
      const autoSuggested = calculateAutoFunding(currentApp);
      if (autoSuggested && !currentApp?.amount) {
        amountToSave = autoSuggested.total;
      }
    }

    try {
      await API.updateSubmissionStatus(Number(selectedAppId), status, {
        decision_notes: decisionNotes,
        amount: amountToSave
      });
      setShowConfirmModal(false);
      setDecisionNotes('');
      setCurrentView(role === 'director' ? 'director-queue' : 'applications');
      fetchApplications();
    } catch (err: any) {
      alert(err.message || 'Action failed');
    }
  };

  const handleShareView = async () => {
    if (!selectedAppId) return;
    try {
       const resp = await API.generateShareLink(Number(selectedAppId)) as any;
       const url = `${window.location.origin}/shared/${resp.token}`;
       await navigator.clipboard.writeText(url);
       alert('Secure share link (valid for 7 days) copied to clipboard!');
    } catch (err: any) {
       alert('Share failed: ' + err.message);
    }
  };

  const handleRequestInfo = async () => {
    if (!selectedAppId) return;
    try {
       await API.requestMoreInfo(Number(selectedAppId));
       alert('Application status updated to RE-OPENED and student notified.');
       fetchApplications();
    } catch (err: any) {
       alert('Action failed: ' + err.message);
    }
  };

  const handlePDFExport = () => {
    if (!selectedAppId) return;
    try {
      const app = applications.find(a => String(a.id) === String(selectedAppId));
      if (!app) {
        alert('Application data not found. Please refresh.');
        return;
      }

      console.log('Generating PDF for:', app.id);
      const doc = new jsPDF();
      doc.setFontSize(20);
      doc.text('DGG Application Summary', 20, 20);
      doc.setFontSize(12);
      doc.text(`Reference: # ${app.id}`, 20, 30);
      doc.text(`Student: ${app.student_details?.full_name || app.student_name || 'N/A'}`, 20, 40);
      doc.text(`Form: ${app.form_title || 'N/A'}`, 20, 50);
      doc.text(`Status: ${(app.status || 'pending').toUpperCase()}`, 20, 60);
      doc.text(`Submitted: ${app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : 'N/A'}`, 20, 70);
      
      doc.text('------------------------------------------------', 20, 80);
      doc.text('Decision Details:', 20, 90);
      doc.text(`Authorized Amount: $${app.amount || 0}`, 20, 100);
      doc.text(`Notes: ${app.decision_notes || 'None'}`, 20, 110);
      
      doc.save(`Application_${app.id}.pdf`);
    } catch (err: any) {
      console.error('PDF Export Error:', err);
      alert('PDF generation failed: ' + err.message);
    }
  };

  const handleAddNote = async () => {
    if (!selectedAppId || !staffNote.trim()) return;
    try {
      await API.addSubmissionNote(Number(selectedAppId), staffNote);
      setStaffNote('');
      fetchApplications(); // Refresh list to get new notes
    } catch (err: any) {
      alert(err.message || 'Failed to add note');
    }
  };

  const handleAppClick = (appId: number) => {
    setSelectedAppId(String(appId));
    setCurrentView(role === 'director' ? 'director-detail' : 'detail');
  };

  const [officeUseInputs, setOfficeUseInputs] = useState({ dateReceived: '', approvedBy: '', commitmentNum: '' });
  const [isSavingOffice, setIsSavingOffice] = useState(false);

  // ── POLICY SETTINGS STATE ──
  const [policySettings, setPolicySettings] = useState<Record<string, any[]>>({});
  const [isDirty, setIsDirty] = useState<Record<string, boolean>>({});
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    'application_deadlines': true // Open first by default
  });

  const getPolicySetting = (section: string, fieldKey: string): number => {
    const fields = policySettings[section] || [];
    const field = fields.find(f => f.field_key === fieldKey);
    return field ? parseFloat(field.value) : 0;
  };


  const fetchPolicySettings = async () => {
    try {
      const data = await API.getPolicySettings() as any;
      setPolicySettings(data || {});
      // Reset dirty state on fetch
      setIsDirty({});
    } catch (err) {
      console.error('Failed to fetch policy settings:', err);
    } 
  };

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (Object.values(isDirty).some(v => v)) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        return e.returnValue;
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  useEffect(() => {
    if (currentView === 'policy') {
      fetchPolicySettings();
    }
    if (currentView === 'payments') {
       API.getPayments().then(res => setPayments(Array.isArray(res) ? res : [])).catch(e => console.error('Payments fetch failed', e));
    }
    if (currentView === 'appeals') {
       API.getAppeals().then(res => setAppeals(Array.isArray(res) ? res : [])).catch(e => console.error('Appeals fetch failed', e));
    }
  }, [currentView]);

  useEffect(() => {
     if (selectedAppId) {
        const app = applications.find(a => Number(a.id) === Number(selectedAppId));
        if (app && app.office_use_data) {
           setOfficeUseInputs({
              dateReceived: app.office_use_data.dateReceived || '',
              approvedBy: app.office_use_data.approvedBy || '',
              commitmentNum: app.office_use_data.commitmentNum || ''
           });
        } else {
           setOfficeUseInputs({ dateReceived: '', approvedBy: '', commitmentNum: '' });
        }
     }
  }, [selectedAppId, applications]);

  const handleSaveOfficeUse = async () => {
     if (!selectedAppId) return;
     setIsSavingOffice(true);
     try {
       const app = applications.find(a => Number(a.id) === Number(selectedAppId));
       if (!app) throw new Error("Application not found in state");
       await API.updateSubmissionStatus(Number(selectedAppId), app.status, { office_use_data: officeUseInputs });
       alert('Office use data saved successfully');
       fetchApplications();
     } catch (err: any) {
       alert(err.message || 'Failed to save office use data');
     } finally {
       setIsSavingOffice(false);
     }
  };


  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const filteredApps = applications.filter(app => {
    const fullName = (app.student_details?.full_name || '').toLowerCase();
    const query = searchQuery.toLowerCase();
    const matchesSearch = fullName.includes(query) ||
      String(app.id).includes(query) ||
      (app.form_title || '').toLowerCase().includes(query);
    const matchesStatus = statusFilter === 'all' || app.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const selectedApp = applications.find(a => String(a.id) === String(selectedAppId));

  const calculateAutoFunding = (app: any) => {
    if (!app || !app.answers || !policySettings) return null;
    
    const student = app.student_details || {};
    const profile = student.profile || {};
    
    // helper to get answer by label (case-insensitive fuzzy match)
    const getAns = (label: string) => app.answers.find((a: any) => a.field_label?.toLowerCase().includes(label.toLowerCase()))?.answer_text;

    const stream = getAns('bursaryStream') || student.primary_stream || 'DGGR';
    const enrollment = getAns('enrollmentType')?.toLowerCase() || student.enrollment_status?.toLowerCase() || 'full-time';
    const isFullTime = enrollment.includes('full');
    const hasDeps = (getAns('hasDependents')?.toLowerCase() === 'yes') || (student.num_dependents > 0);
    const requestedTuition = parseFloat(getAns('tuition') || '0');
    const startStr = getAns('semStart');
    const endStr = getAns('semEnd');

    // 0. Eligibility Check (NWT SFA)
    const isNwtSfaEligible = profile.is_sfa_active || student.financial_assistance_status === 'Eligible';
    if ((stream.includes('PSSSP') || stream.includes('UCEPP')) && isNwtSfaEligible) {
      return {
        total: 0,
        ineligible: true,
        reason: 'Student is eligible for NWT SFA; PSSSP/UCEPP funding not applicable.'
      };
    }

    // 1. Duration Calculation
    let months = 4;
    if (startStr && endStr) {
      const start = new Date(startStr);
      const end = new Date(endStr);
      if (!isNaN(start.getTime()) && !isNaN(end.getTime())) {
        months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
        if (months <= 0) months = 4;
      }
    }

    // 2. Living Allowance
    let livingSection = 'dggr_living';
    if (stream.includes('PSSSP')) livingSection = 'psssp_living';
    else if (stream.includes('UCEPP')) livingSection = 'ucepp_living';

    const depKey = hasDeps ? 'with_dependents' : 'no_dependents';
    const loadKey = isFullTime ? 'fulltime' : 'parttime';
    const fieldKey = `${loadKey}_${depKey}`;
    
    const livingRate = getPolicySetting(livingSection, fieldKey);
    const totalLiving = livingRate * months;

    // 3. Tuition
    let tuitionSection = 'dggr_tuition';
    if (stream.includes('PSSSP')) tuitionSection = 'psssp_tuition';
    else if (stream.includes('UCEPP')) tuitionSection = 'ucepp_tuition';

    let tuitionLimit = 0;
    if (tuitionSection === 'psssp_tuition' || tuitionSection === 'ucepp_tuition') {
      tuitionLimit = getPolicySetting(tuitionSection, 'max_per_semester');
    } else {
      tuitionLimit = getPolicySetting('dggr_tuition', isFullTime ? 'fulltime_per_semester' : 'parttime_per_semester');
    }

    const finalTuition = requestedTuition > 0 ? Math.min(requestedTuition, tuitionLimit) : tuitionLimit;

    // 4. Extra Tuition (DGGR Only)
    let extraAmount = 0;
    if (stream.includes('DGGR') && requestedTuition > tuitionLimit) {
      const threshold = getPolicySetting('dggr_extra_tuition', 'threshold_per_semester');
      if (requestedTuition >= threshold) {
        const maxPercent = getPolicySetting('dggr_extra_tuition', 'max_percent_covered') / 100;
        const maxCap = getPolicySetting('dggr_extra_tuition', 'max_per_semester');
        extraAmount = Math.min((requestedTuition - tuitionLimit) * maxPercent, maxCap);
      }
    }

    // 5. Special Awards/Bursaries
    let specialAwards = 0;
    let specialNote = "";

    // Graduation Bursary (FormG)
    if (app.form_type === 'FormG') {
      const degreeType = getAns('degreeType') || student.program_credential;
      if (degreeType) {
        // Map common titles to field keys
        const mappedKey = degreeType.toLowerCase().replace(/ /g, '_');
        specialAwards = getPolicySetting('dggr_grad_bursary', mappedKey);
        specialNote = `Graduation Bursary: ${degreeType}`;
      }
    }

    // Academic Scholarship (GPA Check)
    const gpa = parseFloat(getAns('gpa') || '0');
    if (gpa > 0) {
      const highThreshold = getPolicySetting('dggr_academic_scholarship', 'high_threshold_percent');
      const midThresholdLower = getPolicySetting('dggr_academic_scholarship', 'mid_threshold_lower');
      const midThresholdUpper = getPolicySetting('dggr_academic_scholarship', 'mid_threshold_upper');

      if (gpa >= highThreshold) {
        specialAwards += getPolicySetting('dggr_academic_scholarship', 'high_achievement_award');
      } else if (gpa >= midThresholdLower && gpa <= midThresholdUpper) {
        specialAwards += getPolicySetting('dggr_academic_scholarship', 'mid_achievement_award');
      }
    }

    // Hardcoded Book Allowance Replacement
    const bookAllowance = getPolicySetting('eligibility_rules', 'min_program_weeks') > 0 ? 500 : 0; // Simplified for now, or use a specific field

    return {
      tuition: { 
        system: finalTuition, 
        requested: requestedTuition, 
        rule: `Max $${tuitionLimit} per semester` 
      },
      living: { 
        system: totalLiving, 
        rate: livingRate, 
        months, 
        rule: `$${livingRate}/mo for ${months} mons` 
      },
      books: {
        system: 500, // Move to system_config later if requested
        rule: '$500 per semester standard allowance'
      },
      special: {
        system: specialAwards,
        rule: specialNote
      },
      total: finalTuition + totalLiving + extraAmount + 500 + specialAwards,
      stream
    };
  };

  const autoSuggested = calculateAutoFunding(selectedApp);

  const getFormDisplayName = (title: string) => {
    const mapping: Record<string, string> = {
      'FormA': 'Admission Application',
      'FormB': 'Enrolment Verification',
      'FormC': 'Continuing Funding',
      'FormD': 'Information Update',
      'FormE': 'Travel Claim',
      'FormF': 'Practicum Report',
      'FormG': 'Graduation Award',
      'FormH': 'Appeal Request'
    };
    return mapping[title] || title;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending': return <span className="admin-badge badge-new">New Submission</span>;
      case 'reviewed': return <span className="admin-badge badge-review">SSW Reviewed</span>;
      case 'forwarded': return <span className="admin-badge badge-pending" style={{ background: '#e0e7ff', color: '#3730a3' }}>Pending Director</span>;
      case 'accepted': return <span className="admin-badge badge-approved">Approved</span>;
      case 'rejected': return <span className="admin-badge badge-denied">Rejected</span>;
      default: return <span className="admin-badge">{status.toUpperCase()}</span>;
    }
  };


  // Mock navigation helper
  const renderNavItem = (id: ViewMode, label: string, icon: React.ReactNode, badge?: number) => (
    <div
      className={`staff-nav-item ${currentView === id ? 'active' : ''}`}
      onClick={() => {
        setCurrentView(id);
        if (id !== 'detail') setSelectedAppId(null);
      }}
    >
      {icon} {label}
      {badge && <span className="staff-nav-badge">{badge}</span>}
    </div>
  );

  return (
    <div className="staff-portal-root">
      {/* Sidebar */}
      <div className="staff-sidebar">
        <div className="staff-sidebar-header">
          <div className="staff-user-block">
            <div className="staff-user-name">{userData?.full_name || (role === 'director' ? 'Director' : 'Staff')}</div>
            <div className="staff-user-role">{userData?.role === 'director' ? 'Director of Education' : 'Student Support Worker'}</div>
          </div>
        </div>

        <nav className="staff-nav">
          {role === 'director' ? (
            <>
              <div className="staff-nav-group">
                <div className="staff-nav-title">Main</div>
                {renderNavItem('dashboard', 'Dashboard', <AdminIcons.Dashboard />)}
                {renderNavItem('director-queue', 'Approval Queue', <AdminIcons.Apps />, applications.filter(a => a.status === 'forwarded').length)}
                {renderNavItem('applications', 'All Applications', <AdminIcons.Apps />)}
              </div>
              
              <div className="staff-nav-group">
                <div className="staff-nav-title">Governance</div>
                {renderNavItem('reports', 'Reports', <AdminIcons.Reports />)}
                {renderNavItem('policy', 'Policy Settings', <AdminIcons.Policy />)}
                {renderNavItem('appeals', 'Appeals', <AdminIcons.Apps />, 1)}
              </div>
            </>
          ) : (
            <>
              <div className="staff-nav-group">
                <div className="staff-nav-title">Main</div>
                {renderNavItem('dashboard', 'Dashboard', <AdminIcons.Dashboard />)}
                {renderNavItem('applications', 'All Applications', <AdminIcons.Apps />, applications.filter(a => a.status === 'pending').length)}
                {renderNavItem('payments', 'Payments', <AdminIcons.Dashboard />)}
              </div>

              <div className="staff-nav-group">
                <div className="staff-nav-title">Governance</div>
                {renderNavItem('reports', 'Reports', <AdminIcons.Reports />)}
                {renderNavItem('policy', 'Policy Settings', <AdminIcons.Policy />)}
              </div>
            </>
          )}
        </nav>

        <div style={{ marginTop: 'auto', padding: '24px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="staff-nav-item" onClick={() => navigate('/signin')}>
            🚪 Sign Out
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="staff-main">
        <header className="staff-topbar">
          <div className="staff-view-title">
            {currentView === 'dashboard' && (role === 'director' ? 'Director Overview' : 'Admin Overview')}
            {currentView === 'applications' && 'All Applications'}
            {currentView === 'detail' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button
                  onClick={() => setCurrentView('applications')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: 'inherit' }}
                >
                  <AdminIcons.ChevronLeft />
                </button>
                Reviewing {selectedAppId}
              </div>
            )}
            {currentView === 'director-detail' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: '800' }}>DIRECTOR</span>
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>—</span>
                <span style={{ fontWeight: '800' }}>{selectedAppId}</span>
              </div>
            )}
            {currentView === 'policy' && 'Policy Settings'}
            {currentView === 'reports' && 'Reports & Analytics'}
            {currentView === 'director-queue' && 'Approval Queue'}
            {currentView === 'director' && 'Director Approval Queue'}
          </div>

          <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
            {/* Notification Bell */}
            <div style={{ position: 'relative', cursor: 'pointer' }} onClick={() => setCurrentView('notifications' as any)}>
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#64748b' }}>
                <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
                <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
              </svg>
              {notifications.filter(n => !n.is_read).length > 0 && (
                <span style={{ position: 'absolute', top: '-4px', right: '-4px', background: '#e11d48', color: '#fff', fontSize: '10px', fontWeight: '800', padding: '2px 5px', borderRadius: '10px', border: '2px solid #fff' }}>
                  {notifications.filter(n => !n.is_read).length}
                </span>
              )}
            </div>

            <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '600' }}>FY 2025/2026</span>
            <div style={{ width: '1px', height: '20px', background: '#e2e8f0' }}></div>
            <button className="admin-badge badge-pending" style={{ border: 'none', cursor: 'pointer' }}>
              Support Active
            </button>
          </div>
        </header>

        <main className="staff-content">
          {isLoading && applications.length === 0 && (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
              <div className="admin-spinner" style={{ width: '24px', height: '24px', border: '2px solid #e2e8f0', borderTopColor: 'var(--admin-accent)', borderRadius: '50%', margin: '0 auto 12px', animation: 'spin 1s linear infinite' }}></div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              Loading staff portal data...
            </div>
          )}

          {error && !isLoading && (
            <div style={{ padding: '24px' }}>
              <div style={{ background: '#fff5f5', border: '1px solid #fed7d7', padding: '16px', borderRadius: '8px', color: '#c53030', fontSize: '13px' }}>
                <strong style={{ display: 'block', marginBottom: '4px' }}>Error Loading Data</strong>
                {error}
                <button onClick={fetchApplications} style={{ marginLeft: '12px', background: 'none', border: 'none', color: '#c53030', textDecoration: 'underline', fontWeight: '800', cursor: 'pointer' }}>Try Again</button>
              </div>
            </div>
          )}
          {/* Dashboard View */}
          {currentView === 'dashboard' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <select className="admin-input" style={{ width: '130px', background: '#fff' }}>
                    <option>FY 2025/26</option>
                    <option>FY 2024/25</option>
                  </select>
                  <select className="admin-input" style={{ width: '140px', background: '#fff' }}>
                    <option>Q1 (Apr-Jun)</option>
                    <option>Q2 (Jul-Sep)</option>
                    <option>Q3 (Oct-Dec)</option>
                    <option>Q4 (Jan-Mar)</option>
                  </select>
                </div>
                <button 
                  className="btn-auth-primary" 
                  style={{ width: 'auto', background: 'var(--admin-accent)', color: '#111', fontWeight: '800', padding: '10px 24px' }}
                  onClick={() => alert("Paper Form entry coming soon.")}
                >
                  + ENTER PAPER FORM
                </button>
              </div>

              <div className="admin-kpi-row" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val">{stats.totalApps}</div>
                  <div className="admin-kpi-label">TOTAL APPLICATIONS</div>
                </div>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val">${(stats.approvedAmount / 1000).toFixed(stats.approvedAmount >= 1000 ? 1 : 2)}k</div>
                  <div className="admin-kpi-label">APPROVED ($)</div>
                </div>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val" style={{ color: 'var(--admin-accent)' }}>{stats.underReview}</div>
                  <div className="admin-kpi-label">UNDER REVIEW</div>
                </div>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val">{stats.activeStudents}</div>
                  <div className="admin-kpi-label">ACTIVE STUDENTS</div>
                </div>
              </div>

              {/* Insights Row - Standardized & Visible */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
                {/* Stream Split Card */}
                <div className="admin-chart-card" style={{ marginBottom: 0, padding: '24px' }}>
                  <h3 style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', marginBottom: '20px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>STREAM SPLIT</h3>
                  
                  <div className="admin-stat-row">
                    <div className="admin-stat-head">
                      <span className="admin-stat-label">C-DFN (PSSSP / Bursary)</span>
                      <span className="admin-stat-val">{(backendStats?.stream_split?.pssp || 0)} students</span>
                    </div>
                    <div className="admin-progress-bg">
                      <div className="admin-progress-fill" style={{ width: `${(backendStats?.stream_split?.pssp_percent || 0)}%`, background: '#1a6b3a' }}></div>
                    </div>
                  </div>

                  <div className="admin-stat-row">
                    <div className="admin-stat-head">
                      <span className="admin-stat-label">DGGR</span>
                      <span className="admin-stat-val">{(backendStats?.stream_split?.dggr || 0)} students</span>
                    </div>
                    <div className="admin-progress-bg">
                      <div className="admin-progress-fill" style={{ width: `${(backendStats?.stream_split?.dggr_percent || 0)}%`, background: '#1e293b' }}></div>
                    </div>
                  </div>

                  <div className="admin-stat-row" style={{ marginBottom: 0 }}>
                    <div className="admin-stat-head">
                      <span className="admin-stat-label">UCEPP (Upgrading)</span>
                      <span className="admin-stat-val">{(backendStats?.stream_split?.ucepp || 0)} students</span>
                    </div>
                    <div className="admin-progress-bg">
                      <div className="admin-progress-fill" style={{ width: `${(backendStats?.stream_split?.ucepp_percent || 0)}%`, background: '#dd6b20' }}></div>
                    </div>
                  </div>
                </div>

                {/* Application Status Card */}
                <div className="admin-chart-card" style={{ marginBottom: 0, padding: '24px' }}>
                  <h3 style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', marginBottom: '20px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>APPLICATION STATUS</h3>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span className="admin-badge badge-approved" style={{ minWidth: '80px', textAlign: 'center' }}>APPROVED</span>
                        <span style={{ fontSize: '13px', fontWeight: '600' }}>Ready for payment</span>
                      </div>
                      <span style={{ fontSize: '14px', fontWeight: '800' }}>{(backendStats?.submissions_by_status?.accepted || 0)}</span>
                    </div>
                    
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span className="admin-badge badge-review" style={{ minWidth: '80px', textAlign: 'center' }}>REVIEW</span>
                        <span style={{ fontSize: '13px', fontWeight: '600' }}>In process</span>
                      </div>
                      <span style={{ fontSize: '14px', fontWeight: '800' }}>{(backendStats?.submissions_by_status?.pending || 0) + (backendStats?.submissions_by_status?.reviewed || 0)}</span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '18px' }}>📜</span>
                        <span style={{ fontSize: '13px', fontWeight: '600' }}>Waiting Enrollment Verification</span>
                      </div>
                      <span style={{ fontSize: '14px', fontWeight: '800' }}>{(backendStats?.form_b_stats?.awaiting || 0)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Activity Table - Spanning Full Width */}
              <div className="admin-table-wrap">
                <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: '13px', fontWeight: '800' }}>RECENT ACTIVITY</div>
                  <button 
                    className="staff-nav-item active" 
                    style={{ fontSize: '10px', padding: '6px 14px', borderRadius: '20px', background: 'var(--admin-accent)', color: '#111', fontWeight: '8400' }} 
                    onClick={() => setCurrentView('applications')}
                  >
                    View All Applications
                  </button>
                </div>
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>REF #</th>
                      <th>STUDENT</th>
                      <th>PROGRAM</th>
                      <th>SUBMITTED</th>
                      <th>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.slice(0, 8).map(app => (
                      <tr key={app.id} style={{ cursor: 'pointer' }} onClick={() => handleAppClick(app.id)}>
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}># {app.id}</span></td>
                        <td><strong>{app.student_details?.full_name || 'Anonymous Student'}</strong></td>
                        <td style={{ fontSize: '12px' }}>{app.form_title || app.form?.title || 'General App'}</td>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>{new Date(app.submitted_at).toLocaleDateString()}</td>
                        <td>{getStatusBadge(app.status)}</td>
                      </tr>
                    ))}
                    {applications.length === 0 && (
                      <tr><td colSpan={5} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No submissions found in system.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Applications View */}
          {currentView === 'applications' && (
            <div className="fade-in">
              <div className="admin-filters" style={{ gridTemplateColumns: '1fr auto auto' }}>
                <div className="admin-search">
                  <input
                    type="text"
                    className="admin-input"
                    placeholder="Search applicant, ref #, institution..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <select className="admin-input" style={{ width: '160px' }}>
                  <option>Status: All</option>
                </select>
                <select className="admin-input" style={{ width: '160px' }}>
                  <option>Semester: All</option>
                </select>
              </div>

              <div className="policy-tabs" style={{ marginBottom: '0', padding: '0 20px' }}>
                <div 
                  className={`policy-tab ${statusFilter === 'all' ? 'active' : ''}`} 
                  onClick={() => setStatusFilter('all')}
                >
                  All ({applications.length})
                </div>
                <div 
                  className={`policy-tab ${statusFilter === 'pending' ? 'active' : ''}`} 
                  style={{ color: '#1a6b3a' }}
                  onClick={() => setStatusFilter('pending')}
                >
                  New ({applications.filter(a => a.status === 'pending').length})
                </div>
                <div 
                  className={`policy-tab ${statusFilter === 'reviewed' ? 'active' : ''}`}
                  onClick={() => setStatusFilter('reviewed')}
                >
                  Review ({applications.filter(a => a.status === 'reviewed').length})
                </div>
                <div 
                  className={`policy-tab ${statusFilter === 'forwarded' ? 'active' : ''}`}
                  onClick={() => setStatusFilter('forwarded')}
                >
                  Pending Director ({applications.filter(a => a.status === 'forwarded').length})
                </div>
                <div 
                  className={`policy-tab ${statusFilter === 'accepted' ? 'active' : ''}`}
                  onClick={() => setStatusFilter('accepted')}
                >
                  Approved ({applications.filter(a => a.status === 'accepted').length})
                </div>
                <div 
                  className={`policy-tab ${statusFilter === 'rejected' ? 'active' : ''}`}
                  onClick={() => setStatusFilter('rejected')}
                >
                  Denied ({applications.filter(a => a.status === 'rejected').length})
                </div>
              </div>

              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>REF #</th>
                      <th>APPLICANT</th>
                      <th>INSTITUTION / PROGRAM</th>
                      <th>SUBMITTED</th>
                      <th>STATUS</th>
                      <th>VERIFICATION</th>
                      <th>FUNDING $</th>
                      <th>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredApps.map(app => (
                      <tr key={app.id}>
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>{app.id}</span></td>
                        <td><strong>{app.student_details?.full_name}</strong></td>
                        <td style={{ fontSize: '12px' }}>{getFormDisplayName(app.form_title || app.form?.title)}</td>
                        <td style={{ fontSize: '12px' }}>{new Date(app.submitted_at).toLocaleDateString()}</td>
                        <td>{getStatusBadge(app.status)}</td>
                        <td>
                          {app.status === 'accepted' ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#166534' }}>
                              <div style={{ width: '8px', height: '8px', background: '#1a6b3a', borderRadius: '50%' }}></div> Completed
                            </div>
                          ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#64748b' }}>
                              <div style={{ width: '8px', height: '8px', background: '#cbd5e1', borderRadius: '50%' }}></div> Pending
                            </div>
                          )}
                        </td>
                        <td><strong>{app.amount > 0 ? `$${parseFloat(app.amount).toLocaleString()}` : '—'}</strong></td>
                        <td>
                          <button
                            className="admin-input"
                            style={{
                              width: 'auto',
                              padding: '6px 12px',
                              background: '#000',
                              color: '#fff',
                              fontSize: '11px',
                              fontWeight: '700',
                              border: 'none',
                              cursor: 'pointer'
                            }}
                            onClick={() => handleAppClick(app.id)}
                          >
                            {app.status === 'forwarded' && role === 'director' ? 'DECIDE →' : 'Review →'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Detail View (Shared by Staff and Director) */}
          {((currentView === 'detail' || currentView === 'director-detail') && selectedAppId) && (
            <div className="fade-in">
              {/* Header Actions */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div style={{ fontSize: '11px', color: '#64748b' }}>
                  All Applications / <span style={{ fontWeight: '700', color: '#1e293b' }}>{selectedAppId}</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }} onClick={handlePDFExport}>Export PDF</button>
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }} onClick={handleShareView}>Share View</button>
                  <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleRequestInfo}>REQUEST MORE INFO</button>
                  <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleAddNote} disabled={!staffNote.trim() || isLoading}>ADD NOTE</button>
                  {role === 'director' ? (
                    <>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: '#1a6b3a', color: '#fff', border: 'none' }} onClick={() => handleDecision('accepted')}>APPROVE APPLICATION</button>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: '#991b1b', color: '#fff', border: 'none' }} onClick={() => handleDecision('rejected')}>REJECT</button>
                    </>
                  ) : (
                    <button 
                      className="admin-input" 
                      style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: 'var(--admin-accent)', color: '#000', border: 'none' }}
                      onClick={() => handleDecision('forwarded')}
                    >
                      SEND TO DIRECTOR →
                    </button>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px' }}>
                {/* Left: Detail Forms */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{selectedAppId}</div>
                        <h2 style={{ fontSize: '20px', fontWeight: '800' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.name} — Post-Secondary Application</h2>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Submitted Mar 3, 2025 · Admission Application</div>
                      </div>
                      <button className="admin-badge badge-review" style={{ height: 'fit-content' }}>UNDER REVIEW</button>
                    </div>

                    <div style={{ padding: '20px', background: '#f8fafc', borderRadius: '10px' }}>
                      <div className="admin-nav-title" style={{ marginBottom: '16px', padding: '0' }}>STUDENT & PROGRAM</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>NAME</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.student_details?.full_name}</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>BENEFICIARY #</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.student_details?.beneficiary_number || 'None'}</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>DOB</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.student_details?.dob || 'Not Provided'}</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>PHONE</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.student_details?.phone || 'None'}</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>ENROLLMENT</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.form_title || 'Application'}</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>STATUS</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.status.toUpperCase()}</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>INSTITUTION</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>U of Calgary</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>PROGRAM</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>Nursing Yr 2</div>
                        </div>
                        <div>
                          <label className="admin-kpi-label" style={{ fontSize: '9px' }}>SEMESTER</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>Fall 2025</div>
                        </div>
                      </div>
                    </div>

                    <div style={{ marginTop: '32px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                        <h3 style={{ fontSize: '14px', fontWeight: '800' }}>AUTO FUNDING CALCULATION</h3>
                        <span className="admin-badge badge-pending" style={{ fontSize: '9px', padding: '2px 8px' }}>SYSTEM CALCULATED</span>
                      </div>
                      <div className="admin-table-wrap" style={{ border: 'none', boxShadow: 'none' }}>
                        <table className="admin-table">
                          <thead>
                            <tr style={{ background: '#f1f5f9' }}>
                              <th>COMPONENT</th>
                              <th>STREAM</th>
                              <th>POLICY RULE</th>
                              <th>SYSTEM $</th>
                              <th>OVERRIDE $</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td style={{ fontSize: '12px' }}>Tuition Award</td>
                              <td style={{ fontSize: '11px' }}><span className="admin-badge" style={{ background: '#dcfce7', color: '#166534' }}>{autoSuggested?.stream || 'DGGR'}</span></td>
                              <td style={{ fontSize: '11px', color: '#64748b' }}>{autoSuggested?.tuition?.rule}</td>
                              <td style={{ fontSize: '13px', fontWeight: '700' }}>${autoSuggested?.tuition?.system.toLocaleString()}</td>
                              <td><input type="text" className="admin-input" defaultValue={autoSuggested?.tuition?.system} style={{ width: '100px', padding: '4px 8px' }} /></td>
                            </tr>
                            <tr>
                              <td style={{ fontSize: '12px' }}>Living Allowance</td>
                              <td style={{ fontSize: '11px' }}><span className="admin-badge" style={{ background: '#e0e7ff', color: '#3730a3' }}>PSSSP</span></td>
                              <td style={{ fontSize: '11px', color: '#64748b' }}>{autoSuggested?.living?.rule}</td>
                              <td style={{ fontSize: '13px', fontWeight: '700' }}>${autoSuggested?.living?.system.toLocaleString()}</td>
                              <td><input type="text" className="admin-input" defaultValue={autoSuggested?.living?.system} style={{ width: '100px', padding: '4px 8px' }} /></td>
                            </tr>
                            <tr>
                              <td style={{ fontSize: '12px' }}>Books & Supplies</td>
                              <td style={{ fontSize: '11px' }}><span className="admin-badge" style={{ background: '#fff7ed', color: '#c2410c' }}>DGGR</span></td>
                              <td style={{ fontSize: '11px', color: '#64748b' }}>{autoSuggested?.books?.rule}</td>
                              <td style={{ fontSize: '13px', fontWeight: '700' }}>${autoSuggested?.books?.system.toLocaleString()}</td>
                              <td><input type="text" className="admin-input" defaultValue={autoSuggested?.books?.system} style={{ width: '100px', padding: '4px 8px' }} /></td>
                            </tr>
                          </tbody>
                          <tfoot>
                            <tr style={{ borderTop: '2px solid #e2e8f0' }}>
                              <td colSpan={3} style={{ textAlign: 'left', fontWeight: '700', padding: '16px' }}>
                                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                                  <span>Total Suggested</span>
                                  <button 
                                    className="admin-badge badge-approved" 
                                    style={{ border: 'none', cursor: 'pointer', fontSize: '9px' }}
                                    onClick={async () => {
                                      if (autoSuggested && selectedApp) {
                                        try {
                                          await API.updateSubmissionStatus(selectedApp.id, selectedApp.status, { amount: autoSuggested.total });
                                          fetchApplications();
                                          alert("System suggested total applied!");
                                        } catch (er) { alert("Failed to apply total"); }
                                      }
                                    }}
                                  >
                                    APPLY SYSTEM TOTAL →
                                  </button>
                                </div>
                              </td>
                              <td style={{ fontSize: '15px' }}><strong>${autoSuggested?.total.toLocaleString()}</strong></td>
                              <td><div className="admin-badge badge-approved" style={{ width: '100px', textAlign: 'center' }}>${selectedApp?.amount?.toLocaleString() || '0'}</div></td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>

                    <div style={{ marginTop: '32px' }}>
                      <div className="admin-nav-title" style={{ marginBottom: '16px', padding: '0' }}>DOCUMENTS</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {selectedApp?.documents?.map((doc: any, i: number) => (
                          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <span style={{ fontSize: '18px' }}>{doc.file?.toLowerCase().endsWith('.pdf') ? '📄' : '🖼️'}</span>
                              <span style={{ fontSize: '12px', fontWeight: '600' }}>{doc.name}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <span className={`admin-badge ${doc.is_verified ? 'badge-approved' : 'badge-review'}`} style={{ fontSize: '9px' }}>
                                {doc.is_verified ? 'VERIFIED' : 'PENDING'}
                              </span>
                              <a href={doc.file} target="_blank" rel="noopener noreferrer" className="btn-ghost" style={{ fontSize: '10px', padding: '4px 8px' }}>View</a>
                            </div>
                          </div>
                        ))}
                        {(!selectedApp?.documents || selectedApp.documents.length === 0) && (
                          <div style={{ fontSize: '11px', color: '#64748b', textAlign: 'center', padding: '20px', border: '1px dashed #e2e8f0', borderRadius: '8px' }}>No documents uploaded.</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right: Sidebar Actions & Logs */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', textAlign: 'center', padding: '8px' }} onClick={() => alert('Download receipt coming soon')}>DOWNLOAD RECEIPT</button>
                    <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', textAlign: 'center', padding: '8px' }} onClick={() => alert('Message student coming soon')}>MESSAGE STUDENT</button>
                  </div>

                  <div className="admin-chart-card">
                    <h3 style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', marginBottom: '20px', color: '#64748b' }}>AUDIT LOG</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      <div style={{ position: 'relative', paddingLeft: '24px', borderLeft: '2px solid #e2e8f0' }}>
                        <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: '#1a6b3a', borderRadius: '50%' }}></div>
                        <div style={{ fontSize: '12px', fontWeight: '700' }}>Application Received</div>
                        <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>{selectedApp ? new Date(selectedApp.submitted_at).toLocaleString() : 'N/A'} via online portal</div>
                      </div>
                      {selectedApp?.ssw_submitted_at && (
                        <div style={{ position: 'relative', paddingLeft: '24px', borderLeft: '2px solid #e2e8f0' }}>
                           <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: '#3a4aaa', borderRadius: '50%' }}></div>
                           <div style={{ fontSize: '12px', fontWeight: '700' }}>SSW Review Completed</div>
                           <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>{new Date(selectedApp.ssw_submitted_at).toLocaleString()}</div>
                        </div>
                      )}
                      {selectedApp?.decision_at && (
                        <div style={{ position: 'relative', paddingLeft: '24px' }}>
                           <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: selectedApp.status === 'accepted' ? '#1a6b3a' : '#c53030', borderRadius: '50%' }}></div>
                           <div style={{ fontSize: '12px', fontWeight: '700' }}>Director Decision: {selectedApp.status.toUpperCase()}</div>
                           <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>{new Date(selectedApp.decision_at).toLocaleString()} by {selectedApp.decision_by || 'Director'}</div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="admin-chart-card">
                    <h3 style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', marginBottom: '20px', color: '#64748b' }}>STAFF NOTES (INTERNAL ONLY)</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto', paddingRight: '4px' }}>
                        {applications.find(a => Number(a.id) === Number(selectedAppId))?.notes?.length > 0 ? (
                          applications.find(a => Number(a.id) === Number(selectedAppId))!.notes.map((note: any) => (
                            <div key={note.id} style={{ background: '#f8fafc', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                              <div style={{ fontSize: '12px', color: '#1e293b', lineHeight: '1.5' }}>{note.text}</div>
                              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '6px', display: 'flex', justifyContent: 'space-between' }}>
                                <span>{note.added_by_name || 'Staff Member'}</span>
                                <span>{new Date(note.created_at).toLocaleDateString()}</span>
                              </div>
                            </div>
                          ))
                        ) : (
                          <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', padding: '12px', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', border: '1px dashed #cbd5e1' }}>
                            No internal notes yet.
                          </div>
                        )}
                      </div>
                      <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                        <textarea
                          className="admin-input"
                          placeholder="Add internal note — not visible to student.."
                          style={{ fontSize: '12px', border: 'none', background: 'transparent', resize: 'none', padding: '0', width: '100%', minHeight: '60px' }}
                          value={staffNote}
                          onChange={(e) => setStaffNote(e.target.value)}
                        ></textarea>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                          <button 
                            className="admin-badge badge-review" 
                            style={{ cursor: 'pointer', border: 'none', opacity: !staffNote.trim() || isLoading ? 0.5 : 1 }}
                            onClick={handleAddNote}
                            disabled={!staffNote.trim() || isLoading}
                          >
                            {isLoading ? 'Posting...' : 'Save Note'}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="admin-chart-card" style={{ marginTop: '24px' }}>
                    <h3 style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', marginBottom: '16px', color: '#64748b' }}>OFFICE USE ONLY</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div>
                        <label className="admin-kpi-label" style={{ fontSize: '9px', marginBottom: '4px', display: 'block' }}>DATE RECEIVED</label>
                        <input className="admin-input" type="date" value={officeUseInputs.dateReceived} onChange={e => setOfficeUseInputs({...officeUseInputs, dateReceived: e.target.value})} style={{ width: '100%', padding: '8px' }} />
                      </div>
                      <div>
                        <label className="admin-kpi-label" style={{ fontSize: '9px', marginBottom: '4px', display: 'block' }}>APPROVED BY</label>
                        <input className="admin-input" type="text" value={officeUseInputs.approvedBy} onChange={e => setOfficeUseInputs({...officeUseInputs, approvedBy: e.target.value})} style={{ width: '100%', padding: '8px' }} placeholder="Admin Name" />
                      </div>
                      <div>
                        <label className="admin-kpi-label" style={{ fontSize: '9px', marginBottom: '4px', display: 'block' }}>COMMITMENT #</label>
                        <input className="admin-input" type="text" value={officeUseInputs.commitmentNum} onChange={e => setOfficeUseInputs({...officeUseInputs, commitmentNum: e.target.value})} style={{ width: '100%', padding: '8px' }} placeholder="CM-00000" />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                        <button 
                          className="admin-badge badge-review" 
                          style={{ cursor: 'pointer', border: 'none', opacity: isSavingOffice ? 0.5 : 1, padding: '8px 16px', fontWeight: '800' }}
                          onClick={handleSaveOfficeUse}
                          disabled={isSavingOffice}
                        >
                          {isSavingOffice ? 'Saving...' : 'Save Office Data'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

                {/* Policy Settings View */}
                {currentView === 'policy' && (
                  <div className="fade-in" style={{ padding: '0 20px 40px' }}>
                    <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <h2 style={{ fontSize: '24px', fontWeight: '800', color: '#1e293b' }}>Policy Settings</h2>
                        <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>Configure funding rules, rates, and deadlines. Changes affect all future calculations.</p>
                      </div>
                      {role !== 'director' && (
                        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '10px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: '600' }}>
                          READ-ONLY ACCESS: Only the Director of Education can modify policy settings.
                        </div>
                      )}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {[
                        { id: 'application_deadlines', title: 'Application Deadlines', desc: 'Define semester start/end and application cut-off dates.' },
                        { id: 'psssp_tuition', title: 'PSSSP — Tuition Bursary', desc: 'Maximum tuition coverage per semester for PSSSP students.' },
                        { id: 'psssp_living', title: 'PSSSP — Living Allowance', desc: 'Monthly living allowance rates based on enrollment and dependents.' },
                        { id: 'psssp_travel', title: 'PSSSP — Travel Bursary', desc: 'Limits and eligibility for student travel reimbursements.' },
                        { id: 'psssp_graduation_travel', title: 'PSSSP — Graduation Travel', desc: 'Assistance for students traveling to attend graduation ceremonies.' },
                        { id: 'ucepp_tuition', title: 'UCEPP — Tuition Bursary', desc: 'Maximum tuition coverage per semester for UCEPP students.' },
                        { id: 'ucepp_living', title: 'UCEPP — Living Allowance', desc: 'Monthly living allowance rates for UCEPP students.' },
                        { id: 'dggr_tuition', title: 'DGGR — Tuition Bursary', desc: 'Tuition rates for DGGR-funded programs.' },
                        { id: 'dggr_extra_tuition', title: 'DGGR — Extra Tuition Bursary', desc: 'Top-up bursary for tuition exceeding standard limits.' },
                        { id: 'dggr_living', title: 'DGGR — Living Allowance', desc: 'Monthly living allowance rates for DGGR students.' },
                        { id: 'dggr_practicum_award', title: 'DGGR — Practicum Award', desc: 'Awards for placements and practicum completions.' },
                        { id: 'dggr_grad_bursary', title: 'DGGR — Graduation Bursary', desc: 'One-time bursaries for completing degrees or certificates.' },
                        { id: 'dggr_academic_scholarship', title: 'DGGR — Academic Scholarship', desc: 'Achievement awards based on GPA thresholds.' },
                        { id: 'dggr_hardship', title: 'DGGR — Hardship Bursary', desc: 'Emergency funding caps for students in financial distress.' },
                        { id: 'eligibility_rules', title: 'Eligibility Rules', desc: 'Global rules for program length and minimum course loads.' },
                        { id: 'misconduct_rules', title: 'Misconduct Rules', desc: 'Suspension rules for academic or financial misconduct.' },
                        { id: 'payment_schedule', title: 'Payment Schedule', desc: 'Processing times and standard payment dates.' }
                      ].map((section) => {
                        const items = policySettings[section.id] || [];
                        const isExpanded = expandedSections[section.id];
                        const hasChanges = isDirty[section.id];
                        const lastUpdated = items[0]?.last_updated_at;
                        const updatedBy = items[0]?.last_updated_by_name;

                        return (
                          <div key={section.id} className="admin-chart-card" style={{ padding: '0', overflow: 'hidden', border: hasChanges ? '2px solid #f97316' : '1px solid #e2e8f0' }}>
                            <div 
                              onClick={() => setExpandedSections({ ...expandedSections, [section.id]: !isExpanded })}
                              style={{ padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', background: isExpanded ? '#f8fafc' : 'white' }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <h3 style={{ fontSize: '15px', fontWeight: '800', color: '#1e293b', margin: '0' }}>{section.title}</h3>
                                {hasChanges && <span style={{ background: '#fff7ed', color: '#c2410c', fontSize: '10px', fontWeight: '800', padding: '2px 8px', borderRadius: '4px', border: '1px solid #fdba74' }}>UNSAVED</span>}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                                {(lastUpdated && !isExpanded) && (
                                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                                    Last updated {new Date(lastUpdated).toLocaleDateString()}
                                  </span>
                                )}
                                <span style={{ fontSize: '18px', color: '#64748b' }}>{isExpanded ? '−' : '+'}</span>
                              </div>
                            </div>

                            {isExpanded && (
                              <div style={{ padding: '0 24px 24px' }}>
                                <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px', marginTop: '-8px' }}>{section.desc}</p>
                                
                                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '20px' }}>
                                    {items.length > 0 ? items.map((field) => (
                                      <div key={field.id} style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                                        <label style={{ display: 'block', fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', marginBottom: '8px' }}>
                                          {field.field_label}
                                        </label>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                          <input 
                                            type="number" 
                                            className="admin-input" 
                                            disabled={role !== 'director'}
                                            value={field.value}
                                            style={{ flex: '1', fontSize: '16px', fontWeight: '700', padding: '10px 14px' }}
                                            onChange={(e) => {
                                              const newVal = e.target.value;
                                              const newSettings = { ...policySettings };
                                              const itemIdx = newSettings[section.id].findIndex(i => i.id === field.id);
                                              newSettings[section.id][itemIdx].value = newVal;
                                              setPolicySettings(newSettings);
                                              setIsDirty({ ...isDirty, [section.id]: true });
                                            }}
                                          />
                                          <span style={{ minWidth: '40px', fontSize: '14px', fontWeight: '600', color: '#94a3b8' }}>{field.unit}</span>
                                        </div>
                                      </div>
                                    )) : (
                                      <div style={{ gridColumn: '1 / -1', padding: '40px', textAlign: 'center', background: '#f1f5f9', borderRadius: '12px', border: '1px dashed #cbd5e1' }}>
                                        <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>Policy parameters for this section are being synchronized or have not been defined.</p>
                                      </div>
                                    )}
                                  </div>

                                  <div style={{ marginTop: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '24px', borderTop: '1px solid #e2e8f0' }}>
                                    <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                                      {lastUpdated ? `Last modified by ${updatedBy || 'System'} on ${new Date(lastUpdated).toLocaleString()}` : 'No previous updates recorded.'}
                                    </div>

                                    {/* Hide Save/Reset buttons for SSW (role !== 'director') */}
                                    {role === 'director' && (
                                      <div style={{ display: 'flex', gap: '12px' }}>
                                        <button 
                                          className="admin-badge badge-review" 
                                          style={{ padding: '10px 20px', fontWeight: '700', background: 'white', border: '1px solid #e2e8f0', color: '#64748b', cursor: 'pointer' }}
                                          onClick={() => {
                                            if (window.confirm("This will reset all values in this section to the original policy defaults. Are you sure?")) {
                                              fetchPolicySettings();
                                              setIsDirty({ ...isDirty, [section.id]: false });
                                            }
                                          }}
                                        >
                                          Reset to Defaults
                                        </button>
                                        <button 
                                          className="admin-badge badge-approved" 
                                          disabled={!hasChanges}
                                          style={{ padding: '10px 20px', fontWeight: '700', border: 'none', cursor: hasChanges ? 'pointer' : 'not-allowed', opacity: hasChanges ? 1 : 0.5 }}
                                          onClick={async () => {
                                            if (window.confirm("Are you sure you want to update these policy values? This will affect all future funding calculations.")) {
                                              try {
                                                await API.updatePolicySetting('bulk', { settings: items });
                                                setIsDirty({ ...isDirty, [section.id]: false });
                                                fetchPolicySettings();
                                                alert("Section updated successfully.");
                                              } catch (err: any) {
                                                alert(err.message || "Failed to update section.");
                                              }
                                            }
                                          }}
                                        >
                                          Save Section
                                        </button>
                                      </div>
                                    )}
                                  </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

           {currentView === 'reports' && (
            <div className="fade-in">
              {(!backendStats && isLoading) ? (
                <div style={{ padding: '60px', textAlign: 'center', background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div className="admin-loading-spinner" style={{ margin: '0 auto 20px' }}></div>
                  <div style={{ color: '#64748b', fontWeight: '600' }}>Aggregating database records...</div>
                </div>
              ) : (
                <React.Fragment>
                  {/* Two-Level Filter System */}
                  <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '32px' }}>
                    <div style={{ marginBottom: '20px' }}>
                      <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '12px', textTransform: 'uppercase' }}>Level 1 — Funding Type</label>
                      <div style={{ display: 'flex', gap: '10px' }}>
                        {['all', 'UCEPP', 'CDFN', 'DGGR'].map(type => (
                          <button 
                            key={type}
                            onClick={() => setReportFundingType(type.toLowerCase())}
                            style={{ 
                              padding: '10px 20px', 
                              borderRadius: '8px', 
                              border: 'none',
                              background: reportFundingType === type.toLowerCase() ? 'var(--admin-accent)' : '#f1f5f9',
                              color: '#111',
                              fontWeight: '800',
                              fontSize: '12px',
                              cursor: 'pointer'
                            }}
                          >
                            {type}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '12px', textTransform: 'uppercase' }}>Level 2 — Sub-Filters</label>
                      <div style={{ display: 'flex', gap: '12px' }}>
                        {[
                          { id: 'students', label: '# of Students' },
                          { id: 'paid', label: 'Amount Paid Out' },
                          { id: 'quarterly', label: 'Quarterly Report' }
                        ].map(sub => (
                          <button 
                            key={sub.id}
                            onClick={() => setReportSubFilter(sub.id)}
                            style={{ 
                              padding: '10px 20px', 
                              borderRadius: '8px', 
                              border: reportSubFilter === sub.id ? '2px solid #111' : '1px solid #e2e8f0',
                              background: 'white',
                              color: '#111',
                              fontWeight: '800',
                              fontSize: '12px',
                              cursor: 'pointer'
                            }}
                          >
                            {sub.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Dashboard Content Area */}
                  <div className="admin-chart-card" style={{ padding: '32px' }}>
                    {reportSubFilter === 'students' && (
                      <div className="fade-in">
                        <div style={{ marginBottom: '32px' }}>
                          <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase' }}>Total Students Enrolled</h3>
                          <div style={{ fontSize: '48px', fontWeight: '900', color: '#111' }}>{backendStats?.total_students || 0}</div>
                        </div>
                        <div className="admin-table-wrap" style={{ border: 'none', boxShadow: 'none' }}>
                          <table className="admin-table">
                            <thead>
                              <tr>
                                <th>REF #</th>
                                <th>STUDENT NAME</th>
                                <th>PROGRAM</th>
                                <th>STATUS</th>
                              </tr>
                            </thead>
                            <tbody>
                              {applications.map((app: any) => (
                                <tr key={app.id}>
                                  <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{app.id}</span></td>
                                  <td><strong>{app.student_details?.full_name || app.name}</strong></td>
                                  <td style={{ fontSize: '12px' }}>{app.form_title}</td>
                                  <td>{getStatusBadge(app.status)}</td>
                                </tr>
                              ))}
                              {applications.length === 0 && (
                                <tr><td colSpan={4} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No students found for this selection.</td></tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {reportSubFilter === 'paid' && (
                      <div className="fade-in">
                        <div style={{ marginBottom: '32px' }}>
                          <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase' }}>Total Amount Paid Out</h3>
                          <div style={{ fontSize: '48px', fontWeight: '900', color: '#166534' }}>${(backendStats?.total_funding_approved || 0).toLocaleString()}</div>
                        </div>
                        <div className="admin-table-wrap" style={{ border: 'none', boxShadow: 'none' }}>
                          <table className="admin-table">
                            <thead>
                              <tr>
                                <th>REF #</th>
                                <th>STUDENT</th>
                                <th>PAYMENT TYPE</th>
                                <th>AMOUNT</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(backendStats?.recent_payouts || []).map((p: any) => (
                                <tr key={p.id}>
                                  <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{p.id}</span></td>
                                  <td><strong>{p.user_name}</strong></td>
                                  <td><span className="admin-badge" style={{ fontSize: '10px' }}>{p.payment_type}</span></td>
                                  <td style={{ fontWeight: '800' }}>${parseFloat(p.amount).toLocaleString()}</td>
                                </tr>
                              ))}
                              {(backendStats?.recent_payouts || []).length === 0 && (
                                <tr><td colSpan={4} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No payments recorded for this selection.</td></tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {reportSubFilter === 'quarterly' && (
                      <div className="fade-in">
                        <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#64748b', textTransform: 'uppercase', marginBottom: '32px' }}>Quarterly Performance</h3>
                        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '40px', height: '250px', paddingBottom: '40px', borderBottom: '1px solid #e2e8f0', justifyContent: 'space-around' }}>
                          {backendStats?.quarterly_report?.map((q: any, i: number) => {
                            const maxAmt = Math.max(...backendStats.quarterly_report.map((x: any) => x.amount), 1);
                            return (
                              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', height: '100%', justifyContent: 'flex-end' }}>
                                <div style={{ fontSize: '12px', fontWeight: '800' }}>${(q.amount / 1000).toFixed(1)}k</div>
                                <div style={{ 
                                  width: '100%', 
                                  maxWidth: '50px', 
                                  height: `${(q.amount / maxAmt) * 100}%`,
                                  background: 'var(--admin-accent)',
                                  borderRadius: '6px 6px 0 0'
                                }}></div>
                                <div style={{ fontSize: '12px', fontWeight: '800' }}>{q.quarter}</div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </React.Fragment>
              )}
            </div>
          )}

          {/* Director Approval Queue View */}
          {currentView === 'director-queue' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: '800' }}>APPROVAL QUEUE</h2>
                <span style={{ fontSize: '11px', color: '#64748b' }}>{applications.filter(a => a.status === 'forwarded').length} awaiting decision</span>
              </div>
              <div className="admin-kpi-row" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val">{(backendStats?.submissions_by_status?.forwarded || 0)}</div>
                  <div className="admin-kpi-label">STANDARD</div>
                </div>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val" style={{ color: '#e5a662' }}>{applications.filter(a => a.status === 'forwarded' && (a.office_use_data?.commitmentNum === 'OVERRIDE')).length}</div>
                  <div className="admin-kpi-label">WITH OVERRIDES</div>
                </div>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val" style={{ color: '#cc3333' }}>{applications.filter(a => a.status === 'forwarded' && a.amount > 10000).length}</div>
                  <div className="admin-kpi-label">HIGH VALUE</div>
                </div>
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val">${((backendStats?.pending_funding_total || 0) / 1000).toFixed(1)}k</div>
                  <div className="admin-kpi-label">TOTAL PENDING $</div>
                </div>
              </div>

              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>REF #</th>
                      <th>STUDENT</th>
                      <th>PROGRAM</th>
                      <th>AMOUNT</th>
                      <th>FLAGS</th>
                      <th>SSW SUBMITTED</th>
                      <th>DECISION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.filter(a => a.status === 'forwarded').map(app => (
                      <tr key={app.id}>
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{app.id}</span></td>
                        <td><strong>{app.student_details?.full_name || 'Student'}</strong></td>
                        <td style={{ fontSize: '12px' }}>{app.form_title}</td>
                        <td style={{ fontSize: '13px', fontWeight: '700' }}>${parseFloat(app.amount || 0).toLocaleString()}</td>
                        <td>
                          {app.amount > 10000 && <span className="admin-badge badge-review" style={{ fontSize: '9px', padding: '2px 6px' }}>HIGH VALUE</span>}
                        </td>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>{new Date(app.submitted_at).toLocaleDateString()}</td>
                        <td>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button 
                              className="director-action-btn" 
                              onClick={() => { setSelectedAppId(app.id); setCurrentView('director-detail'); }}
                              style={{ color: 'var(--admin-accent)', fontWeight: '800' }}
                            >
                              Review →
                            </button>
                            <button className="director-decision-icon-btn approve"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
                            <button className="director-decision-icon-btn deny"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ marginTop: '40px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#64748b', textTransform: 'uppercase' }}>RECENTLY DECIDED</h3>
                <div className="admin-table-wrap">
                  <table className="admin-table table-dense">
                    <thead>
                      <tr>
                        <th>REF #</th>
                        <th>STUDENT</th>
                        <th>PROGRAM</th>
                        <th>AMOUNT</th>
                        <th>DECISION</th>
                        <th>BY</th>
                        <th>WHEN</th>
                      </tr>
                    </thead>
                    <tbody>
                      {applications.filter(a => a.status === 'accepted' || a.status === 'rejected').map(app => (
                        <tr key={app.id}>
                          <td><span style={{ fontSize: '10px', color: '#64748b' }}>{app.id}</span></td>
                          <td><strong>{app.student_details?.full_name || app.name}</strong></td>
                          <td style={{ fontSize: '11px' }}>{app.program || app.form_data?.program || 'N/A'}</td>
                          <td style={{ fontSize: '12px', fontWeight: '700' }}>${parseFloat(app.amount || 0).toLocaleString()}</td>
                          <td>
                            {app.status === 'accepted' ? (
                              <span style={{ color: '#1a6b3a', fontWeight: '700', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Approved
                              </span>
                            ) : (
                              <span style={{ color: '#cc3333', fontWeight: '700', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> Denied
                              </span>
                            )}
                          </td>
                          <td style={{ fontSize: '11px', color: '#64748b' }}>System</td>
                          <td style={{ fontSize: '11px', color: '#64748b' }}>{new Date(app.submitted_at || Date.now()).toLocaleDateString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
              </div>
            </div>
          </div>
        )}

          {/* Director Application Detail View */}
          {(currentView === 'director-detail' && selectedAppId) && (
            <div className="fade-in">
              <div style={{ marginBottom: '20px' }}>
                <span style={{ fontSize: '11px', color: '#64748b' }}>Approval Queue / <span style={{ fontWeight: '700', color: '#1e293b' }}>{selectedAppId}</span></span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px' }}>
                {/* Left: Application Content */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{selectedAppId}</div>
                        <h2 style={{ fontSize: '20px', fontWeight: '800' }}>{applications.find(a => a.id === selectedAppId)?.name} — Post-Secondary Application</h2>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>SSW forwarded {applications.find(a => a.id === selectedAppId)?.date} · J. Villeneuve</div>
                      </div>
                      {applications.find(a => a.id === selectedAppId)?.flags?.map((f: string) => (
                        <span key={f} className={`admin-badge badge-${f.toLowerCase()}`} style={{ fontSize: '9px', padding: '4px 10px' }}>{f}</span>
                      ))}
                    </div>

                    <div style={{ background: '#f8fafc', borderRadius: '10px', padding: '24px', border: '1px solid #e2e8f0', marginBottom: '32px' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', marginBottom: '20px', letterSpacing: '0.05em' }}>STUDENT & PROGRAM</h3>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '32px 24px' }}>
                        <div>
                          <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>NAME</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => a.id === selectedAppId)?.student_details?.full_name || applications.find(a => a.id === selectedAppId)?.name}</div>
                        </div>
                        <div>
                          <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>BENEFICIARY #</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => a.id === selectedAppId)?.student_details?.beneficiary_number || 'DGG-00000'}</div>
                        </div>
                        <div>
                          <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>SFA STATUS</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{applications.find(a => a.id === selectedAppId)?.student_details?.is_sfa_active ? 'Yes' : 'No'}</div>
                        </div>
                      </div>
                      {(() => {
                        const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                        return (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '16px', marginTop: '24px' }}>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>INSTITUTION</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.institute || app?.form_data?.institute || 'N/A'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>PROGRAM</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.form_data?.program || 'N/A'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>ENROLLMENT</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.form_data?.enrollmentStatus || 'Full-Time'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>SEMESTER</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.form_data?.semester || 'N/A'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>DEPENDENTS</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.form_data?.dependentsCount || '0'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>STATUS</label>
                              <div style={{ fontSize: '13px', fontWeight: '700', color: app?.status === 'forwarded' ? '#c2410c' : '#166534' }}>{app?.status.toUpperCase()}</div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>

                    <div style={{ marginBottom: '32px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                        <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>FUNDING BREAKDOWN</h3>
                      </div>
                      <div className="admin-table-wrap" style={{ border: 'none', boxShadow: 'none' }}>
                        {(() => {
                          const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                          return (
                            <table className="admin-table table-dense">
                              <thead style={{ background: '#f8fafc' }}>
                                <tr>
                                  <th>COMPONENT</th>
                                  <th>STREAM</th>
                                  <th>POLICY RULE</th>
                                  <th>AMOUNT</th>
                                  <th>FLAG</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td style={{ fontWeight: '600' }}>Approved Funding</td>
                                  <td><span className="admin-badge" style={{ background: '#e0e7ff' }}>{app?.form_title}</span></td>
                                  <td style={{ fontSize: '10px', color: '#64748b' }}>Full calculated payout</td>
                                  <td><strong>${parseFloat(app?.amount || 0).toLocaleString()}</strong></td>
                                  <td><span style={{ fontSize: '10px', color: '#64748b' }}>—</span></td>
                                </tr>
                                <tr style={{ borderTop: '2px solid #e2e8f0', background: '#f8fafc' }}>
                                  <td colSpan={3} style={{ fontWeight: '800', textAlign: 'right', paddingRight: '20px' }}>Total Authorized</td>
                                  <td colSpan={2} style={{ fontSize: '16px', fontWeight: '800' }}>${parseFloat(app?.amount || 0).toLocaleString()}</td>
                                </tr>
                              </tbody>
                            </table>
                          );
                        })()}
                      </div>
                    </div>

                    <div style={{ background: '#eff6ff', border: '1px solid #dbeafe', borderRadius: '10px', padding: '20px', marginBottom: '32px' }}>
                      <h4 style={{ fontSize: '11px', fontWeight: '800', color: '#1e40af', textTransform: 'uppercase', marginBottom: '8px' }}>SSW RECOMMENDATION</h4>
                      <p style={{ fontSize: '13px', color: '#1e3a8a', lineHeight: '1.5' }}>
                        Recommend Approval — amounts as calculated. Tuition confirmed at $5,000 per institutional invoice.
                      </p>
                      <div style={{ marginTop: '12px', fontSize: '11px', color: '#3b82f6' }}>— J. Villeneuve · Today · 9:45am</div>
                    </div>

                    <div style={{ background: '#fff9f2', border: '1px solid #fef3c7', borderRadius: '10px', padding: '20px', marginBottom: '32px' }}>
                      <h4 style={{ fontSize: '11px', fontWeight: '800', color: '#92400e', textTransform: 'uppercase', marginBottom: '8px' }}>⚠️ EXCEPTION / OVERRIDE DETAILS</h4>
                      <p style={{ fontSize: '13px', color: '#854d0e', lineHeight: '1.5' }}>
                        Tuition Award overridden by SSW: actual tuition invoice confirmed at $5,000. System calculated $4,800 based on prior year data.
                      </p>
                    </div>

                    <div>
                      <h4 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', marginBottom: '16px' }}>DOCUMENTS</h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        {(() => {
                           const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                           return app?.documents?.map((doc: any, i: number) => (
                              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                  <span style={{ fontSize: '16px' }}>📄</span>
                                  <div>
                                    <div style={{ fontSize: '12px', fontWeight: '600' }}>{doc.name}</div>
                                    <div style={{ fontSize: '10px', color: '#94a3b8' }}>Verified Document</div>
                                  </div>
                                </div>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                  <span className={`admin-badge ${doc.is_verified ? 'badge-approved' : 'badge-review'}`} style={{ fontSize: '8px' }}>{doc.is_verified ? 'VERIFIED' : 'PENDING'}</span>
                                  <a href={doc.file} target="_blank" rel="noopener noreferrer" style={{ border: 'none', background: 'none', color: 'var(--admin-accent)', fontSize: '11px', fontWeight: '800', cursor: 'pointer', textDecoration: 'none' }}>View</a>
                                </div>
                              </div>
                           ));
                        })()}
                        {(!applications.find(a => Number(a.id) === Number(selectedAppId))?.documents?.length) && (
                           <div style={{ gridColumn: 'span 2', fontSize: '11px', color: '#64748b', textAlign: 'center', padding: '16px', border: '1px dashed #e2e8f0', borderRadius: '8px' }}>No documents uploaded.</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right: Decision Sidebar & Audit */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card" style={{ padding: '0' }}>
                    <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase' }}>DIRECTOR DECISION</h3>
                    </div>
                    <div style={{ padding: '20px' }}>
                      <div style={{ marginBottom: '20px' }}>
                        <label style={{ fontSize: '11px', fontWeight: '700', color: '#475569', display: 'block', marginBottom: '8px' }}>DECISION</label>
                        <select className="admin-input" style={{ fontSize: '13px' }}>
                          <option>— Select —</option>
                          <option>Approve</option>
                          <option>Deny</option>
                          <option>Defer / Info Needed</option>
                        </select>
                      </div>
                      <div style={{ marginBottom: '24px' }}>
                        <label style={{ fontSize: '11px', fontWeight: '700', color: '#475569', display: 'block', marginBottom: '8px' }}>REASON / NOTES</label>
                        <textarea 
                          className="admin-input" 
                          placeholder="Enter reason, exception justification, or notes for the record.."
                          style={{ height: '120px', resize: 'none', fontSize: '13px', lineHeight: '1.5' }}
                          value={decisionNotes}
                          onChange={(e) => setDecisionNotes(e.target.value)}
                        ></textarea>
                        <div style={{ fontSize: '10px', color: '#cc3333', marginTop: '8px' }}>A written reason is required for exceptions, denials, and deferrals.</div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <button className="director-main-btn approve" onClick={() => handleDecision('accepted')}>✓ APPROVE APPLICATION</button>
                        <button className="director-main-btn deny" onClick={() => handleDecision('rejected')}>✕ DENY APPLICATION</button>
                      </div>
                    </div>
                  </div>

                  <div className="admin-chart-card" style={{ padding: '0' }}>
                    <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase' }}>AUDIT LOG</h3>
                    </div>
                    <div style={{ padding: '24px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                        {(() => {
                           const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                           return (
                             <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                               <div style={{ position: 'relative', paddingLeft: '24px', borderLeft: '1px solid #e2e8f0' }}>
                                 <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: '#166534', borderRadius: '50%', border: '2px solid #fff' }}></div>
                                 <div style={{ fontSize: '12px', fontWeight: '700', color: '#1e293b' }}>Application Received</div>
                                 <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px' }}>{app ? new Date(app.submitted_at).toLocaleString() : 'N/A'} via online portal</div>
                               </div>
                               {app?.ssw_submitted_at && (
                                 <div style={{ position: 'relative', paddingLeft: '24px', borderLeft: '1px solid #e2e8f0' }}>
                                   <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: '#166534', borderRadius: '50%', border: '2px solid #fff' }}></div>
                                   <div style={{ fontSize: '12px', fontWeight: '700', color: '#1e293b' }}>Forwarded to Director</div>
                                   <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px' }}>{new Date(app.ssw_submitted_at).toLocaleString()} by SSW</div>
                                 </div>
                               )}
                               {app?.decision_at && (
                                 <div style={{ position: 'relative', paddingLeft: '24px' }}>
                                   <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: app.status === 'accepted' ? '#166534' : '#c53030', borderRadius: '50%', border: '2px solid #fff' }}></div>
                                   <div style={{ fontSize: '12px', fontWeight: '700', color: '#1e293b' }}>Final Decision: {app.status.toUpperCase()}</div>
                                   <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px' }}>{new Date(app.decision_at).toLocaleString()} by {app.decision_by || 'Director'}</div>
                                 </div>
                               )}
                             </div>
                           );
                        })()}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Confirm Approval Modal */}
          {showConfirmModal && (
            <div className="modal-overlay">
              <div className="modal-card">
                <div className="modal-header">
                  <h3>CONFIRM APPROVAL</h3>
                  <button onClick={() => setShowConfirmModal(false)}>✕</button>
                </div>
                <div className="modal-body">
                  <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#475569', marginBottom: '20px' }}>
                    You are approving <strong>#{selectedAppId} — {applications.find(a => Number(a.id) === Number(selectedAppId))?.student_details?.full_name}</strong>.<br/>
                    Funding amount: <strong>${parseFloat(applications.find(a => Number(a.id) === Number(selectedAppId))?.amount || 0).toLocaleString()}</strong>.
                  </p>
                  <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px' }}>
                    This decision will be recorded in the audit trail and the student and SSW will be notified.
                  </p>
                  
                  <div className="field-group">
                    <label className="field-label" style={{ fontSize: '11px', fontWeight: '800' }}>NOTES (OPTIONAL)</label>
                    <textarea 
                      className="admin-input" 
                      placeholder="Any final notes for the record..."
                      style={{ height: '80px', resize: 'none' }}
                    ></textarea>
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn-secondary" onClick={() => setShowConfirmModal(false)}>Cancel</button>
                  <button className="btn-confirm-approval" onClick={() => handleDecision('accepted')}>✓ CONFIRM APPROVAL</button>
                </div>
              </div>
            </div>
          )}
          {/* Payments View */}
          {currentView === 'payments' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '800' }}>PAYMENT RECORDS</h2>
                  <p style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Records are automatically generated upon application approval.</p>
                </div>
                <button 
                  className="admin-badge badge-approved" 
                  onClick={handleExcelExport}
                  style={{ border: 'none', cursor: 'pointer', padding: '10px 20px', fontWeight: '800' }}
                >
                  {isExporting ? 'GENERATING...' : 'EXPORT APPROVED PAYMENTS'}
                </button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Ref #</th>
                      <th>Student</th>
                      <th>Type</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map((p: any) => (
                      <tr key={p.id}>
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>PAY-{p.id}</span></td>
                        <td><strong>{p.student_details?.full_name || 'Student'}</strong></td>
                        <td style={{ fontSize: '12px' }}>{p.payment_type || p.category}</td>
                        <td style={{ fontSize: '13px', fontWeight: '700' }}>${p.amount.toLocaleString()}</td>
                        <td>
                          <span className="admin-badge badge-approved" style={{ fontSize: '9px' }}>APPROVED</span>
                        </td>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>{new Date(p.date_issued || p.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                    {payments.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No payment records found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Finance Email Modal */}
          {showFinanceModal && (
            <div className="admin-modal-overlay">
              <div className="admin-modal-card" style={{ maxWidth: '400px', textAlign: 'center' }}>
                <div style={{ padding: '32px' }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📧</div>
                  <h3 style={{ fontSize: '20px', fontWeight: '800', marginBottom: '12px' }}>Send Report to Finance?</h3>
                  <p style={{ fontSize: '14px', color: '#64748b', marginBottom: '24px', lineHeight: '1.6' }}>
                    The report has been generated. Send it to the Finance Department email?
                  </p>
                  <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0', marginBottom: '32px', textAlign: 'left' }}>
                    <div style={{ fontSize: '9px', fontWeight: '800', color: '#94a3b8', textTransform: 'uppercase' }}>Recipient</div>
                    <div style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>{financeEmail}</div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button 
                      className="admin-input" 
                      style={{ background: 'var(--admin-accent)', color: '#111', fontWeight: '800', border: 'none', cursor: isExporting ? 'not-allowed' : 'pointer' }}
                      disabled={isExporting}
                      onClick={async () => {
                        setIsExporting(true);
                        try {
                          await API.dispatchFinanceReport();
                          setShowFinanceModal(false);
                          alert(`Report successfully dispatched to ${financeEmail}`);
                        } catch (err: any) {
                          alert("Failed to dispatch report. Please check server connection.");
                        } finally {
                          setIsExporting(false);
                        }
                      }}
                    >
                      {isExporting ? 'SENDING...' : 'SEND EMAIL'}
                    </button>
                    <button 
                      className="admin-input" 
                      style={{ background: 'white', border: '1px solid #e2e8f0', color: '#64748b' }}
                      onClick={() => setShowFinanceModal(false)}
                    >
                      CLOSE
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Appeals View */}
          {currentView === 'appeals' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: '800' }}>APPEAL REQUESTS</h2>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Student</th>
                      <th>Application</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {appeals.map((a: any) => (
                      <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => handleAppClick(a.submission)}>
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>APP-{a.id}</span></td>
                        <td><strong>{a.student_details?.full_name || 'Student'}</strong></td>
                        <td style={{ fontSize: '12px' }}>{a.submission_details?.form_title || 'Application'}</td>
                        <td style={{ fontSize: '12px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.reason}</td>
                        <td>
                          <span className={`admin-badge ${a.status === 'resolved' ? 'badge-approved' : 'badge-review'}`}>
                            {a.status.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>{new Date(a.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                    {appeals.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No appeal requests found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default StaffDashboard;
