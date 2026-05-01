import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
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

type ViewMode = 'dashboard' | 'applications' | 'detail' | 'policy' | 'reports' | 'director' | 'payments' | 'director-queue' | 'director-detail' | 'appeals' | 'notifications';

const StaffDashboard: React.FC = () => {
  const [role, setRole] = useState<'ssw' | 'director'>(
    (localStorage.getItem('dgg_role')?.toLowerCase() === 'director') ? 'director' : 'ssw'
  );
  const [currentView, setCurrentView] = useState<ViewMode>(role === 'director' ? 'director-queue' : 'dashboard');
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [reportFundingType, setReportFundingType] = useState('all');
  const [reportSubFilter, setReportSubFilter] = useState('students');
  const [reportDateFrom, setReportDateFrom] = useState('');
  const [reportDateTo, setReportDateTo] = useState('');
  const [reportStatusFilter, setReportStatusFilter] = useState('all');
  const [showFinanceModal, setShowFinanceModal] = useState(false);
  const [financeEmail, setFinanceEmail] = useState('finance@deline.ca');
  const [isExporting, setIsExporting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Sync currentView with URL path and handle deep links
  useEffect(() => {
    const segments = location.pathname.split('/').filter(Boolean);
    if (segments.length > 1) {
      const view = segments[1] as ViewMode;
      if (view !== currentView) {
        setCurrentView(view);
      }

      // Handle deep-linking for application details via ?id=
      const params = new URLSearchParams(location.search);
      const appId = params.get('id');
      if (appId) {
        setSelectedAppId(appId);
      }
    }
  }, [location.pathname, location.search]);

  const [applications, setApplications] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payments, setPayments] = useState<any[]>([]);
  const [appeals, setAppeals] = useState<any[]>([]);
  const [userData, setUserData] = useState<any>(null);

  const fetchApplications = async (showLoader = false) => {
    if (showLoader || applications.length === 0) setIsLoading(true);
    
    // Start all requests in parallel
    const subsPromise = (role === 'director'
      // Directors only need FormSubmissions (backend already filters to forwarded/decided)
      ? API.getSubmissions().then((subsResp: any) => {
          const subs = Array.isArray(subsResp) ? subsResp : (subsResp?.results || []);
          setApplications(subs);
        })
      // Admins/SSW get both legacy applications and form submissions merged
      : Promise.all([
          API.getApplications(),
          API.getSubmissions()
        ]).then(([appsResp, subsResp]: [any, any]) => {
          const apps = Array.isArray(appsResp) ? appsResp : (appsResp?.results || []);
          const subs = Array.isArray(subsResp) ? subsResp : (subsResp?.results || []);
          const merged = [
            ...apps.map((a: any) => ({ ...a, _is_standard: true })),
            ...subs
          ];
          setApplications(merged);
        })
    );

    const statsPromise = API.getDashboardStats().then((resp: any) => {
      setBackendStats(resp || null);
    });

    const notifsPromise = API.getNotifications().then((resp: any) => {
      setNotifications(Array.isArray(resp) ? resp : []);
    });

    const appealsPromise = API.getAppeals().then((resp: any) => {
      setAppeals(Array.isArray(resp) ? resp : (resp?.results || []));
    });

    const mePromise = API.getMe().then((meResp: any) => {
      setUserData(meResp);
      const mappedRole = meResp.role?.toLowerCase();

      if (mappedRole === 'director' && role !== 'director') {
        setRole('director');
        localStorage.setItem('dgg_role', 'director');
      } else if ((mappedRole === 'admin' || mappedRole === 'ssw') && role !== 'ssw') {
        setRole('ssw');
        localStorage.setItem('dgg_role', 'admin');
      }
    });

    try {
      await Promise.allSettled([subsPromise, statsPromise, notifsPromise, mePromise, appealsPromise]);
    } catch (err: any) {
      console.error('Data sync failed:', err);
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
    fetchApplications(true); // Initial load with spinner
    const interval = setInterval(() => fetchApplications(false), 30000); // Silent poll every 30s
    return () => clearInterval(interval);
  }, [reportFundingType]); // Re-fetch when funding type filter changes

  useEffect(() => {
    const fetchFinanceConfig = async () => {
      try {
        const settings = await API.getPolicySettings() as any;
        // all_settings returns grouped dict: { section: [fields] }
        const sysConfig: any[] = settings?.system_config || [];
        const config = sysConfig.find((s: any) => s.field_key === 'finance_email');
        if (config) setFinanceEmail(config.unit || 'finance@deline.ca');
      } catch (e) { }
    };
    fetchFinanceConfig();
  }, []);

  const handleExcelExport = () => {
    setIsExporting(true);
    try {
      const approved = applications.filter((a: any) => a.status === 'accepted');
      const exportData = approved.map((a: any) => ({
        'Submission ID': a.id,
        'Student Name': a.student_details?.full_name || a.student_name || '',
        'Student Email': a.student_details?.email || '',
        'Beneficiary #': a.student_details?.beneficiary_number || '',
        'Form': a.form_title || '',
        'Stream': a.student_details?.primary_stream || '',
        'Approved Amount ($)': parseFloat(a.amount || 0),
        'Submitted Date': a.submitted_at ? new Date(a.submitted_at).toLocaleDateString() : '',
        'Decision Date': a.decided_at ? new Date(a.decided_at).toLocaleDateString() : '',
        'Decided By': a.decided_by_name || '',
      }));

      const worksheet = XLSX.utils.json_to_sheet(exportData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Approved Applications");
      XLSX.writeFile(workbook, `Approved_Applications_${new Date().toISOString().split('T')[0]}.xlsx`);
      setShowFinanceModal(true);
    } catch (err) {
      alert("Export failed");
    } finally {
      setIsExporting(false);
    }
  };

  const [backendStats, setBackendStats] = useState<any>(null);
  const [reportStats, setReportStats] = useState<any>(null);
  const [isReportLoading, setIsReportLoading] = useState(false);

  // ── REPORT PDF EXPORT (Task 10.7) ──
  const handleReportPDFExport = () => {
    try {
      const stats = reportStats || backendStats;
      const doc = new jsPDF();
      doc.setFontSize(18);
      doc.text('DGG Student Funding Report', 20, 20);
      doc.setFontSize(11);
      doc.text(`Generated: ${new Date().toLocaleDateString()}`, 20, 30);
      doc.text(`Funding Stream: ${reportFundingType.toUpperCase()}`, 20, 38);
      if (reportDateFrom || reportDateTo) {
        doc.text(`Period: ${reportDateFrom || 'All'} to ${reportDateTo || 'Present'}`, 20, 46);
      }
      doc.setFontSize(13);
      doc.text('Summary', 20, 58);
      doc.setFontSize(11);
      doc.text(`Total Students: ${stats?.total_students || 0}`, 20, 68);
      doc.text(`Total Submissions: ${stats?.total_submissions || 0}`, 20, 76);
      doc.text(`Total Approved Funding: $${(stats?.total_funding_approved || 0).toLocaleString()}`, 20, 84);
      doc.text(`Approval Rate: ${stats?.approval_rate || 0}%`, 20, 92);
      doc.setFontSize(13);
      doc.text('Quarterly Breakdown', 20, 106);
      doc.setFontSize(11);
      let y = 116;
      (stats?.quarterly_report || []).forEach((q: any) => {
        doc.text(`${q.quarter}: $${(q.amount || 0).toLocaleString()} (${q.count || 0} apps)`, 20, y);
        y += 8;
      });
      doc.save(`DGG_Report_${reportFundingType}_${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (err: any) {
      alert('PDF export failed: ' + err.message);
    }
  };

  // ── REPORT CSV EXPORT — downloads approved applications from backend ──
  const handleReportCSVExport = async () => {
    try {
      setIsExporting(true);
      const blob = await API.exportApprovedCSV({
        funding_type: reportFundingType,
        ...(reportDateFrom && { date_from: reportDateFrom }),
        ...(reportDateTo && { date_to: reportDateTo }),
      }) as any;
      const url = URL.createObjectURL(new Blob([blob], { type: 'text/csv;charset=utf-8;' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `DGG_Approved_${reportFundingType}_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert('CSV export failed: ' + (err.message || 'Unknown error'));
    } finally {
      setIsExporting(false);
    }
  };

  // ── DISPATCH APPROVED CSV TO FINANCE EMAIL ──
  const [isDispatching, setIsDispatching] = useState(false);
  const handleDispatchFinanceReport = async () => {
    try {
      setIsDispatching(true);
      const resp = await API.dispatchFinanceReport() as any;
      alert(`Report sent to ${resp?.recipient || financeEmail}`);
    } catch (err: any) {
      alert('Dispatch failed: ' + (err.message || 'Unknown error'));
    } finally {
      setIsDispatching(false);
    }
  };

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
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  const handleDecision = async (status: 'accepted' | 'rejected' | 'forwarded', notesOverride?: string) => {
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
      if (currentApp?._is_standard) {
        // Legacy applications use 'pending' for director approval
        const mappedStatus = status === 'forwarded' ? 'pending' : status;
        await API.updateApplicationStatus(Number(selectedAppId), mappedStatus, notesOverride ?? decisionNotes);
      } else {
        await API.updateSubmissionStatus(Number(selectedAppId), status, {
          decision_notes: notesOverride ?? decisionNotes,
          amount: amountToSave
        });
      }
      setShowConfirmModal(false);
      setShowRejectModal(false);
      setDecisionNotes('');
      setRejectReason('');
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
      const url = resp.url || `${window.location.origin}/shared/${resp.token}`;
      await navigator.clipboard.writeText(url);
      const days = resp.expires_at
        ? Math.round((new Date(resp.expires_at).getTime() - Date.now()) / 86400000)
        : 7;
      alert(`Secure share link (valid for ${days} days) copied to clipboard!`);
    } catch (err: any) {
      alert('Share failed: ' + err.message);
    }
  };

  const [showMoreInfoModal, setShowMoreInfoModal] = useState(false);
  const [moreInfoNotes, setMoreInfoNotes] = useState('');
  const [moreInfoLoading, setMoreInfoLoading] = useState(false);

  const handleRequestInfo = () => {
    if (!selectedAppId) return;
    setMoreInfoNotes('');
    setShowMoreInfoModal(true);
  };

  const handleSubmitMoreInfoRequest = async () => {
    if (!selectedAppId || !moreInfoNotes.trim()) return;
    setMoreInfoLoading(true);
    try {
      await API.requestMoreInfo(Number(selectedAppId), moreInfoNotes.trim());
      setShowMoreInfoModal(false);
      setMoreInfoNotes('');
      fetchApplications();
    } catch (err: any) {
      alert('Action failed: ' + err.message);
    } finally {
      setMoreInfoLoading(false);
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
      doc.text(`Notes: ${app.decision_reason || 'None'}`, 20, 110);

      doc.save(`Application_${app.id}.pdf`);
    } catch (err: any) {
      console.error('PDF Export Error:', err);
      alert('PDF generation failed: ' + err.message);
    }
  };

  const handleAddNote = async () => {
    if (!selectedAppId || !staffNote.trim()) return;
    setIsAddingNote(true);
    setNoteError(null);
    try {
      await API.addSubmissionNote(Number(selectedAppId), staffNote);
      setStaffNote('');
      fetchApplications(); // Refresh list to get new notes
    } catch (err: any) {
      setNoteError(err.message || 'Failed to add note');
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleMarkAllNotificationsRead = async () => {
    try {
      await API.markAllNotificationsRead();
      setNotifications(notifications.map((n: any) => ({ ...n, is_read: true })));
    } catch { }
  };

  const handleMarkNotificationRead = async (id: number) => {
    try {
      await API.markNotificationRead(id);
      setNotifications(notifications.map((n: any) => n.id === id ? { ...n, is_read: true } : n));
    } catch { }
  };

  const handleMarkLegitimate = async () => {
    if (!selectedAppId) return;
    try {
      await API.markLegitimate(Number(selectedAppId), 'Marked as legitimate by staff');
      setDuplicateStatus(null);
      delete duplicateCache.current[selectedAppId];
      fetchApplications();
      alert('Application marked as legitimate');
    } catch (err: any) {
      alert(err.message || 'Failed to mark as legitimate');
    }
  };

  const handleMarkDuplicate = async () => {
    if (!selectedAppId) return;
    try {
      await API.markDuplicate(Number(selectedAppId), 'Confirmed as duplicate by staff');
      setDuplicateStatus({ is_flagged: true, is_confirmed: true, message: 'Confirmed duplicate — payment blocked.' });
      duplicateCache.current[selectedAppId] = { is_flagged: true, is_confirmed: true, message: 'Confirmed duplicate — payment blocked.' };
      fetchApplications();
      alert('Application marked as duplicate');
    } catch (err: any) {
      alert(err.message || 'Failed to mark as duplicate');
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

  const fetchReportStats = async () => {
    setIsReportLoading(true);
    try {
      const stats = await API.getReportStats(reportFundingType, {
        dateFrom: reportDateFrom || undefined,
        dateTo: reportDateTo || undefined,
        status: reportStatusFilter !== 'all' ? reportStatusFilter : undefined,
      }) as any;
      setReportStats(stats || null);
    } catch (err) {
      console.error('Report stats fetch failed:', err);
    } finally {
      setIsReportLoading(false);
    }
  };

  useEffect(() => {
    if (currentView === 'policy' || currentView === 'detail' || currentView === 'director-detail') {
      fetchPolicySettings();
    }
    if (currentView === 'payments') {
      API.getPayments().then(res => setPayments(Array.isArray(res) ? res : [])).catch(e => console.error('Payments fetch failed', e));
    }
    if (currentView === 'appeals') {
      API.getAppeals().then(res => setAppeals(Array.isArray(res) ? res : [])).catch(e => console.error('Appeals fetch failed', e));
    }
    if (currentView === 'reports') {
      fetchReportStats();
    }
  }, [currentView]);

  // Re-fetch report stats when filters change
  useEffect(() => {
    if (currentView === 'reports') {
      fetchReportStats();
    }
  }, [reportFundingType, reportDateFrom, reportDateTo, reportStatusFilter]);

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
    // Reset note state when switching applications
    setStaffNote('');
    setNoteError(null);
  }, [selectedAppId, applications]);

  // ── ELIGIBILITY CHECK: Fetch when detail view opens for a selected application ──
  useEffect(() => {
    if (!selectedAppId || (currentView !== 'detail' && currentView !== 'director-detail')) {
      // Reset eligibility state when leaving detail view
      setEligibilityResult(null);
      setEligibilityError(null);
      return;
    }

    let cancelled = false;

    const fetchEligibility = async () => {
      // Check cache first (Task 3.6)
      if (eligibilityCache.current[selectedAppId]) {
        setEligibilityResult(eligibilityCache.current[selectedAppId]);
        return;
      }
      setIsEligibilityLoading(true);
      setEligibilityError(null);
      setEligibilityResult(null);
      try {
        const result = await API.checkEligibility(Number(selectedAppId));
        if (!cancelled) {
          eligibilityCache.current[selectedAppId] = result;
          setEligibilityResult(result);
        }
      } catch (err: any) {
        if (!cancelled) {
          setEligibilityError(err.message || 'Failed to check eligibility');
        }
      } finally {
        if (!cancelled) {
          setIsEligibilityLoading(false);
        }
      }
    };

    fetchEligibility();

    return () => {
      cancelled = true;
    };
  }, [selectedAppId, currentView]);

  // ── DUPLICATE CHECK: Fetch when detail view opens for a selected application ──
  useEffect(() => {
    if (!selectedAppId || (currentView !== 'detail' && currentView !== 'director-detail')) {
      // Reset duplicate state when leaving detail view
      setDuplicateStatus(null);
      setDuplicateError(null);
      return;
    }

    let cancelled = false;

    const fetchDuplicateStatus = async () => {
      // Check cache first (Task 3.6)
      if (duplicateCache.current[selectedAppId]) {
        setDuplicateStatus(duplicateCache.current[selectedAppId]);
        return;
      }
      setIsDuplicateLoading(true);
      setDuplicateError(null);
      setDuplicateStatus(null);
      try {
        const result = await API.checkDuplicates(Number(selectedAppId));
        if (!cancelled) {
          duplicateCache.current[selectedAppId] = result;
          setDuplicateStatus(result);
        }
      } catch (err: any) {
        if (!cancelled) {
          setDuplicateError(err.message || 'Failed to check duplicate status');
        }
      } finally {
        if (!cancelled) {
          setIsDuplicateLoading(false);
        }
      }
    };

    fetchDuplicateStatus();

    return () => {
      cancelled = true;
    };
  }, [selectedAppId, currentView]);

  // ── AUDIT TRAIL: Fetch when detail view opens for a selected application ──
  useEffect(() => {
    if (!selectedAppId || (currentView !== 'detail' && currentView !== 'director-detail')) {
      setAuditLogs([]);
      setAuditError(null);
      return;
    }

    let cancelled = false;

    const fetchAuditLogs = async () => {
      setIsAuditLoading(true);
      setAuditError(null);
      try {
        const result = await API.getAuditLogs({ submission: Number(selectedAppId) }) as any;
        if (!cancelled) {
          setAuditLogs(Array.isArray(result) ? result : []);
        }
      } catch (err: any) {
        if (!cancelled) {
          // Audit logs are supplementary — don't block the UI on error
          setAuditError(err.message || 'Failed to load audit logs');
          setAuditLogs([]);
        }
      } finally {
        if (!cancelled) {
          setIsAuditLoading(false);
        }
      }
    };

    fetchAuditLogs();

    return () => {
      cancelled = true;
    };
  }, [selectedAppId, currentView]);

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
  const [fundingStreamFilter, setFundingStreamFilter] = useState('all');
  const [sortColumn, setSortColumn] = useState<string>('submitted_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [eligibilityResult, setEligibilityResult] = useState<any>(null);
  const [isEligibilityLoading, setIsEligibilityLoading] = useState(false);
  const [eligibilityError, setEligibilityError] = useState<string | null>(null);
  const [duplicateStatus, setDuplicateStatus] = useState<any>(null);
  const [isDuplicateLoading, setIsDuplicateLoading] = useState(false);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // ── AUDIT TRAIL STATE ──
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isAuditLoading, setIsAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  // ── ELIGIBILITY & DUPLICATE CACHE (Task 3.6) ──
  const eligibilityCache = useRef<Record<string, any>>({});
  const duplicateCache = useRef<Record<string, any>>({});

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, fundingStreamFilter]);

  const filteredApps = applications.filter(app => {
    const fullName = (app.student_details?.full_name || '').toLowerCase();
    const email = (app.student_details?.email || '').toLowerCase();
    const beneficiaryNumber = (app.student_details?.beneficiary_number || '').toLowerCase();
    const query = searchQuery.toLowerCase();
    const matchesSearch = fullName.includes(query) ||
      String(app.id).includes(query) ||
      email.includes(query) ||
      beneficiaryNumber.includes(query) ||
      (app.form_title || '').toLowerCase().includes(query);
    const matchesStatus = statusFilter === 'all' || app.status === statusFilter;
    const matchesFunding = fundingStreamFilter === 'all' ||
      (app.form_title || app.form?.title || '').includes(fundingStreamFilter);
    return matchesSearch && matchesStatus && matchesFunding;
  });

  // Sorting logic
  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const getStudentName = (app: any) => {
    if (!app) return 'Student';
    const nameFromAnswers = (app.answers || []).find((a: any) =>
      (a.label || '').toLowerCase().includes('full name') ||
      (a.label || '').toLowerCase().includes('student name')
    )?.answer_text;

    const profileName = app.student_details?.full_name || app.student_name;
    
    // If profile name is generic (like Admin), use the form answer
    if (!profileName || profileName.includes('Administrator') || profileName.includes('Admin')) {
      return nameFromAnswers || profileName || 'Guest Applicant';
    }
    return profileName;
  };

  const filteredAndSortedApps = [...filteredApps].sort((a, b) => {
    let aVal: any;
    let bVal: any;

    // Handle nested student_name field
    if (sortColumn === 'student_name') {
      aVal = (a.student_details?.full_name || '').toLowerCase();
      bVal = (b.student_details?.full_name || '').toLowerCase();
    } else {
      aVal = a[sortColumn as keyof typeof a];
      bVal = b[sortColumn as keyof typeof b];
    }

    // Convert strings to lowercase for case-insensitive sorting
    if (typeof aVal === 'string') {
      aVal = (aVal || '').toLowerCase();
      bVal = (bVal || '').toLowerCase();
    }

    // Handle null/undefined values
    if (aVal == null) aVal = '';
    if (bVal == null) bVal = '';

    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });

  // Pagination
  const itemsPerPage = 10;
  const totalPages = Math.ceil(filteredAndSortedApps.length / itemsPerPage);
  const paginatedApps = filteredAndSortedApps.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const selectedApp = applications.find(a => String(a.id) === String(selectedAppId));

  const calculateAutoFunding = (app: any) => {
    if (!app || !app.answers || !policySettings) return null;

    const student = app.student_details || {};
    const profile = student.profile || {};

    // helper to get answer by label (case-insensitive fuzzy match)
    const getAns = (label: string) => app.answers.find((a: any) => (a.label || a.field_label || '').toLowerCase().includes(label.toLowerCase()))?.answer_text;

    // Stream identification
    let stream = getAns('bursaryStream') || student.primary_stream || 'DGGR';
    if (stream.includes('PSSSP')) stream = 'PSSSP';
    else if (stream.includes('UCEPP')) stream = 'UCEPP';
    else stream = 'DGGR';

    const enrollment = getAns('enrollmentType')?.toLowerCase() || student.enrollment_status?.toLowerCase() || 'full-time';
    const isFullTime = enrollment.includes('full');
    const hasDeps = (getAns('hasDependents')?.toLowerCase() === 'yes') || (student.num_dependents > 0);
    const requestedTuition = parseFloat(getAns('tuition') || '0');
    const startStr = getAns('semStart');
    const endStr = getAns('semEnd');

    // 0. Eligibility Check (NWT SFA Exclusion for PSSSP/UCEPP)
    const isNwtSfaEligible = profile.is_sfa_active || student.financial_assistance_status === 'Eligible';
    if ((stream === 'PSSSP' || stream === 'UCEPP') && isNwtSfaEligible) {
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
    let livingSection = 'dggr_rates';
    if (stream === 'PSSSP') livingSection = 'psssp_rates';
    else if (stream === 'UCEPP') livingSection = 'ucepp_rates';

    const depKey = hasDeps ? 'with_dep' : 'no_dep';
    const loadKey = isFullTime ? 'full' : 'part';
    const livingFieldKey = `living_${loadKey}_${depKey}`;

    const livingRate = getPolicySetting(livingSection, livingFieldKey);
    const totalLiving = livingRate * months;

    // 3. Tuition Award
    let tuitionLimit = 0;
    let tuitionRule = "";
    
    if (stream === 'PSSSP') {
      tuitionLimit = getPolicySetting('psssp_rates', 'tuition_cap');
      tuitionRule = `PSSSP cap: $${tuitionLimit} (includes books/fees)`;
    } else if (stream === 'UCEPP') {
      tuitionLimit = getPolicySetting('ucepp_rates', 'tuition_cap');
      tuitionRule = `UCEPP cap: $${tuitionLimit} (includes books/fees)`;
    } else {
      // DGGR Tuition Top-up (Fixed amount based on load)
      tuitionLimit = getPolicySetting('dggr_rates', isFullTime ? 'tuition_full' : 'tuition_part');
      tuitionRule = `DGGR Top-up: $${tuitionLimit} fixed`;
    }

    let finalTuition = stream === 'DGGR' ? tuitionLimit : Math.min(requestedTuition || tuitionLimit, tuitionLimit);

    // 4. DGGR Extra Tuition Relief (25% top-up for expensive programs)
    let extraRelief = 0;
    if (stream === 'DGGR') {
      const triggerSem = getPolicySetting('dggr_extra_tuition', 'trigger_semester');
      // Trigger if tuition > $5000 per semester or if user requested a lot
      if (requestedTuition > triggerSem) {
        const reliefPercent = getPolicySetting('dggr_extra_tuition', 'relief_percent');
        const reliefMaxSem = getPolicySetting('dggr_extra_tuition', 'relief_max_semester');
        // Up to 25% of tuition, max $4000 INCLUDING the regular bursary
        const potentialRelief = requestedTuition * reliefPercent;
        extraRelief = Math.min(potentialRelief, reliefMaxSem) - finalTuition;
        if (extraRelief < 0) extraRelief = 0;
      }
    }

    // 5. Special Awards/Bursaries (Graduation, Scholarship, etc.)
    let specialAwards = 0;
    let specialNote = "";

    // Graduation Award
    if (app.form_type === 'Graduation Bursary' || app.form_type === 'FormG' || (app.form?.title || '').toLowerCase().includes('graduation')) {
      const degreeType = getAns('degreeType') || student.program_credential || 'Diploma';
      const mappedKey = degreeType.toLowerCase().replace(/ /g, '_');
      specialAwards = getPolicySetting('dggr_grad_bursary', mappedKey);
      specialNote = `Graduation Award: ${degreeType}`;
    }

    // Academic Achievement Scholarship
    const gpa = parseFloat(getAns('gpa') || '0');
    if (gpa >= 80) {
      specialAwards += getPolicySetting('dggr_scholarship', 'gpa_80_plus');
      specialNote += (specialNote ? " + " : "") + "Scholarship (80%+)";
    } else if (gpa >= 70) {
      specialAwards += getPolicySetting('dggr_scholarship', 'gpa_70_79');
      specialNote += (specialNote ? " + " : "") + "Scholarship (70-79%)";
    }

    // Summer/Practicum Award
    if (app.form_type === 'Practicum' || app.form_type === 'FormF' || (app.form?.title || '').toLowerCase().includes('practicum')) {
      specialAwards += getPolicySetting('dggr_rates', 'summer_practicum_award');
      specialNote += (specialNote ? " + " : "") + "Summer/Practicum Award";
    }

    // Books & Supplies (Policy: PSSSP/UCEPP include it in tuition, DGGR doesn't specify a separate book bursary)
    // We will set it to 0 as it is now dynamic or bundled
    const bookAllowance = 0; 

    return {
      tuition: {
        system: finalTuition + extraRelief,
        requested: requestedTuition,
        rule: extraRelief > 0 ? `${tuitionRule} + 25% Extra Relief` : tuitionRule
      },
      living: {
        system: totalLiving,
        rate: livingRate,
        months,
        rule: `$${livingRate}/mo for ${months} months`
      },
      books: {
        system: bookAllowance,
        rule: stream === 'DGGR' ? 'Not specified in policy' : 'Included in tuition cap'
      },
      special: {
        system: specialAwards,
        rule: specialNote
      },
      total: finalTuition + totalLiving + extraRelief + bookAllowance + specialAwards,
      stream
    };
  };

  const autoSuggested = calculateAutoFunding(selectedApp);

  // Single Awards to be shown in the Appeals section for Director review
  const singleAwardTypes = [
    'Graduation Bursary',
    'Practicum',
    'Scholarship',
    'Hardship',
    'Summer Student'
  ];

  const displayAppeals = [
    ...appeals.map(a => ({
      id: `APL-${a.id}`,
      student: a.student_details?.full_name || 'Student',
      form_title: a.submission_details?.form_title || 'Appeal',
      reason: a.reason,
      status: a.status,
      date: a.created_at,
      original: a,
      type: 'appeal'
    })),
    ...applications.filter(app => {
      const type = (app.form_type || '').toLowerCase();
      return singleAwardTypes.some(t => type.includes(t.toLowerCase()));
    }).map(app => ({
      id: `APP-${app.id}`,
      student: app.student_details?.full_name || app.student_name || 'Student',
      form_title: app.form_title || 'Single Award',
      reason: `Direct Award Application: ${app.form_title}`,
      status: app.status,
      date: app.submitted_at || app.created_at,
      original: app,
      type: 'application'
    }))
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const pendingSpecialAwards = applications.filter(app => {
    const type = (app.form_type || '').toLowerCase();
    const isSpecial = singleAwardTypes.some(t => type.includes(t.toLowerCase()));
    return isSpecial && (app.status === 'pending' || app.status === 'new' || app.status === 'review');
  }).length;
  const totalAppealsBadge = (appeals.filter((a: any) => a.status === 'pending').length || 0) + pendingSpecialAwards;

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
    const statusClassMap: Record<string, string> = {
      pending: 'badge-pending',
      reviewed: 'badge-reviewed',
      forwarded: 'badge-forwarded',
      more_info_required: 'badge-pending',
      accepted: 'badge-accepted',
      rejected: 'badge-rejected'
    };
    const statusLabelMap: Record<string, string> = {
      more_info_required: 'More Info Required',
    };

    const badgeClass = statusClassMap[status] || '';
    const label = statusLabelMap[status] || (status.charAt(0).toUpperCase() + status.slice(1));

    return (
      <span className={`admin-badge ${badgeClass}`}>
        {label}
      </span>
    );
  };


  // Eligibility result rendering
  const renderEligibilityResult = () => {
    if (!eligibilityResult) return null;

    return (
      <div className="admin-chart-card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>
          ✓ ELIGIBILITY DETERMINATION
        </h3>

        {eligibilityResult.eligible_streams && eligibilityResult.eligible_streams.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ fontSize: '12px', fontWeight: '700', color: '#1a6b3a', marginBottom: '8px' }}>
              ELIGIBLE FOR
            </h4>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {eligibilityResult.eligible_streams.map((stream: string) => (
                <span key={stream} className="admin-badge" style={{ background: '#10b981', color: '#fff' }}>
                  {stream}
                </span>
              ))}
            </div>
          </div>
        )}

        {eligibilityResult.ineligible_streams && eligibilityResult.ineligible_streams.length > 0 && (
          <div>
            <h4 style={{ fontSize: '12px', fontWeight: '700', color: '#cc3333', marginBottom: '8px' }}>
              NOT ELIGIBLE FOR
            </h4>
            {eligibilityResult.ineligible_streams.map((stream: string) => (
              <div key={stream} style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#1e293b' }}>
                  {stream}
                </div>
                {eligibilityResult.details && eligibilityResult.details[stream] && (
                  <ul style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', paddingLeft: '20px' }}>
                    {eligibilityResult.details[stream].reasons?.map((reason: string, i: number) => (
                      <li key={i}>{reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Duplicate status rendering
  const renderDuplicateStatus = () => {
    if (!duplicateStatus || !duplicateStatus.is_flagged) return null;

    return (
      <div className="admin-chart-card" style={{ background: '#fef2f2', border: '1px solid #fecaca', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#b91c1c' }}>
          ⚠️ DUPLICATE FLAG
        </h3>
        <p style={{ fontSize: '13px', color: '#991b1b', marginBottom: '16px' }}>
          {duplicateStatus.message || 'This application has been flagged for review'}
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="admin-input"
            style={{ background: '#1a6b3a', color: '#fff', border: 'none', cursor: 'pointer', padding: '8px 16px', borderRadius: '6px' }}
            onClick={handleMarkLegitimate}
          >
            ✓ Mark as Legitimate
          </button>
          <button
            className="admin-input"
            style={{ background: '#cc3333', color: '#fff', border: 'none', cursor: 'pointer', padding: '8px 16px', borderRadius: '6px' }}
            onClick={handleMarkDuplicate}
          >
            ✕ Confirm Duplicate
          </button>
        </div>
      </div>
    );
  };

  // Funding breakdown rendering
  const renderFundingBreakdown = () => {
    // Show a "not yet calculated" state when policy settings haven't loaded
    const isPolicyLoaded = Object.keys(policySettings).length > 0;

    if (!isPolicyLoaded && !autoSuggested) {
      return (
        <div className="admin-chart-card" style={{ marginTop: '32px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '800' }}>💰 FUNDING BREAKDOWN</h3>
            <span className="admin-badge badge-pending" style={{ fontSize: '9px', padding: '2px 8px' }}>PENDING</span>
          </div>
          <div style={{ padding: '24px', background: '#f8fafc', borderRadius: '10px', border: '1px dashed #e2e8f0', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
            Funding calculation not yet available. Policy settings are loading or this application has not been processed.
          </div>
        </div>
      );
    }

    if (!autoSuggested) return null;

    // Handle ineligible case
    if (autoSuggested.ineligible) {
      return (
        <div className="admin-chart-card" style={{ marginTop: '32px', marginBottom: '24px', background: '#fef2f2', border: '1px solid #fecaca' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#b91c1c' }}>💰 FUNDING BREAKDOWN</h3>
            <span className="admin-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontSize: '9px', padding: '2px 8px' }}>INELIGIBLE</span>
          </div>
          <p style={{ fontSize: '13px', color: '#991b1b' }}>{autoSuggested.reason || 'Student does not meet eligibility criteria for this funding stream.'}</p>
        </div>
      );
    }

    const tuitionAmount = autoSuggested.tuition?.system ?? 0;
    const livingAmount = autoSuggested.living?.system ?? 0;
    const booksAmount = autoSuggested.books?.system ?? getPolicySetting('system_config', 'book_allowance') ?? 500;
    const specialAmount = autoSuggested.special?.system ?? 0;
    const totalAmount = autoSuggested.total ?? 0;

    const breakdownRows: Array<{ label: string; amount: number; note?: string; icon: string }> = [
      {
        icon: '🎓',
        label: 'Tuition',
        amount: tuitionAmount,
        note: autoSuggested.tuition?.rule,
      },
      {
        icon: '🏠',
        label: 'Living Allowance',
        amount: livingAmount,
        note: autoSuggested.living?.rule,
      },
      {
        icon: '📚',
        label: 'Books & Supplies',
        amount: booksAmount,
        note: autoSuggested.books?.rule,
      },
    ];

    if (specialAmount > 0) {
      breakdownRows.push({
        icon: '⭐',
        label: 'Special Awards',
        amount: specialAmount,
        note: autoSuggested.special?.rule || 'Academic or graduation award',
      });
    }

    return (
      <div className="admin-chart-card" style={{ marginTop: '32px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '800' }}>💰 FUNDING BREAKDOWN</h3>
          <span className="admin-badge" style={{ background: '#dcfce7', color: '#166534', fontSize: '9px', padding: '2px 8px' }}>
            {autoSuggested.stream || 'SYSTEM CALCULATED'}
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
          {breakdownRows.map((row, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '14px 16px',
                background: idx % 2 === 0 ? '#f8fafc' : '#fff',
                borderRadius: idx === 0 ? '8px 8px 0 0' : idx === breakdownRows.length - 1 ? '0 0 8px 8px' : '0',
                border: '1px solid #e2e8f0',
                borderTop: idx === 0 ? '1px solid #e2e8f0' : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '16px', width: '24px', textAlign: 'center' }}>{row.icon}</span>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: '600', color: '#1e293b' }}>{row.label}</div>
                  {row.note && (
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>{row.note}</div>
                  )}
                </div>
              </div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#1e293b' }}>
                ${(row.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
          ))}

          {/* Total row */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '16px 16px',
              background: '#1e293b',
              borderRadius: '0 0 8px 8px',
              marginTop: '2px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '16px', width: '24px', textAlign: 'center' }}>💵</span>
              <div style={{ fontSize: '14px', fontWeight: '800', color: '#fff', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Total Funding
              </div>
            </div>
            <div style={{ fontSize: '18px', fontWeight: '900', color: '#e5a662' }}>
              ${(totalAmount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Approved amount comparison (if already decided) */}
        {selectedApp?.amount > 0 && selectedApp?.status === 'accepted' && (
          <div style={{ marginTop: '16px', padding: '12px 16px', background: '#f0fdf4', borderRadius: '8px', border: '1px solid #dcfce7', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#166534' }}>✓ Approved Amount</div>
            <div style={{ fontSize: '14px', fontWeight: '800', color: '#166534' }}>
              ${parseFloat(selectedApp?.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Banking details rendering (director only)
  const renderBankingDetails = () => {
    if (role !== 'director' || !selectedApp?.student_details) return null;

    return (
      <div className="admin-chart-card" style={{ background: '#f0fdf4', border: '1px solid #dcfce7', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#166534' }}>
          🔒 BANKING DETAILS (DIRECTOR ONLY)
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              ACCOUNT HOLDER
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {selectedApp.student_details.account_holder_name || selectedApp.student_details.full_name}
            </div>
          </div>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              BANK NAME
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {selectedApp.student_details.bank_name || 'N/A'}
            </div>
          </div>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              ACCOUNT NUMBER
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {selectedApp.student_details.account_number || 'N/A'}
            </div>
          </div>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              TRANSIT NUMBER
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {selectedApp.student_details.transit_number || 'N/A'}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Handler functions for duplicate detection

  // ── AUDIT TRAIL TIMELINE ──
  const renderAuditTrail = () => {
    const app = applications.find(a => String(a.id) === String(selectedAppId));

    // Build timeline entries from submission data
    const timelineEntries: Array<{
      action: string;
      performer: string;
      timestamp: string;
      color: string;
      icon: string;
    }> = [];

    if (app) {
      // 1. Application submitted
      if (app.submitted_at) {
        timelineEntries.push({
          action: 'Application Submitted',
          performer: app.student_details?.full_name || 'Student',
          timestamp: app.submitted_at,
          color: '#1a6b3a',
          icon: '📋',
        });
      }

      // 2. Reviewed by SSW
      if (app.reviewed_at) {
        const reviewerName = app.reviewed_by_name || (app.reviewed_by ? `Staff #${app.reviewed_by}` : 'Staff Member');
        timelineEntries.push({
          action: 'Application Reviewed',
          performer: reviewerName,
          timestamp: app.reviewed_at,
          color: '#3182ce',
          icon: '🔍',
        });
      }

      // 3. Forwarded to Director
      if (app.forwarded_at) {
        const forwarderName = app.forwarded_by_name || (app.forwarded_by ? `Staff #${app.forwarded_by}` : 'Staff Member');
        timelineEntries.push({
          action: 'Forwarded to Director',
          performer: forwarderName,
          timestamp: app.forwarded_at,
          color: '#a855f7',
          icon: '📤',
        });
      }

      // 4. Final decision
      if (app.decided_at) {
        const deciderName = app.decided_by_name || (app.decided_by ? `Director #${app.decided_by}` : 'Director');
        const isApproved = app.status === 'accepted';
        timelineEntries.push({
          action: `Application ${isApproved ? 'Approved' : 'Rejected'}`,
          performer: deciderName,
          timestamp: app.decided_at,
          color: isApproved ? '#1a6b3a' : '#cc3333',
          icon: isApproved ? '✅' : '❌',
        });
      }

      // 5. Notes added (from submission notes)
      if (app.notes && Array.isArray(app.notes)) {
        app.notes.forEach((note: any) => {
          if (note.created_at) {
            timelineEntries.push({
              action: 'Note Added',
              performer: note.added_by_name || note.author_name || 'Staff Member',
              timestamp: note.created_at,
              color: '#e5a662',
              icon: '📝',
            });
          }
        });
      }
    }

    // Merge in any additional audit log entries from the API
    auditLogs.forEach((log: any) => {
      if (log.timestamp) {
        const performerName = log.performed_by_details?.full_name || log.role || 'System';
        timelineEntries.push({
          action: log.action || 'Action Recorded',
          performer: performerName,
          timestamp: log.timestamp,
          color: '#64748b',
          icon: '🔒',
        });
      }
    });

    // Sort all entries chronologically (oldest first)
    timelineEntries.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    const formatTimestamp = (ts: string) => {
      try {
        const d = new Date(ts);
        return d.toLocaleString('en-CA', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });
      } catch {
        return ts;
      }
    };

    return (
      <div className="audit-trail-section" style={{ marginTop: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0 }}>🕐 AUDIT TRAIL</h3>
          {!isAuditLoading && (
            <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}>
              {timelineEntries.length} EVENT{timelineEntries.length !== 1 ? 'S' : ''}
            </span>
          )}
        </div>

        {/* Loading state */}
        {isAuditLoading && (
          <div className="audit-trail-loading">
            <div className="audit-trail-spinner"></div>
            <span>Loading audit trail...</span>
          </div>
        )}

        {/* Error state */}
        {auditError && !isAuditLoading && (
          <div className="audit-trail-error">
            <span>⚠️</span>
            <span>Could not load additional audit entries: {auditError}</span>
          </div>
        )}

        {/* Empty state */}
        {!isAuditLoading && timelineEntries.length === 0 && (
          <div className="audit-trail-empty">
            <div className="audit-trail-empty-icon">📋</div>
            <div className="audit-trail-empty-text">No audit entries yet</div>
            <div className="audit-trail-empty-sub">Actions taken on this application will appear here</div>
          </div>
        )}

        {/* Timeline */}
        {!isAuditLoading && timelineEntries.length > 0 && (
          <div className="audit-timeline">
            {timelineEntries.map((entry, idx) => (
              <div key={idx} className={`audit-timeline-item ${idx === timelineEntries.length - 1 ? 'audit-timeline-item--last' : ''}`}>
                <div className="audit-timeline-dot" style={{ background: entry.color }}></div>
                <div className="audit-timeline-content">
                  <div className="audit-timeline-action">
                    <span className="audit-timeline-icon">{entry.icon}</span>
                    <span className="audit-timeline-action-text">{entry.action}</span>
                  </div>
                  <div className="audit-timeline-meta">
                    <span className="audit-timeline-performer">{entry.performer}</span>
                    <span className="audit-timeline-separator">·</span>
                    <span className="audit-timeline-time">{formatTimestamp(entry.timestamp)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ── SUBMITTED INFORMATION SECTION ──
  // Converts snake_case or camelCase field labels to human-readable format
  const formatFieldLabel = (label: string): string => {
    if (!label) return '';
    // Replace underscores and hyphens with spaces
    let formatted = label.replace(/[_-]/g, ' ');
    // Insert space before capital letters (camelCase → words)
    formatted = formatted.replace(/([a-z])([A-Z])/g, '$1 $2');
    // Capitalize first letter of each word
    formatted = formatted.replace(/\b\w/g, (c) => c.toUpperCase());
    return formatted.trim();
  };

  const renderAnswerText = (text: string) => {
    if (!text) return 'N/A';

    // Check if it's a JSON array (like Expense List)
    if (text.startsWith('[') && text.endsWith(']')) {
      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed) && parsed.length > 0) {
          // Check if it's the specific expense list structure
          if (parsed[0].description && parsed[0].amount) {
            return (
              <div className="json-answer-table-wrap" style={{ marginTop: '8px', background: '#fff', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
                <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #cbd5e1', textAlign: 'left', color: '#64748b' }}>
                      <th style={{ padding: '4px 0', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Item</th>
                      <th style={{ padding: '4px 0', textAlign: 'right', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Amt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parsed.map((item: any, idx: number) => (
                      <tr key={idx} style={{ borderBottom: idx === parsed.length - 1 ? 'none' : '1px solid #f1f5f9' }}>
                        <td style={{ padding: '6px 0', color: '#1e293b' }}>{item.description}</td>
                        <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: '700', color: '#1e293b' }}>${parseFloat(item.amount).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
        }
      } catch (e) {
        // Not valid JSON, just return text
      }
    }

    return text;
  };

  // Determine if an answer is a file upload (URL pointing to a file)
  const isFileAnswer = (answer: any): boolean => {
    if (answer.answer_file) return true;
    const text = answer.answer_text || '';
    return (
      text.startsWith('http') ||
      text.startsWith('/media/') ||
      /\.(pdf|doc|docx|jpg|jpeg|png|gif|xlsx|xls|csv)$/i.test(text)
    );
  };

  // Group answers into logical sections based on common field label patterns
  const groupAnswers = (answers: any[]): Record<string, any[]> => {
    const groups: Record<string, any[]> = {
      'Personal Information': [],
      'Program & Enrollment': [],
      'Financial Information': [],
      'Documents & Files': [],
      'Other Information': [],
    };

    const personalKeywords = ['name', 'email', 'phone', 'address', 'dob', 'birth', 'gender', 'treaty', 'beneficiary', 'sin', 'postal', 'city', 'province', 'contact', 'pronouns'];
    const programKeywords = ['program', 'institution', 'school', 'university', 'college', 'semester', 'enrollment', 'enrolment', 'course', 'year', 'start', 'end', 'gpa', 'grade', 'credential', 'degree', 'diploma', 'certificate', 'practicum', 'placement'];
    const financialKeywords = ['tuition', 'income', 'amount', 'funding', 'bursary', 'scholarship', 'payment', 'bank', 'account', 'transit', 'financial', 'dependent', 'stream', 'award', 'cost', 'fee', 'expense', 'budget'];

    for (const answer of answers) {
      const label = (answer.label || answer.field?.label || answer.field_label || '').toLowerCase();

      if (isFileAnswer(answer)) {
        groups['Documents & Files'].push(answer);
      } else if (personalKeywords.some(kw => label.includes(kw))) {
        groups['Personal Information'].push(answer);
      } else if (programKeywords.some(kw => label.includes(kw))) {
        groups['Program & Enrollment'].push(answer);
      } else if (financialKeywords.some(kw => label.includes(kw))) {
        groups['Financial Information'].push(answer);
      } else {
        groups['Other Information'].push(answer);
      }
    }

    // Remove empty groups
    return Object.fromEntries(Object.entries(groups).filter(([, items]) => items.length > 0));
  };

  const renderSubmittedInformation = () => {
    const app = applications.find(a => String(a.id) === String(selectedAppId));
    if (!app) return null;

    const answers: any[] = app.answers || [];

    if (answers.length === 0) {
      return (
        <div style={{ marginTop: '32px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>SUBMITTED INFORMATION</h3>
          <div style={{ padding: '24px', background: '#f8fafc', borderRadius: '10px', border: '1px dashed #e2e8f0', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
            No form answers available for this submission.
          </div>
        </div>
      );
    }

    const grouped = groupAnswers(answers);

    const groupIcons: Record<string, string> = {
      'Personal Information': '👤',
      'Program & Enrollment': '🎓',
      'Financial Information': '💰',
      'Documents & Files': '📎',
      'Other Information': '📋',
    };

    return (
      <div style={{ marginTop: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '800' }}>SUBMITTED INFORMATION</h3>
          <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}>
            {answers.length} FIELD{answers.length !== 1 ? 'S' : ''}
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {Object.entries(grouped).map(([groupName, groupAnswers]) => (
            <div key={groupName} className="submitted-info-group">
              <div className="submitted-info-group-header">
                <span style={{ marginRight: '8px' }}>{groupIcons[groupName] || '📋'}</span>
                {groupName}
              </div>
              <div className="submitted-info-grid">
                {groupAnswers.map((answer: any, idx: number) => {
                  const fieldLabel = answer.label || answer.field?.label || answer.field_label || `Field ${idx + 1}`;
                  const displayLabel = formatFieldLabel(fieldLabel);
                  const fileUrl = answer.answer_file || (isFileAnswer(answer) ? answer.answer_text : null);
                  const textValue = answer.answer_text;

                  return (
                    <div key={answer.id || idx} className="submitted-info-field">
                      <div className="submitted-info-label">{displayLabel}</div>
                      {fileUrl ? (
                        <div className="submitted-info-file">
                          <span style={{ fontSize: '16px', marginRight: '8px' }}>
                            {fileUrl.toLowerCase().endsWith('.pdf') ? '📄' :
                              /\.(jpg|jpeg|png|gif)$/i.test(fileUrl) ? '🖼️' : '📎'}
                          </span>
                          <a
                            href={fileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="submitted-info-download-link"
                            aria-label={`Download ${displayLabel}`}
                          >
                            {fileUrl.split('/').pop() || 'Download File'}
                          </a>
                        </div>
                      ) : (
                        <div className="submitted-info-value">
                          {textValue && textValue.trim() !== '' ? renderAnswerText(textValue) : (
                            <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Not provided</span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Mock navigation helper
  const renderNavItem = (id: ViewMode, label: string, icon: React.ReactNode, badge?: number) => (
    <div
      className={`staff-nav-item ${currentView === id ? 'active' : ''}`}
      onClick={() => {
        setCurrentView(id);
        if (id !== 'detail') setSelectedAppId(null);
        setSidebarOpen(false); // Close sidebar on mobile after navigation
      }}
    >
      {icon} {label}
      {badge && <span className="staff-nav-badge">{badge}</span>}
    </div>
  );

  return (
    <>
    <div className="staff-portal-root">
      {/* Mobile sidebar overlay */}
      <div
        className={`staff-sidebar-overlay ${sidebarOpen ? 'overlay-visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <div id="staff-sidebar" className={`staff-sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
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
                {renderNavItem('director-queue', 'Approval Queue', <AdminIcons.Director />, applications.filter(a => a.status === 'forwarded').length || undefined)}
                {renderNavItem('payments', 'Payments', <AdminIcons.Dashboard />)}
              </div>

              <div className="staff-nav-group">
                <div className="staff-nav-title">Governance</div>
                {renderNavItem('reports', 'Reports', <AdminIcons.Reports />)}
                {renderNavItem('policy', 'Policy Settings', <AdminIcons.Policy />)}
                {renderNavItem('appeals', 'Appeals & Awards', <AdminIcons.Apps />, totalAppealsBadge || undefined)}
                {renderNavItem('notifications', 'Notifications', <AdminIcons.Dashboard />, notifications.filter((n: any) => !n.is_read).length || undefined)}
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
          {/* Hamburger menu button — visible on mobile only */}
          <button
            className="staff-mobile-menu-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={sidebarOpen}
            aria-controls="staff-sidebar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {sidebarOpen ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>
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
            <div style={{ position: 'relative', cursor: 'pointer' }} onClick={() => setCurrentView('notifications')}>
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
                <button onClick={() => fetchApplications(true)} style={{ marginLeft: '12px', background: 'none', border: 'none', color: '#c53030', textDecoration: 'underline', fontWeight: '800', cursor: 'pointer' }}>Try Again</button>
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

              <div className="admin-kpi-row admin-kpi-row-4">
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
              <div className="admin-insights-row">
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
                      <tr
                        key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}
                        className="clickable-row"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleAppClick(app.id)}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                        role="button"
                        aria-label={`View application ${app.id} for ${app.student_details?.full_name || 'Anonymous Student'}`}
                      >
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}># {app.id}</span></td>
                        <td><strong>{getStudentName(app)}</strong></td>
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
          {currentView === 'applications' && role === 'director' && (
            // Directors don't have an "All Applications" view — redirect to queue
            <div className="fade-in" style={{ padding: '40px', textAlign: 'center' }}>
              <div style={{ fontSize: '32px', marginBottom: '16px' }}>🔒</div>
              <h3 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>Access Restricted</h3>
              <p style={{ color: '#64748b', marginBottom: '24px' }}>Directors can only view applications that have been forwarded for approval.</p>
              <button className="admin-badge badge-approved" style={{ padding: '10px 24px', cursor: 'pointer', border: 'none', fontWeight: '700' }} onClick={() => setCurrentView('director-queue')}>
                Go to Approval Queue →
              </button>
            </div>
          )}

          {currentView === 'applications' && role !== 'director' && (
            <div className="fade-in">
              <div className="admin-filters admin-filters-bar">
                <div className="admin-search">
                  <input
                    type="text"
                    className="admin-input"
                    placeholder="Search by name, ID, email, or beneficiary number..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <select
                  className="admin-input"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="all">Status: All</option>
                  <option value="pending">Pending</option>
                  <option value="reviewed">Reviewed</option>
                  <option value="forwarded">Forwarded</option>
                  <option value="accepted">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
                <select
                  className="admin-input"
                  value={fundingStreamFilter}
                  onChange={(e) => setFundingStreamFilter(e.target.value)}
                >
                  <option value="all">Stream: All</option>
                  <option value="PSSSP">PSSSP</option>
                  <option value="UCEPP">UCEPP</option>
                  <option value="DGGR">DGGR</option>
                </select>
                <select className="admin-input">
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
                      <th
                        onClick={() => handleSort('id')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        REF # {sortColumn === 'id' && (sortDirection === 'asc' ? '↑' : '↓')}
                      </th>
                      <th
                        onClick={() => handleSort('student_name')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        APPLICANT {sortColumn === 'student_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                      </th>
                      <th
                        onClick={() => handleSort('form_title')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        INSTITUTION / PROGRAM {sortColumn === 'form_title' && (sortDirection === 'asc' ? '↑' : '↓')}
                      </th>
                      <th
                        onClick={() => handleSort('submitted_at')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        SUBMITTED {sortColumn === 'submitted_at' && (sortDirection === 'asc' ? '↑' : '↓')}
                      </th>
                      <th
                        onClick={() => handleSort('status')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        STATUS {sortColumn === 'status' && (sortDirection === 'asc' ? '↑' : '↓')}
                      </th>
                      <th>VERIFICATION</th>
                      <th
                        onClick={() => handleSort('amount')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        FUNDING $ {sortColumn === 'amount' && (sortDirection === 'asc' ? '↑' : '↓')}
                      </th>
                      <th>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedApps.map(app => (
                      <tr
                        key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}
                        className="clickable-row"
                        onClick={() => handleAppClick(app.id)}
                        style={{ cursor: 'pointer' }}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                        role="button"
                        aria-label={`View application ${app.id} for ${app.student_details?.full_name || 'Student'}`}
                      >
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>{app.id}</span></td>
                        <td><strong>{getStudentName(app)}</strong></td>
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
                            {app.status === 'forwarded' ? 'DECIDE →' : 'Review →'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="pagination-container">
                  <div style={{ fontSize: '12px', color: '#64748b' }}>
                    Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredAndSortedApps.length)} of {filteredAndSortedApps.length} applications
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button
                      className="pagination-btn"
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      ← Previous
                    </button>
                    <span style={{ fontSize: '12px', color: '#64748b', fontWeight: '600' }}>
                      Page {currentPage} of {totalPages}
                    </span>
                    <button
                      className="pagination-btn"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >
                      Next →
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {/* end applications view for non-directors */}

          {/* Detail View (Shared by Staff and Director) */}
          {(currentView === 'detail' && selectedAppId) && (
            <div className="fade-in">
              {/* Header Actions */}
              <div className="admin-detail-header">
                <div style={{ fontSize: '11px', color: '#64748b' }}>
                  All Applications / <span style={{ fontWeight: '700', color: '#1e293b' }}>{selectedAppId}</span>
                </div>
                <div className="admin-detail-actions">
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }} onClick={handlePDFExport}>Export PDF</button>
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }} onClick={handleShareView}>Share View</button>
                  {/* SSW-only actions — hidden from director */}
                  {role !== 'director' && (
                    <>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleRequestInfo}>REQUEST MORE INFO</button>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleAddNote} disabled={!staffNote.trim() || isLoading}>ADD NOTE</button>
                    </>
                  )}
                  {role === 'director' ? (
                    <>
                      <button
                        className="admin-input"
                        style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: duplicateStatus?.is_confirmed ? '#94a3b8' : '#1a6b3a', color: '#fff', border: 'none', cursor: duplicateStatus?.is_confirmed ? 'not-allowed' : 'pointer' }}
                        disabled={!!duplicateStatus?.is_confirmed}
                        title={duplicateStatus?.is_confirmed ? 'Blocked: confirmed duplicate application' : undefined}
                        onClick={() => setShowConfirmModal(true)}
                      >
                        APPROVE APPLICATION
                      </button>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: '#991b1b', color: '#fff', border: 'none' }} onClick={() => setShowRejectModal(true)}>REJECT</button>
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

              <div className="admin-detail-grid">
                {/* Left: Detail Forms */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    {(() => {
                      const app = applications.find(a => String(a.id) === String(selectedAppId));
                      const sd = app?.student_details || {};
                      const getAns = (lbl: string) => (app?.answers || []).find((a: any) =>
                        (a.label || a.field_label || '').toLowerCase().includes(lbl.toLowerCase())
                      )?.answer_text;
                      return (
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <div style={{ fontSize: '11px', color: '#64748b' }}>#{selectedAppId}</div>
                              <h2 style={{ fontSize: '20px', fontWeight: '800' }}>{sd.full_name || 'Student'} — {app?.form_title || 'Application'}</h2>
                              <div style={{ fontSize: '11px', color: '#64748b' }}>
                                Submitted {app?.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' }) : 'N/A'}
                              </div>
                            </div>
                            {getStatusBadge(app?.status || 'pending')}
                          </div>

                          <div style={{ padding: '20px', background: '#f8fafc', borderRadius: '10px' }}>
                            <div className="admin-nav-title" style={{ marginBottom: '16px', padding: '0' }}>STUDENT & PROGRAM</div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>NAME</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.full_name || 'N/A'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>BENEFICIARY #</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.beneficiary_number || 'None'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>DOB</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.dob || 'Not Provided'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>PHONE</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.phone || 'None'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>ENROLLMENT</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.enrollment_status || getAns('enrollment') || 'N/A'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>FUNDING STREAM</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.primary_stream || 'N/A'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>INSTITUTION</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.institution_name || getAns('institution') || getAns('school') || 'N/A'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>PROGRAM</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.program_credential || getAns('program') || 'N/A'}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>SEMESTER</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{sd.current_semester || getAns('semester') || 'N/A'}</div>
                              </div>
                            </div>
                          </div>
                        </>
                      );
                    })()}

                    {/* Eligibility Determination Section */}
                    <div style={{ marginTop: '32px' }}>
                      {isEligibilityLoading && (
                        <div className="admin-chart-card" style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{ width: '16px', height: '16px', border: '2px solid #e2e8f0', borderTopColor: 'var(--admin-accent)', borderRadius: '50%', animation: 'spin 1s linear infinite', flexShrink: 0 }}></div>
                          <span style={{ fontSize: '13px', color: '#64748b' }}>Checking eligibility...</span>
                        </div>
                      )}
                      {eligibilityError && !isEligibilityLoading && (
                        <div className="admin-chart-card" style={{ marginBottom: '24px', background: '#fef2f2', border: '1px solid #fecaca' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '16px' }}>⚠️</span>
                            <div>
                              <div style={{ fontSize: '13px', fontWeight: '700', color: '#b91c1c' }}>Eligibility Check Failed</div>
                              <div style={{ fontSize: '12px', color: '#991b1b', marginTop: '2px' }}>{eligibilityError}</div>
                            </div>
                          </div>
                        </div>
                      )}
                      {renderEligibilityResult()}
                    </div>

                    {/* Duplicate Flag Section */}
                    <div style={{ marginTop: '24px' }}>
                      {isDuplicateLoading && (
                        <div className="admin-chart-card" style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{ width: '16px', height: '16px', border: '2px solid #e2e8f0', borderTopColor: 'var(--admin-accent)', borderRadius: '50%', animation: 'spin 1s linear infinite', flexShrink: 0 }}></div>
                          <span style={{ fontSize: '13px', color: '#64748b' }}>Checking for duplicates...</span>
                        </div>
                      )}
                      {duplicateError && !isDuplicateLoading && (
                        <div className="admin-chart-card" style={{ marginBottom: '24px', background: '#fef2f2', border: '1px solid #fecaca' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '16px' }}>⚠️</span>
                            <div>
                              <div style={{ fontSize: '13px', fontWeight: '700', color: '#b91c1c' }}>Duplicate Check Failed</div>
                              <div style={{ fontSize: '12px', color: '#991b1b', marginTop: '2px' }}>{duplicateError}</div>
                            </div>
                          </div>
                        </div>
                      )}
                      {renderDuplicateStatus()}
                    </div>

                    {/* Submitted Information Section */}
                    {renderSubmittedInformation()}

                    {/* Funding Breakdown Section */}
                    {renderFundingBreakdown()}

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
                              <td style={{ fontSize: '11px' }}><span className="admin-badge" style={{ background: '#dcfce7', color: '#166534' }}>{autoSuggested?.stream || selectedApp?.student_details?.primary_stream || 'DGGR'}</span></td>
                              <td style={{ fontSize: '11px', color: '#64748b' }}>{autoSuggested?.tuition?.rule}</td>
                              <td style={{ fontSize: '13px', fontWeight: '700' }}>${(autoSuggested?.tuition?.system || 0).toLocaleString()}</td>
                              <td><input type="text" className="admin-input" defaultValue={autoSuggested?.tuition?.system || 0} style={{ width: '100px', padding: '4px 8px' }} /></td>
                            </tr>
                            <tr>
                              <td style={{ fontSize: '12px' }}>Living Allowance</td>
                              <td style={{ fontSize: '11px' }}><span className="admin-badge" style={{ background: '#e0e7ff', color: '#3730a3' }}>{autoSuggested?.stream || selectedApp?.student_details?.primary_stream || 'DGGR'}</span></td>
                              <td style={{ fontSize: '11px', color: '#64748b' }}>{autoSuggested?.living?.rule}</td>
                              <td style={{ fontSize: '13px', fontWeight: '700' }}>${(autoSuggested?.living?.system || 0).toLocaleString()}</td>
                              <td><input type="text" className="admin-input" defaultValue={autoSuggested?.living?.system || 0} style={{ width: '100px', padding: '4px 8px' }} /></td>
                            </tr>
                            {(autoSuggested?.books?.system || 0) > 0 && (
                              <tr>
                                <td style={{ fontSize: '12px' }}>Books & Supplies</td>
                                <td style={{ fontSize: '11px' }}><span className="admin-badge" style={{ background: '#fff7ed', color: '#c2410c' }}>{autoSuggested?.stream || selectedApp?.student_details?.primary_stream || 'DGGR'}</span></td>
                                <td style={{ fontSize: '11px', color: '#64748b' }}>{autoSuggested?.books?.rule}</td>
                                <td style={{ fontSize: '13px', fontWeight: '700' }}>${(autoSuggested?.books?.system || 0).toLocaleString()}</td>
                                <td><input type="text" className="admin-input" defaultValue={autoSuggested?.books?.system || 0} style={{ width: '100px', padding: '4px 8px' }} /></td>
                              </tr>
                            )}
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
                              <td style={{ fontSize: '15px' }}><strong>${(autoSuggested?.total || 0).toLocaleString()}</strong></td>
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
                    <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', textAlign: 'center', padding: '8px' }} onClick={handlePDFExport}>EXPORT PDF</button>
                    <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', textAlign: 'center', padding: '8px' }} onClick={handleShareView}>SHARE LINK</button>
                  </div>

                  {/* Banking Details — Director only (Task 2.7) */}
                  {renderBankingDetails()}

                  {/* Duplicate confirmed warning banner (Task 4.6) */}
                  {duplicateStatus?.is_confirmed && (
                    <div style={{ background: '#fef2f2', border: '2px solid #ef4444', borderRadius: '10px', padding: '16px' }}>
                      <div style={{ fontSize: '13px', fontWeight: '800', color: '#b91c1c', marginBottom: '4px' }}>🚫 PAYMENT BLOCKED</div>
                      <div style={{ fontSize: '12px', color: '#991b1b' }}>This application is confirmed as a duplicate. Approval is disabled until resolved.</div>
                    </div>
                  )}

                  <div className="admin-chart-card">
                    {renderAuditTrail()}
                  </div>

                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#64748b', margin: 0 }}>STAFF NOTES (INTERNAL ONLY)</h3>
                      {applications.find(a => Number(a.id) === Number(selectedAppId))?.notes?.length > 0 && (
                        <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}>
                          {applications.find(a => Number(a.id) === Number(selectedAppId))!.notes.length} NOTE{applications.find(a => Number(a.id) === Number(selectedAppId))!.notes.length !== 1 ? 'S' : ''}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {/* Notes list */}
                      <div className="staff-notes-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto', paddingRight: '4px' }}>
                        {applications.find(a => Number(a.id) === Number(selectedAppId))?.notes?.length > 0 ? (
                          applications.find(a => Number(a.id) === Number(selectedAppId))!.notes.map((note: any) => (
                            <div key={note.id} className="staff-note-item" style={{ background: '#fcfaf8', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e5d5c0' }}>
                              <div style={{ fontSize: '12px', color: '#1e293b', lineHeight: '1.5' }}>{note.text}</div>
                              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: '600' }}>{note.author_name || note.added_by_name || 'Staff Member'}</span>
                                <span>{new Date(note.created_at).toLocaleString('en-CA', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                            </div>
                          ))
                        ) : (
                          <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', padding: '12px', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', border: '1px dashed #cbd5e1' }}>
                            No internal notes yet.
                          </div>
                        )}
                      </div>

                      {/* Error display */}
                      {noteError && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', fontSize: '12px', color: '#991b1b' }}>
                          <span>⚠️</span>
                          <span>{noteError}</span>
                          <button
                            onClick={() => setNoteError(null)}
                            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b', fontSize: '14px', lineHeight: 1 }}
                            aria-label="Dismiss error"
                          >
                            ✕
                          </button>
                        </div>
                      )}

                      {/* Add note input */}
                      <div style={{ background: '#fcfaf8', padding: '12px', borderRadius: '8px', border: '1px solid #e5d5c0' }}>
                        <textarea
                          className="admin-input"
                          placeholder="Add internal note — not visible to student..."
                          style={{ fontSize: '12px', border: 'none', background: 'transparent', resize: 'none', padding: '0', width: '100%', minHeight: '60px' }}
                          value={staffNote}
                          onChange={(e) => { setStaffNote(e.target.value); if (noteError) setNoteError(null); }}
                          disabled={isAddingNote}
                          aria-label="Internal staff note"
                        ></textarea>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                          <button
                            className="admin-badge badge-review"
                            style={{ cursor: !staffNote.trim() || isAddingNote ? 'not-allowed' : 'pointer', border: 'none', opacity: !staffNote.trim() || isAddingNote ? 0.5 : 1, padding: '6px 14px' }}
                            onClick={handleAddNote}
                            disabled={!staffNote.trim() || isAddingNote}
                            aria-label="Save internal note"
                          >
                            {isAddingNote ? (
                              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ width: '10px', height: '10px', border: '2px solid #e2e8f0', borderTopColor: '#475569', borderRadius: '50%', display: 'inline-block', animation: 'spin 1s linear infinite' }}></span>
                                Saving...
                              </span>
                            ) : 'Save Note'}
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
                        <input className="admin-input" type="date" value={officeUseInputs.dateReceived} onChange={e => setOfficeUseInputs({ ...officeUseInputs, dateReceived: e.target.value })} style={{ width: '100%', padding: '8px' }} />
                      </div>
                      <div>
                        <label className="admin-kpi-label" style={{ fontSize: '9px', marginBottom: '4px', display: 'block' }}>APPROVED BY</label>
                        <input className="admin-input" type="text" value={officeUseInputs.approvedBy} onChange={e => setOfficeUseInputs({ ...officeUseInputs, approvedBy: e.target.value })} style={{ width: '100%', padding: '8px' }} placeholder="Admin Name" />
                      </div>
                      <div>
                        <label className="admin-kpi-label" style={{ fontSize: '9px', marginBottom: '4px', display: 'block' }}>COMMITMENT #</label>
                        <input className="admin-input" type="text" value={officeUseInputs.commitmentNum} onChange={e => setOfficeUseInputs({ ...officeUseInputs, commitmentNum: e.target.value })} style={{ width: '100%', padding: '8px' }} placeholder="CM-00000" />
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
                {/* Policy editing is now open to both staff and directors */}
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
                  { id: 'payment_schedule', title: 'Payment Schedule', desc: 'Processing times and standard payment dates.' },
                  { id: 'application_deadlines', title: 'Application Deadlines', desc: 'Month numbers for semester application deadlines (1=Jan, 8=Aug, 12=Dec).' },
                  { id: 'system_config', title: 'System Configuration', desc: 'Contact info, email addresses, book allowance, and system defaults.' }
                ].map((section) => {
                  const items = policySettings[section.id] || [];
                  const isSectionExpanded = expandedSections[section.id];
                  const hasChanges = isDirty[section.id];
                  const lastUpdated = items[0]?.last_updated_at;
                  const updatedBy = items[0]?.last_updated_by_name;

                  return (
                    <div key={section.id} className="admin-chart-card" style={{ padding: '0', overflow: 'hidden', border: hasChanges ? '2px solid #f97316' : '1px solid #e2e8f0' }}>
                      <div
                        onClick={() => setExpandedSections({ ...expandedSections, [section.id]: !isSectionExpanded })}
                        style={{ padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', background: isSectionExpanded ? '#f8fafc' : 'white' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <h3 style={{ fontSize: '15px', fontWeight: '800', color: '#1e293b', margin: '0' }}>{section.title}</h3>
                          {hasChanges && <span style={{ background: '#fff7ed', color: '#c2410c', fontSize: '10px', fontWeight: '800', padding: '2px 8px', borderRadius: '4px', border: '1px solid #fdba74' }}>UNSAVED</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                          {(lastUpdated && !isSectionExpanded) && (
                            <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                              Last updated {new Date(lastUpdated).toLocaleDateString()}
                            </span>
                          )}
                          <span style={{ fontSize: '18px', color: '#64748b' }}>{isSectionExpanded ? '−' : '+'}</span>
                        </div>
                      </div>

                      {isSectionExpanded && (
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
                                    disabled={false} // Open to all staff/directors
                                    value={field.value}
                                    style={{ flex: '1', fontSize: '16px', fontWeight: '700', padding: '10px 14px' }}
                                    onChange={(e) => {
                                      const newVal = e.target.value;
                                      const newSettings = { ...policySettings };
                                      // Deep copy the array for this section to trigger React re-render
                                      const updatedSection = [...newSettings[section.id]];
                                      const itemIdx = updatedSection.findIndex(i => i.id === field.id);

                                      updatedSection[itemIdx] = {
                                        ...updatedSection[itemIdx],
                                        value: newVal
                                      };

                                      newSettings[section.id] = updatedSection;
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

                            {/* Visible to both staff and directors */}
                            <div style={{ display: 'flex', gap: '12px' }}>
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
                                    try {
                                      console.log("Saving policy section:", section.id, items);
                                      const resp = await API.updatePolicySetting('bulk', { section: section.id, settings: items }) as any;
                                      if (resp && (resp.success || resp.updated_count !== undefined)) {
                                        setIsDirty({ ...isDirty, [section.id]: false });
                                        await fetchPolicySettings();
                                        alert("Section updated successfully.");
                                      } else {
                                        alert("Failed to update section: " + (resp?.message || "Unknown error"));
                                      }
                                    } catch (err: any) {
                                      console.error("Policy save error:", err);
                                      alert(err.message || "Failed to update section.");
                                    }
                                  }}
                                >
                                  Save Section
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {currentView === 'reports' && (
            <div className="fade-in" style={{ padding: '0 20px 40px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                <div>
                  <h2 style={{ fontSize: '24px', fontWeight: '800', color: '#1e293b' }}>Reports & Analytics</h2>
                  <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>Real-time data aggregation for funding streams and student enrollment.</p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', padding: '10px 20px', fontWeight: '700' }} onClick={handleReportPDFExport}>
                    <span style={{ marginRight: '8px' }}>📄</span> Export PDF
                  </button>
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', padding: '10px 20px', fontWeight: '700' }} onClick={handleReportCSVExport} disabled={isExporting}>
                    <span style={{ marginRight: '8px' }}>📊</span> {isExporting ? 'Exporting...' : 'Export CSV'}
                  </button>
                  <button className="admin-badge badge-approved" style={{ border: 'none', cursor: 'pointer', padding: '10px 20px', fontWeight: '700' }} onClick={() => setShowFinanceModal(true)}>
                    <span style={{ marginRight: '8px' }}>📧</span> Email to Finance
                  </button>
                </div>
              </div>

              {/* Enhanced Filter Bar */}
              <div className="admin-chart-card" style={{ padding: '24px', marginBottom: '32px', background: '#fff' }}>
                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <div style={{ flex: '1', minWidth: '200px' }}>
                    <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '8px', textTransform: 'uppercase' }}>Funding Stream</label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {['all', 'UCEPP', 'CDFN', 'DGGR'].map(type => (
                        <button
                          key={type}
                          onClick={() => setReportFundingType(type.toLowerCase())}
                          style={{
                            flex: 1,
                            padding: '10px',
                            borderRadius: '8px',
                            border: reportFundingType === type.toLowerCase() ? '2px solid #111' : '1px solid #e2e8f0',
                            background: reportFundingType === type.toLowerCase() ? '#111' : '#f8fafc',
                            color: reportFundingType === type.toLowerCase() ? '#fff' : '#64748b',
                            fontWeight: '700',
                            fontSize: '12px',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                        >
                          {type}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '8px', textTransform: 'uppercase' }}>Period</label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <input type="date" className="admin-input" style={{ width: '140px' }} value={reportDateFrom} onChange={e => setReportDateFrom(e.target.value)} />
                      <span style={{ color: '#94a3b8' }}>to</span>
                      <input type="date" className="admin-input" style={{ width: '140px' }} value={reportDateTo} onChange={e => setReportDateTo(e.target.value)} />
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '8px', textTransform: 'uppercase' }}>Application Status</label>
                    <select className="admin-input" style={{ width: '160px' }} value={reportStatusFilter} onChange={e => setReportStatusFilter(e.target.value)}>
                      <option value="all">All Statuses</option>
                      <option value="pending">Pending</option>
                      <option value="reviewed">Reviewed</option>
                      <option value="forwarded">Forwarded</option>
                      <option value="accepted">Approved</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>

                  {(reportDateFrom || reportDateTo || reportStatusFilter !== 'all' || reportFundingType !== 'all') && (
                    <button
                      onClick={() => { setReportDateFrom(''); setReportDateTo(''); setReportStatusFilter('all'); setReportFundingType('all'); }}
                      style={{ height: '42px', padding: '0 16px', background: 'none', border: 'none', color: '#e11d48', fontWeight: '700', fontSize: '12px', cursor: 'pointer' }}
                    >
                      Reset Filters
                    </button>
                  )}
                </div>
              </div>

              {isReportLoading ? (
                <div style={{ padding: '100px', textAlign: 'center' }}>
                  <div className="admin-spinner" style={{ width: '40px', height: '40px', border: '3px solid #f1f5f9', borderTopColor: '#111', borderRadius: '50%', margin: '0 auto 20px', animation: 'spin 1s linear infinite' }}></div>
                  <div style={{ color: '#64748b', fontWeight: '600' }}>Aggregating system records...</div>
                </div>
              ) : (
                <div className="fade-in">
                  {/* Stats Cards Row */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px', marginBottom: '32px' }}>
                    <div className="admin-kpi-card" style={{ background: 'linear-gradient(135deg, #fff 0%, #f0f9ff 100%)', border: '1px solid #bae6fd' }}>
                      <div style={{ fontSize: '32px', fontWeight: '900', color: '#0369a1' }}>{(reportStats || backendStats)?.total_students || 0}</div>
                      <div className="admin-kpi-label" style={{ color: '#0ea5e9' }}>ACTIVE STUDENTS</div>
                    </div>
                    <div className="admin-kpi-card" style={{ background: 'linear-gradient(135deg, #fff 0%, #f0fdf4 100%)', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '32px', fontWeight: '900', color: '#15803d' }}>${((reportStats || backendStats)?.total_funding_approved || 0).toLocaleString()}</div>
                      <div className="admin-kpi-label" style={{ color: '#22c55e' }}>TOTAL DISBURSED</div>
                    </div>
                    <div className="admin-kpi-card" style={{ background: 'linear-gradient(135deg, #fff 0%, #fffbeb 100%)', border: '1px solid #fef3c7' }}>
                      <div style={{ fontSize: '32px', fontWeight: '900', color: '#b45309' }}>{(reportStats || backendStats)?.total_submissions || 0}</div>
                      <div className="admin-kpi-label" style={{ color: '#f59e0b' }}>TOTAL APPLICATIONS</div>
                    </div>
                    <div className="admin-kpi-card" style={{ background: 'linear-gradient(135deg, #fff 0%, #f8fafc 100%)', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '32px', fontWeight: '900', color: '#1e293b' }}>{Math.round(((reportStats || backendStats)?.submissions_by_status?.accepted || 0) / ((reportStats || backendStats)?.total_submissions || 1) * 100)}%</div>
                      <div className="admin-kpi-label">APPROVAL RATE</div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '32px' }}>
                    {/* Main Report Table */}
                    <div className="admin-chart-card" style={{ padding: '0' }}>
                      <div style={{ padding: '24px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0 }}>DETAILED RECORDS</h3>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>Showing {applications.length} results</div>
                      </div>
                      <div className="admin-table-wrap" style={{ border: 'none', boxShadow: 'none' }}>
                        <table className="admin-table">
                          <thead>
                            <tr>
                              <th>REF #</th>
                              <th>STUDENT</th>
                              <th>STREAM</th>
                              <th>STATUS</th>
                              <th>AMOUNT</th>
                            </tr>
                          </thead>
                          <tbody>
                            {applications.map((app: any) => (
                              <tr key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}>
                                <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{app.id}</span></td>
                                <td><strong>{app.student_details?.full_name || app.name}</strong></td>
                                <td><span className="admin-badge" style={{ background: '#f1f5f9', color: '#475569' }}>{app.form_title || 'General'}</span></td>
                                <td>{getStatusBadge(app.status)}</td>
                                <td style={{ fontWeight: '800' }}>${parseFloat(app.amount || 0).toLocaleString()}</td>
                              </tr>
                            ))}
                            {applications.length === 0 && (
                              <tr><td colSpan={5} style={{ textAlign: 'center', padding: '60px', color: '#94a3b8' }}>No records found for the selected filters.</td></tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Secondary Insights */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                      <div className="admin-chart-card">
                        <h3 style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', marginBottom: '20px', textTransform: 'uppercase' }}>STREAM ALLOCATION</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                          {['CDFN', 'DGGR', 'UCEPP'].map(stream => {
                            const stats = (reportStats || backendStats);
                            const streamKeyMap: Record<string, string> = { 'CDFN': 'pssp', 'DGGR': 'dggr', 'UCEPP': 'ucepp' };
                            const count = stats?.stream_split?.[streamKeyMap[stream]] || 0;
                            const total = stats?.total_submissions || 1;
                            const percent = (count / total) * 100;
                            const color = stream === 'CDFN' ? '#0369a1' : stream === 'DGGR' ? '#15803d' : '#b45309';

                            return (
                              <div key={stream}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '700', marginBottom: '6px' }}>
                                  <span>{stream}</span>
                                  <span>{count} apps</span>
                                </div>
                                <div style={{ height: '8px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                                  <div style={{ height: '100%', width: `${percent}%`, background: color, transition: 'width 0.5s ease-out' }}></div>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>

                      <div className="admin-chart-card" style={{ background: '#1e293b', color: '#fff' }}>
                        <h3 style={{ fontSize: '11px', fontWeight: '800', color: 'rgba(255,255,255,0.5)', marginBottom: '20px', textTransform: 'uppercase' }}>QUARTERLY TREND</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          {((reportStats || backendStats)?.quarterly_report || []).map((q: any) => (
                            <div key={q.quarter} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                              <div style={{ fontSize: '13px', fontWeight: '600' }}>{q.quarter}</div>
                              <div style={{ fontSize: '14px', fontWeight: '800', color: '#e5a662' }}>${(q.amount || 0).toLocaleString()}</div>
                            </div>
                          ))}
                          {((reportStats || backendStats)?.quarterly_report || []).length === 0 && (
                            <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.3)', fontSize: '12px', padding: '20px' }}>No quarterly data yet.</div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
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
              <div className="admin-kpi-row admin-kpi-row-4">
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
                      <tr key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}>
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{app.id}</span></td>
                        <td>
                          <strong>{getStudentName(app)}</strong>
                        </td>
                        <td style={{ fontSize: '12px' }}>{app.form_title}</td>
                        <td style={{ fontSize: '13px', fontWeight: '700' }}>${parseFloat(app.amount || 0).toLocaleString()}</td>
                        <td>
                          {app.amount > 10000 && <span className="admin-badge badge-review" style={{ fontSize: '9px', padding: '2px 6px' }}>HIGH VALUE</span>}
                          {!app.student_details && <span className="admin-badge" style={{ fontSize: '9px', padding: '2px 6px', background: '#fef3c7', color: '#92400e' }}>GUEST</span>}
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
                            <button
                              className="director-decision-icon-btn approve"
                              title="Quick Approve"
                              onClick={() => { setSelectedAppId(String(app.id)); setShowConfirmModal(true); }}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                            </button>
                            <button
                              className="director-decision-icon-btn deny"
                              title="Quick Deny"
                              onClick={() => { setSelectedAppId(String(app.id)); setShowRejectModal(true); }}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                            </button>
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
                        <tr key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`} style={{ cursor: 'pointer' }} onClick={() => { setSelectedAppId(String(app.id)); setCurrentView('director-detail'); }}>
                          <td><span style={{ fontSize: '10px', color: '#64748b' }}>{app.id}</span></td>
                          <td><strong>{getStudentName(app)}</strong></td>
                          <td style={{ fontSize: '11px' }}>{app.form_title || 'N/A'}</td>
                          <td style={{ fontSize: '12px', fontWeight: '700' }}>${parseFloat(app.amount || 0).toLocaleString()}</td>
                          <td>{getStatusBadge(app.status)}</td>
                          <td style={{ fontSize: '11px', color: '#64748b' }}>{app.decided_by_name || 'Director'}</td>
                          <td style={{ fontSize: '11px', color: '#64748b' }}>{app.decided_at ? new Date(app.decided_at).toLocaleDateString() : new Date(app.submitted_at || Date.now()).toLocaleDateString()}</td>
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
            (() => {
              const app = applications.find(a => String(a.id) === String(selectedAppId));
              return (
                <div className="fade-in">
              <div style={{ marginBottom: '20px' }}>
                <span style={{ fontSize: '11px', color: '#64748b' }}>Approval Queue / <span style={{ fontWeight: '700', color: '#1e293b' }}>{selectedAppId}</span></span>
              </div>

              <div className="admin-detail-grid">
                {/* Left: Application Content */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{selectedAppId}</div>
                        <h2 style={{ fontSize: '20px', fontWeight: '800' }}>
                          {(() => {
                            const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                            return `${getStudentName(app)} — ${app?.form_title || 'Application'}`;
                          })()}
                        </h2>
                        <div style={{ display: 'none' }}></div>
                        {(() => { const app = applications.find(a => Number(a.id) === Number(selectedAppId)); const ts = app?.forwarded_at || app?.submitted_at; return <div style={{ fontSize: '11px', color: '#64748b' }}>{app?.forwarded_at ? 'SSW forwarded' : 'Submitted'} {ts ? new Date(ts).toLocaleDateString() : 'N/A'}</div>; })()}
                      </div>
                      {applications.find(a => Number(a.id) === Number(selectedAppId))?.flags?.map((f: string) => (
                        <span key={f} className={`admin-badge badge-${f.toLowerCase()}`} style={{ fontSize: '9px', padding: '4px 10px' }}>{f}</span>
                      ))}
                    </div>

                    <div style={{ background: '#f8fafc', borderRadius: '10px', padding: '24px', border: '1px solid #e2e8f0', marginBottom: '32px' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', marginBottom: '20px', letterSpacing: '0.05em' }}>STUDENT & PROGRAM</h3>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '32px 24px' }}>
                        <div>
                          <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>NAME</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{getStudentName(app)}</div>
                        </div>
                        <div>
                          <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>BENEFICIARY #</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>
                            {app?.student_details?.beneficiary_number ||
                              (app?.answers || []).find((a: any) => (a.label || '').toLowerCase().includes('treaty') || (a.label || '').toLowerCase().includes('beneficiary'))?.answer_text ||
                              'N/A'}
                          </div>
                        </div>
                        <div>
                          <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>SFA STATUS</label>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.financial_assistance_status || 'N/A'}</div>
                        </div>
                      </div>
                      {(() => {
                        const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                        const getField = (lbl: string) => (app?.answers || []).find((a: any) =>
                          (a.label || a.field?.label || a.field_label || '').toLowerCase().includes(lbl.toLowerCase())
                        )?.answer_text;
                        return (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '16px', marginTop: '24px' }}>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>INSTITUTION</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.institution_name || getField('institution') || getField('school') || 'N/A'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>PROGRAM</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.program_credential || getField('program') || 'N/A'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>ENROLLMENT</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.enrollment_status || getField('enrollment') || 'Full-Time'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>SEMESTER</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.current_semester || getField('semester') || 'N/A'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>DEPENDENTS</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{app?.student_details?.num_dependents ?? getField('dependent') ?? '0'}</div>
                            </div>
                            <div>
                              <label style={{ fontSize: '9px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>STATUS</label>
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{getStatusBadge(app?.status || 'pending')}</div>
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
                          const answers: any[] = app?.answers || [];
                          const getField = (lbl: string) => answers.find((a: any) =>
                            (a.label || a.field?.label || '').toLowerCase().includes(lbl.toLowerCase())
                          )?.answer_text;

                          const formTitle = (app?.form_title || '').toLowerCase();
                          const isGraduation = formTitle.includes('graduation') || formTitle.includes('form g');
                          const isPracticum = formTitle.includes('practicum') || formTitle.includes('form f') || formTitle.includes('summer');

                          // Build dynamic rows from answers
                          const rows: { component: string; stream: string; rule: string; amount: number }[] = [];

                          if (isGraduation) {
                            const credential = getField('credential') || 'Certificate';
                            rows.push({
                              component: 'Graduation Bursary',
                              stream: 'DGGR',
                              rule: `${credential} — per policy dggr_grad_bursary`,
                              amount: parseFloat(app?.amount || 0),
                            });
                          } else if (isPracticum) {
                            rows.push({
                              component: 'Practicum / Summer Award',
                              stream: 'DGGR',
                              rule: 'Fixed award — per policy dggr_practicum_award',
                              amount: parseFloat(app?.amount || 0),
                            });
                          } else {
                            // Standard funding — show per-component breakdown from office_use_data if available
                            const officeData = app?.office_use_data || {};
                            const stream = getField('funding stream') || getField('bursarystream') || app?.student_details?.primary_stream || 'CDFN';
                            const tuition = parseFloat(officeData.tuition || 0);
                            const living = parseFloat(officeData.living || 0);
                            const books = parseFloat(officeData.books || 0);
                            const extra = parseFloat(officeData.extra_tuition || 0);
                            const total = parseFloat(app?.amount || 0);

                            if (tuition > 0) rows.push({ component: 'Tuition', stream, rule: `${stream} tuition cap`, amount: tuition });
                            if (living > 0) rows.push({ component: 'Living Allowance', stream, rule: `${stream} living rate × months`, amount: living });
                            if (books > 0) rows.push({ component: 'Books', stream, rule: 'Standard $500 allowance', amount: books });
                            if (extra > 0) rows.push({ component: 'Extra Tuition Relief', stream, rule: 'DGGR extra tuition cap', amount: extra });

                            // Fallback: single row if no breakdown available
                            if (rows.length === 0) {
                              rows.push({ component: 'Approved Funding', stream, rule: 'Full calculated payout', amount: total });
                            }
                          }

                          return (
                            <table className="admin-table table-dense">
                              <thead style={{ background: '#f8fafc' }}>
                                <tr>
                                  <th>COMPONENT</th>
                                  <th>STREAM</th>
                                  <th>POLICY RULE</th>
                                  <th>AMOUNT</th>
                                </tr>
                              </thead>
                              <tbody>
                                {rows.map((row, i) => (
                                  <tr key={i}>
                                    <td style={{ fontWeight: '600' }}>{row.component}</td>
                                    <td><span className="admin-badge" style={{ background: '#e0e7ff' }}>{row.stream}</span></td>
                                    <td style={{ fontSize: '10px', color: '#64748b' }}>{row.rule}</td>
                                    <td><strong>${(row.amount || 0).toLocaleString()}</strong></td>
                                  </tr>
                                ))}
                                <tr style={{ borderTop: '2px solid #e2e8f0', background: '#f8fafc' }}>
                                  <td colSpan={3} style={{ fontWeight: '800', textAlign: 'right', paddingRight: '20px' }}>Total Authorized</td>
                                  <td style={{ fontSize: '16px', fontWeight: '800' }}>${parseFloat(app?.amount || 0).toLocaleString()}</td>
                                </tr>
                              </tbody>
                            </table>
                          );
                        })()}
                      </div>
                    </div>

                    {(() => {
                      const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                      if (!app?.more_info_request_notes) return null;
                      return (
                        <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '10px', padding: '20px', marginBottom: '24px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                            <h4 style={{ fontSize: '11px', fontWeight: '800', color: '#c2410c', textTransform: 'uppercase', margin: 0 }}>⚠ INFORMATION REQUESTED FROM STUDENT</h4>
                            <span style={{ fontSize: '10px', color: '#9a3412' }}>
                              {app.more_info_requested_at ? new Date(app.more_info_requested_at).toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                              {app.more_info_requested_by_name ? ` · by ${app.more_info_requested_by_name}` : ''}
                            </span>
                          </div>
                          <p style={{ fontSize: '13px', color: '#7c2d12', lineHeight: '1.6', margin: '0 0 10px' }}>{app.more_info_request_notes}</p>
                          {app.more_info_responded_at ? (
                            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '8px 12px', fontSize: '11px', color: '#166534', fontWeight: '700' }}>
                              ✅ Student responded on {new Date(app.more_info_responded_at).toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </div>
                          ) : (
                            <div style={{ fontSize: '11px', color: '#9a3412', fontStyle: 'italic' }}>⏳ Awaiting student response...</div>
                          )}
                        </div>
                      );
                    })()}

                    {(() => {
                      const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                      const notes: any[] = app?.notes || [];
                      if (notes.length === 0) return null;
                      return (
                        <div style={{ background: '#eff6ff', border: '1px solid #dbeafe', borderRadius: '10px', padding: '20px', marginBottom: '32px' }}>
                          <h4 style={{ fontSize: '11px', fontWeight: '800', color: '#1e40af', textTransform: 'uppercase', marginBottom: '12px' }}>SSW NOTES</h4>
                          {notes.map((note: any, i: number) => (
                            <div key={note.id || i} style={{ marginBottom: i < notes.length - 1 ? '12px' : 0 }}>
                              <p style={{ fontSize: '13px', color: '#1e3a8a', lineHeight: '1.5', margin: 0 }}>{note.text}</p>
                              <div style={{ marginTop: '6px', fontSize: '11px', color: '#3b82f6' }}>
                                — {note.author_name || 'Staff'} · {note.created_at ? new Date(note.created_at).toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                              </div>
                            </div>
                          ))}
                        </div>
                      );
                    })()}

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
                      <div style={{ marginBottom: '24px' }}>
                        <label style={{ fontSize: '11px', fontWeight: '700', color: '#475569', display: 'block', marginBottom: '8px' }}>NOTES (OPTIONAL)</label>
                        <textarea
                          className="admin-input"
                          placeholder="Enter justification, exception details, or notes for the record..."
                          style={{ height: '120px', resize: 'none', fontSize: '13px', lineHeight: '1.5' }}
                          value={decisionNotes}
                          onChange={(e) => setDecisionNotes(e.target.value)}
                        ></textarea>
                        <div style={{ fontSize: '10px', color: '#cc3333', marginTop: '8px' }}>A written reason is required for all denials and deferrals.</div>
                      </div>
                      {duplicateStatus?.is_confirmed && (
                        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '12px', marginBottom: '12px', fontSize: '12px', color: '#991b1b', fontWeight: '600' }}>
                          🚫 Confirmed duplicate — approval blocked.
                        </div>
                      )}
                      {(() => {
                        const app = applications.find(a => Number(a.id) === Number(selectedAppId));
                        const isDecided = app?.status === 'accepted' || app?.status === 'rejected';
                        if (isDecided) {
                          return (
                            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '14px', fontSize: '13px', color: '#166534', fontWeight: '600', textAlign: 'center' }}>
                              ✓ Decision already recorded: {(app?.status || '').toUpperCase()}
                            </div>
                          );
                        }
                        return (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            <button
                              className="director-main-btn approve"
                              disabled={!!duplicateStatus?.is_confirmed}
                              style={{ opacity: duplicateStatus?.is_confirmed ? 0.5 : 1, cursor: duplicateStatus?.is_confirmed ? 'not-allowed' : 'pointer' }}
                              onClick={() => setShowConfirmModal(true)}
                            >
                              ✓ APPROVE APPLICATION
                            </button>
                            <button className="director-main-btn deny" onClick={() => setShowRejectModal(true)}>✕ DENY APPLICATION</button>
                            <button
                              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#475569', borderRadius: '8px', padding: '10px', fontWeight: '700', fontSize: '13px', cursor: 'pointer' }}
                              onClick={handleRequestInfo}
                            >
                              ↩ REQUEST MORE INFO
                            </button>
                          </div>
                        );
                      })()}
                    </div>
                  </div>

                  {/* Banking Details — Director only (Task 2.7) */}
                  {renderBankingDetails()}

                  <div className="admin-chart-card" style={{ padding: '0' }}>
                    <div style={{ padding: '20px', borderBottom: '1px solid #e2e8f0' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase' }}>AUDIT LOG</h3>
                    </div>
                    <div style={{ padding: '24px' }}>
                      {renderAuditTrail()}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })()
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
                    You are approving <strong>#{selectedAppId} — {applications.find(a => Number(a.id) === Number(selectedAppId))?.student_details?.full_name}</strong>.<br />
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
                      value={decisionNotes}
                      onChange={(e) => setDecisionNotes(e.target.value)}
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
          {/* Reject Modal (Task 2.9) */}
          {showRejectModal && (
            <div className="modal-overlay">
              <div className="modal-card">
                <div className="modal-header">
                  <h3>REJECT APPLICATION</h3>
                  <button onClick={() => { setShowRejectModal(false); setRejectReason(''); }}>✕</button>
                </div>
                <div className="modal-body">
                  <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#475569', marginBottom: '20px' }}>
                    You are rejecting <strong>#{selectedAppId} — {applications.find(a => Number(a.id) === Number(selectedAppId))?.student_details?.full_name}</strong>.
                  </p>
                  <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px' }}>
                    This decision is permanent and will be logged. The student will be notified.
                  </p>
                  <div className="field-group">
                    <label className="field-label" style={{ fontSize: '11px', fontWeight: '800' }}>REASON FOR REJECTION <span style={{ color: '#cc3333' }}>*</span></label>
                    <textarea
                      className="admin-input"
                      placeholder="Provide a reason for rejection (required)..."
                      style={{ height: '100px', resize: 'none' }}
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      autoFocus
                    ></textarea>
                    <div style={{ fontSize: '10px', color: '#cc3333', marginTop: '6px' }}>A written reason is required for all rejections.</div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn-secondary" onClick={() => { setShowRejectModal(false); setRejectReason(''); }}>Cancel</button>
                  <button
                    style={{ background: '#991b1b', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '8px', fontWeight: '800', fontSize: '13px', cursor: !rejectReason.trim() ? 'not-allowed' : 'pointer', opacity: !rejectReason.trim() ? 0.5 : 1 }}
                    disabled={!rejectReason.trim()}
                    onClick={() => handleDecision('rejected', rejectReason)}
                  >
                    ✕ CONFIRM REJECTION
                  </button>
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
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="admin-badge badge-approved"
                    onClick={handleReportCSVExport}
                    style={{ border: 'none', cursor: 'pointer', padding: '10px 20px', fontWeight: '800' }}
                    disabled={isExporting}
                  >
                    {isExporting ? 'EXPORTING...' : 'EXPORT CSV'}
                  </button>
                  <button
                    className="admin-badge"
                    onClick={() => setShowFinanceModal(true)}
                    style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', padding: '10px 20px', fontWeight: '800' }}
                  >
                    EMAIL TO FINANCE
                  </button>
                </div>
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
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>{p.reference_number || `PAY-${p.id}`}</span></td>
                        <td><strong>{p.user_name || p.student_details?.full_name || `Student #${p.user}`}</strong></td>
                        <td style={{ fontSize: '12px' }}>{p.payment_type || '—'}</td>
                        <td style={{ fontSize: '13px', fontWeight: '700' }}>${parseFloat(p.amount || 0).toLocaleString()}</td>
                        <td>
                          <span className={`admin-badge ${p.status === 'issued' ? 'badge-approved' : p.status === 'cancelled' ? 'badge-rejected' : 'badge-pending'}`} style={{ fontSize: '9px' }}>
                            {(p.status || 'pending').toUpperCase()}
                          </span>
                        </td>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>{p.date_issued ? new Date(p.date_issued).toLocaleDateString() : '—'}</td>
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
                      style={{ background: 'var(--admin-accent)', color: '#111', fontWeight: '800', border: 'none', cursor: isDispatching ? 'not-allowed' : 'pointer' }}
                      disabled={isDispatching}
                      onClick={async () => {
                        setShowFinanceModal(false);
                        await handleDispatchFinanceReport();
                      }}
                    >
                      {isDispatching ? 'SENDING...' : 'SEND EMAIL'}
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
          {currentView === 'notifications' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: '800' }}>NOTIFICATIONS</h2>
                {notifications.some((n: any) => !n.is_read) && (
                  <button
                    onClick={handleMarkAllNotificationsRead}
                    style={{ background: 'none', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 16px', cursor: 'pointer', fontSize: '13px', color: '#64748b' }}
                  >
                    Mark All Read
                  </button>
                )}
              </div>
              {notifications.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {notifications.map((notif: any) => (
                    <div
                      key={notif.id}
                      onClick={() => handleMarkNotificationRead(notif.id)}
                      style={{
                        display: 'flex', gap: '16px', padding: '16px 20px',
                        background: notif.is_read ? '#fff' : '#fffbeb',
                        border: `1px solid ${notif.is_read ? '#e2e8f0' : '#fcd34d'}`,
                        borderRadius: '10px', cursor: 'pointer',
                        transition: 'background 0.15s',
                      }}
                    >
                      <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <AdminIcons.Dashboard />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: notif.is_read ? '500' : '700', fontSize: '14px', marginBottom: '2px' }}>{notif.title}</div>
                        <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '4px' }}>{notif.message}</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                          {new Date(notif.created_at).toLocaleDateString()} {new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                      {!notif.is_read && <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f59e0b', flexShrink: 0, marginTop: '6px' }} />}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '60px 20px', color: '#94a3b8' }}>
                  <div style={{ fontSize: '40px', marginBottom: '12px' }}>🔔</div>
                  <div style={{ fontSize: '16px', fontWeight: '600', marginBottom: '6px', color: '#64748b' }}>No Notifications</div>
                  <div style={{ fontSize: '13px' }}>You're all caught up!</div>
                </div>
              )}
            </div>
          )}

          {currentView === 'appeals' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <h2 style={{ fontSize: '20px', fontWeight: '800' }}>APPEALS & SPECIAL AWARDS</h2>
                  <button 
                    onClick={() => fetchApplications(true)}
                    className="admin-btn-secondary"
                    style={{ padding: '4px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    title="Refresh List"
                  >
                    Refresh
                  </button>
                </div>
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
                    {displayAppeals.map((a: any) => (
                      <tr
                        key={a.id}
                        className="clickable-row"
                        style={{ cursor: 'pointer' }}
                        onClick={() => {
                          if (a.type === 'appeal') {
                            handleAppClick(a.original.submission);
                          } else {
                            handleAppClick(a.original.id);
                          }
                        }}
                        tabIndex={0}
                        onKeyDown={(e) => { 
                          if (e.key === 'Enter' || e.key === ' ') { 
                            e.preventDefault(); 
                            if (a.type === 'appeal') handleAppClick(a.original.submission);
                            else handleAppClick(a.original.id);
                          } 
                        }}
                        role="button"
                        aria-label={`View ${a.type} ${a.id} for ${a.student || 'Student'}`}
                      >
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>{a.id}</span></td>
                        <td><strong>{a.student}</strong></td>
                        <td style={{ fontSize: '12px' }}>{a.form_title}</td>
                        <td style={{ fontSize: '12px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.reason}</td>
                        <td>
                          <span className={`admin-badge ${a.status === 'accepted' || a.status === 'resolved' || a.status === 'approved' ? 'badge-approved' : 'badge-review'}`}>
                            {a.status.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ fontSize: '12px', color: '#64748b' }}>{new Date(a.date).toLocaleDateString()}</td>
                      </tr>
                    ))}
                    {displayAppeals.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No items found in review queue.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>

    {/* ── Request More Info Modal ── */}
    {showMoreInfoModal && (
      <div
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        onClick={() => setShowMoreInfoModal(false)}
      >
        <div
          style={{ background: '#fff', borderRadius: '12px', padding: '32px', width: '100%', maxWidth: '520px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}
          onClick={e => e.stopPropagation()}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: 0 }}>Request Additional Information</h3>
            <button onClick={() => setShowMoreInfoModal(false)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#64748b' }}>✕</button>
          </div>

          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '12px 16px', marginBottom: '20px', fontSize: '12px', color: '#92400e' }}>
            <strong>⚠ Note:</strong> The student will be notified by email and in-app with your message. The application will be paused until they respond.
          </div>

          <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#374151', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            What information is needed? *
          </label>
          <textarea
            value={moreInfoNotes}
            onChange={e => setMoreInfoNotes(e.target.value)}
            placeholder="e.g. Please upload a current official transcript. Your enrollment letter must show full-time status for the current semester."
            style={{ width: '100%', minHeight: '120px', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '13px', lineHeight: '1.6', resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit' }}
            autoFocus
          />
          <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px' }}>
            {moreInfoNotes.length} characters — be specific so the student knows exactly what to provide.
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
            <button
              onClick={() => setShowMoreInfoModal(false)}
              style={{ flex: 1, padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmitMoreInfoRequest}
              disabled={!moreInfoNotes.trim() || moreInfoLoading}
              style={{ flex: 2, padding: '12px', border: 'none', borderRadius: '8px', background: moreInfoNotes.trim() ? '#f97316' : '#e2e8f0', color: moreInfoNotes.trim() ? '#fff' : '#94a3b8', cursor: moreInfoNotes.trim() ? 'pointer' : 'not-allowed', fontWeight: '700', fontSize: '13px' }}
            >
              {moreInfoLoading ? 'Sending...' : 'Send Request to Student'}
            </button>
          </div>
        </div>
      </div>
    )}
  </>
  );
};

export default StaffDashboard;
