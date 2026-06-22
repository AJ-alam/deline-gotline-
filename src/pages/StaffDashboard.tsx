import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import API from '../api/client';
import { jsPDF } from 'jspdf';
import * as XLSX from 'xlsx';
import '../styles/staff.css';
import * as Ic from '../components/Icons';

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
  ),
  Pulse: () => (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" fill="#10b981" fillOpacity="0.2"><animate attributeName="r" from="8" to="12" dur="1.5s" repeatCount="indefinite" /><animate attributeName="fill-opacity" from="0.6" to="0" dur="1.5s" repeatCount="indefinite" /></circle><circle cx="12" cy="12" r="4" fill="#10b981" /></svg>
  )
};

// ── CUSTOM CHART COMPONENTS ──

const DonutChart: React.FC<{ data: { label: string, value: number, color: string }[] }> = ({ data }) => {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  let cumulativePercent = 0;

  const getCoordinatesForPercent = (percent: number) => {
    const x = Math.cos(2 * Math.PI * percent);
    const y = Math.sin(2 * Math.PI * percent);
    return [x, y];
  };

  return (
    <div className="donut-wrap">
      <svg viewBox="-1 -1 2 2" style={{ transform: 'rotate(-90deg)', width: '100%', height: '100%' }}>
        {data.map((item, i) => {
          const start = getCoordinatesForPercent(cumulativePercent);
          cumulativePercent += item.value / (total || 1);
          const end = getCoordinatesForPercent(cumulativePercent);
          const largeArcFlag = item.value / (total || 1) > 0.5 ? 1 : 0;
          const pathData = [
            `M ${start[0]} ${start[1]}`,
            `A 1 1 0 ${largeArcFlag} 1 ${end[0]} ${end[1]}`,
            `L 0 0`,
          ].join(' ');
          return <path key={i} d={pathData} fill={item.color} />;
        })}
        <circle cx="0" cy="0" r="0.65" fill="#fff" />
      </svg>
      <div className="donut-center">
        <div className="donut-val">{total}</div>
        <div className="donut-lbl">Apps</div>
      </div>
    </div>
  );
};

const BarChart: React.FC<{ data: { label: string, value: number, color: string }[] }> = ({ data }) => {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="bar-chart-wrap">
      {data.map((item, i) => (
        <div key={i} className="bar-item">
          <div className="bar-rail">
            <div className="bar-fill" style={{ height: `${(item.value / max) * 100}%`, backgroundColor: item.color }}>
              <div className="bar-tooltip">${item.value.toLocaleString()}</div>
            </div>
          </div>
          <div className="bar-label">{item.label}</div>
        </div>
      ))}
    </div>
  );
};

type ViewMode = 'dashboard' | 'applications' | 'detail' | 'policy' | 'reports' | 'director' | 'payments' | 'director-queue' | 'director-detail' | 'appeals' | 'notifications' | 'user-management';

const StaffDashboard: React.FC = () => {
  const [role, setRole] = useState<'ssw' | 'director'>(
    (localStorage.getItem('dgg_role')?.toLowerCase() === 'director') ? 'director' : 'ssw'
  );
  const [currentView, setCurrentView] = useState<ViewMode>(role === 'director' ? 'director-queue' : 'dashboard');
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);
  const [detailApp, setDetailApp] = useState<any>(null);
  const [studentDocs, setStudentDocs] = useState<any[]>([]);
  const [isLoadingStudentDocs, setIsLoadingStudentDocs] = useState(false);
  const [studentProfile, setStudentProfile] = useState<any>(null);
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileEdits, setProfileEdits] = useState<Record<string, string>>({});
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [reportFundingType, setReportFundingType] = useState('all');
  const [reportDateFrom, setReportDateFrom] = useState('');
  const [reportDateTo, setReportDateTo] = useState('');
  const [reportStatusFilter, setReportStatusFilter] = useState('all');
  const [showFinanceModal, setShowFinanceModal] = useState(false);
  const [financeEmail, setFinanceEmail] = useState('finance@deline.ca');
  const [isExporting, setIsExporting] = useState(false);
  const [isForwarding, setIsForwarding] = useState(false);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const fetchApplicationsRef = useRef<(showLoader?: boolean) => Promise<void>>(() => Promise.resolve());

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

  // Sequential 1-based ref numbers sorted by submission date ascending (oldest = 1)
  const appRefMap = useMemo(() => {
    const sorted = [...applications].sort(
      (a, b) => new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime()
    );
    const map = new Map<any, number>();
    sorted.forEach((app, i) => map.set(app.id, i + 1));
    return map;
  }, [applications]);

  const getRef = (id: any) => appRefMap.get(id) ?? id;

  const [notifications, setNotifications] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payments, setPayments] = useState<any[]>([]);
  const [isPaymentsLoading, setIsPaymentsLoading] = useState(false);
  // Track which payer rows are expanded in the Payments view. Key = user id (as string).
  const [expandedPayers, setExpandedPayers] = useState<Set<string>>(new Set());
  const togglePayer = (key: string) => setExpandedPayers(prev => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  const [appeals, setAppeals] = useState<any[]>([]);
  const [isAppealsLoading, setIsAppealsLoading] = useState(false);
  const [userData, setUserData] = useState<any>(null);

  const fetchApplications = async (showLoader = false) => {
    if (showLoader) setIsLoading(true);

    // Fire all requests immediately in parallel — no sequential phases
    const appsP     = API.getApplications().catch(() => []) as Promise<any>;
    const subsP     = API.getSubmissions().catch(() => []) as Promise<any>;
    const statsP    = API.getDashboardStats().catch(() => null) as Promise<any>;
    const notifsP   = API.getNotifications().catch(() => []) as Promise<any>;
    const appealsP  = API.getAppeals().catch(() => []) as Promise<any>;
    const paymentsP = API.getPayments().catch(() => []) as Promise<any>;
    const meP       = API.getMe().catch(() => null) as Promise<any>;

    // Update each slice of state as soon as its request resolves
    statsP.then(resp => setBackendStats(resp || null));
    notifsP.then(resp => setNotifications(Array.isArray(resp) ? resp : []));
    appealsP.then(resp => setAppeals(Array.isArray(resp) ? resp : (resp?.results || [])));
    // Payments power the dashboard KPI totals (funding approved / pending),
    // so load them once at boot rather than waiting for the Payments tab.
    paymentsP.then(resp => setPayments(Array.isArray(resp) ? resp : []));
    meP.then(meResp => {
      if (!meResp) return;
      // Only update state when data actually changed — prevents re-render cascade on every poll
      setUserData((prev: any) => {
        if (prev && JSON.stringify(prev) === JSON.stringify(meResp)) return prev;
        return meResp;
      });
      const mappedRole = meResp.role?.toLowerCase();
      if (mappedRole === 'director' && role !== 'director') {
        setRole('director');
        localStorage.setItem('dgg_role', 'director');
      } else if ((mappedRole === 'admin' || mappedRole === 'ssw') && role !== 'ssw') {
        setRole('ssw');
        localStorage.setItem('dgg_role', 'admin');
      }
    });

    // Merge apps + subs as soon as both resolve (independent of stats/notifs/me)
    Promise.all([appsP, subsP]).then(([appsResp, subsResp]) => {
      const apps = Array.isArray(appsResp) ? appsResp : ((appsResp as any)?.results || []);
      const subs = Array.isArray(subsResp) ? subsResp : ((subsResp as any)?.results || []);
      setApplications([
        ...apps.map((a: any) => ({ ...a, _is_standard: true })),
        ...subs,
      ]);
    });

    // Turn off the loader only after everything settles
    await Promise.allSettled([appsP, subsP, statsP, notifsP, appealsP, meP]);
    setIsLoading(false);
  };

  // Keep ref pointing at latest fetchApplications so the interval never holds a stale closure
  useEffect(() => { fetchApplicationsRef.current = fetchApplications; });

  // Lightweight refresh — only re-fetches app/submission lists, not stats/notifs/me.
  // Use this after actions (approve, reject, note, etc.) to avoid 6-request storms.
  const refreshApps = async () => {
    const [appsResp, subsResp] = await Promise.all([
      API.getApplications().catch(() => []),
      API.getSubmissions().catch(() => []),
    ]) as any[];
    const apps = Array.isArray(appsResp) ? appsResp : (appsResp?.results || []);
    const subs = Array.isArray(subsResp) ? subsResp : (subsResp?.results || []);
    setApplications([
      ...apps.map((a: any) => ({ ...a, _is_standard: true })),
      ...subs,
    ]);
  };

  // ── FORCE STOP LOADER AFTER 3 SECONDS FOR UI RESPONSIVENESS ──
  useEffect(() => {
    const timer = setTimeout(() => {
      if (isLoading) setIsLoading(false);
    }, 3000);
    return () => clearTimeout(timer);
  }, [isLoading]);

  // ── POLLING FOR REAL-TIME UPDATES ──
  // Skip polls while the tab is hidden, and refresh once on re-visibility so
  // staff returning to the tab see fresh data without waiting for the next tick.
  useEffect(() => {
    fetchApplicationsRef.current(true); // Initial load with spinner
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchApplicationsRef.current(false);
      }
    }, 30000);
    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchApplicationsRef.current(false);
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []); // runs once on mount — ref keeps the callback fresh without re-registering the interval

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

  // ── DISPATCH PAYMENTS TO FINANCE — staff-driven modal flow ──
  // The dispatch modal lets staff pick recipients + filter/select the exact
  // payment rows to email (no more relying on the .env FINANCE_EMAIL).
  const [isDispatching, setIsDispatching] = useState(false);
  const [dispatchToast, setDispatchToast] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);
  const [showDispatchModal, setShowDispatchModal] = useState(false);
  const [dispatchRecipients, setDispatchRecipients] = useState<string[]>([]);
  const [dispatchRecipientInput, setDispatchRecipientInput] = useState('');
  const [dispatchNotes, setDispatchNotes] = useState('');
  const [dispatchSubject, setDispatchSubject] = useState('');
  const [dispatchSelected, setDispatchSelected] = useState<Set<number>>(new Set());
  const [dispatchFilters, setDispatchFilters] = useState<{ status: string; type: string; search: string }>({
    status: 'pending',
    type: 'all',
    search: '',
  });

  // Open the modal: pre-fill recipients from the policy-stored finance email
  // (so the .env fallback still works as a default) and pre-select all pending
  // payments so the common case is one click away.
  const openDispatchModal = () => {
    setDispatchRecipients(financeEmail ? [financeEmail] : []);
    setDispatchRecipientInput('');
    setDispatchNotes('');
    setDispatchSubject('');
    setDispatchFilters({ status: 'pending', type: 'all', search: '' });
    const defaults = new Set<number>(
      payments.filter((p: any) => (p.status || 'pending') === 'pending').map((p: any) => p.id)
    );
    setDispatchSelected(defaults);
    setShowDispatchModal(true);
  };

  const addDispatchRecipient = (raw: string) => {
    const cleaned = raw.trim().replace(/[,;]+$/, '');
    if (!cleaned) return;
    const emailRe = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    if (!emailRe.test(cleaned)) {
      setDispatchToast({ type: 'error', msg: `Not a valid email: ${cleaned}` });
      setTimeout(() => setDispatchToast(null), 4000);
      return;
    }
    if (dispatchRecipients.includes(cleaned)) return;
    setDispatchRecipients(prev => [...prev, cleaned]);
    setDispatchRecipientInput('');
  };

  const handleDispatchFinanceReport = async () => {
    // New behavior: opens the modal instead of firing the legacy endpoint.
    openDispatchModal();
  };

  const submitDispatch = async () => {
    if (dispatchRecipients.length === 0) {
      setDispatchToast({ type: 'error', msg: 'Add at least one recipient email.' });
      setTimeout(() => setDispatchToast(null), 4000);
      return;
    }
    if (dispatchSelected.size === 0) {
      setDispatchToast({ type: 'error', msg: 'Select at least one payment to dispatch.' });
      setTimeout(() => setDispatchToast(null), 4000);
      return;
    }
    try {
      setIsDispatching(true);
      setDispatchToast(null);
      const resp = await API.dispatchFinanceCustom({
        recipients: dispatchRecipients,
        payment_ids: Array.from(dispatchSelected),
        notes: dispatchNotes,
        subject: dispatchSubject,
      }) as any;
      setDispatchToast({
        type: 'success',
        msg: `✓ Sent ${resp?.count ?? dispatchSelected.size} payment(s) to ${dispatchRecipients.length} recipient(s).`,
      });
      setTimeout(() => setDispatchToast(null), 5000);
      setShowDispatchModal(false);
      // Refresh payments so newly-issued rows reflect the dispatch.
      API.getPayments()
        .then(res => setPayments(Array.isArray(res) ? res : []))
        .catch(() => {});
    } catch (err: any) {
      setDispatchToast({ type: 'error', msg: `✕ Failed to send: ${err.message || 'Unknown error'}` });
      setTimeout(() => setDispatchToast(null), 6000);
    } finally {
      setIsDispatching(false);
    }
  };

  const getStats = () => {
    const all = applications;
    const n = all.length;

    // Normalize statuses — legacy Application uses 'approved'/'denied'/'review'/'pending'(=forwarded);
    // FormSubmission uses 'accepted'/'rejected'/'pending'(=new)/'reviewed'/'forwarded'/'more_info_required'
    const isApproved  = (a: any) => a.status === 'accepted' || a.status === 'approved';
    const isRejected  = (a: any) => a.status === 'rejected' || a.status === 'denied';
    const isForwarded = (a: any) =>
      a.status === 'forwarded' || (a._is_standard && a.status === 'pending');
    const isInReview  = (a: any) =>
      a.status === 'more_info_required' ||
      (a._is_standard  ? (a.status === 'review' || a.status === 'waiting_b')
                       : (a.status === 'pending' || a.status === 'reviewed'));

    // Funding totals — pull from the Payment table when available (truth source
    // for $ amounts; FormSubmission.amount is 0 for forms without a calculator
    // like Admission). Fall back to summing application amounts only when the
    // payments list hasn't been fetched yet.
    const approvedFromPayments = payments.reduce(
      (sum: number, p: any) => sum + ((p.status !== 'cancelled') ? (parseFloat(p.amount) || 0) : 0), 0
    );
    const pendingFromPayments = payments.reduce(
      (sum: number, p: any) => sum + ((p.status === 'pending') ? (parseFloat(p.amount) || 0) : 0), 0
    );
    const approvedFromApps = all.reduce(
      (sum, a) => sum + (isApproved(a) ? (parseFloat(a.amount) || 0) : 0), 0
    );
    const approvedAmount = payments.length > 0 ? approvedFromPayments : approvedFromApps;
    const pendingAmount  = pendingFromPayments;
    const underReview   = all.filter(a => isInReview(a) || isForwarded(a)).length;

    // Count unique submitting students (not all registered users)
    const studentIds = new Set(
      all.map((a: any) => a.student || a.student_details?.id).filter(Boolean)
    );

    // Status breakdown — fallback when backendStats unavailable. Frontend
    // primarily reads backend's unified counts; these locals cover the offline
    // path so the dashboard still renders reasonable numbers.
    const isReviewed = (a: any) => a.status === 'reviewed' || a.status === 'review';
    const isMoreInfo = (a: any) => a.status === 'more_info_required';
    const isSentToFinance = (a: any) => a.status === 'sent_to_finance';
    const statusCounts = {
      accepted:  all.filter(a => isApproved(a) || isSentToFinance(a)).length,
      pending:   all.filter(a => a.status === 'pending' || a.status === 'new').length,
      reviewed:  all.filter(a => isReviewed(a)).length,
      forwarded: all.filter(a => isForwarded(a)).length,
      moreInfo:  all.filter(a => isMoreInfo(a)).length,
      sentToFinance: all.filter(a => isSentToFinance(a)).length,
      rejected:  all.filter(a => isRejected(a)).length,
    };

    // Stream split from form title
    const ft = (a: any) => (a.form_type || a.form?.title || '').toUpperCase();
    const cdfnCount  = all.filter(a => /FORMA|FORMC|PSSSP/.test(ft(a))).length;
    const dggrCount  = all.filter(a => /DGGR|SCHOLARSHIP|HARDSHIP|FORMD|FORMF|FORMG/.test(ft(a))).length;
    const uceppCount = all.filter(a => /UCEPP|UPGRADING/.test(ft(a))).length;

    return {
      totalApps:      n,
      approvedAmount,
      pendingAmount,
      underReview,
      activeStudents: studentIds.size,
      statusCounts,
      cdfnCount,
      dggrCount,
      uceppCount,
      pssspPercent:  n ? (cdfnCount  / n) * 100 : 0,
      dggrPercent:   n ? (dggrCount  / n) * 100 : 0,
      uceppPercent:  n ? (uceppCount / n) * 100 : 0,
      formBPending:  backendStats?.form_b_stats?.awaiting || 0,
    };
  };

  const stats = getStats();

  const [staffNote, setStaffNote] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  const handleDecision = async (status: 'accepted' | 'rejected' | 'forwarded' | 'reviewed' | 'review', notesOverride?: string) => {
    if (!selectedAppId) return;
    // Prefer hydrated detailApp so auto-calc at approval time sees guest
    // answers/student_details (lean list row omits them for guests).
    const currentApp = (detailApp && String(detailApp.id) === String(selectedAppId))
      ? detailApp
      : applications.find(a => String(a.id) === String(selectedAppId));

    // Immutable storage: Capture auto-calculated total at time of approval
    let amountToSave = currentApp?.amount || 0;
    if (status === 'accepted') {
      const autoSuggested = calculateAutoFunding(currentApp);
      if (autoSuggested && !currentApp?.amount) {
        amountToSave = autoSuggested.total;
      }
    }

    // Show loading state
    setIsSubmittingDecision(true);
    if (status === 'forwarded') setIsForwarding(true);

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
      setDetailApp(null);
      setCurrentView(role === 'director' ? 'director-queue' : 'applications');
      refreshApps();
    } catch (err: any) {
      alert(err.message || 'Action failed');
    } finally {
      setIsSubmittingDecision(false);
      setIsForwarding(false);
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
      refreshApps();
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
      const doc = new jsPDF();
      doc.setFontSize(20);
      doc.text('DGG Application Summary', 20, 20);
      doc.setFontSize(12);
      doc.text(`Reference: # ${getRef(app.id)}`, 20, 30);
      doc.text(`Student: ${app.student_details?.full_name || app.student_name || 'N/A'}`, 20, 40);
      doc.text(`Form: ${getFormDisplayName(app.form_title || app.form?.title)}`, 20, 50);
      doc.text(`Status: ${(app.status || 'pending').toUpperCase()}`, 20, 60);
      doc.text(`Submitted: ${app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : 'N/A'}`, 20, 70);

      doc.text('------------------------------------------------', 20, 80);
      doc.text('Decision Details:', 20, 90);
      doc.text(`Authorized Amount: $${app.amount || 0}`, 20, 100);
      doc.text(`Notes: ${app.decision_reason || 'None'}`, 20, 110);

      doc.save(`Application_${getRef(app.id)}.pdf`);
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
      refreshApps();
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
      refreshApps();
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
      refreshApps();
      alert('Application marked as duplicate');
    } catch (err: any) {
      alert(err.message || 'Failed to mark as duplicate');
    }
  };

  const handleAppClick = (appId: number) => {
    setSelectedAppId(String(appId));
    setDetailApp(null);
    setCurrentView('detail');
    API.getSubmission(appId).then((data: any) => {
      setDetailApp(data);
    }).catch((err: any) => {
      console.error('Failed to fetch application detail:', err);
    });
  };

  const [officeUseInputs, setOfficeUseInputs] = useState({ dateReceived: '', approvedBy: '', commitmentNum: '' });
  const [isSavingOffice, setIsSavingOffice] = useState(false);

  // Editable Auto Funding Calculation rows. Each row is { id, label, stream?, note?, amount }.
  // Loaded from office_use_data.funding_breakdown if present; otherwise seeded from policy
  // calculation (autoSuggested). Admin can edit label/amount, add custom rows, delete.
  type BreakdownRow = { id: string; label: string; stream?: string; note?: string; amount: number };
  const [breakdownRows, setBreakdownRows] = useState<BreakdownRow[]>([]);
  const [isSavingBreakdown, setIsSavingBreakdown] = useState(false);

  // ── POLICY SETTINGS STATE ──
  const [policySettings, setPolicySettings] = useState<Record<string, any[]>>({});
  const [isDirty, setIsDirty] = useState<Record<string, boolean>>({});
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    'application_deadlines': true // Open first by default
  });
  const [policyTab, setPolicyTab] = useState<string>('tuition');
  const [policyHistory, setPolicyHistory] = useState<any[]>([]);
  const [isPolicyHistoryLoading, setIsPolicyHistoryLoading] = useState(false);
  const [isSavingPolicy, setIsSavingPolicy] = useState(false);
  const [saveToast, setSaveToast] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);
  // Add-field form state per tab. Open form for which tab + draft fields.
  const [addFieldDraft, setAddFieldDraft] = useState<{ tab: string; section: string; label: string; value: string; unit: string } | null>(null);

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

  // ── POLICY HELPERS ──
  // Lookup the raw row for a (section, field_key) so the JSX stays readable.
  const policyField = (section: string, fieldKey: string): any | null => {
    const list = policySettings[section] || [];
    return list.find((f: any) => f.field_key === fieldKey) || null;
  };

  // Mutate a single field's value or unit by section + key. Marks the section dirty.
  const updatePolicyField = (section: string, fieldKey: string, patch: { value?: string | number; unit?: string; field_label?: string }) => {
    setPolicySettings(prev => {
      const next = { ...prev };
      const list = [...(next[section] || [])];
      const idx = list.findIndex((f: any) => f.field_key === fieldKey);
      if (idx === -1) return prev;
      list[idx] = { ...list[idx], ...patch };
      next[section] = list;
      return next;
    });
    setIsDirty(prev => ({ ...prev, [section]: true }));
  };

  // Save every dirty section that belongs to the current tab. One bulk_update per section.
  const savePolicySections = async (sections: string[]) => {
    const dirtySections = sections.filter(s => isDirty[s] && policySettings[s]?.length);
    if (dirtySections.length === 0) {
      alert('No changes to save.');
      return;
    }
    setIsSavingPolicy(true);
    try {
      for (const section of dirtySections) {
        const items = policySettings[section];
        const resp = await API.updatePolicySetting('bulk', { section, settings: items }) as any;
        if (!resp || (!resp.success && resp.updated_count === undefined)) {
          throw new Error(resp?.message || `Failed to save ${section}`);
        }
      }
      await fetchPolicySettings();
      // Always refresh history so the next visit to the History tab shows the
      // change immediately — not only when the admin happens to be on it.
      setIsPolicyHistoryLoading(true);
      try {
        const resp = await API.getPolicyHistory(200) as any;
        setPolicyHistory(Array.isArray(resp) ? resp : []);
      } catch {}
      finally { setIsPolicyHistoryLoading(false); }
      // Mark sections as clean so the unsaved-changes badge clears.
      setIsDirty(prev => {
        const next = { ...prev };
        for (const s of dirtySections) next[s] = false;
        return next;
      });
      setSaveToast({ type: 'success', msg: `Saved ${dirtySections.length} section${dirtySections.length === 1 ? '' : 's'}. Change History updated.` });
      // Auto-dismiss the toast after 3s.
      setTimeout(() => setSaveToast(null), 3000);
    } catch (err: any) {
      console.error('Policy save error:', err);
      setSaveToast({ type: 'error', msg: err?.message || 'Failed to save changes.' });
      setTimeout(() => setSaveToast(null), 5000);
    } finally {
      setIsSavingPolicy(false);
    }
  };

  // Field keys seeded by `python manage.py seed_policies` per section. Anything in
  // `policySettings[section]` whose field_key is NOT in this list is treated as a
  // user-added custom field — admins can rename, edit, and delete those freely.
  const SEEDED_FIELD_KEYS: Record<string, string[]> = {
    psssp_tuition: ['max_per_semester'],
    ucepp_tuition: ['max_per_semester'],
    dggr_tuition: ['fulltime_per_semester', 'parttime_per_semester'],
    dggr_extra_tuition: ['annual_cap_all_students', 'threshold_per_semester', 'threshold_per_year', 'max_percent_covered', 'max_per_semester', 'max_per_year'],
    psssp_living: ['fulltime_no_dependents', 'fulltime_with_dependents', 'parttime_no_dependents', 'parttime_with_dependents'],
    ucepp_living: ['fulltime_no_dependents', 'fulltime_with_dependents', 'parttime_no_dependents', 'parttime_with_dependents'],
    dggr_living:  ['fulltime_no_dependents', 'fulltime_with_dependents', 'parttime_no_dependents', 'parttime_with_dependents'],
    psssp_travel: ['max_trips_per_year', 'min_distance_km', 'max_per_trip_no_dependents', 'max_per_trip_with_dependents'],
    psssp_graduation_travel: ['max_total', 'max_family_members', 'max_hotel_per_night', 'max_hotel_nights'],
    dggr_practicum_award: ['award_amount', 'application_deadline_months'],
    dggr_grad_bursary: ['high_school_diploma', 'certificate', 'trades_certificate', 'trades_journeyperson', 'diploma', 'pilot_licence', 'red_seal', 'bachelors_degree', 'masters_degree', 'doctorate', 'juris_doctor', 'doctor_medicine_dental'],
    dggr_academic_scholarship: ['high_threshold_percent', 'high_achievement_award', 'mid_threshold_lower', 'mid_threshold_upper', 'mid_achievement_award'],
    dggr_hardship: ['max_per_student'],
    eligibility_rules: ['min_program_weeks', 'fulltime_min_load_percent', 'fulltime_min_load_disability', 'parttime_max_load_percent', 'parttime_max_load_disability'],
    misconduct_rules: ['suspension_misconduct_years', 'suspension_overpayment_years'],
    application_deadlines: ['fall_deadline', 'winter_deadline', 'spring_deadline', 'summer_deadline'],
    payment_schedule: ['tuition_payment_weeks_after_deadline', 'living_payment_day_of_month', 'other_bursary_max_processing_days'],
    system_config: ['finance_email', 'registrar_email', 'contact_email', 'contact_phone', 'contact_address', 'travel_claim_days', 'share_link_expiry_days', 'book_allowance'],
  };
  const customFieldsForTab = (sections: string[]): Array<{ section: string; field: any }> => {
    const out: Array<{ section: string; field: any }> = [];
    for (const section of sections) {
      const seeded = SEEDED_FIELD_KEYS[section] || [];
      for (const f of (policySettings[section] || [])) {
        if (!seeded.includes(f.field_key)) out.push({ section, field: f });
      }
    }
    return out;
  };

  // Delete a single policy field. Confirms first; warns if the field_key matches one
  // the auto-funding calculator relies on (best-effort heuristic — admins can re-seed).
  const CRITICAL_FIELD_KEY_PATTERNS = [
    /^max_per_semester$/, /^fulltime_(no|with)_dependents$/, /^parttime_(no|with)_dependents$/,
    /^max_per_trip_/, /^max_(percent_covered|per_year)$/, /^threshold_per_/, /^book_allowance$/,
  ];
  const deletePolicyField = async (field: any) => {
    if (!field?.id) return;
    const isCritical = CRITICAL_FIELD_KEY_PATTERNS.some(re => re.test(field.field_key || ''));
    const warn = isCritical
      ? `\n\n⚠ This field key ("${field.field_key}") appears to be used by the auto-funding calculator. Deleting it may break automatic funding calculations until it's re-seeded.`
      : '';
    if (!window.confirm(`Delete "${field.field_label}" from [${field.section}]?${warn}\n\nThis cannot be undone.`)) return;
    try {
      await API.deletePolicySetting(field.id);
      await fetchPolicySettings();
    } catch (err: any) {
      console.error('Policy delete failed:', err);
      alert(err?.message || 'Failed to delete field.');
    }
  };

  // Create a new policy field via POST. Auto-generates field_key from label if missing.
  const createPolicyField = async (payload: { section: string; field_label: string; value: string; unit?: string }) => {
    const trimmedLabel = (payload.field_label || '').trim();
    if (!trimmedLabel) { alert('Field label is required.'); return; }
    if (!payload.section) { alert('Pick a section.'); return; }
    const field_key = trimmedLabel.toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 100) || `field_${Date.now()}`;
    try {
      await API.createPolicySetting({
        section: payload.section,
        field_key,
        field_label: trimmedLabel,
        value: parseFloat(payload.value || '0') || 0,
        unit: payload.unit || '',
      });
      setAddFieldDraft(null);
      await fetchPolicySettings();
    } catch (err: any) {
      console.error('Policy create failed:', err);
      alert(err?.message || 'Failed to add field.');
    }
  };

  // Most recent updated_at across a set of sections — drives the "Effective date" footer.
  const latestUpdatedAt = (sections: string[]): string | null => {
    let latest: number = 0;
    for (const s of sections) {
      for (const f of (policySettings[s] || [])) {
        if (f.last_updated_at) {
          const t = new Date(f.last_updated_at).getTime();
          if (t > latest) latest = t;
        }
      }
    }
    return latest > 0 ? new Date(latest).toISOString().slice(0, 10) : null;
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
      setIsPaymentsLoading(true);
      API.getPayments()
        .then(res => setPayments(Array.isArray(res) ? res : []))
        .catch(e => console.error('Payments fetch failed', e))
        .finally(() => setIsPaymentsLoading(false));
    }
    if (currentView === 'appeals') {
      setIsAppealsLoading(true);
      API.getAppeals()
        .then(res => setAppeals(Array.isArray(res) ? res : []))
        .catch(e => console.error('Appeals fetch failed', e))
        .finally(() => setIsAppealsLoading(false));
    }
    if (currentView === 'reports') {
      fetchReportStats();
    }
    if (currentView === 'user-management') {
      fetchStaffUsers();
    }
  }, [currentView]);

  // Fetch policy change history when the History tab is opened.
  useEffect(() => {
    if (currentView === 'policy' && policyTab === 'history') {
      setIsPolicyHistoryLoading(true);
      API.getPolicyHistory(200)
        .then((resp: any) => setPolicyHistory(Array.isArray(resp) ? resp : []))
        .catch(e => console.error('Policy history fetch failed', e))
        .finally(() => setIsPolicyHistoryLoading(false));
    }
  }, [currentView, policyTab]);

  // Re-fetch report stats when filters change
  useEffect(() => {
    if (currentView === 'reports') {
      fetchReportStats();
    }
  }, [reportFundingType, reportDateFrom, reportDateTo, reportStatusFilter]);

  useEffect(() => {
    if (selectedAppId) {
      const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
      if (app && app.office_use_data) {
        setOfficeUseInputs({
          dateReceived: app.office_use_data.dateReceived || '',
          approvedBy: app.office_use_data.approvedBy || '',
          commitmentNum: app.office_use_data.commitmentNum || ''
        });
      } else {
        setOfficeUseInputs({ dateReceived: '', approvedBy: '', commitmentNum: '' });
      }
      // Funding breakdown: prefer admin overrides from office_use_data, else seed from policy.
      const saved = app?.office_use_data?.funding_breakdown;
      if (Array.isArray(saved) && saved.length > 0) {
        setBreakdownRows(saved.map((r: any, i: number) => ({
          id: r.id || `row-${i}`,
          label: String(r.label || ''),
          stream: r.stream,
          note: r.note,
          amount: Number(r.amount) || 0,
        })));
      } else {
        setBreakdownRows([]); // will be seeded from autoSuggested in renderAutoFundingTable when available
      }
    }
    // Reset note state when switching applications
    setStaffNote('');
    setNoteError(null);
  }, [selectedAppId, applications]);

  // ── DETAIL HYDRATION SAFETY NET ──
  // Some entry points (director-queue Quick-Approve/Quick-Deny, table row clicks)
  // historically set selectedAppId without calling handleAppClick(), which left
  // detailApp null and made the director see only the lean summary (name only).
  // This effect guarantees detailApp is fetched whenever a detail view opens,
  // regardless of how the user navigated there.
  useEffect(() => {
    if (!selectedAppId) return;
    if (currentView !== 'detail' && currentView !== 'director-detail') return;
    if (detailApp && String(detailApp.id) === String(selectedAppId)) return; // already fresh
    API.getSubmission(Number(selectedAppId))
      .then((data: any) => setDetailApp(data))
      .catch((err: any) => console.error('Failed to hydrate application detail:', err));
  }, [selectedAppId, currentView]);

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

  // ── STUDENT DOCUMENTS & PROFILE: Fetch when detail view opens ──
  useEffect(() => {
    if (!selectedAppId || (currentView !== 'detail' && currentView !== 'director-detail')) {
      setStudentDocs([]);
      setStudentProfile(null);
      setEditingProfile(false);
      setProfileEdits({});
      return;
    }
    const app = detailApp || applications.find((a: any) => String(a.id) === String(selectedAppId));
    const studentId = app?.student_details?.user_id || app?.student;
    if (!studentId) return;

    setIsLoadingStudentDocs(true);
    API.getStudentDocuments(Number(studentId))
      .then((data: any) => setStudentDocs(Array.isArray(data) ? data : (data?.results || [])))
      .catch(() => setStudentDocs([]))
      .finally(() => setIsLoadingStudentDocs(false));

    API.getStudentProfile(Number(studentId))
      .then((data: any) => {
        const results = Array.isArray(data) ? data : (data?.results || []);
        setStudentProfile(results[0] || null);
      })
      .catch(() => setStudentProfile(null));
  }, [selectedAppId, currentView, detailApp]);

  const handleSaveOfficeUse = async () => {
    if (!selectedAppId) return;
    setIsSavingOffice(true);
    try {
      const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
      if (!app) throw new Error("Application not found in state");
      await API.updateSubmissionStatus(Number(selectedAppId), app.status, { office_use_data: officeUseInputs });
      alert('Office use data saved successfully');
      refreshApps();
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

  // ── USER MANAGEMENT STATE (director-only) ──
  const [staffUsers, setStaffUsers] = useState<any[]>([]);
  const [userMgmtLoading, setUserMgmtLoading] = useState(false);
  const [userMgmtError, setUserMgmtError] = useState<string | null>(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<any | null>(null);
  const [userForm, setUserForm] = useState({ full_name: '', email: '', role: 'admin', password: '', is_active: true });
  const [userFormError, setUserFormError] = useState<string | null>(null);
  const [userFormLoading, setUserFormLoading] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const fetchStaffUsers = async () => {
    setUserMgmtLoading(true);
    setUserMgmtError(null);
    try {
      const res = await API.getStaffUsers() as any;
      setStaffUsers(Array.isArray(res) ? res : []);
    } catch (err: any) {
      setUserMgmtError(err.message || 'Failed to load users');
    } finally {
      setUserMgmtLoading(false);
    }
  };

  const openAddUser = () => {
    setEditingUser(null);
    setUserForm({ full_name: '', email: '', role: 'admin', password: '', is_active: true });
    setUserFormError(null);
    setShowUserModal(true);
  };

  const openEditUser = (u: any) => {
    setEditingUser(u);
    setUserForm({ full_name: u.full_name, email: u.email, role: u.role, password: '', is_active: u.is_active });
    setUserFormError(null);
    setShowUserModal(true);
  };

  const handleUserFormSubmit = async () => {
    setUserFormError(null);
    if (!userForm.full_name.trim()) { setUserFormError('Full name is required.'); return; }
    if (!editingUser && (!userForm.email.trim() || !userForm.email.includes('@'))) { setUserFormError('Valid email is required.'); return; }
    if (!editingUser && !userForm.password) { setUserFormError('Password is required.'); return; }
    setUserFormLoading(true);
    try {
      if (editingUser) {
        const payload: any = { full_name: userForm.full_name, role: userForm.role, is_active: userForm.is_active };
        if (userForm.password) payload.password = userForm.password;
        await API.updateStaffUser(editingUser.id, payload);
      } else {
        await API.createStaffUser({ full_name: userForm.full_name, email: userForm.email, role: userForm.role, password: userForm.password });
      }
      setShowUserModal(false);
      fetchStaffUsers();
    } catch (err: any) {
      setUserFormError(err.message || 'Operation failed. Please try again.');
    } finally {
      setUserFormLoading(false);
    }
  };

  const handleDeleteUser = async (id: number) => {
    try {
      await API.deleteStaffUser(id);
      setDeleteConfirmId(null);
      fetchStaffUsers();
    } catch (err: any) {
      setUserMgmtError(err.message || 'Failed to delete user');
    }
  };

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

  // Map any raw form title or form_type code to the proper user-facing label.
  // Mirrors backend api/services/form_service.py::pretty_form_title so the
  // Payments dashboard never shows internal codes like "FormA" or "FormG".
  const prettyFormName = (raw: string | null | undefined): string => {
    if (!raw) return 'Application';
    const t = String(raw).toLowerCase();
    if (/(form\s*a|forma|psssp|c-dfn|new student|admission)/.test(t)) return 'New Student Application';
    if (/(form\s*b|formb|enroll?ment verif|profile update)/.test(t)) return 'Enrollment Verification';
    if (/(form\s*c|formc|continuing fund)/.test(t)) return 'Continuing Funding Application';
    if (/(form\s*d|formd|appeal|reconsider|specialized train)/.test(t)) return 'Appeal & Reconsideration';
    if (/(form\s*e|forme|travel|emergency fund)/.test(t)) return 'Travel & Relocation Claim';
    if (/(form\s*f|formf|practicum|placement)/.test(t)) return 'Practicum Placement Allowance';
    if (/(form\s*g|formg|graduation)/.test(t)) return 'Graduation Bursary';
    if (/(form\s*h|formh|summer student)/.test(t)) return 'Summer Student Employment';
    if (/hardship/.test(t)) return 'Hardship Bursary';
    if (/scholarship/.test(t)) return 'Academic Scholarship';
    return raw;
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

  // Prefer the fully-hydrated detailApp (includes answers + student_details,
  // incl. guest data extracted from answers) over the lean applications-list
  // row, which lacks answers/student_details for guest submissions and made
  // the Auto Funding Calculation table render blank for them.
  const selectedApp = (detailApp && String(detailApp.id) === String(selectedAppId))
    ? detailApp
    : applications.find(a => String(a.id) === String(selectedAppId));

  // True while detailApp is still hydrating for the currently selected application —
  // used to swap N/A placeholders for skeleton shimmers so users never see empty fields.
  const isDetailLoading = !!selectedAppId &&
    (!detailApp || String(detailApp.id) !== String(selectedAppId));

  // Skeleton shimmer used in place of text values while detail data is loading.
  const Skel: React.FC<{ w?: string | number; h?: number; cls?: string }> = ({ w, h, cls }) => (
    <span
      className={`skeleton ${cls || 'skeleton-line-md'}`}
      style={{ width: w, height: h }}
      aria-hidden
    >·</span>
  );

  // Render `value` if detail is loaded, otherwise a skeleton placeholder of the given size.
  const fieldOrSkel = (value: any, skelWidth: string | number = '70%') =>
    isDetailLoading ? <Skel w={skelWidth} /> : (value ?? 'N/A');

  const calculateAutoFunding = (app: any, streamOverride?: string) => {
    // Policy settings must be loaded — without rates we can't compute anything.
    // BUT we no longer require app.answers: legacy Applications + form types
    // that don't capture detailed answers still get a useful breakdown from
    // student profile + form_data. Empty-answer apps used to short-circuit
    // here, which is why the Auto Funding Calculation table rendered blank.
    if (!app || !policySettings) return null;

    const student = app.student_details || {};
    const profile = student.profile || {};
    const answers = Array.isArray(app.answers) ? app.answers : [];
    const formData = app.form_data || app.office_use_data?.form_data || {};

    // helper to get answer by label (case-insensitive fuzzy match), with
    // form_data fallback so legacy rows still resolve common fields.
    const getAns = (label: string) => {
      const fromAns = answers.find((a: any) =>
        (a.label || a.field_label || '').toLowerCase().includes(label.toLowerCase())
      )?.answer_text;
      if (fromAns !== undefined && fromAns !== null && fromAns !== '') return fromAns;
      const key = label.toLowerCase();
      for (const [k, v] of Object.entries(formData)) {
        if (String(k).toLowerCase().includes(key) && v !== undefined && v !== null && v !== '') return String(v);
      }
      return undefined;
    };

    // Stream identification — caller can override (used when iterating both
    // primary + secondary eligible streams for the AUTO FUNDING CALCULATION table)
    let stream = streamOverride || getAns('bursaryStream') || student.primary_stream || 'DGGR';
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

    // 2. Living Allowance — canonical backend sections: psssp_living / ucepp_living / dggr_living
    //    field keys: {fulltime|parttime}_{no|with}_dependents
    let livingSection = 'dggr_living';
    if (stream === 'PSSSP') livingSection = 'psssp_living';
    else if (stream === 'UCEPP') livingSection = 'ucepp_living';

    const depKey = hasDeps ? 'with_dependents' : 'no_dependents';
    const loadKey = isFullTime ? 'fulltime' : 'parttime';
    const livingFieldKey = `${loadKey}_${depKey}`;

    const livingRate = getPolicySetting(livingSection, livingFieldKey);
    const totalLiving = livingRate * months;

    // 3. Tuition Award — canonical sections psssp_tuition / ucepp_tuition / dggr_tuition
    let tuitionLimit = 0;
    let tuitionRule = "";

    if (stream === 'PSSSP') {
      tuitionLimit = getPolicySetting('psssp_tuition', 'max_per_semester');
      tuitionRule = `PSSSP cap: $${tuitionLimit} (includes books/fees)`;
    } else if (stream === 'UCEPP') {
      tuitionLimit = getPolicySetting('ucepp_tuition', 'max_per_semester');
      tuitionRule = `UCEPP cap: $${tuitionLimit} (includes books/fees)`;
    } else {
      tuitionLimit = getPolicySetting('dggr_tuition', isFullTime ? 'fulltime_per_semester' : 'parttime_per_semester');
      tuitionRule = `DGGR Top-up: $${tuitionLimit} fixed`;
    }

    let finalTuition = stream === 'DGGR' ? tuitionLimit : Math.min(requestedTuition || tuitionLimit, tuitionLimit);

    // 4. DGGR Extra Tuition Relief — section dggr_extra_tuition
    let extraRelief = 0;
    if (stream === 'DGGR') {
      const triggerSem = getPolicySetting('dggr_extra_tuition', 'threshold_per_semester');
      if (requestedTuition > 0 && triggerSem > 0 && requestedTuition >= triggerSem) {
        const reliefPercentRaw = getPolicySetting('dggr_extra_tuition', 'max_percent_covered'); // stored as e.g. 25
        const reliefPercent = reliefPercentRaw / 100;
        const reliefMaxSem = getPolicySetting('dggr_extra_tuition', 'max_per_semester');
        const potentialRelief = requestedTuition * reliefPercent;
        extraRelief = Math.min(potentialRelief, reliefMaxSem) - finalTuition;
        if (extraRelief < 0) extraRelief = 0;
      }
    }

    // 5. Special Awards — Graduation / Scholarship / Practicum
    let specialAwards = 0;
    let specialNote = "";

    if (app.form_type === 'Graduation Bursary' || app.form_type === 'FormG' || (app.form?.title || '').toLowerCase().includes('graduation')) {
      const degreeType = getAns('degreeType') || student.program_credential || 'Diploma';
      // Map free-form credential to seeded keys (high_school_diploma, certificate, diploma, bachelors_degree, …)
      const norm = degreeType.toLowerCase();
      let mappedKey = 'certificate';
      if (norm.includes('high school')) mappedKey = 'high_school_diploma';
      else if (norm.includes('trades') && norm.includes('journey')) mappedKey = 'trades_journeyperson';
      else if (norm.includes('trades')) mappedKey = 'trades_certificate';
      else if (norm.includes('diploma')) mappedKey = 'diploma';
      else if (norm.includes('pilot')) mappedKey = 'pilot_licence';
      else if (norm.includes('red seal')) mappedKey = 'red_seal';
      else if (norm.includes('master')) mappedKey = 'masters_degree';
      else if (norm.includes('doctor') || norm.includes('phd')) mappedKey = 'doctorate';
      else if (norm.includes('bachelor') || norm.includes('degree')) mappedKey = 'bachelors_degree';
      specialAwards = getPolicySetting('dggr_grad_bursary', mappedKey);
      specialNote = `Graduation Award: ${degreeType}`;
    }

    // Academic Achievement Scholarship — section dggr_academic_scholarship
    const gpa = parseFloat(getAns('gpa') || '0');
    const highThr = getPolicySetting('dggr_academic_scholarship', 'high_threshold_percent') || 80;
    const midThr  = getPolicySetting('dggr_academic_scholarship', 'mid_threshold_lower')   || 70;
    if (gpa >= highThr) {
      specialAwards += getPolicySetting('dggr_academic_scholarship', 'high_achievement_award');
      specialNote += (specialNote ? " + " : "") + `Scholarship (${highThr}%+)`;
    } else if (gpa >= midThr) {
      specialAwards += getPolicySetting('dggr_academic_scholarship', 'mid_achievement_award');
      specialNote += (specialNote ? " + " : "") + `Scholarship (${midThr}-${highThr - 0.01}%)`;
    }

    // Practicum / Placement / Summer — section dggr_practicum_award
    const titleL = (app.form?.title || app.form_title || '').toLowerCase();
    if (app.form_type === 'Practicum' || app.form_type === 'FormF' || app.form_type === 'FormH' ||
        titleL.includes('practicum') || titleL.includes('placement') || titleL.includes('summer student')) {
      specialAwards += getPolicySetting('dggr_practicum_award', 'award_amount');
      specialNote += (specialNote ? " + " : "") + "Practicum / Summer Award";
    }

    // Books & Supplies — section system_config.book_allowance (DGGR only — PSSSP/UCEPP bundled in tuition cap)
    const bookAllowance = stream === 'DGGR' ? getPolicySetting('system_config', 'book_allowance') : 0;

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
        rule: stream === 'DGGR' ? `Standard book allowance: $${bookAllowance}` : 'Included in tuition cap'
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

  // Seed breakdownRows from autoSuggested only when nothing has been saved/edited yet.
  // Re-runs when policy settings, selected app, or computed totals change so the
  // table populates as soon as data is available (was previously blank when
  // policy settings loaded after the selection).
  useEffect(() => {
    if (!selectedAppId || !autoSuggested || autoSuggested.ineligible) return;
    // Guard moved to functional update below — do not early-return here as the
    // stale closure may see length=0 even when rows exist.

    // Determine every stream the student is eligible for so the table lists
    // ALL streams (primary + secondary). Signup persists these on the user;
    // fall back to the resolved auto-calc stream if missing.
    const sd = selectedApp?.student_details || {};
    const eligible: string[] = [];
    const norm = (s: string) => (s || '').toUpperCase().includes('PSSSP') ? 'PSSSP'
      : (s || '').toUpperCase().includes('UCEPP') ? 'UCEPP'
      : (s || '').toUpperCase().includes('DGGR') ? 'DGGR'
      : '';
    [sd.primary_stream, sd.secondary_stream, autoSuggested.stream].forEach((s: any) => {
      const n = norm(s);
      if (n && !eligible.includes(n)) eligible.push(n);
    });
    if (eligible.length === 0) eligible.push(autoSuggested.stream || 'DGGR');

    const seeded: BreakdownRow[] = [];
    eligible.forEach((stream) => {
      const breakdown = eligible.length === 1 ? autoSuggested : calculateAutoFunding(selectedApp, stream);
      if (!breakdown || breakdown.ineligible) return;
      const tag = eligible.length > 1 ? ` (${stream})` : '';
      seeded.push(
        { id: `tuition-${stream}`, label: `Tuition Award${tag}`,    stream, note: breakdown.tuition?.rule || '', amount: Number(breakdown.tuition?.system) || 0 },
        { id: `living-${stream}`,  label: `Living Allowance${tag}`, stream, note: breakdown.living?.rule  || '', amount: Number(breakdown.living?.system)  || 0 },
        { id: `books-${stream}`,   label: `Books & Supplies${tag}`, stream, note: breakdown.books?.rule   || '', amount: Number(breakdown.books?.system)   || 0 },
      );
      if (Number(breakdown.special?.system) > 0 || (breakdown.special?.rule || '')) {
        seeded.push({ id: `special-${stream}`, label: `Special Awards${tag}`, stream, note: breakdown.special?.rule || '', amount: Number(breakdown.special?.system) || 0 });
      }
    });
    // Use functional update so we always read the latest state — avoids the stale-
    // closure bug where the guard saw an empty array even after the user added a row.
    setBreakdownRows(prev => prev.length > 0 ? prev : seeded);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAppId, autoSuggested?.total, autoSuggested?.stream, policySettings]);

  const breakdownTotal = breakdownRows.reduce((sum, r) => sum + (Number(r.amount) || 0), 0);

  const updateBreakdownRow = (id: string, patch: Partial<BreakdownRow>) => {
    setBreakdownRows(rows => rows.map(r => (r.id === id ? { ...r, ...patch } : r)));
  };
  const deleteBreakdownRow = (id: string) => {
    setBreakdownRows(rows => rows.filter(r => r.id !== id));
  };
  const addBreakdownRow = () => {
    setBreakdownRows(rows => [...rows, {
      id: `custom-${Date.now()}`,
      label: 'Custom Item',
      stream: autoSuggested?.stream || selectedApp?.student_details?.primary_stream || '',
      note: '',
      amount: 0,
    }]);
  };
  const saveBreakdown = async (applyTotal: boolean = false) => {
    if (!selectedAppId) return;
    setIsSavingBreakdown(true);
    try {
      const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
      if (!app) throw new Error('Application not found');
      const payload: any = {
        office_use_data: { funding_breakdown: breakdownRows },
      };
      if (applyTotal) payload.amount = breakdownTotal;
      await API.updateSubmissionStatus(Number(selectedAppId), app.status, payload);
      refreshApps();
      alert(applyTotal ? `Saved and applied total $${breakdownTotal.toLocaleString()}` : 'Funding breakdown saved');
    } catch (e: any) {
      alert(e?.message || 'Failed to save funding breakdown');
    } finally {
      setIsSavingBreakdown(false);
    }
  };

  // Single Awards to be shown in the Appeals section for Director review
  const singleAwardTypes = [
    'Graduation Bursary',
    'Practicum',
    'Scholarship',
    'Hardship',
    'Summer Student',
    'Appeal'
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
    }).map(app => {
      // Find name from answers if student_details is missing (for guest submissions)
      const answers = app.answers || [];
      const nameAnswer = answers.find((ans: any) => {
        const lbl = (ans.label || ans.field_label || '').toLowerCase();
        return lbl === 'full name' || lbl === 'student name' || lbl.includes('applicant name');
      });
      const studentName = app.student_details?.full_name || nameAnswer?.answer_text || app.student_name || 'Guest Student';

      return {
        id: `APP-${app.id}`,
        student: studentName,
        form_title: app.form_title || 'Single Award',
        reason: `Direct Award Application: ${app.form_title}`,
        status: app.status,
        date: app.submitted_at || app.created_at,
        original: app,
        type: 'application'
      };
    })
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const pendingSpecialAwards = applications.filter(app => {
    const type = (app.form_type || '').toLowerCase();
    const isSpecial = singleAwardTypes.some(t => type.includes(t.toLowerCase()));
    return isSpecial && (app.status === 'pending' || app.status === 'new' || app.status === 'review');
  }).length;

  const getFormDisplayName = (title?: string): string => {
    const t = (title || '').toLowerCase();
    if (!t) return 'Application';
    if (/(form\s*a\b|forma|psssp|c-dfn|new student|admission)/.test(t)) return 'New Student Application';
    if (/(form\s*b\b|formb|enroll|enrol.*verif|profile update)/.test(t))  return 'Enrollment Verification';
    if (/(form\s*c\b|formc|continuing fund)/.test(t))                      return 'Continuing Funding Application';
    if (/(form\s*d\b|formd|appeal|reconsider|specialized train)/.test(t))  return 'Appeal & Reconsideration';
    if (/(form\s*e\b|forme|travel|emergency fund)/.test(t))                return 'Travel & Relocation Claim';
    if (/(form\s*f\b|formf|practicum|placement)/.test(t))                  return 'Practicum Placement Allowance';
    if (/(form\s*g\b|formg|graduation)/.test(t))                           return 'Graduation Bursary';
    if (/(form\s*h\b|formh|summer student)/.test(t))                       return 'Summer Student Employment';
    if (/hardship/.test(t))                                                 return 'Hardship Bursary';
    if (/scholarship/.test(t))                                              return 'Academic Scholarship';
    return title || 'Application';
  };

  const getStatusBadge = (status: string, app?: any) => {
    const statusClassMap: Record<string, string> = {
      pending: 'badge-pending',
      reviewed: 'badge-reviewed',
      forwarded: 'badge-forwarded',
      more_info_required: 'badge-pending',
      accepted: 'badge-accepted',
      rejected: 'badge-rejected',
      sent_to_finance: 'badge-finance',
    };
    const statusLabelMap: Record<string, string> = {
      more_info_required: 'More Info Required',
      sent_to_finance: 'Sent to Finance',
      reviewed: 'Admin Reviewed',
      review: 'Admin Reviewed',
    };

    // Show Form B waiting status for Form A submissions
    if (app && status === 'pending' && app.form_b_status === 'sent') {
      return (
        <span className="admin-badge" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d' }}>
          Awaiting Enrollment Verification
        </span>
      );
    }

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
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Ic.AlertTriangle size={14} /> DUPLICATE FLAG
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
            <h3 style={{ fontSize: '14px', fontWeight: '800' }}>FUNDING BREAKDOWN</h3>
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
            <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#b91c1c' }}>FUNDING BREAKDOWN</h3>
            <span className="admin-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontSize: '9px', padding: '2px 8px' }}>INELIGIBLE</span>
          </div>
          <p style={{ fontSize: '13px', color: '#991b1b' }}>{autoSuggested.reason || 'Student does not meet eligibility criteria for this funding stream.'}</p>
        </div>
      );
    }

    const tuitionAmount = autoSuggested.tuition?.system ?? 0;
    const livingAmount = autoSuggested.living?.system ?? 0;
    const booksAmount = autoSuggested.books?.system ?? getPolicySetting('system_config', 'book_allowance') ?? 0;
    const specialAmount = autoSuggested.special?.system ?? 0;
    const totalAmount = autoSuggested.total ?? 0;

    const breakdownRows: Array<{ label: string; amount: number; note?: string; icon: React.ReactNode }> = [
      {
        icon: <Ic.GraduationCap size={16} />,
        label: 'Tuition',
        amount: tuitionAmount,
        note: autoSuggested.tuition?.rule,
      },
      {
        icon: <Ic.Home size={16} />,
        label: 'Living Allowance',
        amount: livingAmount,
        note: (autoSuggested.living?.rule ? autoSuggested.living.rule + ' — ' : '') + 'This is the total amount you may be eligible for the full semester.',
      },
      {
        icon: <Ic.BookOpen size={16} />,
        label: 'Books & Supplies',
        amount: booksAmount,
        note: autoSuggested.books?.rule,
      },
    ];

    if (specialAmount > 0) {
      breakdownRows.push({
        icon: <Ic.Star size={16} />,
        label: 'Special Awards',
        amount: specialAmount,
        note: autoSuggested.special?.rule || 'Academic or graduation award',
      });
    }

    return (
      <div className="admin-chart-card" style={{ marginTop: '32px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '800' }}>FUNDING BREAKDOWN</h3>
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
                <span style={{ width: '24px', display: 'flex', justifyContent: 'center' }}>{row.icon}</span>
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
              <span style={{ width: '24px', display: 'flex', justifyContent: 'center' }}><Ic.DollarSign size={16} style={{ color: '#e5a662' }} /></span>
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
    if (role !== 'director') return null;
    // While the detail is still loading we may not have student_details yet.
    if (!selectedApp?.student_details && !isDetailLoading) return null;
    const sd: any = detailApp?.student_details || selectedApp?.student_details || {};

    return (
      <div className="admin-chart-card" style={{ background: '#f0fdf4', border: '1px solid #dcfce7', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#166534' }}>
          <Ic.Lock size={14} style={{ marginRight: '6px' }} /> BANKING DETAILS (DIRECTOR ONLY)
        </h3>
        <div className="banking-details-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              ACCOUNT HOLDER
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {fieldOrSkel(sd.account_holder_name || sd.full_name, '80%')}
            </div>
          </div>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              BANK NAME
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {fieldOrSkel(sd.bank_name, '70%')}
            </div>
          </div>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              ACCOUNT NUMBER
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {fieldOrSkel(sd.account_number, '65%')}
            </div>
          </div>
          <div>
            <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
              TRANSIT NUMBER
            </label>
            <div style={{ fontSize: '13px', fontWeight: '600' }}>
              {fieldOrSkel(sd.transit_number, '50%')}
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
      icon: React.ReactNode;
    }> = [];

    if (app) {
      // 1. Application submitted
      if (app.submitted_at) {
        timelineEntries.push({
          action: 'Application Submitted',
          performer: app.student_details?.full_name || 'Student',
          timestamp: app.submitted_at,
          color: '#1a6b3a',
          icon: <Ic.Clipboard size={14} />,
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
          icon: <Ic.Search size={14} />,
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
          icon: <Ic.Send size={14} />,
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
          icon: isApproved ? <Ic.CheckCircle size={14} /> : <Ic.XCircle size={14} />,
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
              icon: <Ic.FileEdit size={14} />,
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
          icon: <Ic.Lock size={14} />,
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
          <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}><Ic.Clock size={14} /> AUDIT TRAIL</h3>
          {!isAuditLoading && (
            <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}>
              {timelineEntries.length} EVENT{timelineEntries.length !== 1 ? 'S' : ''}
            </span>
          )}
        </div>

        {/* Loading state — skeleton timeline */}
        {isAuditLoading && (
          <div className="audit-timeline" aria-busy="true">
            {[0, 1, 2].map(i => (
              <div key={i} className={`audit-timeline-item ${i === 2 ? 'audit-timeline-item--last' : ''}`}>
                <div className="audit-timeline-dot skeleton" style={{ background: undefined }}></div>
                <div className="audit-timeline-content">
                  <div className="audit-timeline-action">
                    <span className="skeleton skeleton-line" style={{ width: '50%' }} aria-hidden>·</span>
                  </div>
                  <div className="audit-timeline-meta" style={{ marginTop: '6px' }}>
                    <span className="skeleton skeleton-line-xs" style={{ width: '70%' }} aria-hidden>·</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {auditError && !isAuditLoading && (
          <div className="audit-trail-error">
            <Ic.AlertTriangle size={14} />
            <span>Could not load additional audit entries: {auditError}</span>
          </div>
        )}

        {/* Empty state */}
        {!isAuditLoading && timelineEntries.length === 0 && (
          <div className="audit-trail-empty">
            <div className="audit-trail-empty-icon"><Ic.Clipboard size={32} /></div>
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
          // Check if it's the specific expense list structure (handles 'description' or 'purpose')
          if ((parsed[0].description || parsed[0].purpose) && parsed[0].amount) {
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
                        <td style={{ padding: '6px 0', color: '#1e293b' }}>{item.description || item.purpose}</td>
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
    const app = detailApp || applications.find(a => String(a.id) === String(selectedAppId));
    if (!app) return null;

    // While the detail record is still hydrating, show a skeleton instead of
    // a misleading "no answers" empty state.
    if (isDetailLoading) {
      return (
        <div style={{ marginTop: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '800' }}>SUBMITTED INFORMATION</h3>
            <span className="skeleton skeleton-chip" aria-hidden>·</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{ padding: '16px', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                <span className="skeleton skeleton-line-xs" style={{ width: '30%' }} aria-hidden>·</span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '14px 24px', marginTop: '12px' }}>
                  {[0, 1, 2, 3].map(j => (
                    <div key={j}>
                      <span className="skeleton skeleton-line-xs" style={{ width: '50%' }} aria-hidden>·</span>
                      <div style={{ marginTop: '6px' }}>
                        <span className="skeleton skeleton-line" style={{ width: `${55 + ((i + j) * 7) % 35}%` }} aria-hidden>·</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

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

    const groupIcons: Record<string, React.ReactNode> = {
      'Personal Information': <Ic.User size={14} />,
      'Program & Enrollment': <Ic.GraduationCap size={14} />,
      'Financial Information': <Ic.DollarSign size={14} />,
      'Documents & Files': <Ic.Paperclip size={14} />,
      'Other Information': <Ic.Clipboard size={14} />,
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
                <span style={{ marginRight: '8px' }}>{groupIcons[groupName] || <Ic.Clipboard size={14} />}</span>
                {groupName}
              </div>
              <div className="submitted-info-grid">
                {groupAnswers.map((answer: any, idx: number) => {
                  const fieldLabel = answer.label || answer.field?.label || answer.field_label || `Field ${idx + 1}`;
                  const displayLabel = formatFieldLabel(fieldLabel);
                  const fileUrl = answer.answer_file || (isFileAnswer(answer) ? answer.answer_text : null);
                  // Prefer the user's original filename (post-migration). For pre-migration
                  // rows it's NULL — fall through to the readable field label, NOT the
                  // UUID-encoded storage filename.
                  const urlTail = fileUrl ? (fileUrl.split('/').pop() || '').split('?')[0] : '';
                  const urlLooksRandom = /^[0-9a-f]{16,}\.\w+$/i.test(urlTail);
                  const fileName = answer.original_filename
                    || (urlTail && !urlLooksRandom ? urlTail : '')
                    || displayLabel
                    || 'Download File';
                  const textValue = answer.answer_text;

                  return (
                    <div key={answer.id || idx} className="submitted-info-field">
                      <div className="submitted-info-label">{displayLabel}</div>
                      {fileUrl ? (
                        <div className="submitted-info-file">
                          <span style={{ marginRight: '8px' }}>
                            {fileUrl.toLowerCase().endsWith('.pdf') ? <Ic.FileText size={16} /> :
                              /\.(jpg|jpeg|png|gif)$/i.test(fileUrl) ? <Ic.Image size={16} /> : <Ic.Paperclip size={16} />}
                          </span>
                          <a
                            href={fileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="submitted-info-download-link"
                            aria-label={`Download ${fileName}`}
                          >
                            {fileName}
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
                {renderNavItem('appeals', 'Special Awards', <AdminIcons.Apps />, pendingSpecialAwards || undefined)}
                {renderNavItem('notifications', 'Notifications', <AdminIcons.Dashboard />, notifications.filter((n: any) => !n.is_read).length || undefined)}
              </div>

              <div className="staff-nav-group">
                <div className="staff-nav-title">Administration</div>
                {renderNavItem('user-management', 'User Management', <Ic.Users size={16} />)}
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
                {renderNavItem('appeals', 'Special Awards', <AdminIcons.Apps />, pendingSpecialAwards || undefined)}
              </div>
            </>
          )}
        </nav>

        <div style={{ marginTop: 'auto', padding: '24px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="staff-nav-item" onClick={() => {
            ['dgg_token','dgg_refresh','dgg_role','dgg_profile_cache'].forEach(k => localStorage.removeItem(k));
            navigate('/internal/login');
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Ic.Lock size={14} /> Sign Out</span>
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
                  onClick={() => setCurrentView(role === 'director' ? 'director-queue' : 'applications')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: 'inherit' }}
                >
                  <AdminIcons.ChevronLeft />
                </button>
                Reviewing #{getRef(Number(selectedAppId))}
              </div>
            )}
            {currentView === 'director-detail' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: '800' }}>DIRECTOR</span>
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>—</span>
                <span style={{ fontWeight: '800' }}>#{getRef(Number(selectedAppId))}</span>
              </div>
            )}
            {currentView === 'policy' && 'Policy Settings'}
            {currentView === 'reports' && 'Reports & Analytics'}
            {currentView === 'director-queue' && 'Approval Queue'}
            {currentView === 'director' && 'Director Approval Queue'}
            {currentView === 'user-management' && 'User Management'}
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

            <span className="staff-topbar-meta" style={{ fontSize: '11px', color: '#64748b', fontWeight: '600' }}>FY 2025/2026</span>
            <div className="staff-topbar-meta" style={{ width: '1px', height: '20px', background: '#e2e8f0' }}></div>
            <button className="admin-badge badge-pending staff-topbar-meta" style={{ border: 'none', cursor: 'pointer' }}>
              Support Active
            </button>
          </div>
        </header>

        <main className="staff-content">
          {isLoading && applications.length === 0 && (
            <div className="ui-loading-block">
              <span className="ui-spinner ui-spinner-lg" />
              <span>Loading staff portal data…</span>
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
          {currentView === 'dashboard' && (() => {
            // Prefer server-computed stats — they reflect the full dataset, not just the
            // first paginated page of applications loaded locally.
            const sbs = backendStats?.submissions_by_status || {};
            const totalApps      = backendStats?.total_submissions      ?? stats.totalApps;
            const totalStudents  = backendStats?.total_students         ?? stats.activeStudents;
            const approvedAmount = backendStats?.total_funding_approved ?? stats.approvedAmount;
            const pendingFunding = backendStats?.pending_funding_total  ?? stats.pendingAmount ?? 0;
            const cntPending  = sbs.pending     ?? stats.statusCounts.pending;
            const cntReviewed = sbs.reviewed    ?? 0;
            const cntForwarded= sbs.forwarded   ?? stats.statusCounts.forwarded;
            const cntAccepted = sbs.accepted    ?? stats.statusCounts.accepted;
            const cntRejected = sbs.rejected    ?? stats.statusCounts.rejected;
            const cntMoreInfo = sbs.more_info_required ?? 0;
            const cntFinance  = sbs.sent_to_finance ?? 0;
            const formBAwait  = sbs.waiting_form_b ?? backendStats?.form_b_stats?.awaiting ?? stats.formBPending;
            const underReview = cntPending + cntReviewed + cntForwarded;
            const approvalRate = backendStats?.approval_rate
              ?? (totalApps > 0 ? +(cntAccepted / totalApps * 100).toFixed(1) : 0);

            // Stream split — prefer backend (counts full dataset by FUNDING_TYPE regex)
            const streams = backendStats?.stream_split;
            // Stream split — primary navy, secondary gold, neutral slate (brand-aligned trio)
            const streamData = streams ? [
              { key: 'pssp',  label: 'C-DFN (PSSSP / Bursary)', count: streams.pssp  || 0, pct: streams.pssp_percent  || 0, color: '#0f172a' },
              { key: 'dggr',  label: 'DGGR Bursaries',          count: streams.dggr  || 0, pct: streams.dggr_percent  || 0, color: '#e5a662' },
              { key: 'ucepp', label: 'UCEPP (Upgrading)',       count: streams.ucepp || 0, pct: streams.ucepp_percent || 0, color: '#94a3b8' },
            ] : [
              { key: 'pssp',  label: 'C-DFN (PSSSP / Bursary)', count: stats.cdfnCount,  pct: stats.pssspPercent, color: '#0f172a' },
              { key: 'dggr',  label: 'DGGR Bursaries',          count: stats.dggrCount,  pct: stats.dggrPercent,  color: '#e5a662' },
              { key: 'ucepp', label: 'UCEPP (Upgrading)',       count: stats.uceppCount, pct: stats.uceppPercent, color: '#94a3b8' },
            ];

            // Smart $ formatter — no fake "k" suffix on small values
            const fmtMoney = (v: number): string => {
              if (!v) return '$0';
              if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
              if (v >= 10_000)    return `$${(v / 1_000).toFixed(0)}k`;
              if (v >= 1_000)     return `$${(v / 1_000).toFixed(1)}k`;
              return `$${Math.round(v).toLocaleString()}`;
            };

            const recent = applications
              .slice()
              .sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime())
              .slice(0, 8);
            const initials = (name: string) => {
              const parts = (name || '').trim().split(/\s+/).filter(Boolean);
              if (parts.length === 0) return '?';
              if (parts.length === 1) return parts[0][0]?.toUpperCase() || '?';
              return ((parts[0][0] || '') + (parts[parts.length - 1][0] || '')).toUpperCase();
            };

            return (
            <div className="fade-in">
              {/* ── Header ── */}
              <div className="apps-header">
                <div>
                  <h2 className="apps-header-title">{role === 'director' ? 'Director Overview' : 'Admin Overview'}</h2>
                  <p className="apps-header-sub">
                    {totalApps > 0
                      ? `Snapshot of ${totalApps.toLocaleString()} submission${totalApps === 1 ? '' : 's'} across ${totalStudents.toLocaleString()} student${totalStudents === 1 ? '' : 's'}.`
                      : 'No submissions yet — applications will appear here as they come in.'}
                  </p>
                </div>
              </div>

              {/* ── KPI strip (4 cards) ── */}
              <div className="dash-kpi-grid">
                <div className="dash-kpi">
                  <div className="dash-kpi-icon"><Ic.Inbox size={18} /></div>
                  <div className="dash-kpi-body">
                    <div className="dash-kpi-value">{totalApps.toLocaleString()}</div>
                    <div className="dash-kpi-label">Total applications</div>
                    <div className="dash-kpi-foot">{totalStudents.toLocaleString()} unique students</div>
                  </div>
                </div>
                <div className="dash-kpi dash-kpi-accent">
                  <div className="dash-kpi-icon"><Ic.DollarSign size={18} /></div>
                  <div className="dash-kpi-body">
                    <div className="dash-kpi-value">{fmtMoney(approvedAmount)}</div>
                    <div className="dash-kpi-label">Funding approved</div>
                    <div className="dash-kpi-foot">{approvalRate}% approval rate</div>
                  </div>
                </div>
                <div className="dash-kpi">
                  <div className="dash-kpi-icon"><Ic.Clock size={18} /></div>
                  <div className="dash-kpi-body">
                    <div className="dash-kpi-value">{underReview.toLocaleString()}</div>
                    <div className="dash-kpi-label">Awaiting decision</div>
                    <div className="dash-kpi-foot">{cntForwarded.toLocaleString()} with director</div>
                  </div>
                </div>
                <div className="dash-kpi">
                  <div className="dash-kpi-icon"><Ic.Send size={18} /></div>
                  <div className="dash-kpi-body">
                    <div className="dash-kpi-value">{fmtMoney(pendingFunding)}</div>
                    <div className="dash-kpi-label">Pending funding</div>
                    <div className="dash-kpi-foot">Forwarded but not decided</div>
                  </div>
                </div>
              </div>

              {/* ── Insights row: stream split + status breakdown ── */}
              <div className="dash-insights">
                <div className="dash-panel">
                  <div className="dash-panel-header">
                    <h3 className="dash-panel-title">Stream split</h3>
                    <span className="dash-panel-sub">{totalApps.toLocaleString()} submissions</span>
                  </div>
                  <div className="dash-stream-list">
                    {streamData.map(s => (
                      <div key={s.key} className="dash-stream-row">
                        <div className="dash-stream-head">
                          <div className="dash-stream-label">
                            <span className="dash-stream-dot" style={{ background: s.color }}></span>
                            {s.label}
                          </div>
                          <div className="dash-stream-meta">
                            <span className="dash-stream-count">{s.count.toLocaleString()}</span>
                            <span className="dash-stream-pct">{Math.round(s.pct)}%</span>
                          </div>
                        </div>
                        <div className="dash-stream-bar">
                          <div className="dash-stream-bar-fill" style={{ width: `${Math.min(100, s.pct)}%`, background: s.color }}></div>
                        </div>
                      </div>
                    ))}
                    {totalApps === 0 && (
                      <div className="dash-empty-mini">No submissions to break down yet.</div>
                    )}
                  </div>
                </div>

                <div className="dash-panel">
                  <div className="dash-panel-header">
                    <h3 className="dash-panel-title">Status breakdown</h3>
                  </div>
                  <div className="dash-status-list">
                    {[
                      { label: 'Approved',             count: cntAccepted,  badgeClass: 'badge-approved',  hint: 'Approved across the system (includes dispatched)' },
                      { label: 'Sent to Finance',      count: cntFinance,   badgeClass: 'badge-approved',  hint: 'Approved + dispatched for payment' },
                      { label: 'Awaiting director',    count: cntForwarded, badgeClass: 'badge-forwarded', hint: 'Forwarded for decision' },
                      { label: 'Admin reviewed',       count: cntReviewed,  badgeClass: 'badge-reviewed',  hint: 'Ready to forward' },
                      { label: 'New / pending',        count: cntPending,   badgeClass: 'badge-pending',   hint: 'Awaiting first review' },
                      { label: 'More info requested',  count: cntMoreInfo,  badgeClass: 'badge-pending',   hint: 'Waiting on student' },
                      { label: 'Awaiting Form B',      count: formBAwait,   badgeClass: 'badge-pending',   hint: 'Enrollment verification pending', icon: <Ic.FileText size={14} /> },
                      { label: 'Denied',               count: cntRejected,  badgeClass: 'badge-denied',    hint: 'Closed' },
                    ].map(item => (
                      <div key={item.label} className="dash-status-row">
                        <div className="dash-status-left">
                          <span className={`admin-badge ${item.badgeClass}`} style={{ minWidth: '90px', textAlign: 'center' }}>
                            {item.icon ? <span style={{ display: 'inline-flex', verticalAlign: 'middle', marginRight: '4px' }}>{item.icon}</span> : null}
                            {item.label}
                          </span>
                          <span className="dash-status-hint">{item.hint}</span>
                        </div>
                        <span className="dash-status-count">{item.count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* ── Recent activity ── */}
              <div className="dash-activity">
                <div className="dash-activity-header">
                  <div>
                    <h3 className="dash-panel-title">Recent activity</h3>
                    <p className="dash-activity-sub">Latest {Math.min(recent.length, 8)} submissions</p>
                  </div>
                  <button
                    className="btn-primary"
                    style={{ fontSize: '12px', padding: '8px 16px' }}
                    onClick={() => setCurrentView('applications')}
                  >View all applications →</button>
                </div>
                <table className="apps-table">
                  <thead>
                    <tr>
                      <th>Ref</th>
                      <th>Applicant</th>
                      <th>Program / Form</th>
                      <th>Submitted</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.length === 0 && (
                      <tr>
                        <td colSpan={5} className="apps-empty">
                          <Ic.Inbox size={28} />
                          <div className="apps-empty-title">No submissions yet</div>
                          <div className="apps-empty-sub">New applications will show up here as they come in.</div>
                        </td>
                      </tr>
                    )}
                    {recent.map(app => {
                      const name = getStudentName(app);
                      return (
                        <tr
                          key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}
                          className="apps-row"
                          onClick={() => handleAppClick(app.id)}
                          tabIndex={0}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                          role="button"
                          aria-label={`View application ${app.id} for ${name}`}
                        >
                          <td className="apps-cell-ref">#{getRef(app.id)}</td>
                          <td>
                            <div className="apps-applicant">
                              <div className="apps-avatar">{initials(name)}</div>
                              <div className="apps-applicant-info">
                                <div className="apps-applicant-name">{name}</div>
                                {app.student_details?.email && (
                                  <div className="apps-applicant-sub">{app.student_details.email}</div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td>
                            <div className="apps-program">{getFormDisplayName(app.form_title || app.form?.title)}</div>
                          </td>
                          <td className="apps-cell-date">
                            {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                          </td>
                          <td>{getStatusBadge(app.status, app)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            );
          })()}

          {/* Applications View */}
          {currentView === 'applications' && role === 'director' && (
            <div className="fade-in" style={{ padding: '40px', textAlign: 'center' }}>
              <div style={{ marginBottom: '16px', color: '#64748b' }}><Ic.Lock size={32} /></div>
              <h3 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>Access Restricted</h3>
              <p style={{ color: '#64748b', marginBottom: '24px' }}>Directors can only view applications that have been forwarded for approval.</p>
              <button className="admin-badge badge-approved" style={{ padding: '10px 24px', cursor: 'pointer', border: 'none', fontWeight: '700' }} onClick={() => setCurrentView('director-queue')}>
                Go to Approval Queue →
              </button>
            </div>
          )}

          {currentView === 'applications' && role !== 'director' && (() => {
            const counts = {
              all: applications.length,
              pending: applications.filter(a => a.status === 'pending').length,
              reviewed: applications.filter(a => a.status === 'reviewed').length,
              forwarded: applications.filter(a => a.status === 'forwarded').length,
              accepted: applications.filter(a => a.status === 'accepted').length,
              rejected: applications.filter(a => a.status === 'rejected').length,
              more_info: applications.filter(a => a.status === 'more_info_required').length,
            };
            const approvedFunding = applications
              .filter(a => a.status === 'accepted')
              .reduce((s, a) => s + (parseFloat(a.amount) || 0), 0);
            const tabs: Array<{ key: string; label: string; count: number; tone?: string }> = [
              { key: 'all',       label: 'All',               count: counts.all },
              { key: 'pending',   label: 'New',               count: counts.pending,   tone: 'warn' },
              { key: 'reviewed',  label: 'Reviewed',          count: counts.reviewed },
              { key: 'forwarded', label: 'Awaiting Director', count: counts.forwarded },
              { key: 'accepted',  label: 'Approved',          count: counts.accepted,  tone: 'good' },
              { key: 'rejected',  label: 'Denied',            count: counts.rejected,  tone: 'bad' },
            ];
            const initials = (name: string) => {
              const parts = (name || '').trim().split(/\s+/).filter(Boolean);
              if (parts.length === 0) return '?';
              if (parts.length === 1) return parts[0][0]?.toUpperCase() || '?';
              return ((parts[0][0] || '') + (parts[parts.length - 1][0] || '')).toUpperCase();
            };
            const sortIndicator = (col: string) => sortColumn === col ? (sortDirection === 'asc' ? '↑' : '↓') : '';
            return (
            <div className="fade-in">
              {/* ── Page header with title + KPIs ── */}
              <div className="apps-header">
                <div>
                  <h2 className="apps-header-title">All Applications</h2>
                  <p className="apps-header-sub">Review, route, and decide on incoming funding applications.</p>
                </div>
                <div className="apps-kpi-strip">
                  <div className="apps-kpi">
                    <div className="apps-kpi-icon"><Ic.Inbox size={16} /></div>
                    <div>
                      <div className="apps-kpi-value">{counts.all.toLocaleString()}</div>
                      <div className="apps-kpi-label">Total</div>
                    </div>
                  </div>
                  <div className="apps-kpi">
                    <div className="apps-kpi-icon"><Ic.Clock size={16} /></div>
                    <div>
                      <div className="apps-kpi-value">{counts.pending + counts.reviewed}</div>
                      <div className="apps-kpi-label">Awaiting Action</div>
                    </div>
                  </div>
                  <div className="apps-kpi">
                    <div className="apps-kpi-icon"><Ic.Send size={16} /></div>
                    <div>
                      <div className="apps-kpi-value">{counts.forwarded}</div>
                      <div className="apps-kpi-label">With Director</div>
                    </div>
                  </div>
                  <div className="apps-kpi apps-kpi-accent">
                    <div className="apps-kpi-icon"><Ic.DollarSign size={16} /></div>
                    <div>
                      <div className="apps-kpi-value">${approvedFunding.toLocaleString()}</div>
                      <div className="apps-kpi-label">Funding Approved</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* ── Filter bar ── */}
              <div className="apps-toolbar">
                <div className="apps-search">
                  <span className="apps-search-icon"><Ic.Search size={14} /></span>
                  <input
                    type="text"
                    className="apps-search-input"
                    placeholder="Search by name, ID, email, or beneficiary number…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <select
                  className="apps-select"
                  value={fundingStreamFilter}
                  onChange={(e) => setFundingStreamFilter(e.target.value)}
                  aria-label="Filter by funding stream"
                >
                  <option value="all">All streams</option>
                  <option value="PSSSP">PSSSP</option>
                  <option value="UCEPP">UCEPP</option>
                  <option value="DGGR">DGGR</option>
                </select>
              </div>

              {/* ── Status pills with counts ── */}
              <div className="apps-tabs">
                {tabs.map(t => (
                  <button
                    key={t.key}
                    className={`apps-tab ${statusFilter === t.key ? 'is-active' : ''}`}
                    onClick={() => { setStatusFilter(t.key); setCurrentPage(1); }}
                  >
                    <span>{t.label}</span>
                    <span className={`apps-tab-count tone-${t.tone || 'slate'}`}>{t.count}</span>
                  </button>
                ))}
              </div>

              {/* ── Table ── */}
              <div className="apps-table-card">
                <table className="apps-table">
                  <thead>
                    <tr>
                      <th onClick={() => handleSort('id')} className="apps-th-sort">Ref {sortIndicator('id')}</th>
                      <th onClick={() => handleSort('student_name')} className="apps-th-sort">Applicant {sortIndicator('student_name')}</th>
                      <th onClick={() => handleSort('form_title')} className="apps-th-sort">Program / Form {sortIndicator('form_title')}</th>
                      <th onClick={() => handleSort('submitted_at')} className="apps-th-sort">Submitted {sortIndicator('submitted_at')}</th>
                      <th>Status</th>
                      <th onClick={() => handleSort('amount')} className="apps-th-sort" style={{ textAlign: 'right' }}>Funding {sortIndicator('amount')}</th>
                      <th style={{ width: '120px' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedApps.length === 0 && (
                      <tr>
                        <td colSpan={7} className="apps-empty">
                          <Ic.Inbox size={28} />
                          <div className="apps-empty-title">No applications match the current filters</div>
                          <div className="apps-empty-sub">Try changing the status tab or clearing the search.</div>
                        </td>
                      </tr>
                    )}
                    {paginatedApps.map(app => {
                      const name = getStudentName(app);
                      const cta = app.status === 'forwarded' ? 'Decide'
                                : (app.status === 'reviewed' || app.status === 'review') ? 'Forward'
                                : app.status === 'accepted' || app.status === 'rejected' ? 'View'
                                : 'Review';
                      return (
                      <tr
                        key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}
                        className="apps-row"
                        onClick={() => handleAppClick(app.id)}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                        role="button"
                        aria-label={`View application ${app.id} for ${name}`}
                      >
                        <td className="apps-cell-ref">#{getRef(app.id)}</td>
                        <td>
                          <div className="apps-applicant">
                            <div className="apps-avatar">{initials(name)}</div>
                            <div className="apps-applicant-info">
                              <div className="apps-applicant-name">{name}</div>
                              {app.student_details?.email && (
                                <div className="apps-applicant-sub">{app.student_details.email}</div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td>
                          <div className="apps-program">{getFormDisplayName(app.form_title || app.form?.title)}</div>
                          {app.student_details?.primary_stream && (
                            <div className="apps-program-stream">{app.student_details.primary_stream}</div>
                          )}
                        </td>
                        <td className="apps-cell-date">
                          {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                        </td>
                        <td>
                          {getStatusBadge(app.status, app)}
                          {(() => {
                            const hasFileDocs = (app.answers || []).some((a: any) => a.answer_file);
                            const hasAppDocs = (app.documents || []).length > 0;
                            if (!hasFileDocs && !hasAppDocs) {
                              return (
                                <span title="No documentation attached to this application" style={{ marginLeft: '6px', display: 'inline-flex', alignItems: 'center', gap: '2px', padding: '2px 6px', background: '#fef9c3', color: '#854d0e', border: '1px solid #fde68a', borderRadius: '4px', fontSize: '9px', fontWeight: '800', verticalAlign: 'middle' }}>
                                  <Ic.AlertTriangle size={9} /> NO DOCS
                                </span>
                              );
                            }
                            return null;
                          })()}
                        </td>
                        <td className="apps-cell-amount">
                          {parseFloat(app.amount) > 0
                            ? <span className="apps-amount-positive">${parseFloat(app.amount).toLocaleString()}</span>
                            : <span className="apps-amount-muted">—</span>
                          }
                        </td>
                        <td>
                          <button
                            className="apps-row-cta"
                            onClick={(e) => { e.stopPropagation(); handleAppClick(app.id); }}
                          >
                            {cta} <span aria-hidden="true">→</span>
                          </button>
                        </td>
                      </tr>
                    );})}
                  </tbody>
                </table>
              </div>

              {/* ── Pagination ── */}
              {totalPages > 1 && (
                <div className="apps-pagination">
                  <div className="apps-pagination-info">
                    Showing <strong>{((currentPage - 1) * itemsPerPage) + 1}</strong>–<strong>{Math.min(currentPage * itemsPerPage, filteredAndSortedApps.length)}</strong> of <strong>{filteredAndSortedApps.length}</strong>
                  </div>
                  <div className="apps-pagination-controls">
                    <button
                      className="apps-pagination-btn"
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                    >← Previous</button>
                    <span className="apps-pagination-page">Page {currentPage} of {totalPages}</span>
                    <button
                      className="apps-pagination-btn"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >Next →</button>
                  </div>
                </div>
              )}
            </div>
            );
          })()}
          {/* end applications view for non-directors */}

          {/* Detail View (Shared by Staff and Director) */}
          {(currentView === 'detail' && selectedAppId) && (
            <div className="fade-in">
              {/* Header Actions */}
              <div className="admin-detail-header">
                <div style={{ fontSize: '11px', color: '#64748b' }}>
                  <span
                    style={{ cursor: 'pointer' }}
                    onClick={() => { setSelectedAppId(null); setDetailApp(null); setCurrentView(role === 'director' ? 'director-queue' : 'applications'); }}
                  >
                    {role === 'director' ? 'Approval Queue' : 'All Applications'}
                  </span>
                  {' / '}
                  <span style={{ fontWeight: '700', color: '#1e293b' }}>#{getRef(Number(selectedAppId))}</span>
                </div>
                <div className="admin-detail-actions">
                  {/* SSW-only actions — hidden from director */}
                  {role !== 'director' && (
                    <>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleRequestInfo}>REQUEST MORE INFO</button>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleAddNote} disabled={!staffNote.trim() || isLoading}>ADD NOTE</button>
                    </>
                  )}
                  {role === 'director' ? (
                    <>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={handleRequestInfo}>REQUEST MORE INFO</button>
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
                    (() => {
                      const isStandard = selectedApp?._is_standard;
                      const isApprovedByAdmin = selectedApp?.status === 'reviewed' || selectedApp?.status === 'review';
                      const isForwarded = selectedApp?.status === 'forwarded' || (isStandard && selectedApp?.status === 'pending');
                      const isDecided = selectedApp?.status === 'accepted' || selectedApp?.status === 'rejected';
                      // Form B (Enrollment Verification) gate — required for Admission (Form A) BEFORE
                      // admin can approve AND before forwarding to director. Other form types skip
                      // the gate entirely (form_b_status will be null/undefined on non-Admission apps).
                      const fbStatus = selectedApp?.form_b_status;
                      const isFormA = fbStatus !== undefined && fbStatus !== null;
                      const formBBlocked = isFormA && fbStatus !== 'received';
                      const isDisabled = isForwarded || isDecided || isSubmittingDecision || formBBlocked;

                      return (
                        <button
                          className="admin-input"
                          title={formBBlocked
                            ? (isApprovedByAdmin
                                ? 'Cannot forward — Form B (Enrollment Verification) not yet received from registrar.'
                                : 'Cannot approve — Form B (Enrollment Verification) not yet received from registrar.')
                            : undefined}
                          style={{
                            width: 'auto', fontSize: '11px', fontWeight: '700',
                            background: isDisabled ? '#94a3b8' : isSubmittingDecision ? '#64748b' : isApprovedByAdmin ? 'var(--admin-accent)' : '#10b981',
                            color: isDisabled ? '#fff' : '#000',
                            border: 'none',
                            cursor: isDisabled ? 'not-allowed' : 'pointer',
                            display: 'flex', alignItems: 'center', gap: '8px',
                          }}
                          disabled={isDisabled}
                          onClick={() => {
                            if (isApprovedByAdmin) {
                              handleDecision('forwarded');
                            } else {
                              handleDecision(isStandard ? 'review' : 'reviewed');
                            }
                          }}
                        >
                          {isSubmittingDecision ? (
                            <>
                              <span style={{ width: '12px', height: '12px', border: '2px solid rgba(0,0,0,0.2)', borderTopColor: '#000', borderRadius: '50%', animation: 'spin 0.8s linear infinite', display: 'inline-block' }} />
                              {isForwarding ? 'SENDING...' : 'UPDATING...'}
                            </>
                          ) : isForwarded ? (
                            '✓ SENT TO DIRECTOR'
                          ) : isDecided ? (
                            '✓ DECIDED'
                          ) : formBBlocked ? (
                            'AWAITING FORM B'
                          ) : isApprovedByAdmin ? (
                            'SEND TO DIRECTOR →'
                          ) : (
                            'APPROVE REVIEW'
                          )}
                        </button>
                      );
                    })()
                  )}
                </div>
              </div>

              <div className="admin-detail-grid">
                {/* Left: Detail Forms */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    {(() => {
                      const app = detailApp || applications.find(a => String(a.id) === String(selectedAppId));
                      const sd = app?.student_details || {};
                      const getAns = (lbl: string) => (app?.answers || []).find((a: any) =>
                        (a.label || a.field_label || '').toLowerCase().includes(lbl.toLowerCase())
                      )?.answer_text;
                      return (
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
                              <div style={{ fontSize: '11px', color: '#64748b' }}>#{getRef(Number(selectedAppId))}</div>
                              <h2 style={{ fontSize: '20px', fontWeight: '800' }}>
                                {isDetailLoading
                                  ? <Skel w={260} h={22} />
                                  : `${sd.full_name || 'Student'} — ${getFormDisplayName(app?.form_title || app?.form?.title)}`}
                              </h2>
                              <div style={{ fontSize: '11px', color: '#64748b' }}>
                                {isDetailLoading
                                  ? <Skel w={140} cls="skeleton-line-sm" />
                                  : `Submitted ${app?.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' }) : 'N/A'}`}
                              </div>
                            </div>
                            {isDetailLoading
                              ? <Skel w={84} cls="skeleton-badge" />
                              : getStatusBadge(app?.status || 'pending', app)}
                          </div>

                          <div style={{ padding: '20px', background: '#f8fafc', borderRadius: '10px' }}>
                            <div className="admin-nav-title" style={{ marginBottom: '16px', padding: '0' }}>STUDENT & PROGRAM</div>
                            <div className="dir-student-grid" style={{ display: 'grid', gap: '24px' }}>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>NAME</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.full_name, '80%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>BENEFICIARY #</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.beneficiary_number || (isDetailLoading ? null : 'None'), '60%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>DOB</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.dob || (isDetailLoading ? null : 'Not Provided'), '65%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>PHONE</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.phone || (isDetailLoading ? null : 'None'), '70%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>ENROLLMENT</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.enrollment_status || getAns('enrollment'), '55%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>FUNDING STREAM</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.primary_stream, '50%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>INSTITUTION</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.institution_name || getAns('institution') || getAns('school'), '85%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>PROGRAM</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.program_credential || getAns('program'), '75%')}</div>
                              </div>
                              <div>
                                <label className="admin-kpi-label" style={{ fontSize: '9px' }}>SEMESTER</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fieldOrSkel(sd.current_semester || getAns('semester'), '55%')}</div>
                              </div>
                            </div>
                          </div>
                        </>
                      );
                    })()}

                    {/* Form B Enrollment Verification Section */}
                    {(() => {
                      const app = detailApp || applications.find(a => String(a.id) === String(selectedAppId));
                      const fb = app?.form_b;
                      const fbStatus = app?.form_b_status;
                      if (!fbStatus) return null; // Not a Form A submission

                      if (fbStatus === 'sent') {
                        return (
                          <div style={{ marginTop: '16px', padding: '10px 14px', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <Ic.Clock size={14} style={{ color: '#92400e', flexShrink: 0 }} />
                            <div style={{ fontSize: '12px', color: '#92400e' }}>
                              Enrollment verification sent to <strong>{fb?.registrar_email || 'registrar'}</strong> — awaiting response. Forwarding is locked until Form B is received.
                            </div>
                          </div>
                        );
                      }

                      if (fbStatus === 'received' && fb) {
                        return (
                          <div className="admin-chart-card" style={{ marginTop: '32px', background: '#f0fdf4', border: '1px solid #bbf7d0' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                              <Ic.CheckCircle size={20} style={{ color: '#166534' }} />
                              <div>
                                <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#166534', margin: 0 }}>FORM B RECEIVED — ENROLLMENT VERIFIED</h3>
                                <p style={{ fontSize: '12px', color: '#15803d', margin: '4px 0 0' }}>
                                  Verified by {fb.registrar_name || 'Registrar'}{fb.registrar_title ? ` (${fb.registrar_title})` : ''}
                                  {fb.received_at && ` on ${new Date(fb.received_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' })}`}
                                </p>
                              </div>
                            </div>
                            <div className="dir-student-grid" style={{ display: 'grid', gap: '16px', padding: '16px', background: 'rgba(255,255,255,0.6)', borderRadius: '10px' }}>
                              <div>
                                <label style={{ fontSize: '9px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>ENROLLED</label>
                                <div style={{ fontSize: '13px', fontWeight: '700', color: fb.is_enrolled ? '#166534' : '#b91c1c' }}>
                                  {fb.is_enrolled
                                    ? <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#166534' }}><Ic.CheckCircle size={13} /> Yes</span>
                                    : <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#b91c1c' }}><Ic.XCircle size={13} /> No</span>}
                                </div>
                              </div>
                              <div>
                                <label style={{ fontSize: '9px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>ENROLLMENT STATUS</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fb.enrollment_status || 'N/A'}</div>
                              </div>
                              <div>
                                <label style={{ fontSize: '9px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>COURSE LOAD</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fb.course_load_percent != null ? `${fb.course_load_percent}%` : 'N/A'}</div>
                              </div>
                              <div>
                                <label style={{ fontSize: '9px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>CONFIRMED PROGRAM</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>{fb.confirmed_program || fb.program || 'N/A'}</div>
                              </div>
                              <div>
                                <label style={{ fontSize: '9px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>OFFICIAL TUITION</label>
                                <div style={{ fontSize: '13px', fontWeight: '700', color: '#166534' }}>
                                  {fb.official_tuition != null ? `$${parseFloat(fb.official_tuition).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : 'N/A'}
                                </div>
                              </div>
                              <div>
                                <label style={{ fontSize: '9px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>SEMESTER</label>
                                <div style={{ fontSize: '13px', fontWeight: '700' }}>
                                  {fb.confirmed_sem_start || fb.sem_start || '?'} — {fb.confirmed_sem_end || fb.sem_end || '?'}
                                </div>
                              </div>
                            </div>
                            {fb.registrar_notes && (
                              <div style={{ marginTop: '16px', padding: '12px 16px', background: 'rgba(255,255,255,0.6)', borderRadius: '8px', border: '1px solid #dcfce7' }}>
                                <div style={{ fontSize: '11px', fontWeight: '700', color: '#166534', textTransform: 'uppercase', marginBottom: '6px' }}>REGISTRAR NOTES</div>
                                <div style={{ fontSize: '13px', color: '#1e293b', lineHeight: '1.5' }}>{fb.registrar_notes}</div>
                              </div>
                            )}
                          </div>
                        );
                      }

                      return null;
                    })()}


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
                            <Ic.AlertTriangle size={16} style={{ color: '#b91c1c', flexShrink: 0 }} />
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

                    {/* Student Personal Documents (from My Documents) */}
                    <div style={{ marginTop: '32px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                        <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0 }}>STUDENT PERSONAL DOCUMENTS</h3>
                        {studentDocs.length > 0 && (
                          <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}>{studentDocs.length} FILE{studentDocs.length !== 1 ? 'S' : ''}</span>
                        )}
                      </div>
                      {isLoadingStudentDocs ? (
                        <div style={{ fontSize: '12px', color: '#64748b', padding: '16px', background: '#f8fafc', borderRadius: '8px' }}>Loading documents…</div>
                      ) : studentDocs.length === 0 ? (
                        <div style={{ fontSize: '12px', color: '#94a3b8', fontStyle: 'italic', padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px dashed #e2e8f0', textAlign: 'center' }}>
                          No personal documents uploaded by this student.
                        </div>
                      ) : (
                        <div style={{ display: 'grid', gap: '10px' }}>
                          {studentDocs.map((doc: any) => (
                            <div key={doc.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                                <Ic.FileText size={16} style={{ flexShrink: 0, color: '#3b82f6' }} />
                                <div style={{ minWidth: 0 }}>
                                  <div style={{ fontSize: '12px', fontWeight: '600', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.name || doc.original_filename || (doc.file || '').split('/').pop() || 'Document'}</div>
                                  <div style={{ fontSize: '10px', color: '#94a3b8' }}>{doc.document_type || 'Personal document'} · Uploaded {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString('en-CA') : '—'}</div>
                                </div>
                              </div>
                              <a href={doc.file} target="_blank" rel="noopener noreferrer" style={{ fontSize: '11px', fontWeight: '800', color: 'var(--admin-accent)', textDecoration: 'none', flexShrink: 0 }}>View</a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Admin: Edit Student Profile */}
                    {role !== 'director' && (
                    <div style={{ marginTop: '32px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                        <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0 }}>EDIT STUDENT PROFILE</h3>
                        <button className="btn-ghost" style={{ fontSize: '11px', padding: '4px 10px' }} onClick={() => { setEditingProfile(p => !p); setProfileEdits({}); }}>
                          {editingProfile ? 'Cancel' : 'Edit'}
                        </button>
                      </div>
                      {editingProfile && studentProfile ? (
                        <div style={{ background: '#f8fafc', borderRadius: '10px', padding: '20px', border: '1px solid #e2e8f0' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
                            {[
                              { key: 'beneficiary_number', label: 'Beneficiary Number' },
                              { key: 'treaty_number', label: 'Treaty Number' },
                              { key: 'num_dependents', label: 'Number of Dependents' },
                              { key: 'financial_assistance_status', label: 'Financial Assistance Status' },
                              { key: 'institution_name', label: 'Institution Name' },
                              { key: 'enrollment_status', label: 'Enrollment Status' },
                            ].map(({ key, label }) => {
                              const app = detailApp || applications.find((a: any) => String(a.id) === String(selectedAppId));
                              const sd = app?.student_details || {};
                              const currentVal = profileEdits[key] !== undefined ? profileEdits[key] : (sd[key] ?? '');
                              return (
                                <div key={key}>
                                  <label style={{ fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>{label}</label>
                                  <input
                                    className="admin-input"
                                    style={{ fontSize: '13px' }}
                                    value={currentVal}
                                    onChange={e => setProfileEdits(prev => ({ ...prev, [key]: e.target.value }))}
                                  />
                                </div>
                              );
                            })}
                          </div>
                          <button
                            className="btn-primary"
                            style={{ fontSize: '12px', padding: '8px 20px' }}
                            onClick={async () => {
                              if (!studentProfile?.id || Object.keys(profileEdits).length === 0) return;
                              try {
                                await API.updateStudentProfile(studentProfile.id, profileEdits);
                                setEditingProfile(false);
                                setProfileEdits({});
                                // Re-fetch detail to refresh student_details
                                const refreshed = await API.getSubmission(Number(selectedAppId));
                                setDetailApp(refreshed);
                              } catch (err: any) {
                                alert(err?.message || 'Failed to save profile changes.');
                              }
                            }}
                          >
                            Save Profile Changes
                          </button>
                        </div>
                      ) : !editingProfile && studentProfile ? (
                        <div style={{ fontSize: '12px', color: '#64748b', padding: '12px 16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                          Click <strong>Edit</strong> to modify beneficiary number, dependents, financial status, institution info, and more.
                        </div>
                      ) : (
                        <div style={{ fontSize: '12px', color: '#94a3b8', fontStyle: 'italic' }}>Profile data not available.</div>
                      )}
                    </div>
                    )}

                    {/* AUTO FUNDING CALCULATION is the single source of truth — replaces
                        the prior read-only FUNDING BREAKDOWN duplicate. Admin can edit
                        rows live; director sees the persisted breakdown. */}

                    {role !== 'director' && (
                    <div style={{ marginTop: '32px' }}>
                      {/* Student-requested tuition callout */}
                      {(() => {
                        const app = detailApp || applications.find((a: any) => String(a.id) === String(selectedAppId));
                        const tuitionAnswer = (app?.answers || []).find((a: any) =>
                          (a.label || a.field_label || '').toLowerCase().includes('tuition amount')
                        );
                        const requestedTuition = tuitionAnswer?.answer_text;
                        if (!requestedTuition || requestedTuition === '0' || requestedTuition === '') return null;
                        return (
                          <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '12px 16px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <Ic.Info size={14} style={{ color: '#d97706', flexShrink: 0 }} />
                            <div style={{ fontSize: '12px', color: '#92400e' }}>
                              <strong>Student's requested tuition:</strong> ${parseFloat(requestedTuition).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} — compare to policy cap below.
                            </div>
                          </div>
                        );
                      })()}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
                        <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0 }}>AUTO FUNDING CALCULATION</h3>
                        {(selectedApp?.office_use_data?.funding_breakdown || []).length > 0 ? (
                          <span className="admin-badge breakdown-state-edited">ADMIN EDITED</span>
                        ) : (
                          <span className="admin-badge breakdown-state-default">POLICY DEFAULT</span>
                        )}
                        <button
                          onClick={addBreakdownRow}
                          className="btn-ghost"
                          style={{ marginLeft: 'auto' }}
                        >+ Add Row</button>
                      </div>
                      <div className="admin-table-wrap">
                        <table className="admin-table table-dense">
                          <thead>
                            <tr>
                              <th style={{ width: '28%' }}>Component</th>
                              <th style={{ width: '10%' }}>Stream</th>
                              <th>Policy Rule / Note</th>
                              <th style={{ width: '140px', textAlign: 'right' }}>Amount ($)</th>
                              <th style={{ width: '48px' }} aria-label="Actions"></th>
                            </tr>
                          </thead>
                          <tbody>
                            {breakdownRows.length === 0 && (
                              <tr>
                                <td colSpan={5} style={{ fontSize: '12px', color: '#64748b', textAlign: 'center', padding: '28px 20px', fontStyle: 'italic' }}>
                                  {!policySettings
                                    ? 'Loading policy settings…'
                                    : autoSuggested?.ineligible
                                      ? `Auto-funding not applicable — ${autoSuggested.reason || 'student not eligible for this stream.'}`
                                      : 'No funding components yet. Click + Add Row to add one.'}
                                </td>
                              </tr>
                            )}
                            {breakdownRows.map((row) => {
                              const streamLabel = row.stream || autoSuggested?.stream || selectedApp?.student_details?.primary_stream || '—';
                              return (
                                <tr key={row.id}>
                                  <td>
                                    <input
                                      type="text"
                                      className="admin-input table-cell-input"
                                      value={row.label}
                                      onChange={e => updateBreakdownRow(row.id, { label: e.target.value })}
                                      placeholder="Component name"
                                    />
                                  </td>
                                  <td>
                                    <span className="admin-badge breakdown-stream-badge">
                                      {streamLabel}
                                    </span>
                                  </td>
                                  <td>
                                    <input
                                      type="text"
                                      className="admin-input table-cell-input"
                                      value={row.note || ''}
                                      onChange={e => updateBreakdownRow(row.id, { note: e.target.value })}
                                      placeholder="Optional note or rule reference"
                                      style={{ color: '#64748b' }}
                                    />
                                  </td>
                                  <td style={{ textAlign: 'right' }}>
                                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                      <span style={{ color: '#94a3b8', fontWeight: 700 }}>$</span>
                                      <input
                                        type="number"
                                        step="0.01"
                                        min="0"
                                        className="admin-input table-cell-input"
                                        value={row.amount}
                                        onChange={e => updateBreakdownRow(row.id, { amount: parseFloat(e.target.value) || 0 })}
                                        style={{ width: '100px', textAlign: 'right', fontWeight: 700, color: '#1e293b' }}
                                      />
                                    </div>
                                  </td>
                                  <td style={{ textAlign: 'center' }}>
                                    <button
                                      onClick={() => deleteBreakdownRow(row.id)}
                                      aria-label={`Delete ${row.label}`}
                                      title="Delete row"
                                      className="breakdown-row-delete"
                                    >×</button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                          <tfoot>
                            <tr>
                              <td colSpan={3} style={{ padding: '14px 20px' }}>
                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                                  <button
                                    className="btn-ghost"
                                    disabled={isSavingBreakdown || breakdownRows.length === 0}
                                    onClick={() => saveBreakdown(false)}
                                    style={{ fontSize: '11px' }}
                                  >{isSavingBreakdown ? 'Saving…' : 'Save breakdown'}</button>
                                  <button
                                    className="btn-primary"
                                    disabled={isSavingBreakdown || breakdownRows.length === 0}
                                    onClick={() => saveBreakdown(true)}
                                    style={{ fontSize: '11px', padding: '6px 14px' }}
                                  >Save &amp; apply total →</button>
                                </div>
                              </td>
                              <td style={{ textAlign: 'right', fontWeight: 800, fontSize: '15px', color: '#1e293b' }}>
                                ${breakdownTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                              <td></td>
                            </tr>
                            <tr>
                              <td colSpan={3} style={{ padding: '6px 20px 14px', fontSize: '11px', color: '#64748b' }}>
                                Currently applied amount on this application
                              </td>
                              <td style={{ textAlign: 'right', padding: '6px 20px 14px' }}>
                                <span className="admin-badge" style={{ background: '#d1fae5', color: '#065f46', fontSize: '11px' }}>
                                  ${(selectedApp?.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </span>
                              </td>
                              <td></td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>
                    )}

                  </div>
                </div>

                {/* Right: Sidebar Actions & Logs */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  {/* Banking Details — Director only (Task 2.7) */}
                  {renderBankingDetails()}

                  {/* Duplicate confirmed warning banner (Task 4.6) */}
                  {duplicateStatus?.is_confirmed && (
                    <div style={{ background: '#fef2f2', border: '2px solid #ef4444', borderRadius: '10px', padding: '16px' }}>
                      <div style={{ fontSize: '13px', fontWeight: '800', color: '#b91c1c', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}><Ic.Ban size={13} /> PAYMENT BLOCKED</div>
                      <div style={{ fontSize: '12px', color: '#991b1b' }}>This application is confirmed as a duplicate. Approval is disabled until resolved.</div>
                    </div>
                  )}

                  <div className="admin-chart-card">
                    {renderAuditTrail()}
                  </div>

                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#64748b', margin: 0 }}>STAFF NOTES (INTERNAL ONLY)</h3>
                      {(detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))?.notes?.length > 0 && (
                        <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}>
                          {(detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))!.notes.length} NOTE{(detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))!.notes.length !== 1 ? 'S' : ''}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {/* Notes list */}
                      <div className="staff-notes-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto', paddingRight: '4px' }}>
                        {isDetailLoading ? (
                          [0, 1].map(i => (
                            <div key={i} style={{ background: '#fcfaf8', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e5d5c0' }}>
                              <span className="skeleton skeleton-line" style={{ width: '90%' }} aria-hidden>·</span>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px' }}>
                                <span className="skeleton skeleton-line-xs" style={{ width: '30%' }} aria-hidden>·</span>
                                <span className="skeleton skeleton-line-xs" style={{ width: '25%' }} aria-hidden>·</span>
                              </div>
                            </div>
                          ))
                        ) : (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))?.notes?.length > 0 ? (
                          (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))!.notes.map((note: any) => (
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
                          <Ic.AlertTriangle size={14} style={{ flexShrink: 0 }} />
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

                      {/* Add note input — SSW only; director sees notes list as read-only context */}
                      {role !== 'director' && (
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
                      )}
                    </div>
                  </div>

                  {role !== 'director' && (
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
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Policy Settings View */}
          {currentView === 'policy' && (() => {
            // Map tab → which sections it edits. Used to decide what `Save changes` writes.
            const tabSections: Record<string, string[]> = {
              tuition:      ['psssp_tuition', 'ucepp_tuition', 'dggr_tuition', 'dggr_extra_tuition'],
              living:       ['psssp_living', 'ucepp_living', 'dggr_living'],
              travel:       ['psssp_travel', 'psssp_graduation_travel'],
              awards:       ['dggr_grad_bursary', 'dggr_academic_scholarship', 'dggr_practicum_award', 'dggr_hardship'],
              deadlines:    ['application_deadlines', 'payment_schedule'],
              eligibility:  ['eligibility_rules', 'misconduct_rules'],
              history:      [],
            };
            const tabs = [
              { key: 'tuition',     label: 'Tuition Bursaries' },
              { key: 'living',      label: 'Living Allowances' },
              { key: 'travel',      label: 'Travel Bursaries' },
              { key: 'awards',      label: 'One-Time Awards' },
              { key: 'deadlines',   label: 'Deadlines & Payment' },
              { key: 'eligibility', label: 'Eligibility Rules' },
              { key: 'history',     label: 'Change History' },
            ];

            const currentSections = tabSections[policyTab] || [];
            const tabHasDirty = currentSections.some(s => isDirty[s]);
            const lastEffective = latestUpdatedAt(currentSections);
            const isLoaded = Object.keys(policySettings).length > 0;

            // ── Compact, reusable inputs that match the screenshot styling ──
            // Strip trailing zeros so DecimalField values like "30.00" display as "30",
            // "30.50" as "30.5", and "30.25" as "30.25".
            const cleanNumeric = (v: any): string => {
              if (v === null || v === undefined || v === '') return '';
              const n = parseFloat(String(v));
              if (!Number.isFinite(n)) return String(v);
              return String(n);
            };
            const NumberInput: React.FC<{ value: any; onChange: (v: string) => void; suffix?: string; width?: number; placeholder?: string }> = ({ value, onChange, suffix, width = 110, placeholder }) => (
              <div className="policy-input-wrap" style={{ maxWidth: width }}>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  className="policy-input"
                  value={cleanNumeric(value)}
                  placeholder={placeholder}
                  onChange={e => onChange(e.target.value)}
                />
                {suffix && <span className="policy-input-suffix">{suffix}</span>}
              </div>
            );

            const SectionBadge: React.FC<{ tone: 'pssp' | 'ucepp' | 'dggr' | 'neutral'; children: React.ReactNode }> = ({ tone, children }) => (
              <span className={`policy-sec-badge tone-${tone}`}>{children}</span>
            );

            const InfoBar: React.FC<{ children: React.ReactNode }> = ({ children }) => (
              <div className="policy-info-bar">{children}</div>
            );

            const TableHeader: React.FC<{ title: string; tone?: 'pssp' | 'ucepp' | 'dggr' | 'neutral'; chip?: string }> = ({ title, tone = 'neutral', chip }) => (
              <div className="policy-table-header">
                <h4 className="policy-table-title">{title}</h4>
                {chip && <SectionBadge tone={tone}>{chip}</SectionBadge>}
              </div>
            );

            // ── Field renderers ──
            const renderEditableNumber = (section: string, fieldKey: string, width?: number) => {
              const f = policyField(section, fieldKey);
              if (!f) return <span className="policy-input-missing">—</span>;
              return (
                <NumberInput
                  value={f.value}
                  onChange={(v) => updatePolicyField(section, fieldKey, { value: v })}
                  suffix={f.unit === '$' ? '$' : (f.unit || '')}
                  width={width}
                />
              );
            };

            // Two-column row: same fieldKey across two streams (used in living/travel tables).
            // Not used directly — kept inline below for clarity.

            // Tab icon map. Pulled from Icons.tsx — keep tab keys in sync with `tabs` array above.
            const TAB_ICONS: Record<string, React.ReactNode> = {
              tuition:     <Ic.GraduationCap size={16} />,
              living:      <Ic.Home size={16} />,
              travel:      <Ic.MapPin size={16} />,
              awards:      <Ic.Star size={16} />,
              deadlines:   <Ic.Clock size={16} />,
              eligibility: <Ic.Scale size={16} />,
              history:     <Ic.Clipboard size={16} />,
            };
            const activeTabLabel = tabs.find(t => t.key === policyTab)?.label || '';
            const totalDirtyCount = Object.values(isDirty).filter(Boolean).length;

            return (
              <div className="fade-in policy-page-v2">
                {/* ── Slim toolbar (replaces old banner) ── */}
                <div className="policy-toolbar">
                  <div className="policy-toolbar-left">
                    <span className="policy-toolbar-icon"><Ic.FileEdit size={18} /></span>
                    <div>
                      <h2 className="policy-toolbar-title">Policy Settings</h2>
                      <p className="policy-toolbar-sub">Configure funding amounts, deadlines, and eligibility rules.</p>
                    </div>
                  </div>
                  <div className="policy-toolbar-right">
                    <span className="policy-chip policy-chip-version">
                      <Ic.Clock size={12} /> Last update: <strong>{lastEffective || 'never'}</strong>
                    </span>
                    {totalDirtyCount > 0 && (
                      <span className="policy-chip policy-chip-dirty">
                        <Ic.AlertTriangle size={12} /> {totalDirtyCount} unsaved
                      </span>
                    )}
                    <span className="policy-chip policy-chip-access">
                      <Ic.Lock size={12} /> Admin only
                    </span>
                  </div>
                </div>

                {/* ── Two-pane layout: rail nav (left) + content (right) ── */}
                <div className="policy-shell">
                  <nav className="policy-rail" aria-label="Policy sections">
                    {tabs.map(t => {
                      const isDirtyTab = tabSections[t.key]?.some(s => isDirty[s]);
                      return (
                        <button
                          key={t.key}
                          className={`policy-rail-item ${policyTab === t.key ? 'is-active' : ''} ${isDirtyTab ? 'is-dirty' : ''}`}
                          onClick={() => setPolicyTab(t.key)}
                        >
                          <span className="policy-rail-icon">{TAB_ICONS[t.key]}</span>
                          <span className="policy-rail-label">{t.label}</span>
                          {isDirtyTab && <span className="policy-rail-dot" aria-hidden />}
                        </button>
                      );
                    })}
                  </nav>

                  <div className="policy-pane">
                    {/* Pane header */}
                    <div className="policy-pane-head">
                      <span className="policy-pane-icon">{TAB_ICONS[policyTab]}</span>
                      <h3 className="policy-pane-title">{activeTabLabel}</h3>
                    </div>

                    {/* Tab content */}
                    <div className="policy-pane-body">
                    {!isLoaded ? (
                      <div className="policy-loading">Loading policy data…</div>
                    ) : policyTab === 'tuition' ? (
                      <>
                        <InfoBar>
                          Tuition bursary amounts are paid per semester. Amounts can be edited with an effective date — changes apply to applications submitted from that date onward. All students applying for the same semester receive the same rates.
                        </InfoBar>

                        <TableHeader title="Tuition Bursaries — per semester" chip="C-DFN PSSSP & DGGR" tone="pssp" />
                        <table className="policy-table">
                          <thead>
                            <tr><th>Stream</th><th>Description</th><th>Max amount ($)</th><th>Notes / rule</th></tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td><SectionBadge tone="pssp">C-DFN PSSSP</SectionBadge></td>
                              <td>Tuition Bursary</td>
                              <td>{renderEditableNumber('psssp_tuition', 'max_per_semester')}</td>
                              <td className="policy-cell-note">Actual tuition, books &amp; fees confirmed by institution — whichever is lower. Not available if student receives SFA.</td>
                            </tr>
                            <tr>
                              <td><SectionBadge tone="ucepp">C-DFN UCEPP</SectionBadge></td>
                              <td>Tuition Bursary (Upgrading)</td>
                              <td>{renderEditableNumber('ucepp_tuition', 'max_per_semester')}</td>
                              <td className="policy-cell-note">Actual cost — whichever is lower. Not available if student receives SFA.</td>
                            </tr>
                            <tr>
                              <td><SectionBadge tone="dggr">DGGR</SectionBadge></td>
                              <td>Tuition Top-Up — Full-Time</td>
                              <td>{renderEditableNumber('dggr_tuition', 'fulltime_per_semester')}</td>
                              <td className="policy-cell-note">Fixed rate. Not affected by SFA.</td>
                            </tr>
                            <tr>
                              <td><SectionBadge tone="dggr">DGGR</SectionBadge></td>
                              <td>Tuition Top-Up — Part-Time</td>
                              <td>{renderEditableNumber('dggr_tuition', 'parttime_per_semester')}</td>
                              <td className="policy-cell-note">Fixed rate. Not affected by SFA.</td>
                            </tr>
                          </tbody>
                        </table>

                        <TableHeader title="DGGR Extra Tuition Bursary" chip="DGGR only" tone="dggr" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Parameter</th><th>Value</th><th>Notes</th></tr></thead>
                          <tbody>
                            <tr>
                              <td>Rate (% of tuition)</td>
                              <td>{renderEditableNumber('dggr_extra_tuition', 'max_percent_covered')}</td>
                              <td className="policy-cell-note">Only when tuition exceeds the per-semester threshold below.</td>
                            </tr>
                            <tr>
                              <td>Per-semester cap ($)</td>
                              <td>{renderEditableNumber('dggr_extra_tuition', 'max_per_semester')}</td>
                              <td className="policy-cell-note">Inclusive of regular DGGR tuition bursary — not additive.</td>
                            </tr>
                            <tr>
                              <td>Annual cap ($)</td>
                              <td>{renderEditableNumber('dggr_extra_tuition', 'max_per_year')}</td>
                              <td className="policy-cell-note">Per student per year.</td>
                            </tr>
                            <tr>
                              <td>Total annual pool ($)</td>
                              <td>{renderEditableNumber('dggr_extra_tuition', 'annual_cap_all_students')}</td>
                              <td className="policy-cell-note">Combined pool for all students. Director manages allocation.</td>
                            </tr>
                            <tr>
                              <td>Trigger threshold — per semester ($)</td>
                              <td>{renderEditableNumber('dggr_extra_tuition', 'threshold_per_semester')}</td>
                              <td className="policy-cell-note">Extra bursary only applies when tuition exceeds this amount.</td>
                            </tr>
                            <tr>
                              <td>Trigger threshold — per year ($)</td>
                              <td>{renderEditableNumber('dggr_extra_tuition', 'threshold_per_year')}</td>
                              <td className="policy-cell-note">Annual tuition threshold for eligibility.</td>
                            </tr>
                          </tbody>
                        </table>
                      </>
                    ) : policyTab === 'living' ? (
                      <>
                        <InfoBar>
                          Monthly living allowances are paid on the 1st of each month the student is enrolled. Full-time vs. part-time is determined by the institution's Form B, not the student's self-report. A documented disability allows full-time classification at a lower course load.
                        </InfoBar>

                        {[
                          { section: 'psssp_living', title: 'C-DFN PSSSP — Monthly Living Allowances', tone: 'pssp', chip: 'C-DFN PSSSP', note: 'Not available to students receiving SFA.' },
                          { section: 'ucepp_living', title: 'C-DFN UCEPP — Monthly Living Allowances', tone: 'ucepp', chip: 'C-DFN UCEPP', note: 'Not available to students receiving SFA.' },
                          { section: 'dggr_living',  title: 'DGGR — Monthly Living Allowances',        tone: 'dggr',  chip: 'DGGR',        note: 'Not affected by SFA status.' },
                        ].map(grp => (
                          <React.Fragment key={grp.section}>
                            <TableHeader title={grp.title} chip={grp.chip} tone={grp.tone as any} />
                            <table className="policy-table">
                              <thead>
                                <tr><th>Enrollment</th><th>No dependents ($/mo)</th><th>With dependents ($/mo)</th><th>Notes</th></tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td><strong>Full-Time</strong></td>
                                  <td>{renderEditableNumber(grp.section, 'fulltime_no_dependents')}</td>
                                  <td>{renderEditableNumber(grp.section, 'fulltime_with_dependents')}</td>
                                  <td className="policy-cell-note">{grp.note}</td>
                                </tr>
                                <tr>
                                  <td><strong>Part-Time</strong></td>
                                  <td>{renderEditableNumber(grp.section, 'parttime_no_dependents')}</td>
                                  <td>{renderEditableNumber(grp.section, 'parttime_with_dependents')}</td>
                                  <td className="policy-cell-note">{grp.note}</td>
                                </tr>
                              </tbody>
                            </table>
                          </React.Fragment>
                        ))}
                      </>
                    ) : policyTab === 'travel' ? (
                      <>
                        <InfoBar>
                          Travel bursaries are reimbursement-only — no advance payments. Students must submit receipts within 1 month of travel completion. Students studying &gt; 200 km from home and not receiving SFA are eligible for the Travel Bursary.
                        </InfoBar>

                        <TableHeader title="C-DFN PSSSP Travel Bursary" chip="C-DFN PSSSP only" tone="pssp" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Parameter</th><th>No dependents ($)</th><th>With dependents ($)</th><th>Notes</th></tr></thead>
                          <tbody>
                            <tr>
                              <td>Max per trip</td>
                              <td>{renderEditableNumber('psssp_travel', 'max_per_trip_no_dependents')}</td>
                              <td>{renderEditableNumber('psssp_travel', 'max_per_trip_with_dependents')}</td>
                              <td className="policy-cell-note">Reimbursement only. First-come, first-served.</td>
                            </tr>
                            <tr>
                              <td>Max trips per year</td>
                              <td colSpan={2}>{renderEditableNumber('psssp_travel', 'max_trips_per_year')}</td>
                              <td className="policy-cell-note">Per student per year.</td>
                            </tr>
                            <tr>
                              <td>Distance threshold (km)</td>
                              <td colSpan={2}>{renderEditableNumber('psssp_travel', 'min_distance_km')}</td>
                              <td className="policy-cell-note">Student must be studying more than this distance from home.</td>
                            </tr>
                            <tr>
                              <td>Claim deadline (days after travel)</td>
                              <td colSpan={2}>{renderEditableNumber('system_config', 'travel_claim_days')}</td>
                              <td className="policy-cell-note">Within 1 month of travel completion.</td>
                            </tr>
                          </tbody>
                        </table>

                        <TableHeader title="C-DFN PSSSP Graduation Travel Bursary" chip="C-DFN PSSSP only" tone="pssp" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Parameter</th><th>Value</th><th>Notes</th></tr></thead>
                          <tbody>
                            <tr>
                              <td>Maximum amount ($)</td>
                              <td>{renderEditableNumber('psssp_graduation_travel', 'max_total')}</td>
                              <td className="policy-cell-note">One-time. Covers airfare for 2 immediate family members + 3 nights' accommodation.</td>
                            </tr>
                            <tr>
                              <td>Family members covered</td>
                              <td>{renderEditableNumber('psssp_graduation_travel', 'max_family_members')}</td>
                              <td className="policy-cell-note">Immediate family members only.</td>
                            </tr>
                            <tr>
                              <td>Accommodation max / night ($)</td>
                              <td>{renderEditableNumber('psssp_graduation_travel', 'max_hotel_per_night')}</td>
                              <td className="policy-cell-note">Reimbursement only.</td>
                            </tr>
                            <tr>
                              <td>Accommodation nights covered</td>
                              <td>{renderEditableNumber('psssp_graduation_travel', 'max_hotel_nights')}</td>
                              <td className="policy-cell-note">Reimbursement only.</td>
                            </tr>
                          </tbody>
                        </table>
                      </>
                    ) : policyTab === 'awards' ? (
                      <>
                        <InfoBar>
                          All one-time DGGR awards are paid within 15 business days of Director approval. Students must apply within the rolling window — no semester deadlines apply except where noted.
                        </InfoBar>

                        <TableHeader title="Graduation Bursary — amount by credential" chip="DGGR" tone="dggr" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Credential type</th><th>Amount ($)</th><th>Claim window</th></tr></thead>
                          <tbody>
                            {[
                              { key: 'high_school_diploma',  label: 'High School Diploma' },
                              { key: 'certificate',          label: 'Certificate' },
                              { key: 'trades_certificate',   label: 'Trades Certificate of Qualification' },
                              { key: 'trades_journeyperson', label: 'Trades Journeyperson / Professional Pilot / Red Seal' },
                              { key: 'diploma',              label: 'Diploma' },
                              { key: 'bachelors_degree',     label: "Bachelor's Degree (incl. BEd)" },
                              { key: 'masters_degree',       label: 'Master\'s / PhD / JD / MD / DDS' },
                            ].map(c => (
                              <tr key={c.key}>
                                <td>{c.label}</td>
                                <td>{renderEditableNumber('dggr_grad_bursary', c.key)}</td>
                                <td className="policy-cell-note">Within 6 months of program completion.</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                        <TableHeader title="Academic Achievement Scholarship" chip="DGGR" tone="dggr" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>GPA threshold</th><th>Amount ($)</th><th>Claim window</th></tr></thead>
                          <tbody>
                            <tr>
                              <td>GPA ≥ {renderEditableNumber('dggr_academic_scholarship', 'high_threshold_percent', 80)} %</td>
                              <td>{renderEditableNumber('dggr_academic_scholarship', 'high_achievement_award')}</td>
                              <td className="policy-cell-note">Within 6 months of semester end.</td>
                            </tr>
                            <tr>
                              <td>GPA {renderEditableNumber('dggr_academic_scholarship', 'mid_threshold_lower', 80)} – {renderEditableNumber('dggr_academic_scholarship', 'mid_threshold_upper', 80)} %</td>
                              <td>{renderEditableNumber('dggr_academic_scholarship', 'mid_achievement_award')}</td>
                              <td className="policy-cell-note">Within 6 months of semester end.</td>
                            </tr>
                          </tbody>
                        </table>

                        <TableHeader title="Summer / Practicum Award & Hardship Bursary" chip="DGGR" tone="dggr" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Award</th><th>Amount ($)</th><th>Trigger / deadline</th></tr></thead>
                          <tbody>
                            <tr>
                              <td>Summer / Practicum Award</td>
                              <td>{renderEditableNumber('dggr_practicum_award', 'award_amount')}</td>
                              <td className="policy-cell-note">Per placement. Employer confirms. Within 6 months of placement completion in Délı̨nę.</td>
                            </tr>
                            <tr>
                              <td>Hardship Bursary (max)</td>
                              <td>{renderEditableNumber('dggr_hardship', 'max_per_student')}</td>
                              <td className="policy-cell-note">Director decides amount. No deadline. Unexpected financial hardship while enrolled.</td>
                            </tr>
                          </tbody>
                        </table>
                      </>
                    ) : policyTab === 'deadlines' ? (
                      <>
                        <InfoBar>
                          Application deadlines determine which semester rates apply. If the Director approves a late application, all missed monthly payments are back-paid from the semester start date. No advance or pre-payments permitted under any circumstances.
                        </InfoBar>

                        <TableHeader title="Application deadlines by semester" />
                        <table className="policy-table">
                          <thead><tr><th>Semester</th><th>Deadline</th><th>Streams</th></tr></thead>
                          <tbody>
                            {(['fall', 'winter', 'spring', 'summer'] as const).map(sem => {
                              const f = policyField('application_deadlines', `${sem}_deadline`);
                              if (!f) return null;
                              const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                              const month = Math.max(1, Math.min(12, Math.round(Number(f.value)) || 1));
                              const day = Math.max(1, Math.min(31, parseInt(f.unit) || 1));
                              return (
                                <tr key={sem}>
                                  <td style={{ textTransform: 'capitalize' }}><strong>{sem}</strong></td>
                                  <td>
                                    <div className="policy-date-pair">
                                      <select
                                        className="policy-input"
                                        value={String(month)}
                                        onChange={e => updatePolicyField('application_deadlines', `${sem}_deadline`, { value: e.target.value })}
                                      >
                                        {MONTHS.map((m, i) => <option key={i + 1} value={String(i + 1)}>{m}</option>)}
                                      </select>
                                      <input
                                        type="number"
                                        min="1" max="31"
                                        className="policy-input"
                                        value={day}
                                        style={{ width: '64px' }}
                                        onChange={e => {
                                          const d = Math.max(1, Math.min(31, parseInt(e.target.value) || 1));
                                          updatePolicyField('application_deadlines', `${sem}_deadline`, { unit: String(d) });
                                        }}
                                      />
                                    </div>
                                  </td>
                                  <td className="policy-cell-note">DGGR Tuition + Living, C-DFN PSSSP + UCEPP Tuition + Living</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>

                        <TableHeader title="Payment timing rules" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Payment type</th><th>Timing rule</th></tr></thead>
                          <tbody>
                            <tr>
                              <td><strong>Tuition</strong></td>
                              <td className="policy-cell-note">Within {renderEditableNumber('payment_schedule', 'tuition_payment_weeks_after_deadline', 90)} <span style={{ marginLeft: 6 }}>weeks of the application deadline for that semester.</span></td>
                            </tr>
                            <tr>
                              <td><strong>Monthly Living Allowance</strong></td>
                              <td className="policy-cell-note">On day {renderEditableNumber('payment_schedule', 'living_payment_day_of_month', 90)} <span style={{ marginLeft: 6 }}>of each month the student is enrolled.</span></td>
                            </tr>
                            <tr>
                              <td><strong>One-Time Awards (days)</strong></td>
                              <td className="policy-cell-note">{renderEditableNumber('payment_schedule', 'other_bursary_max_processing_days', 110)} <span style={{ marginLeft: 6 }}>business days after Director approval.</span></td>
                            </tr>
                            <tr>
                              <td><strong>Late Application Back-Pay</strong></td>
                              <td className="policy-cell-note">If Director approves a late application, all missed monthly payments are back-paid from the semester start date.</td>
                            </tr>
                            <tr>
                              <td><strong>C-DFN Travel Bursary claim window</strong></td>
                              <td className="policy-cell-note">Within {renderEditableNumber('system_config', 'travel_claim_days', 90)} <span style={{ marginLeft: 6 }}>days of travel completion. First-come, first-served.</span></td>
                            </tr>
                          </tbody>
                        </table>
                      </>
                    ) : policyTab === 'eligibility' ? (
                      <>
                        <InfoBar>
                          Eligibility rules are fixed by policy and cannot be changed without a formal policy update approved by the Director. Course-load thresholds below are editable so the system can correctly classify FT vs PT enrollment.
                        </InfoBar>

                        <TableHeader title="Stream eligibility" />
                        <table className="policy-table">
                          <thead><tr><th>Stream</th><th>Who qualifies</th><th>Key restrictions</th></tr></thead>
                          <tbody>
                            <tr>
                              <td><SectionBadge tone="pssp">C-DFN PSSSP</SectionBadge></td>
                              <td>Students with Indian Act Status affiliated with the Délı̨nę First Nation, in a non-upgrading post-secondary program.</td>
                              <td className="policy-cell-note">Not available to students receiving GNWT SFA or already receiving the same funding from another organization.</td>
                            </tr>
                            <tr>
                              <td><SectionBadge tone="ucepp">C-DFN UCEPP</SectionBadge></td>
                              <td>Same as PSSSP but for upgrading and university entrance preparation programs only.</td>
                              <td className="policy-cell-note">Same SFA and other-organization restrictions as PSSSP.</td>
                            </tr>
                            <tr>
                              <td><SectionBadge tone="dggr">DGGR</SectionBadge></td>
                              <td>Registered Délı̨nę Beneficiaries in any approved program.</td>
                              <td className="policy-cell-note">SFA status has no effect. Not available to students already receiving funding from another land-claim agreement.</td>
                            </tr>
                          </tbody>
                        </table>

                        <TableHeader title="Course-load thresholds (editable)" />
                        <table className="policy-table policy-table-kv">
                          <thead><tr><th>Parameter</th><th>Value</th><th>Notes</th></tr></thead>
                          <tbody>
                            <tr>
                              <td>Minimum program length (weeks)</td>
                              <td>{renderEditableNumber('eligibility_rules', 'min_program_weeks')}</td>
                              <td className="policy-cell-note">Programs shorter than this are not eligible for any funding stream.</td>
                            </tr>
                            <tr>
                              <td>Full-Time minimum course load (%)</td>
                              <td>{renderEditableNumber('eligibility_rules', 'fulltime_min_load_percent')}</td>
                              <td className="policy-cell-note">Students at or above this percent are classified Full-Time.</td>
                            </tr>
                            <tr>
                              <td>Full-Time min load with disability (%)</td>
                              <td>{renderEditableNumber('eligibility_rules', 'fulltime_min_load_disability')}</td>
                              <td className="policy-cell-note">Documented disability lowers the FT threshold.</td>
                            </tr>
                            <tr>
                              <td>Part-Time maximum course load (%)</td>
                              <td>{renderEditableNumber('eligibility_rules', 'parttime_max_load_percent')}</td>
                              <td className="policy-cell-note">Standard PT cap.</td>
                            </tr>
                            <tr>
                              <td>Part-Time max load with disability (%)</td>
                              <td>{renderEditableNumber('eligibility_rules', 'parttime_max_load_disability')}</td>
                              <td className="policy-cell-note">Documented disability lowers the PT cap.</td>
                            </tr>
                            <tr>
                              <td>Misconduct suspension (years)</td>
                              <td>{renderEditableNumber('misconduct_rules', 'suspension_misconduct_years')}</td>
                              <td className="policy-cell-note">Academic or financial misconduct triggers automatic suspension.</td>
                            </tr>
                            <tr>
                              <td>Overpayment suspension (years)</td>
                              <td>{renderEditableNumber('misconduct_rules', 'suspension_overpayment_years')}</td>
                              <td className="policy-cell-note">Failure to repay an overpayment triggers automatic suspension.</td>
                            </tr>
                          </tbody>
                        </table>

                        <TableHeader title="Stacking rules" />
                        <ul className="policy-rule-list">
                          <li><span className="policy-rule-tick is-yes">✓</span> <strong>C-DFN + DGGR stacking is permitted.</strong> A student can receive both C-DFN (PSSSP or UCEPP) and DGGR funding simultaneously if they qualify for both. DGGR supplements C-DFN — it does not replace it.</li>
                          <li><span className="policy-rule-tick is-no">✕</span> <strong>SFA blocks C-DFN.</strong> Students receiving GNWT Student Financial Assistance are not eligible for C-DFN tuition or living allowances (DGGR is unaffected).</li>
                          <li><span className="policy-rule-tick is-no">✕</span> <strong>Other land-claim agreement blocks DGGR.</strong> Students already receiving equivalent funding from another land-claim agreement are not eligible for DGGR bursaries.</li>
                          <li><span className="policy-rule-tick is-no">✕</span> <strong>Other organization blocks C-DFN.</strong> Students already receiving C-DFN-equivalent funding from another organization are not eligible for C-DFN streams through DGG.</li>
                        </ul>

                        <TableHeader title="Appeals process" />
                        <table className="policy-table">
                          <thead><tr><th>Step</th><th>Escalation path</th></tr></thead>
                          <tbody>
                            <tr><td><strong>Step 1</strong></td><td>Appeal to Director of Education.</td></tr>
                            <tr><td><strong>Step 2 — DGGR</strong></td><td>If unresolved, escalate to senior DGGR official.</td></tr>
                            <tr><td><strong>Step 2 — C-DFN</strong></td><td>If unresolved, escalate to CEO.</td></tr>
                            <tr><td><strong>Record keeping</strong></td><td>Full appeal history must be recorded in the system for every appeal at every step.</td></tr>
                          </tbody>
                        </table>
                      </>
                    ) : policyTab === 'history' ? (
                      <>
                        <InfoBar>
                          All policy changes are logged automatically with the user, timestamp, and previous value. Change records are immutable — they cannot be deleted. Each row also records the effective date.
                        </InfoBar>

                        <div className="policy-table-header" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <h4 className="policy-table-title">Policy change log</h4>
                          {isPolicyHistoryLoading && (
                            <span className="ui-loading-inline"><span className="ui-spinner ui-spinner-sm" /> Loading…</span>
                          )}
                          {!isPolicyHistoryLoading && policyHistory.length > 0 && (
                            <span className="admin-badge" style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '10px' }}>
                              {policyHistory.length} ENTR{policyHistory.length === 1 ? 'Y' : 'IES'}
                            </span>
                          )}
                        </div>
                        <table className="policy-table policy-table-history" aria-busy={isPolicyHistoryLoading}>
                          <thead><tr><th>Timestamp</th><th>User</th><th>Field changed</th><th>Old value</th><th>New value</th><th>Effective date</th></tr></thead>
                          <tbody>
                            {isPolicyHistoryLoading && policyHistory.length === 0 && (
                              [0, 1, 2, 3, 4, 5].map(i => (
                                <tr key={`skel-${i}`}>
                                  <td><span className="skeleton skeleton-line-sm" style={{ width: '80%' }} aria-hidden>·</span></td>
                                  <td><span className="skeleton skeleton-line" style={{ width: `${55 + (i * 11) % 30}%` }} aria-hidden>·</span></td>
                                  <td><span className="skeleton skeleton-line" style={{ width: `${60 + (i * 7) % 35}%` }} aria-hidden>·</span></td>
                                  <td><span className="skeleton skeleton-line-xs" style={{ width: '45%' }} aria-hidden>·</span></td>
                                  <td><span className="skeleton skeleton-line-xs" style={{ width: '45%' }} aria-hidden>·</span></td>
                                  <td><span className="skeleton skeleton-line-xs" style={{ width: '70%' }} aria-hidden>·</span></td>
                                </tr>
                              ))
                            )}
                            {!isPolicyHistoryLoading && policyHistory.length === 0 && (
                              <tr><td colSpan={6} className="policy-empty">No policy changes recorded yet.</td></tr>
                            )}
                            {policyHistory.map((h: any) => {
                              // Strip trailing zeros from numeric history values so "30.00" reads as "30"
                              const tidy = (s: any): string => {
                                if (s === null || s === undefined || s === '') return '—';
                                const str = String(s);
                                const n = parseFloat(str);
                                if (Number.isFinite(n) && /^-?\d+(\.\d+)?$/.test(str.trim())) return String(n);
                                return str;
                              };
                              return (
                                <tr key={h.id}>
                                  <td className="policy-cell-mono">{h.timestamp ? new Date(h.timestamp).toLocaleString('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                                  <td>{h.user_name || 'System'}</td>
                                  <td>{h.field_changed}</td>
                                  <td className="policy-cell-old">{tidy(h.old_value)}</td>
                                  <td className="policy-cell-new">{tidy(h.new_value)}</td>
                                  <td className="policy-cell-mono">{h.effective_date || '—'}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </>
                    ) : null}

                    {/* ── Custom fields panel — admin can add / edit / delete non-seeded rows ── */}
                    {policyTab !== 'history' && (() => {
                      const customs = customFieldsForTab(currentSections);
                      const draftMatchesTab = addFieldDraft && addFieldDraft.tab === policyTab;
                      return (
                        <div className="policy-custom-panel">
                          <div className="policy-custom-head">
                            <span className="policy-custom-label">Custom fields for this tab</span>
                            {!draftMatchesTab && (
                              <button
                                className="policy-add-btn"
                                onClick={() => setAddFieldDraft({
                                  tab: policyTab,
                                  section: currentSections[0] || '',
                                  label: '',
                                  value: '',
                                  unit: '',
                                })}
                              >
                                + Add field
                              </button>
                            )}
                          </div>

                          {customs.length === 0 && !draftMatchesTab && (
                            <p className="policy-custom-empty">No custom fields yet. Use "+ Add field" to define additional policy values for this tab.</p>
                          )}

                          {customs.length > 0 && (
                            <table className="policy-table policy-table-custom">
                              <thead>
                                <tr>
                                  <th>Section</th>
                                  <th>Label</th>
                                  <th>Value</th>
                                  <th>Unit</th>
                                  <th></th>
                                </tr>
                              </thead>
                              <tbody>
                                {customs.map(({ section, field }) => (
                                  <tr key={field.id}>
                                    <td><span className="policy-custom-section">{section}</span></td>
                                    <td>
                                      <input
                                        className="policy-input policy-input-inline"
                                        value={field.field_label}
                                        onChange={e => updatePolicyField(section, field.field_key, { field_label: e.target.value })}
                                      />
                                    </td>
                                    <td>
                                      <input
                                        type="number"
                                        step="0.01"
                                        min="0"
                                        className="policy-input policy-input-inline"
                                        style={{ maxWidth: 110 }}
                                        value={field.value ?? ''}
                                        onChange={e => updatePolicyField(section, field.field_key, { value: e.target.value })}
                                      />
                                    </td>
                                    <td>
                                      <input
                                        className="policy-input policy-input-inline"
                                        style={{ maxWidth: 80 }}
                                        placeholder="e.g. $, %, days"
                                        value={field.unit ?? ''}
                                        onChange={e => updatePolicyField(section, field.field_key, { unit: e.target.value })}
                                      />
                                    </td>
                                    <td>
                                      <button
                                        className="policy-delete-btn"
                                        title="Delete this field"
                                        onClick={() => deletePolicyField(field)}
                                      >
                                        ✕
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}

                          {draftMatchesTab && (
                            <div className="policy-add-form">
                              <div className="policy-add-form-title">New custom field</div>
                              <div className="policy-add-form-row">
                                {currentSections.length > 1 && (
                                  <div className="policy-add-form-group">
                                    <label className="policy-add-form-label">Section</label>
                                    <select
                                      className="policy-input"
                                      value={addFieldDraft!.section}
                                      onChange={e => setAddFieldDraft(d => d ? { ...d, section: e.target.value } : d)}
                                    >
                                      {currentSections.map(s => <option key={s} value={s}>{s}</option>)}
                                    </select>
                                  </div>
                                )}
                                <div className="policy-add-form-group" style={{ flex: 2 }}>
                                  <label className="policy-add-form-label">Label <span className="policy-add-form-req">*</span></label>
                                  <input
                                    className="policy-input"
                                    placeholder="e.g. Max book allowance"
                                    value={addFieldDraft!.label}
                                    onChange={e => setAddFieldDraft(d => d ? { ...d, label: e.target.value } : d)}
                                  />
                                </div>
                                <div className="policy-add-form-group">
                                  <label className="policy-add-form-label">Value</label>
                                  <input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    className="policy-input"
                                    style={{ maxWidth: 120 }}
                                    placeholder="0"
                                    value={addFieldDraft!.value}
                                    onChange={e => setAddFieldDraft(d => d ? { ...d, value: e.target.value } : d)}
                                  />
                                </div>
                                <div className="policy-add-form-group">
                                  <label className="policy-add-form-label">Unit</label>
                                  <input
                                    className="policy-input"
                                    style={{ maxWidth: 90 }}
                                    placeholder="e.g. $, %"
                                    value={addFieldDraft!.unit}
                                    onChange={e => setAddFieldDraft(d => d ? { ...d, unit: e.target.value } : d)}
                                  />
                                </div>
                              </div>
                              <div className="policy-add-form-actions">
                                <button className="btn-ghost" onClick={() => setAddFieldDraft(null)}>Cancel</button>
                                <button
                                  className="btn-primary"
                                  onClick={() => createPolicyField({
                                    section: addFieldDraft!.section || currentSections[0] || '',
                                    field_label: addFieldDraft!.label,
                                    value: addFieldDraft!.value,
                                    unit: addFieldDraft!.unit,
                                  })}
                                >
                                  Save field
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Sticky footer: effective date + save/reset for editable tabs */}
                    {policyTab !== 'history' && (
                      <div className="policy-footer">
                        <div className="policy-footer-info">
                          {lastEffective
                            ? <>Effective date: <strong>{lastEffective}</strong> · Changes apply to applications submitted on or after this date.</>
                            : <>No changes recorded for this section yet.</>}
                        </div>
                        <div className="policy-footer-actions">
                          <button
                            className="btn-ghost"
                            disabled={!tabHasDirty || isSavingPolicy}
                            onClick={() => {
                              if (window.confirm('Discard unsaved changes in this section?')) {
                                fetchPolicySettings();
                              }
                            }}
                          >Reset</button>
                          <button
                            className="btn-primary"
                            disabled={!tabHasDirty || isSavingPolicy}
                            onClick={() => savePolicySections(currentSections)}
                            style={{ padding: '8px 18px', display: 'inline-flex', alignItems: 'center', gap: '8px', minWidth: '120px', justifyContent: 'center' }}
                          >
                            {isSavingPolicy ? (
                              <>
                                <span className="ui-spinner ui-spinner-sm ui-spinner-on-dark" />
                                Saving…
                              </>
                            ) : 'Save changes'}
                          </button>
                        </div>
                      </div>
                    )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {currentView === 'reports' && (() => {
            // Single, consistent source of truth. reportStats reflects the active filter
            // selection (server-computed); backendStats is the unfiltered baseline.
            const rs = reportStats || backendStats || {};
            const sbs = rs.submissions_by_status || {};
            const ss  = rs.stream_split || {};
            const total = rs.total_submissions ?? 0;
            const cntAccepted = sbs.accepted ?? 0;
            const approvalRate = rs.approval_rate ?? (total > 0 ? +(cntAccepted / total * 100).toFixed(1) : 0);
            const hasFilters = reportDateFrom || reportDateTo || reportStatusFilter !== 'all' || reportFundingType !== 'all';
            const fmtMoney = (v: number): string => {
              if (!v) return '$0';
              if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
              if (v >= 10_000)    return `$${(v / 1_000).toFixed(0)}k`;
              if (v >= 1_000)     return `$${(v / 1_000).toFixed(1)}k`;
              return `$${Math.round(v).toLocaleString()}`;
            };
            const initials = (name: string) => {
              const parts = (name || '').trim().split(/\s+/).filter(Boolean);
              if (parts.length === 0) return '?';
              if (parts.length === 1) return parts[0][0]?.toUpperCase() || '?';
              return ((parts[0][0] || '') + (parts[parts.length - 1][0] || '')).toUpperCase();
            };

            // Pipeline rows — semantic colors only where it carries meaning
            const pipelineRows = [
              { label: 'Awaiting Staff Review',  key: 'pending',   color: '#d97706', icon: <Ic.Clock size={14} /> },
              { label: 'Reviewed by SSW',        key: 'reviewed',  color: '#475569', icon: <Ic.Search size={14} /> },
              { label: 'Forwarded to Director',  key: 'forwarded', color: '#475569', icon: <Ic.Send size={14} /> },
              { label: 'Approved & Funded',      key: 'accepted',  color: '#16a34a', icon: <Ic.CheckCircle size={14} /> },
              { label: 'Not Approved',           key: 'rejected',  color: '#dc2626', icon: <Ic.XCircle size={14} /> },
            ];

            // Stream split — brand trio (primary navy / accent gold / neutral slate)
            const streamRows = [
              { label: 'C-DFN PSSSP',     sublabel: 'Post-Secondary Student Support', key: 'pssp',  color: '#0f172a' },
              { label: 'DGGR Bursaries',  sublabel: "Délı̨nę Got'ı̨nę Grants",         key: 'dggr',  color: '#e5a662' },
              { label: 'UCEPP Upgrading', sublabel: 'Upgrading & Continuing Ed.',     key: 'ucepp', color: '#94a3b8' },
            ];

            // Recent submissions — prefer server-filtered list, fall back to local apps
            const recent: any[] = (rs.recent_submissions && rs.recent_submissions.length > 0)
              ? rs.recent_submissions
              : applications.slice(0, 20);

            return (
            <div className="fade-in reports-page">
              {/* ── Hero header ── */}
              <div className="reports-hero">
                <div className="reports-hero-inner">
                  <div>
                    <h2 className="reports-hero-title">
                      <span className="reports-hero-icon"><Ic.BarChart2 size={22} /></span>
                      Reports &amp; Analytics
                    </h2>
                    <p className="reports-hero-sub">
                      {hasFilters
                        ? `Filtered view · ${total.toLocaleString()} submission${total === 1 ? '' : 's'} match the current filters.`
                        : `Real-time funding overview · ${total.toLocaleString()} submission${total === 1 ? '' : 's'} across all programs.`}
                    </p>
                  </div>
                  <div className="reports-hero-actions">
                    <button onClick={handleReportPDFExport} className="reports-hero-btn">
                      <Ic.FileText size={14} /> Export PDF
                    </button>
                    <button onClick={handleReportCSVExport} disabled={isExporting} className="reports-hero-btn">
                      <Ic.Download size={14} /> {isExporting ? 'Exporting…' : 'Download CSV'}
                    </button>
                    <button onClick={handleDispatchFinanceReport} disabled={isDispatching} className="reports-hero-btn is-primary">
                      <Ic.Mail size={14} /> {isDispatching ? 'Sending…' : 'Email to Finance'}
                    </button>
                  </div>
                </div>

                {/* KPI strip — hero-colored cards on dark */}
                <div className="reports-hero-kpis">
                  <div className="reports-hero-kpi">
                    <div className="reports-hero-kpi-icon"><Ic.Users size={18} /></div>
                    <div>
                      <div className="reports-hero-kpi-value">{(rs.total_students ?? 0).toLocaleString()}</div>
                      <div className="reports-hero-kpi-label">Unique Students</div>
                    </div>
                  </div>
                  <div className="reports-hero-kpi reports-hero-kpi-accent">
                    <div className="reports-hero-kpi-icon"><Ic.DollarSign size={18} /></div>
                    <div>
                      <div className="reports-hero-kpi-value">{fmtMoney(rs.total_funding_approved ?? 0)}</div>
                      <div className="reports-hero-kpi-label">Funding Approved</div>
                    </div>
                  </div>
                  <div className="reports-hero-kpi">
                    <div className="reports-hero-kpi-icon"><Ic.Clipboard size={18} /></div>
                    <div>
                      <div className="reports-hero-kpi-value">{total.toLocaleString()}</div>
                      <div className="reports-hero-kpi-label">Applications</div>
                    </div>
                  </div>
                  <div className="reports-hero-kpi">
                    <div className="reports-hero-kpi-icon"><Ic.CheckCircle size={18} /></div>
                    <div>
                      <div className="reports-hero-kpi-value">{approvalRate}%</div>
                      <div className="reports-hero-kpi-label">Approval Rate</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="reports-body">
                {/* ── Filter bar ── */}
                <div className="reports-filter-bar">
                  <div className="reports-filter-group reports-filter-group-flex">
                    <label className="reports-filter-label">Funding Program</label>
                    <div className="reports-filter-segs">
                      {[
                        { key: 'all',   label: 'All Programs' },
                        { key: 'cdfn',  label: 'C-DFN / PSSSP' },
                        { key: 'dggr',  label: 'DGGR' },
                        { key: 'ucepp', label: 'UCEPP' },
                      ].map(t => (
                        <button
                          key={t.key}
                          onClick={() => setReportFundingType(t.key)}
                          className={`reports-seg ${reportFundingType === t.key ? 'is-active' : ''}`}
                        >{t.label}</button>
                      ))}
                    </div>
                  </div>
                  <div className="reports-filter-group">
                    <label className="reports-filter-label">Date Range</label>
                    <div className="reports-filter-dates">
                      <input type="date" className="apps-search-input" style={{ width: '140px' }} value={reportDateFrom} onChange={e => setReportDateFrom(e.target.value)} />
                      <span className="reports-filter-sep">to</span>
                      <input type="date" className="apps-search-input" style={{ width: '140px' }} value={reportDateTo} onChange={e => setReportDateTo(e.target.value)} />
                    </div>
                  </div>
                  <div className="reports-filter-group">
                    <label className="reports-filter-label">Application Status</label>
                    <select className="apps-select" style={{ minWidth: '180px' }} value={reportStatusFilter} onChange={e => setReportStatusFilter(e.target.value)}>
                      <option value="all">All Statuses</option>
                      <option value="pending">Awaiting Review</option>
                      <option value="reviewed">Reviewed by SSW</option>
                      <option value="forwarded">Forwarded to Director</option>
                      <option value="accepted">Approved &amp; Funded</option>
                      <option value="rejected">Not Approved</option>
                    </select>
                  </div>
                  {hasFilters && (
                    <button
                      onClick={() => { setReportDateFrom(''); setReportDateTo(''); setReportStatusFilter('all'); setReportFundingType('all'); }}
                      className="reports-filter-clear"
                    >Clear filters</button>
                  )}
                </div>

                {isReportLoading ? (
                  <div className="reports-loading">
                    <div className="reports-spinner"></div>
                    <div>Loading report data…</div>
                  </div>
                ) : total === 0 ? (
                  <div className="reports-empty">
                    <Ic.Inbox size={36} />
                    <div className="reports-empty-title">No data for the selected filters</div>
                    <div className="reports-empty-sub">Try clearing filters or widening the date range.</div>
                  </div>
                ) : (
                  <div className="fade-in">
                    {/* ── Row 1: Pipeline + Stream split ── */}
                    <div className="reports-two-col" style={{ display: 'grid', gap: '20px', marginBottom: '20px' }}>
                      <div className="reports-panel">
                        <div className="reports-panel-header">
                          <h3 className="reports-panel-title">Application Pipeline</h3>
                          <span className="reports-panel-sub">by current status</span>
                        </div>
                        <div className="reports-pipeline-list">
                          {pipelineRows.map(item => {
                            const count = sbs[item.key] || 0;
                            const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                            return (
                              <div key={item.key} className="reports-pipeline-row">
                                <div className="reports-pipeline-head">
                                  <div className="reports-pipeline-label">
                                    <span className="reports-pipeline-icon" style={{ color: item.color }}>{item.icon}</span>
                                    {item.label}
                                  </div>
                                  <div className="reports-pipeline-meta">
                                    <span className="reports-pipeline-count">{count.toLocaleString()}</span>
                                    <span className="reports-pipeline-pct">{pct}%</span>
                                  </div>
                                </div>
                                <div className="reports-pipeline-bar">
                                  <div className="reports-pipeline-bar-fill" style={{ width: `${pct}%`, background: item.color }}></div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div className="reports-panel">
                        <div className="reports-panel-header">
                          <h3 className="reports-panel-title">Funding Program Breakdown</h3>
                          <span className="reports-panel-sub">by program type</span>
                        </div>
                        <div className="reports-program-body">
                          <div className="reports-program-donut">
                            <DonutChart data={streamRows.map(r => ({
                              label: r.label,
                              value: ss[r.key] || 0,
                              color: r.color,
                            }))} />
                          </div>
                          <div className="reports-program-list">
                            {streamRows.map(item => (
                              <div key={item.key} className="reports-program-row">
                                <div className="reports-program-left">
                                  <span className="reports-program-swatch" style={{ background: item.color }}></span>
                                  <div>
                                    <div className="reports-program-label">{item.label}</div>
                                    <div className="reports-program-sub">{item.sublabel}</div>
                                  </div>
                                </div>
                                <span className="reports-program-count">{(ss[item.key] || 0).toLocaleString()}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* ── Row 2: Quarterly chart + Live metrics ── */}
                    <div className="reports-two-col-asymm" style={{ display: 'grid', gap: '20px', marginBottom: '20px' }}>
                      <div className="reports-panel">
                        <div className="reports-panel-header">
                          <h3 className="reports-panel-title">Quarterly Funding Disbursements</h3>
                          <span className="reports-panel-sub">approved amounts (fiscal year)</span>
                        </div>
                        <div style={{ height: '180px' }}>
                          <BarChart data={(rs.quarterly_report || []).map((q: any) => ({
                            label: q.quarter.split(' ')[0],
                            value: q.amount || 0,
                            color: '#0f172a',
                          }))} />
                        </div>
                        <div className="reports-quarter-grid">
                          {(rs.quarterly_report || []).map((q: any) => (
                            <div key={q.quarter} className="reports-quarter-cell">
                              <div className="reports-quarter-label">{q.quarter.split(' ')[0]}</div>
                              <div className="reports-quarter-value">{fmtMoney(q.amount || 0)}</div>
                              <div className="reports-quarter-foot">{(q.count || 0).toLocaleString()} approved</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="reports-metrics-panel">
                        <h3 className="reports-metrics-title">Live Metrics</h3>
                        {[
                          { icon: <Ic.Inbox size={16} />,      label: 'Pending Info Requests', value: (sbs.more_info_required || 0).toLocaleString() },
                          { icon: <Ic.CreditCard size={16} />, label: 'Sent to Finance',        value: (sbs.sent_to_finance || 0).toLocaleString() },
                          { icon: <Ic.Send size={16} />,       label: 'Awaiting Director',      value: (sbs.forwarded || 0).toLocaleString() },
                          { icon: <Ic.Building size={16} />,   label: 'Total Disbursed',        value: fmtMoney(rs.total_funding_approved || 0) },
                          { icon: <Ic.TrendingUp size={16} />, label: 'Approval Rate',          value: `${approvalRate}%` },
                        ].map(m => (
                          <div key={m.label} className="reports-metric-row">
                            <div className="reports-metric-left">
                              <span className="reports-metric-icon">{m.icon}</span>
                              <span className="reports-metric-label">{m.label}</span>
                            </div>
                            <span className="reports-metric-value">{m.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* ── Recent applications ── */}
                    <div className="dash-activity">
                      <div className="dash-activity-header">
                        <div>
                          <h3 className="dash-panel-title">Recent Applications</h3>
                          <p className="dash-activity-sub">
                            {hasFilters ? 'Latest submissions matching the active filters' : 'Latest submissions across all funding programs'}
                            {' · '}{recent.length} record{recent.length === 1 ? '' : 's'}
                          </p>
                        </div>
                      </div>
                      <table className="apps-table">
                        <thead>
                          <tr>
                            <th>Ref</th>
                            <th>Applicant</th>
                            <th>Submitted</th>
                            <th>Program</th>
                            <th>Status</th>
                            <th style={{ textAlign: 'right' }}>Approved $</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recent.length === 0 && (
                            <tr>
                              <td colSpan={6} className="apps-empty">
                                <Ic.Inbox size={28} />
                                <div className="apps-empty-title">No applications found</div>
                                <div className="apps-empty-sub">Try adjusting your filters above.</div>
                              </td>
                            </tr>
                          )}
                          {recent.map((app: any) => {
                            // Server `recent_submissions` rows use flattened keys (form__title, student__full_name).
                            const name = app.student_details?.full_name || app.student__full_name || app.student_name || '—';
                            const programTitle = app.form_title || app.form?.title || app.form__title || app.form_type;
                            return (
                              <tr
                                key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`}
                                className="apps-row"
                                onClick={() => handleAppClick(app.id)}
                                tabIndex={0}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                                role="button"
                                aria-label={`View application ${app.id} for ${name}`}
                              >
                                <td className="apps-cell-ref">#{getRef(app.id)}</td>
                                <td>
                                  <div className="apps-applicant">
                                    <div className="apps-avatar">{initials(name)}</div>
                                    <div className="apps-applicant-info">
                                      <div className="apps-applicant-name">{name}</div>
                                      {app.student_details?.email && (
                                        <div className="apps-applicant-sub">{app.student_details.email}</div>
                                      )}
                                    </div>
                                  </div>
                                </td>
                                <td className="apps-cell-date">
                                  {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                                </td>
                                <td>
                                  <div className="apps-program">{getFormDisplayName(programTitle)}</div>
                                </td>
                                <td>{getStatusBadge(app.status, app)}</td>
                                <td className="apps-cell-amount">
                                  {parseFloat(app.amount || 0) > 0
                                    ? <span className="apps-amount-positive">${parseFloat(app.amount).toLocaleString()}</span>
                                    : <span className="apps-amount-muted">—</span>
                                  }
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
            );
          })()}


          {/* Director Approval Queue View */}
          {currentView === 'director-queue' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: '800' }}>APPROVAL QUEUE</h2>
                <span style={{ fontSize: '11px', color: '#64748b' }}>{applications.filter(a => a.status === 'forwarded').length} awaiting decision</span>
              </div>
              <div className="admin-kpi-row admin-kpi-row-4">
                <div className="admin-kpi-card">
                  <div className="admin-kpi-val">{stats.statusCounts.forwarded}</div>
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
                        <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{getRef(app.id)}</span></td>
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
                              onClick={() => handleAppClick(Number(app.id))}
                              style={{ color: 'var(--admin-accent)', fontWeight: '800' }}
                            >
                              Review →
                            </button>
                            <button
                              className="director-decision-icon-btn approve"
                              title="Quick Approve"
                              onClick={() => {
                                // Quick-approve from the queue: stay on the queue, just open the modal.
                                // Hydrate detailApp in the background so the modal shows real amount/name.
                                setSelectedAppId(String(app.id));
                                setDetailApp(null);
                                API.getSubmission(Number(app.id)).then((d: any) => setDetailApp(d)).catch(() => {});
                                setShowConfirmModal(true);
                              }}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                            </button>
                            <button
                              className="director-decision-icon-btn deny"
                              title="Quick Deny"
                              onClick={() => {
                                // Quick-deny from the queue: stay on the queue, just open the modal.
                                setSelectedAppId(String(app.id));
                                setDetailApp(null);
                                API.getSubmission(Number(app.id)).then((d: any) => setDetailApp(d)).catch(() => {});
                                setShowRejectModal(true);
                              }}
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
                        <tr key={app._is_standard ? `std-${app.id}` : `sub-${app.id}`} style={{ cursor: 'pointer' }} onClick={() => handleAppClick(Number(app.id))}>
                          <td><span style={{ fontSize: '10px', color: '#64748b' }}>{getRef(app.id)}</span></td>
                          <td><strong>{getStudentName(app)}</strong></td>
                          <td style={{ fontSize: '11px' }}>{getFormDisplayName(app.form_title)}</td>
                          <td style={{ fontSize: '12px', fontWeight: '700' }}>${parseFloat(app.amount || 0).toLocaleString()}</td>
                          <td>{getStatusBadge(app.status, app)}</td>
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

          {/* Director Application Detail View — prefer detailApp (full hydrated payload
              from API.getSubmission) over the lean `applications` summary, so answers,
              notes, documents, and office_use_data render correctly. Falls back to the
              summary while detailApp is still loading. */}
          {(currentView === 'director-detail' && selectedAppId) && (
            (() => {
              const app = detailApp || applications.find(a => String(a.id) === String(selectedAppId));
              return (
                <div className="fade-in">
              {/* ── Director review header — matches the SSW admin detail header layout ── */}
              <div className="admin-detail-header">
                <div className="admin-detail-breadcrumb">
                  <button
                    className="admin-back-btn"
                    onClick={() => {
                      setSelectedAppId(null);
                      setDetailApp(null);
                      setCurrentView('director-queue');
                    }}
                    aria-label="Back to Approval Queue"
                    title="Back to Approval Queue"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
                    <span>Back</span>
                  </button>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                    <span style={{ cursor: 'pointer' }} onClick={() => { setSelectedAppId(null); setDetailApp(null); setCurrentView('director-queue'); }}>Approval Queue</span>
                    {' / '}
                    <span style={{ fontWeight: '700', color: '#1e293b' }}>#{getRef(selectedAppId)}</span>
                  </div>
                </div>
                <div className="admin-detail-actions">
                  {getStatusBadge(app?.status || 'pending', app)}
                  {(() => {
                    const isDecided = app?.status === 'accepted' || app?.status === 'rejected';
                    if (isDecided) return null;
                    return (
                      <>
                        <button
                          className="admin-input"
                          style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: duplicateStatus?.is_confirmed ? '#94a3b8' : '#1a6b3a', color: '#fff', border: 'none', cursor: duplicateStatus?.is_confirmed ? 'not-allowed' : 'pointer' }}
                          disabled={!!duplicateStatus?.is_confirmed}
                          title={duplicateStatus?.is_confirmed ? 'Blocked: confirmed duplicate application' : undefined}
                          onClick={() => setShowConfirmModal(true)}
                        >
                          APPROVE
                        </button>
                        <button
                          className="admin-input"
                          style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: '#991b1b', color: '#fff', border: 'none' }}
                          onClick={() => setShowRejectModal(true)}
                        >
                          REJECT
                        </button>
                      </>
                    );
                  })()}
                </div>
              </div>

              <div className="admin-detail-grid">
                {/* Left: Application Content */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    <div className="dir-detail-header">
                      <div className="dir-detail-header-main">
                        <div className="dir-detail-ref-chip">REF · {getRef(selectedAppId)}</div>
                        <h2 className="dir-detail-title">
                          {(() => {
                            const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
                            return `${getStudentName(app)} — ${getFormDisplayName(app?.form_title || app?.form?.title)}`;
                          })()}
                        </h2>
                        {(() => {
                          const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
                          const ts = app?.forwarded_at || app?.submitted_at;
                          return (
                            <div className="dir-detail-meta">
                              <span>{app?.forwarded_at ? 'Forwarded by SSW' : 'Submitted'}</span>
                              <span className="dir-detail-meta-sep">·</span>
                              <span>{ts ? new Date(ts).toLocaleDateString() : 'N/A'}</span>
                              {app?.amount ? (<><span className="dir-detail-meta-sep">·</span><span><strong>${parseFloat(app.amount).toLocaleString()}</strong> requested</span></>) : null}
                            </div>
                          );
                        })()}
                      </div>
                      <div className="dir-detail-header-flags">
                        {(detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))?.flags?.map((f: string) => (
                          <span key={f} className={`admin-badge badge-${f.toLowerCase()}`} style={{ fontSize: '9px', padding: '4px 10px' }}>{f}</span>
                        ))}
                      </div>
                    </div>

                    <div style={{ background: '#f8fafc', borderRadius: '10px', padding: '24px', border: '1px solid #e2e8f0', marginBottom: '32px' }}>
                      <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', marginBottom: '20px', letterSpacing: '0.05em' }}>STUDENT & PROGRAM</h3>
                      <div className="dir-student-grid" style={{ display: 'grid', gap: '32px 24px' }}>
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
                        const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
                        const getField = (lbl: string) => (app?.answers || []).find((a: any) =>
                          (a.label || a.field?.label || a.field_label || '').toLowerCase().includes(lbl.toLowerCase())
                        )?.answer_text;
                        return (
                          <div className="dir-enrollment-grid" style={{ display: 'grid', gap: '16px', marginTop: '24px' }}>
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
                              <div style={{ fontSize: '13px', fontWeight: '700' }}>{getStatusBadge(app?.status || 'pending', app)}</div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>

                    {/* Full submitted form answers for director review */}
                    {renderSubmittedInformation()}

                    <div style={{ marginBottom: '32px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                        <h3 style={{ fontSize: '11px', fontWeight: '700', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>FUNDING BREAKDOWN</h3>
                      </div>
                      <div className="admin-table-wrap" style={{ border: 'none', boxShadow: 'none' }}>
                        {(() => {
                          const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
                          const answers: any[] = app?.answers || [];
                          const getField = (lbl: string) => answers.find((a: any) =>
                            (a.label || a.field?.label || '').toLowerCase().includes(lbl.toLowerCase())
                          )?.answer_text;

                          const formTitle = (app?.form_title || '').toLowerCase();
                          const isGraduation = formTitle.includes('graduation') || formTitle.includes('form g');
                          const isPracticum = formTitle.includes('practicum') || formTitle.includes('form f') || formTitle.includes('summer');

                          // Build dynamic rows from answers
                          const rows: { component: string; stream: string; rule: string; amount: number }[] = [];

                          // PRIMARY SOURCE: admin-edited AUTO FUNDING CALCULATION rows persisted on the
                          // submission. Director sees the exact breakdown admin produced — one source of truth.
                          const adminBreakdown: any[] = app?.office_use_data?.funding_breakdown || [];
                          if (adminBreakdown.length > 0) {
                            adminBreakdown.forEach((r: any) => {
                              rows.push({
                                component: r.label || 'Component',
                                stream: r.stream || app?.student_details?.primary_stream || '—',
                                rule: r.note || '',
                                amount: parseFloat(r.amount || 0),
                              });
                            });
                          } else if (isGraduation) {
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
                            // Fallback for legacy submissions with no admin breakdown — show per-component
                            // shape from raw office_use_data fields if any are populated.
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
                      const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
                      if (!app?.more_info_request_notes) return null;
                      return (
                        <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '10px', padding: '20px', marginBottom: '24px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                            <h4 style={{ fontSize: '11px', fontWeight: '800', color: '#c2410c', textTransform: 'uppercase', margin: 0, display: 'flex', alignItems: 'center', gap: '5px' }}><Ic.AlertTriangle size={11} /> INFORMATION REQUESTED FROM STUDENT</h4>
                            <span style={{ fontSize: '10px', color: '#9a3412' }}>
                              {app.more_info_requested_at ? new Date(app.more_info_requested_at).toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                              {app.more_info_requested_by_name ? ` · by ${app.more_info_requested_by_name}` : ''}
                            </span>
                          </div>
                          <p style={{ fontSize: '13px', color: '#7c2d12', lineHeight: '1.6', margin: '0 0 10px' }}>{app.more_info_request_notes}</p>
                          {app.more_info_responded_at ? (
                            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '8px 12px', fontSize: '11px', color: '#166534', fontWeight: '700' }}>
                              <Ic.CheckCircle size={11} style={{ color: '#166534', marginRight: '4px', verticalAlign: 'middle' }} /> Student responded on {new Date(app.more_info_responded_at).toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </div>
                          ) : (
                            <div style={{ fontSize: '11px', color: '#9a3412', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '4px' }}><Ic.Clock size={11} /> Awaiting student response...</div>
                          )}
                        </div>
                      );
                    })()}

                    {(() => {
                      const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
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
                      <div className="dir-docs-grid" style={{ display: 'grid', gap: '12px' }}>
                        {(() => {
                          // Documents come from two sources:
                          //   1. UserDocument records on the student profile  → app.documents (legacy/admin-only)
                          //   2. File-type answers on the submission           → answer.answer_file
                          // FormSubmissionSerializer exposes only #2, so the director view derives
                          // its document list from answers.answer_file (matches SSW detail behaviour).
                          const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
                          const fromAnswers: Array<{ name: string; url: string; label: string }> = (app?.answers || [])
                            .filter((a: any) => a?.answer_file)
                            .map((a: any) => ({
                              name: a.original_filename || (a.answer_file || '').split('/').pop() || 'document',
                              url: a.answer_file,
                              label: a.label || a.field?.label || 'Uploaded file',
                            }));
                          const fromDocs: Array<{ name: string; url: string; label: string; is_verified?: boolean }> = (app?.documents || [])
                            .map((d: any) => ({ name: d.name || (d.file || '').split('/').pop() || 'document', url: d.file, label: 'Verified Document', is_verified: d.is_verified }));
                          const docs = [...fromAnswers, ...fromDocs];
                          if (docs.length === 0) {
                            return (
                              <div style={{ gridColumn: 'span 2', fontSize: '11px', color: '#64748b', textAlign: 'center', padding: '16px', border: '1px dashed #e2e8f0', borderRadius: '8px' }}>No documents uploaded.</div>
                            );
                          }
                          return docs.map((doc, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                                <Ic.FileText size={16} />
                                <div style={{ minWidth: 0 }}>
                                  <div style={{ fontSize: '12px', fontWeight: '600', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.name}</div>
                                  <div style={{ fontSize: '10px', color: '#94a3b8' }}>{doc.label}</div>
                                </div>
                              </div>
                              <a href={doc.url} target="_blank" rel="noopener noreferrer" style={{ border: 'none', background: 'none', color: 'var(--admin-accent)', fontSize: '11px', fontWeight: '800', cursor: 'pointer', textDecoration: 'none', flexShrink: 0 }}>View</a>
                            </div>
                          ));
                        })()}
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
                          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><Ic.Ban size={12} /> Confirmed duplicate — approval blocked.</span>
                        </div>
                      )}
                      {(() => {
                        const app = (detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)));
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
                    You are approving <strong>#{selectedAppId} — {(detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))?.student_details?.full_name}</strong>.<br />
                    Funding amount: <strong>${parseFloat((detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))?.amount || 0).toLocaleString()}</strong>.
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
                    You are rejecting <strong>#{selectedAppId} — {(detailApp || applications.find(a => Number(a.id) === Number(selectedAppId)))?.student_details?.full_name}</strong>.
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
                    onClick={handleDispatchFinanceReport}
                    disabled={isDispatching}
                    style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: isDispatching ? 'not-allowed' : 'pointer', padding: '10px 20px', fontWeight: '800' }}
                  >
                    {isDispatching ? <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Ic.Clock size={12} /> SENDING...</span> : <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Ic.Mail size={12} /> EMAIL TO FINANCE</span>}
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
                    {isPaymentsLoading && payments.length === 0 ? (
                      [0, 1, 2, 3, 4, 5].map(i => (
                        <tr key={`skel-${i}`} aria-busy="true">
                          <td><span className="skeleton skeleton-line-xs" style={{ width: '70%' }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line" style={{ width: `${55 + (i * 7) % 30}%` }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line-sm" style={{ width: '60%' }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line" style={{ width: '50%' }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-badge" aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line-xs" style={{ width: '65%' }} aria-hidden>·</span></td>
                        </tr>
                      ))
                    ) : payments.length > 0 ? (
                      (() => {
                        // Group payments by user. Each group carries the rolled-up totals
                        // plus a child map keyed by application id so multi-app students
                        // see their payments split per application in the dropdown.
                        const resolveName = (p: any): string => {
                          if (p.user_name) return p.user_name;
                          if (p.student_details?.full_name) return p.student_details.full_name;
                          const app = applications.find(a => Number(a.user) === Number(p.user));
                          if (app) return getStudentName(app);
                          return `Student #${p.user}`;
                        };
                        const statusBadge = (s: string) => (
                          <span className={`admin-badge ${s === 'issued' ? 'badge-approved' : s === 'cancelled' ? 'badge-rejected' : 'badge-pending'}`} style={{ fontSize: '9px' }}>
                            {(s || 'pending').toUpperCase()}
                          </span>
                        );
                        type Group = { key: string; name: string; payments: any[]; total: number; latest: string | null };
                        const groupMap = new Map<string, Group>();
                        for (const p of payments) {
                          const key = String(p.user ?? `anon-${p.id}`);
                          if (!groupMap.has(key)) {
                            groupMap.set(key, { key, name: resolveName(p), payments: [], total: 0, latest: null });
                          }
                          const g = groupMap.get(key)!;
                          g.payments.push(p);
                          g.total += parseFloat(p.amount || 0) || 0;
                          if (p.date_issued && (!g.latest || new Date(p.date_issued) > new Date(g.latest))) {
                            g.latest = p.date_issued;
                          }
                        }
                        // Sort groups by latest date desc (nulls last), then by name.
                        const groups = Array.from(groupMap.values()).sort((a, b) => {
                          if (a.latest && b.latest) return new Date(b.latest).getTime() - new Date(a.latest).getTime();
                          if (a.latest) return -1;
                          if (b.latest) return 1;
                          return a.name.localeCompare(b.name);
                        });
                        return groups.flatMap((g) => {
                          // Single payment → render flat (no dropdown overhead).
                          if (g.payments.length === 1) {
                            const p = g.payments[0];
                            return [
                              <tr key={`pay-${p.id}`}>
                                <td><span style={{ fontSize: '11px', color: '#64748b' }}>{p.reference_number || `PAY-${p.id}`}</span></td>
                                <td><strong>{g.name}</strong></td>
                                <td style={{ fontSize: '12px' }}>{p.payment_type || '—'}</td>
                                <td style={{ fontSize: '13px', fontWeight: '700' }}>${parseFloat(p.amount || 0).toLocaleString()}</td>
                                <td>{statusBadge(p.status)}</td>
                                <td style={{ fontSize: '12px', color: '#64748b' }}>{p.date_issued ? new Date(p.date_issued).toLocaleDateString() : '—'}</td>
                              </tr>,
                            ];
                          }
                          // Multi-payment payer → parent toggle row + child rows when expanded.
                          const isOpen = expandedPayers.has(g.key);
                          // Distinct payment types preview (max 2) for the parent type column.
                          const types = Array.from(new Set(g.payments.map(p => p.payment_type).filter(Boolean)));
                          const typePreview = types.length === 0 ? '—' : types.length <= 2 ? types.join(', ') : `${types.slice(0, 2).join(', ')} +${types.length - 2}`;
                          // Roll-up status: if any pending → pending; else if any issued → issued; else cancelled.
                          const rollupStatus = g.payments.some(p => p.status === 'pending') ? 'pending'
                            : g.payments.some(p => p.status === 'issued') ? 'issued' : 'cancelled';
                          const parent = (
                            <tr
                              key={`grp-${g.key}`}
                              onClick={() => togglePayer(g.key)}
                              style={{ cursor: 'pointer', background: isOpen ? '#f8fafc' : undefined }}
                              aria-expanded={isOpen}
                            >
                              <td>
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#0369a1', fontWeight: 700 }}>
                                  <span style={{ display: 'inline-block', width: 10, transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform 120ms ease' }}>▶</span>
                                  {g.payments.length} PMTS
                                </span>
                              </td>
                              <td><strong>{g.name}</strong></td>
                              <td style={{ fontSize: '12px' }}>{typePreview}</td>
                              <td style={{ fontSize: '13px', fontWeight: '800' }}>${g.total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                              <td>{statusBadge(rollupStatus)}</td>
                              <td style={{ fontSize: '12px', color: '#64748b' }}>{g.latest ? new Date(g.latest).toLocaleDateString() : '—'}</td>
                            </tr>
                          );
                          if (!isOpen) return [parent];
                          // Bucket child payments by application id when set, else by
                          // submission id (calculation_service creates payments with
                          // application=None and links via `submission` only — the
                          // submission is the real source-of-truth in that case).
                          const byApp = new Map<string, any[]>();
                          for (const p of g.payments) {
                            const k = p.application
                              ? `app-${p.application}`
                              : p.submission
                                ? `sub-${p.submission}`
                                : 'no-app';
                            if (!byApp.has(k)) byApp.set(k, []);
                            byApp.get(k)!.push(p);
                          }
                          const childRows: any[] = [];
                          for (const [appKey, list] of byApp.entries()) {
                            let appLabel: string;
                            if (appKey.startsWith('app-')) {
                              const appId = appKey.replace(/^app-/, '');
                              const app = applications.find(a => String(a.id) === String(appId));
                              // Prefer the form's user-facing name; fall back to the
                              // first payment's submission form_title so the label
                              // still reads naturally even before backfill runs.
                              const sdTitle = list.find((p: any) => p.submission_details)?.submission_details?.form_title;
                              const niceName = prettyFormName(sdTitle || app?.form_type);
                              const semester = app?.semester
                                ? app.semester.charAt(0).toUpperCase() + app.semester.slice(1)
                                : '';
                              const year = app?.academic_year ? ` ${app.academic_year}` : '';
                              const period = semester ? ` · ${semester}${year}` : '';
                              appLabel = `${niceName}${period} · Application #${appId}`;
                            } else if (appKey.startsWith('sub-')) {
                              const subId = appKey.replace(/^sub-/, '');
                              const sd = list.find((p: any) => p.submission_details)?.submission_details;
                              appLabel = `${prettyFormName(sd?.form_title)} · Submission #${subId}`;
                            } else {
                              appLabel = 'No application linked';
                            }
                            childRows.push(
                              <tr key={`grp-${g.key}-${appKey}-hdr`} style={{ background: '#eff6ff' }}>
                                <td colSpan={6} style={{ fontSize: '11px', fontWeight: 800, color: '#1e3a8a', padding: '6px 12px', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                                  {appLabel} · {list.length} payment{list.length === 1 ? '' : 's'}
                                </td>
                              </tr>
                            );
                            for (const p of list) {
                              childRows.push(
                                <tr key={`pay-${p.id}`} style={{ background: '#fafafa' }}>
                                  <td style={{ paddingLeft: '32px' }}><span style={{ fontSize: '11px', color: '#64748b' }}>{p.reference_number || `PAY-${p.id}`}</span></td>
                                  <td style={{ fontSize: '12px', color: '#64748b' }}>↳ {g.name}</td>
                                  <td style={{ fontSize: '12px' }}>{p.payment_type || '—'}</td>
                                  <td style={{ fontSize: '13px', fontWeight: '700' }}>${parseFloat(p.amount || 0).toLocaleString()}</td>
                                  <td>{statusBadge(p.status)}</td>
                                  <td style={{ fontSize: '12px', color: '#64748b' }}>{p.date_issued ? new Date(p.date_issued).toLocaleDateString() : '—'}</td>
                                </tr>
                              );
                            }
                          }
                          return [parent, ...childRows];
                        });
                      })()
                    ) : (
                      <tr><td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No payment records found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {currentView === 'appeals' && (
            <div className="fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <h2 style={{ fontSize: '20px', fontWeight: '800' }}>SPECIAL AWARDS & APPEALS</h2>
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
                    {isAppealsLoading && displayAppeals.length === 0 ? (
                      [0, 1, 2, 3, 4].map(i => (
                        <tr key={`skel-${i}`} aria-busy="true">
                          <td><span className="skeleton skeleton-line-xs" style={{ width: '60%' }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line" style={{ width: `${55 + (i * 9) % 30}%` }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line-sm" style={{ width: '75%' }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line" style={{ width: '90%' }} aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-badge" aria-hidden>·</span></td>
                          <td><span className="skeleton skeleton-line-xs" style={{ width: '65%' }} aria-hidden>·</span></td>
                        </tr>
                      ))
                    ) : displayAppeals.length > 0 ? (
                      displayAppeals.map((a: any) => (
                        <tr
                          key={a.id}
                          className="clickable-row"
                          style={{ cursor: 'pointer' }}
                          onClick={() => handleAppClick(a.original.id)}
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleAppClick(a.original.id);
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
                      ))
                    ) : (
                      <tr><td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No special awards or appeals pending review.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Finance Email Toast */}
          {dispatchToast && (
            <div style={{
              position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999,
              background: dispatchToast.type === 'success' ? '#166534' : '#991b1b',
              color: '#fff', padding: '14px 24px', borderRadius: '10px',
              fontWeight: '700', fontSize: '14px', boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
              maxWidth: '380px', lineHeight: '1.5'
            }}>
              {dispatchToast.msg}
            </div>
          )}

          {/* Dispatch-to-Finance Modal — staff picks recipients + payment rows */}
          {showDispatchModal && (() => {
            // Derive the rows shown in the modal table based on the current
            // filter chips. Status filter values mirror Payment.Status; type
            // filter is a case-insensitive substring match on payment_type.
            const rowsAll = payments.filter((p: any) => {
              if (dispatchFilters.status !== 'all' && (p.status || 'pending') !== dispatchFilters.status) return false;
              if (dispatchFilters.type !== 'all') {
                const t = (p.payment_type || '').toLowerCase();
                if (!t.includes(dispatchFilters.type)) return false;
              }
              if (dispatchFilters.search.trim()) {
                const q = dispatchFilters.search.trim().toLowerCase();
                const name = (p.user_name || p.student_details?.full_name || '').toLowerCase();
                const email = (p.student_details?.email || '').toLowerCase();
                const ref = (p.reference_number || '').toLowerCase();
                if (!name.includes(q) && !email.includes(q) && !ref.includes(q)) return false;
              }
              return true;
            });
            const visibleIds = new Set<number>(rowsAll.map((p: any) => p.id));
            const allVisibleSelected = rowsAll.length > 0 && rowsAll.every((p: any) => dispatchSelected.has(p.id));
            const toggleAllVisible = () => setDispatchSelected(prev => {
              const next = new Set(prev);
              if (allVisibleSelected) {
                for (const id of visibleIds) next.delete(id);
              } else {
                for (const id of visibleIds) next.add(id);
              }
              return next;
            });
            const toggleOne = (id: number) => setDispatchSelected(prev => {
              const next = new Set(prev);
              if (next.has(id)) next.delete(id); else next.add(id);
              return next;
            });
            const selectedTotal = rowsAll.reduce(
              (sum: number, p: any) => sum + (dispatchSelected.has(p.id) ? (parseFloat(p.amount) || 0) : 0),
              0,
            );
            // Distinct payment types in the current payments list — drives the type filter chips.
            const typeOptions = Array.from(new Set(payments.map((p: any) => (p.payment_type || '').toLowerCase()).filter(Boolean))).sort();

            return (
              <div
                role="dialog"
                aria-modal="true"
                aria-label="Email payments to finance"
                style={{
                  position: 'fixed', inset: 0, zIndex: 10000,
                  background: 'rgba(15, 23, 42, 0.55)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  padding: '24px',
                }}
                onClick={(e) => { if (e.target === e.currentTarget) setShowDispatchModal(false); }}
              >
                <div style={{
                  background: '#fff', borderRadius: '14px', width: '100%', maxWidth: '1100px',
                  maxHeight: '92vh', display: 'flex', flexDirection: 'column',
                  boxShadow: '0 24px 60px rgba(0,0,0,0.35)', overflow: 'hidden',
                }}>
                  {/* Header */}
                  <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Ic.Mail size={18} /> Email Payments to Finance
                      </h3>
                      <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                        Choose the recipients and payment rows. The selected payments will be marked as issued.
                      </p>
                    </div>
                    <button
                      onClick={() => setShowDispatchModal(false)}
                      style={{ background: 'none', border: 'none', fontSize: '22px', cursor: 'pointer', color: '#64748b', lineHeight: 1 }}
                      aria-label="Close"
                    >×</button>
                  </div>

                  {/* Body */}
                  <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
                    {/* Recipients */}
                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: '6px' }}>Finance recipients</label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', padding: '8px', border: '1px solid #cbd5e1', borderRadius: '8px', background: '#f8fafc', minHeight: '44px' }}>
                        {dispatchRecipients.map(r => (
                          <span key={r} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#0369a1', color: '#fff', padding: '4px 10px', borderRadius: '14px', fontSize: '12px', fontWeight: 600 }}>
                            {r}
                            <button
                              onClick={() => setDispatchRecipients(prev => prev.filter(x => x !== r))}
                              style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '14px', lineHeight: 1, padding: 0 }}
                              aria-label={`Remove ${r}`}
                            >×</button>
                          </span>
                        ))}
                        <input
                          type="email"
                          value={dispatchRecipientInput}
                          onChange={(e) => setDispatchRecipientInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ',' || e.key === ';' || e.key === ' ') {
                              e.preventDefault();
                              addDispatchRecipient(dispatchRecipientInput);
                            } else if (e.key === 'Backspace' && !dispatchRecipientInput && dispatchRecipients.length) {
                              setDispatchRecipients(prev => prev.slice(0, -1));
                            }
                          }}
                          onBlur={() => { if (dispatchRecipientInput) addDispatchRecipient(dispatchRecipientInput); }}
                          placeholder={dispatchRecipients.length ? 'Add another…' : 'finance@example.com'}
                          style={{ flex: 1, minWidth: '200px', border: 'none', background: 'transparent', outline: 'none', fontSize: '13px' }}
                        />
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#94a3b8' }}>Press Enter, comma, or semicolon to add. Multiple recipients allowed.</p>
                    </div>

                    {/* Filters */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center', marginBottom: '10px' }}>
                      <div>
                        <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>Status</label>
                        <select
                          value={dispatchFilters.status}
                          onChange={(e) => setDispatchFilters(f => ({ ...f, status: e.target.value }))}
                          style={{ padding: '6px 10px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '12px' }}
                        >
                          <option value="all">All</option>
                          <option value="pending">Pending</option>
                          <option value="issued">Issued</option>
                          <option value="cancelled">Cancelled</option>
                        </select>
                      </div>
                      <div>
                        <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>Payment type</label>
                        <select
                          value={dispatchFilters.type}
                          onChange={(e) => setDispatchFilters(f => ({ ...f, type: e.target.value }))}
                          style={{ padding: '6px 10px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '12px' }}
                        >
                          <option value="all">All types</option>
                          {typeOptions.map(t => <option key={t} value={t}>{t.replace(/\b\w/g, c => c.toUpperCase())}</option>)}
                        </select>
                      </div>
                      <div style={{ flex: 1, minWidth: '200px' }}>
                        <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>Search</label>
                        <input
                          value={dispatchFilters.search}
                          onChange={(e) => setDispatchFilters(f => ({ ...f, search: e.target.value }))}
                          placeholder="Name, email, or reference #"
                          style={{ width: '100%', padding: '6px 10px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '12px' }}
                        />
                      </div>
                      <div style={{ alignSelf: 'flex-end', fontSize: '12px', color: '#0f172a', fontWeight: 700 }}>
                        {dispatchSelected.size} selected · ${selectedTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                    </div>

                    {/* Payments table */}
                    <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', maxHeight: '320px', overflowY: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead style={{ position: 'sticky', top: 0, background: '#f8fafc', zIndex: 1 }}>
                          <tr>
                            <th style={{ padding: '8px', width: '32px' }}>
                              <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible} aria-label="Select all visible" />
                            </th>
                            <th style={{ padding: '8px', textAlign: 'left', fontSize: '11px', color: '#64748b' }}>Student</th>
                            <th style={{ padding: '8px', textAlign: 'left', fontSize: '11px', color: '#64748b' }}>Email</th>
                            <th style={{ padding: '8px', textAlign: 'left', fontSize: '11px', color: '#64748b' }}>Program · Year</th>
                            <th style={{ padding: '8px', textAlign: 'left', fontSize: '11px', color: '#64748b' }}>Type</th>
                            <th style={{ padding: '8px', textAlign: 'right', fontSize: '11px', color: '#64748b' }}>Amount</th>
                            <th style={{ padding: '8px', textAlign: 'left', fontSize: '11px', color: '#64748b' }}>Account</th>
                            <th style={{ padding: '8px', textAlign: 'left', fontSize: '11px', color: '#64748b' }}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rowsAll.length === 0 && (
                            <tr><td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>No payments match the current filters.</td></tr>
                          )}
                          {rowsAll.map((p: any) => {
                            const u = p.student_details || {};
                            const studentName = p.user_name || u.full_name || `Student #${p.user}`;
                            const acct = u.account_number ? `${u.bank_name || '—'} · ${u.account_number}` : '—';
                            const program = u.program_credential || u.institution_name || '—';
                            const year = u.enrollment_status || '';
                            return (
                              <tr key={p.id} style={{ borderTop: '1px solid #f1f5f9', background: dispatchSelected.has(p.id) ? '#f0f9ff' : undefined }}>
                                <td style={{ padding: '6px 8px' }}>
                                  <input type="checkbox" checked={dispatchSelected.has(p.id)} onChange={() => toggleOne(p.id)} aria-label={`Select payment ${p.reference_number || p.id}`} />
                                </td>
                                <td style={{ padding: '6px 8px', fontWeight: 700 }}>{studentName}</td>
                                <td style={{ padding: '6px 8px', color: '#475569' }}>{u.email || '—'}</td>
                                <td style={{ padding: '6px 8px', color: '#475569' }}>{program}{year ? ` · ${year}` : ''}</td>
                                <td style={{ padding: '6px 8px' }}>{p.payment_type || '—'}</td>
                                <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700 }}>${parseFloat(p.amount || 0).toLocaleString()}</td>
                                <td style={{ padding: '6px 8px', color: '#475569', fontFamily: 'ui-monospace, monospace', fontSize: '11px' }}>{acct}</td>
                                <td style={{ padding: '6px 8px' }}>
                                  <span className={`admin-badge ${p.status === 'issued' ? 'badge-approved' : p.status === 'cancelled' ? 'badge-rejected' : 'badge-pending'}`} style={{ fontSize: '9px' }}>
                                    {(p.status || 'pending').toUpperCase()}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Subject + Notes */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px', marginTop: '16px' }}>
                      <div>
                        <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>Subject (optional)</label>
                        <input
                          value={dispatchSubject}
                          onChange={(e) => setDispatchSubject(e.target.value)}
                          placeholder="Leave blank for default subject"
                          style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '13px' }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>Notes for finance (optional)</label>
                        <textarea
                          value={dispatchNotes}
                          onChange={(e) => setDispatchNotes(e.target.value)}
                          rows={3}
                          placeholder="Any context the finance team should know — payment urgency, special handling, etc."
                          style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '13px', resize: 'vertical', fontFamily: 'inherit' }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Footer actions */}
                  <div style={{ padding: '14px 24px', borderTop: '1px solid #e2e8f0', background: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                      {dispatchRecipients.length} recipient{dispatchRecipients.length === 1 ? '' : 's'} · {dispatchSelected.size} payment{dispatchSelected.size === 1 ? '' : 's'} selected
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => setShowDispatchModal(false)}
                        disabled={isDispatching}
                        style={{ padding: '8px 18px', background: '#fff', border: '1px solid #cbd5e1', borderRadius: '8px', fontWeight: 700, fontSize: '13px', cursor: 'pointer' }}
                      >Cancel</button>
                      <button
                        onClick={submitDispatch}
                        disabled={isDispatching || dispatchRecipients.length === 0 || dispatchSelected.size === 0}
                        style={{
                          padding: '8px 18px', borderRadius: '8px', border: 'none',
                          background: (isDispatching || dispatchRecipients.length === 0 || dispatchSelected.size === 0) ? '#94a3b8' : '#0369a1',
                          color: '#fff', fontWeight: 800, fontSize: '13px', cursor: 'pointer',
                          display: 'inline-flex', alignItems: 'center', gap: '8px', minWidth: '140px', justifyContent: 'center',
                        }}
                      >
                        {isDispatching ? (
                          <><span className="ui-spinner ui-spinner-sm ui-spinner-on-dark" /> Sending…</>
                        ) : (
                          <><Ic.Send size={13} /> Send to Finance</>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Policy Save Toast — appears after Save changes completes */}
          {saveToast && (
            <div
              role="status"
              aria-live="polite"
              className="policy-save-toast"
              style={{
                position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999,
                background: saveToast.type === 'success' ? '#1a6b3a' : '#991b1b',
                color: '#fff', padding: '14px 20px', borderRadius: '10px',
                fontWeight: '700', fontSize: '13px', boxShadow: '0 8px 28px rgba(0,0,0,0.25)',
                maxWidth: '420px', lineHeight: '1.5',
                display: 'flex', alignItems: 'center', gap: '10px',
              }}
            >
              <Ic.CheckCircle size={16} />
              {saveToast.msg}
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
                  <div style={{ marginBottom: '12px', color: '#94a3b8' }}><Ic.Bell size={40} /></div>
                  <div style={{ fontSize: '16px', fontWeight: '600', marginBottom: '6px', color: '#64748b' }}>No Notifications</div>
                  <div style={{ fontSize: '13px' }}>You're all caught up!</div>
                </div>
              )}
            </div>
          )}


          {/* User Management View — director only */}
          {currentView === 'user-management' && role === 'director' && (
            <div className="fade-in" style={{ padding: '0 0 48px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: '800', margin: '0 0 4px' }}>Staff & Director Accounts</h2>
                  <p style={{ fontSize: '13px', color: '#64748b', margin: 0 }}>Create, edit, and remove internal portal access.</p>
                </div>
                <button
                  onClick={openAddUser}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 20px', background: '#1e293b', color: '#e5a662', border: 'none', borderRadius: '8px', fontWeight: '700', fontSize: '13px', cursor: 'pointer' }}
                >
                  <Ic.Users size={14} /> Add User
                </button>
              </div>

              {userMgmtError && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '12px 16px', marginBottom: '20px', color: '#991b1b', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Ic.AlertTriangle size={14} /> {userMgmtError}
                </div>
              )}

              {userMgmtLoading ? (
                <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }} aria-busy="true">
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                        {['Name', 'Email', 'Role', 'Status', 'Joined', 'Actions'].map(h => (
                          <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '700', fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[0, 1, 2, 3, 4, 5].map(i => (
                        <tr key={`skel-${i}`} style={{ borderBottom: i < 5 ? '1px solid #f1f5f9' : 'none' }}>
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span className="skeleton" style={{ width: '28px', height: '28px', borderRadius: '50%', display: 'inline-block' }} aria-hidden>·</span>
                              <span className="skeleton skeleton-line" style={{ width: `${55 + (i * 11) % 30}%` }} aria-hidden>·</span>
                            </div>
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <span className="skeleton skeleton-line-sm" style={{ width: `${65 + (i * 7) % 25}%` }} aria-hidden>·</span>
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <span className="skeleton skeleton-badge" style={{ width: '66px' }} aria-hidden>·</span>
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <span className="skeleton skeleton-badge" style={{ width: '58px' }} aria-hidden>·</span>
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <span className="skeleton skeleton-line-xs" style={{ width: '60%' }} aria-hidden>·</span>
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ display: 'flex', gap: '8px' }}>
                              <span className="skeleton" style={{ width: '52px', height: '26px', borderRadius: '6px' }} aria-hidden>·</span>
                              <span className="skeleton" style={{ width: '62px', height: '26px', borderRadius: '6px' }} aria-hidden>·</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="ui-loading-inline" style={{ justifyContent: 'center', padding: '14px', borderTop: '1px solid #f1f5f9', background: '#fafbfc' }}>
                    <span className="ui-spinner ui-spinner-sm" /> Loading staff accounts…
                  </div>
                </div>
              ) : staffUsers.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px', color: '#94a3b8' }}>
                  <div style={{ marginBottom: '12px' }}><Ic.Users size={36} /></div>
                  <div style={{ fontSize: '15px', fontWeight: '600', color: '#64748b' }}>No staff accounts found</div>
                  <div style={{ fontSize: '13px', marginTop: '6px' }}>Click "Add User" to create the first account.</div>
                </div>
              ) : (
                <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                        {['Name', 'Email', 'Role', 'Status', 'Joined', 'Actions'].map(h => (
                          <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '700', fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {staffUsers.map((u: any, i: number) => (
                        <tr key={u.id} style={{ borderBottom: i < staffUsers.length - 1 ? '1px solid #f1f5f9' : 'none', background: u.id === userData?.id ? '#fffbeb' : '#fff' }}>
                          <td style={{ padding: '14px 16px', fontWeight: '600', color: '#1e293b' }}>
                            {u.full_name}
                            {u.id === userData?.id && <span style={{ marginLeft: '8px', fontSize: '10px', background: '#fef3c7', color: '#92400e', padding: '2px 6px', borderRadius: '4px', fontWeight: '700' }}>YOU</span>}
                          </td>
                          <td style={{ padding: '14px 16px', color: '#374151' }}>{u.email}</td>
                          <td style={{ padding: '14px 16px' }}>
                            <span style={{ padding: '3px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: '700', background: u.role === 'director' ? '#dbeafe' : '#f1f5f9', color: u.role === 'director' ? '#1e40af' : '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              {u.role}
                            </span>
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <span style={{ padding: '3px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: '700', background: u.is_active ? '#dcfce7' : '#fee2e2', color: u.is_active ? '#166534' : '#991b1b' }}>
                              {u.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td style={{ padding: '14px 16px', color: '#64748b' }}>{u.date_joined}</td>
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ display: 'flex', gap: '8px' }}>
                              <button
                                onClick={() => openEditUser(u)}
                                style={{ padding: '6px 14px', background: '#f1f5f9', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600', color: '#374151' }}
                              >
                                Edit
                              </button>
                              {u.id !== userData?.id && (
                                <button
                                  onClick={() => setDeleteConfirmId(u.id)}
                                  style={{ padding: '6px 14px', background: '#fef2f2', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600', color: '#991b1b' }}
                                >
                                  Delete
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
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
            <strong><Ic.AlertTriangle size={12} style={{ verticalAlign: 'middle', marginRight: '3px' }} /> Note:</strong> The student will be notified by email and in-app with your message. The application will be paused until they respond.
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

    {/* ── Add / Edit User Modal ── */}
    {showUserModal && (
      <div
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
        onClick={() => setShowUserModal(false)}
      >
        <div
          style={{ background: '#fff', borderRadius: '12px', padding: '32px', width: '100%', maxWidth: '480px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}
          onClick={e => e.stopPropagation()}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: 0 }}>{editingUser ? 'Edit User' : 'Add Staff User'}</h3>
            <button onClick={() => setShowUserModal(false)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#64748b' }}>✕</button>
          </div>

          {userFormError && (
            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', color: '#991b1b', fontSize: '13px', display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Ic.AlertTriangle size={13} /> {userFormError}
            </div>
          )}

          {[
            { label: 'Full Name *', key: 'full_name', type: 'text', placeholder: 'e.g. Jane Smith' },
            ...(!editingUser ? [{ label: 'Email Address *', key: 'email', type: 'email', placeholder: 'e.g. jane@deline.ca' }] : []),
            { label: editingUser ? 'New Password (leave blank to keep current)' : 'Password *', key: 'password', type: 'password', placeholder: '••••••••' },
          ].map(({ label, key, type, placeholder }) => (
            <div key={key} style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#374151', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</label>
              <input
                type={type}
                placeholder={placeholder}
                value={(userForm as any)[key]}
                onChange={e => setUserForm(f => ({ ...f, [key]: e.target.value }))}
                style={{ width: '100%', padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box', fontFamily: 'inherit' }}
              />
            </div>
          ))}

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#374151', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Role *</label>
            <select
              value={userForm.role}
              onChange={e => setUserForm(f => ({ ...f, role: e.target.value }))}
              style={{ width: '100%', padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box', fontFamily: 'inherit', background: '#fff' }}
            >
              <option value="admin">Admin (Student Support Worker)</option>
              <option value="director">Director</option>
            </select>
          </div>

          {editingUser && (
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '700', color: '#374151', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Account Status</label>
              <div style={{ display: 'flex', gap: '16px' }}>
                {[true, false].map(val => (
                  <label key={String(val)} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
                    <input type="radio" name="um-is-active" checked={userForm.is_active === val} onChange={() => setUserForm(f => ({ ...f, is_active: val }))} />
                    {val ? 'Active' : 'Inactive (suspended)'}
                  </label>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <button
              onClick={() => setShowUserModal(false)}
              style={{ flex: 1, padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
            >
              Cancel
            </button>
            <button
              onClick={handleUserFormSubmit}
              disabled={userFormLoading}
              style={{ flex: 2, padding: '12px', border: 'none', borderRadius: '8px', background: userFormLoading ? '#94a3b8' : '#1e293b', color: '#e5a662', cursor: userFormLoading ? 'not-allowed' : 'pointer', fontWeight: '700', fontSize: '13px' }}
            >
              {userFormLoading ? 'Saving…' : editingUser ? 'Save Changes' : 'Create Account'}
            </button>
          </div>
        </div>
      </div>
    )}

    {/* ── Delete Confirm Modal ── */}
    {deleteConfirmId !== null && (() => {
      const target = staffUsers.find(u => u.id === deleteConfirmId);
      return (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1001, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}
          onClick={() => setDeleteConfirmId(null)}
        >
          <div
            style={{ background: '#fff', borderRadius: '12px', padding: '32px', width: '100%', maxWidth: '400px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)', textAlign: 'center' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ marginBottom: '16px', color: '#991b1b' }}><Ic.AlertTriangle size={40} /></div>
            <h3 style={{ fontSize: '18px', fontWeight: '800', margin: '0 0 8px' }}>Delete Account?</h3>
            <p style={{ fontSize: '14px', color: '#374151', marginBottom: '4px' }}><strong>{target?.full_name}</strong></p>
            <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px' }}>{target?.email}</p>
            <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '24px', lineHeight: '1.6' }}>
              This will permanently remove their access to the portal. This action cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => setDeleteConfirmId(null)}
                style={{ flex: 1, padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteUser(deleteConfirmId)}
                style={{ flex: 1, padding: '12px', border: 'none', borderRadius: '8px', background: '#991b1b', color: '#fff', cursor: 'pointer', fontWeight: '700', fontSize: '13px' }}
              >
                Delete Account
              </button>
            </div>
          </div>
        </div>
      );
    })()}
  </>
  );
};

export default StaffDashboard;
