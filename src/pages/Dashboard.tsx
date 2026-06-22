import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import API from '../api/client';
import '../styles/dashboard.css';
import FormA from './Forms/FormA';
import FormC from './Forms/FormC';
import FormD from './Forms/FormD';
import FormE from './Forms/FormE';
import FormF from './Forms/FormF';
import FormG from './Forms/FormG';
import FormH from './Forms/FormH';
import HardshipBursary from './Forms/HardshipBursary';
import AcademicScholarship from './Forms/AcademicScholarship';
import StudentProfile from './StudentProfile';
import * as Ic from '../components/Icons';

type DashboardView =
  | 'dashboard'
  | 'applications'
  | 'payments'
  | 'documents'
  | 'notifications'
  | 'help'
  | 'profile'
  | 'application-detail'
  | 'admission'
  | 'continuing-funding'
  | 'information-update'
  | 'travel-claim'
  | 'practicum-report'
  | 'practicum-report'
  | 'graduation-award'
  | 'scholarship'
  | 'hardship'
  | 'appeal-request';

// SVG Icons for professional look
const Icons = {
  Home: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>
  ),
  Files: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2-2H12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14.5 2 14.5 7.5 20 7.5" /></svg>
  ),
  Payments: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="14" x="2" y="5" rx="2" /><line x1="2" x2="22" y1="10" y2="10" /></svg>
  ),
  Documents: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" /></svg>
  ),
  Bell: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
  ),
  Help: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" x2="12.01" y1="17" y2="17" /></svg>
  ),
  LogOut: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" x2="9" y1="12" y2="12" /></svg>
  ),
  ChevronRight: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
  ),
  Info: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" x2="12" y1="16" y2="12" /><line x1="12" x2="12.01" y1="8" y2="8" /></svg>
  ),
  Check: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
  ),
  Star: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
  )
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentView, setCurrentView] = useState<DashboardView>('dashboard');
  const [showToast, setShowToast] = useState<string | null>(null);
  const [errorPopup, setErrorPopup] = useState<string | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(null);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [applications, setApplications] = useState<any[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const [isPaymentsLoading, setIsPaymentsLoading] = useState(true);
  const [deadlineSettings, setDeadlineSettings] = useState<Record<string, number>>({});
  const [sysConfig, setSysConfig] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState<any>(() => {
    try { return JSON.parse(localStorage.getItem('dgg_profile_cache') || 'null'); }
    catch { return null; }
  });
  // Start non-loading when we already have cached profile so the shell renders immediately
  const [isLoading, setIsLoading] = useState(() => {
    try { return !localStorage.getItem('dgg_profile_cache'); }
    catch { return true; }
  });
  const [documents, setDocuments] = useState<any[]>([]);
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedApplication, setSelectedApplication] = useState<any>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [showPaperFormsModal, setShowPaperFormsModal] = useState(false);
  const [submittedFormPopup, setSubmittedFormPopup] = useState<string | null>(null);
  const [availableForms, setAvailableForms] = useState<any[]>([]);
  const [hasFormA, setHasFormA] = useState(false);
  const [isFirstTimeCheck, setIsFirstTimeCheck] = useState(true);

  // More info response state
  const [infoResponseText, setInfoResponseText] = useState('');
  const [infoResponseFiles, setInfoResponseFiles] = useState<File[]>([]);
  const [infoResponseLoading, setInfoResponseLoading] = useState(false);
  const [infoResponseSuccess, setInfoResponseSuccess] = useState(false);

  const handleInfoResponse = async () => {
    if (!selectedApplication) return;
    if (!infoResponseText.trim() && infoResponseFiles.length === 0) return;
    setInfoResponseLoading(true);
    try {
      const formData = new FormData();
      if (infoResponseText.trim()) {
        formData.append('response_text', infoResponseText.trim());
      }
      infoResponseFiles.forEach((file, i) => {
        formData.append(`answers[${i}]field_label`, file.name);
        formData.append(`answers[${i}]answer_text`, 'File Uploaded');
        formData.append(`answers[${i}]answer_file`, file);
      });
      await API.respondToInfoRequest(selectedApplication.id, formData);
      setInfoResponseSuccess(true);
      setInfoResponseText('');
      setInfoResponseFiles([]);
      // Refresh the application data
      const resp = await API.getSubmissions() as any;
      const updated = (Array.isArray(resp) ? resp : resp?.results || [])
        .find((a: any) => a.id === selectedApplication.id);
      if (updated) setSelectedApplication(updated);
    } catch (err: any) {
      alert(err.message || 'Failed to submit response. Please try again.');
    } finally {
      setInfoResponseLoading(false);
    }
  };

  // Sync currentView with URL path and handle deep links
  useEffect(() => {
    const segments = location.pathname.split('/').filter(Boolean);
    if (segments.length > 1) {
      const view = segments[1] as DashboardView;
      setCurrentView(view);

      // Handle deep-linking for application details via ?id=
      const params = new URLSearchParams(location.search);
      const appId = params.get('id');
      if (view === 'application-detail' && appId && applications.length > 0) {
        const targetApp = applications.find(a => a.id.toString() === appId);
        if (targetApp) {
          setSelectedApplication(targetApp);
          if (!targetApp._is_standard && !targetApp.answers) {
            setIsDetailLoading(true);
            API.getSubmission(targetApp.id)
              .then((full: any) => {
                setSelectedApplication((prev: any) =>
                  prev && prev.id === targetApp.id ? { ...prev, ...full } : prev
                );
              })
              .catch((err: any) => console.error('Failed to load submission detail:', err))
              .finally(() => setIsDetailLoading(false));
          }
        }
      }
    } else if (segments.length === 1 && segments[0] === 'dashboard') {
      setCurrentView('dashboard');
    }
  }, [location.pathname, location.search, applications.length]);

  const handleViewApplication = (app: any) => {
    setSelectedApplication(app);
    setCurrentView('application-detail');
    // The list endpoint omits answers for performance — pull the full
    // submission (with answers) when opening the detail view. Legacy
    // Application records (_is_standard) have no submission detail endpoint.
    if (!app._is_standard && !app.answers) {
      setIsDetailLoading(true);
      API.getSubmission(app.id)
        .then((full: any) => {
          setSelectedApplication((prev: any) =>
            prev && prev.id === app.id ? { ...prev, ...full } : prev
          );
        })
        .catch((err: any) => console.error('Failed to load submission detail:', err))
        .finally(() => setIsDetailLoading(false));
    }
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
              <div className="json-answer-table-wrap" style={{ marginTop: '8px', background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <table style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #cbd5e1', textAlign: 'left', color: '#64748b' }}>
                      <th style={{ padding: '6px 0', fontWeight: '600' }}>Item Description</th>
                      <th style={{ padding: '6px 0', textAlign: 'right', fontWeight: '600' }}>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parsed.map((item: any, idx: number) => (
                      <tr key={idx} style={{ borderBottom: idx === parsed.length - 1 ? 'none' : '1px solid #e2e8f0' }}>
                        <td style={{ padding: '8px 0', color: '#1e293b' }}>{item.description}</td>
                        <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: '600', color: '#1e293b' }}>${parseFloat(item.amount).toLocaleString()}</td>
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
  const fetchDashboardData = async () => {
    // Start all requests in parallel
    const subsPromise = Promise.all([
      API.getSubmissions().catch(() => ({ results: [] })),
      API.getApplications().catch(() => ({ results: [] }))
    ]).then(([subsResp, appsResp]: [any, any]) => {
      const subs = Array.isArray(subsResp) ? subsResp : (subsResp?.results || []);
      const apps = Array.isArray(appsResp) ? appsResp : (appsResp?.results || []);

      // Legacy Application rows (form_type codes like "FormA") are internal
      // payment-linkage records the backend auto-creates alongside a
      // FormSubmission. Hide any whose category is already covered by a real
      // submission so students don't see duplicates; keep them only as a
      // fallback for old data with no matching submission.
      const deriveCode = (title: string): string | null => {
        const t = (title || '').toLowerCase();
        if (['form a', 'forma', 'psssp', 'c-dfn', 'new student', 'admission'].some(x => t.includes(x))) return 'FormA';
        if (['form b', 'formb', 'enrollment verif', 'enrolment verif', 'profile update'].some(x => t.includes(x))) return 'FormB';
        if (['form c', 'formc', 'continuing fund'].some(x => t.includes(x))) return 'FormC';
        if (['form d', 'formd', 'appeal', 'reconsider', 'specialized train'].some(x => t.includes(x))) return 'FormD';
        if (['form e', 'forme', 'travel', 'emergency fund'].some(x => t.includes(x))) return 'FormE';
        if (['form f', 'formf', 'practicum', 'placement'].some(x => t.includes(x))) return 'FormF';
        if (['form g', 'formg', 'graduation'].some(x => t.includes(x))) return 'FormG';
        if (['form h', 'formh', 'summer student'].some(x => t.includes(x))) return 'FormH';
        if (t.includes('hardship')) return 'FormHardship';
        if (t.includes('scholarship')) return 'FormScholarship';
        return null;
      };
      const subCodes = new Set(subs.map((s: any) => deriveCode(s.form_title || s.form?.title || '')).filter(Boolean));
      const uniqueApps = apps.filter((a: any) => !subCodes.has(deriveCode(a.form_type || '')));

      const merged = [
        ...subs,
        ...uniqueApps.map((a: any) => ({ ...a, _is_standard: true, form_title: a.form_type }))
      ];
      setApplications(merged);

      const admission = merged.find((a: any) => {
        const title = (a.form_title || '').toLowerCase();
        const type = (a.form_type || '').toLowerCase();
        return title.includes('admission') || title.includes('form a') || type.includes('psssp') || type.includes('form a');
      });
      setHasFormA(!!admission && admission.status !== 'rejected');
      setIsFirstTimeCheck(false);
    });

    const userPromise = API.getMe().then((resp: any) => {
      setProfile(resp);
      try { localStorage.setItem('dgg_profile_cache', JSON.stringify(resp)); } catch {}
    }).catch(() => {});

    const notifsPromise = API.getNotifications().then((resp: any) => {
      setNotifications(Array.isArray(resp) ? resp : []);
    }).catch(() => {});

    const paymentsPromise = API.getPayments().then((resp: any) => {
      const list = Array.isArray(resp) ? resp : (resp?.results || []);
      setPayments(list);
    }).catch(() => { }).finally(() => setIsPaymentsLoading(false));

    const policyPromise = API.getPolicySettings().then((resp: any) => {
      const deadlines = (resp?.application_deadlines || []) as any[];
      const dlMap: Record<string, number> = {};
      for (const item of deadlines) {
        dlMap[item.field_key] = Number(item.value); // month (1-12)
        const day = parseInt(item.unit);
        dlMap[item.field_key + '_day'] = (!isNaN(day) && day > 0) ? day : 1;
      }
      setDeadlineSettings(dlMap);

      const sysItems = (resp?.system_config || []) as any[];
      const cfgMap: Record<string, string> = {};
      for (const item of sysItems) {
        // Seed convention: numeric settings (travel_claim_days, book_allowance, …)
        // store the number in `value` and a label in `unit`. Text settings
        // (contact_email, contact_phone, …) store value=0 and the actual string
        // in `unit`. Prefer the numeric value when it's a real, non-zero number;
        // otherwise fall back to unit. This makes the substitution match what
        // the admin edits in Policy Settings.
        const num = parseFloat(item.value);
        const useValue = Number.isFinite(num) && num !== 0;
        cfgMap[item.field_key] = useValue ? String(item.value) : (item.unit || String(item.value ?? ''));
      }
      setSysConfig(cfgMap);
    }).catch(() => { });

    // Only fetch forms once (they don't change often)
    const formsPromise = availableForms.length === 0 
      ? API.getForms().then((resp: any) => {
          const formsList = Array.isArray(resp) ? resp : (resp?.results || []);
          setAvailableForms(formsList);
        }).catch(() => { })
      : Promise.resolve();

    try {
      // Run all requests fully in parallel — submissions and user are "essential",
      // the rest populate in the background without blocking the render.
      await Promise.all([subsPromise, userPromise]);
      setIsLoading(false);
      Promise.allSettled([notifsPromise, paymentsPromise, policyPromise, formsPromise]);
    } catch (err: any) {
      console.error('Failed to fetch dashboard data:', err);
      if (err.status === 401) {
        handleLogout();
      }
      setIsLoading(false);
    }
  };

  // \u2500\u2500 POLLING FOR REAL-TIME UPDATES \u2500\u2500
  // Skip polls while the tab is hidden; refresh once on re-visibility.
  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') fetchDashboardData();
    }, 60000);
    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchDashboardData();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  const fetchDocuments = async () => {
    setIsDocumentsLoading(true);
    try {
      const resp = await API.getUserDocuments();
      setDocuments(Array.isArray(resp) ? resp : []);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setIsDocumentsLoading(false);
    }
  };

  useEffect(() => {
    if (currentView === 'documents') {
      fetchDocuments();
    }
  }, [currentView]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so same file can be re-selected
    e.target.value = '';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', file.name);
    formData.append('category', 'User Upload');

    setIsUploading(true);
    try {
      await API.uploadUserDocument(formData);
      setShowToast('✓ Document uploaded successfully');
      fetchDocuments();
    } catch (err: any) {
      console.error('Upload failed:', err);
      const msg = err?.message || err?.data?.detail || 'An error occurred while uploading. Please try again.';
      setErrorPopup(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDocument = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return;
    try {
      await API.deleteUserDocument(id);
      setShowToast('Document deleted');
      fetchDocuments();
    } catch (err) {
      console.error('Delete failed:', err);
      setShowToast('Failed to delete document');
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  const handleMarkAllRead = async () => {
    try {
      await API.markAllNotificationsRead();
      setNotifications(notifications.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all as read:', err);
    }
  };

  const handleMarkRead = async (id: number) => {
    try {
      await API.markNotificationRead(id);
      setNotifications(notifications.map(n => n.id === id ? { ...n, is_read: true } : n));
    } catch (err) {
      console.error('Failed to mark as read:', err);
    }
  };

  const getApprovedTotal = () => {
    if (!Array.isArray(applications)) return 0;
    return applications
      .filter(app => app.status === 'accepted')
      .reduce((sum, app) => {
        const amt = parseFloat(app.amount || '0');
        return sum + (isNaN(amt) ? 0 : amt);
      }, 0);
  };


  const getJourneyStage = () => {
    if (applications.length === 0) {
      return { title: '1. Getting Started', milestone: 'Start Admission Application to begin', pips: [true, false, false] };
    }

    const latest = applications[0]; // Ordered by -submitted_at in backend

    if (latest.status === 'accepted') return { title: '4. Funding Active', milestone: 'Disbursement Phase', pips: [true, true, true] };
    if (latest.status === 'rejected') return { title: 'Policy Notice', milestone: 'Application Rejected', pips: [true, true, true] };
    if (latest.status === 'forwarded') return { title: '3. Final Approval', milestone: 'In Director Queue', pips: [true, true, true] };
    if (latest.status === 'reviewed') return { title: '2. Review Process', milestone: 'SSW Reviewed', pips: [true, true, false] };

    return { title: '1. Submitted', milestone: 'Awaiting Staff Review', pips: [true, false, false] };
  };

  const stage = getJourneyStage();

  const handleLogout = () => {
    localStorage.removeItem('dgg_token');
    localStorage.removeItem('dgg_refresh');
    localStorage.removeItem('dgg_role');
    localStorage.removeItem('dgg_profile_cache');
    navigate('/signin');
  };

  useEffect(() => {
    if (showToast) {
      const timer = setTimeout(() => setShowToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [showToast]);


  const handleFormComplete = async (_label?: string) => {
    setShowToast(`✓ Submission successful · You will receive an email confirmation`);
    navigate('/dashboard/applications');
    setIsMobileMenuOpen(false);
    await fetchDashboardData();
  };

  const handleNavClick = (view: DashboardView) => {
    setIsMobileMenuOpen(false);

    // Block duplicate admission applications
    if (view === 'admission') {
      const admissionApp = applications.find((a: any) => {
        const title = (a.form_title || '').toLowerCase();
        const type = (a.form_type || '').toLowerCase();
        return title.includes('admission') || title.includes('form a') || type.includes('psssp') || type.includes('form a');
      });
      if (admissionApp && admissionApp.status !== 'rejected') {
        setSubmittedFormPopup('Admission Application');
        return;
      }
    }

    // Always clear selected application when moving to a non-detail view
    if (view !== 'application-detail') {
      setSelectedApplication(null);
    }

    // The home view lives at /dashboard, not /dashboard/dashboard
    navigate(view === 'dashboard' ? '/dashboard' : `/dashboard/${view}`);
    // Immediately update currentView for responsiveness
    setCurrentView(view);
  };

  const renderSidebarNav = (id: DashboardView, label: string, icon: React.ReactNode) => (
    <div
      className={`snav ${currentView === id ? 'active' : ''}`}
      onClick={() => handleNavClick(id)}
    >
      <span className="snav-icon">{icon}</span> {label}
      {id === 'notifications' && unreadCount > 0 && <span className="notif-dot"></span>}
    </div>
  );

  const getStudentId = () => {
    if (profile?.beneficiary_number) return profile.beneficiary_number;
    if (profile?.id) return `DGG-${new Date().getFullYear()}-${profile.id.toString().padStart(4, '0')}`;
    return 'Pending';
  };

  return (
    <div className={`dashboard-root ${isMobileMenuOpen ? 'mobile-menu-open' : ''}`}>
      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div className="sidebar-overlay" onClick={() => setIsMobileMenuOpen(false)}></div>
      )}

      {/* Sidebar */}
      <div className={`sidebar ${isMobileMenuOpen ? 'open' : ''}`}>

        <div className="user-block" onClick={() => handleNavClick('profile')} style={{ cursor: 'pointer' }}>
          <div className="user-avatar">{profile?.full_name?.[0] || 'S'}</div>
          <div className="user-name">{profile ? profile.full_name : 'Student User'}</div>
          <div className="user-meta">{`ID: ${getStudentId()}`} · Student</div>
        </div>

        <div className="sidebar-section-title">Main</div>
        {renderSidebarNav('dashboard', 'Dashboard', <Icons.Home />)}
        {renderSidebarNav('applications', 'My Applications', <Ic.Clipboard size={14} />)}
        {renderSidebarNav('payments', 'My Payments', <Icons.Payments />)}
        {renderSidebarNav('documents', 'My Documents', <Icons.Documents />)}
        {renderSidebarNav('notifications', 'Notifications', <Icons.Bell />)}

        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Applications</div>
        {/* Only show Admission Application link if not submitted OR if rejected */}
        {(() => {
          const admissionApp = applications.find((a: any) => {
            const title = (a.form_title || '').toLowerCase();
            const type = (a.form_type || '').toLowerCase();
            return title.includes('admission') || title.includes('form a') || type.includes('psssp') || type.includes('form a');
          });
          const shouldShow = !admissionApp || admissionApp.status === 'rejected';
          return shouldShow ? renderSidebarNav('admission', 'Admission Application', <Ic.FileEdit size={14} />) : null;
        })()}
        {renderSidebarNav('continuing-funding', 'Continuing Funding', <Ic.DollarSign size={14} />)}
        {renderSidebarNav('information-update', 'Information Update', <Ic.User size={14} />)}

        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Claims</div>
        {renderSidebarNav('travel-claim', 'Travel Claim', <Ic.MapPin size={14} />)}
        {renderSidebarNav('practicum-report', 'Practicum Report', <Ic.BookOpen size={14} />)}
        {renderSidebarNav('graduation-award', 'Graduation Award', <Ic.GraduationCap size={14} />)}
        {renderSidebarNav('appeal-request', 'Appeal Request', <Ic.Scale size={14} />)}


        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Special</div>
        {renderSidebarNav('scholarship', 'Academic Scholarship', <Ic.Star size={14} />)}
        {renderSidebarNav('hardship', 'Hardship Bursary', <Ic.AlertTriangle size={14} />)}

        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Other</div>
        {renderSidebarNav('help', 'Help & FAQ', <Icons.Help />)}
        <div className="snav" onClick={handleLogout}>
          <span className="snav-icon"><Icons.LogOut /></span> Sign Out
        </div>
      </div>

      <div className="dashboard-shell">

        {/* Top Nav */}
        <div className="top-nav">
          <div className="top-nav-left">
            <button className="mobile-menu-btn" onClick={() => setIsMobileMenuOpen(true)}>
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" /></svg>
            </button>
            <div className="top-nav-brand">Délı̨nę Got'ı̨nę Government — Student Portal</div>
          </div>
          <div className="round-menu-bar desktop-only">
            <span className="top-nav-link" onClick={() => handleNavClick('dashboard')}>Home</span>
            <span className="top-nav-link" onClick={() => handleNavClick('applications')}>My Applications</span>
            <span className="top-nav-link" onClick={() => handleNavClick('profile')}>Profile</span>
            <span className="top-nav-link" onClick={() => handleNavClick('notifications')}>
              Notifications {unreadCount > 0 && <span className="nav-badge">{unreadCount}</span>}
            </span>
          </div>
        </div>

        <div className="main-content">
          <div className="deadline-bar">
            {(() => {
              const monthNames = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
              const fmt = (key: string, fallbackMonth: number, fallbackDay: number) => {
                const m = deadlineSettings[key] || fallbackMonth;
                const d = deadlineSettings[key + '_day'] || fallbackDay;
                return `${monthNames[m]} ${d}`;
              };
              return (
                <>
                  <span className="dl-item"><span className="dl-label">Fall deadline</span><span className="dl-date">{fmt('fall_deadline', 8, 1)}</span></span>
                  <span className="dl-sep">·</span>
                  <span className="dl-item"><span className="dl-label">Winter deadline</span><span className="dl-date">{fmt('winter_deadline', 12, 1)}</span></span>
                  <span className="dl-sep">·</span>
                  <span className="dl-item"><span className="dl-label">Spring deadline</span><span className="dl-date">{fmt('spring_deadline', 4, 1)}</span></span>
                  <span className="dl-sep">·</span>
                  <span className="dl-item"><span className="dl-label">Travel claims</span><span className="dl-urgent">within {sysConfig['travel_claim_days'] || '30'} days of travel</span></span>
                </>
              );
            })()}
          </div>

          <div className="view-container">

            {/* ── DASHBOARD VIEW ── */}
            {currentView === 'dashboard' && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <div className="view-title">
                    <div style={{ fontSize: '24px', fontWeight: '800', color: '#1e293b' }}>
                      Welcome back, {profile?.full_name?.split(' ')[0] || 'Student'}
                    </div>
                    <div style={{ fontSize: '13px', color: '#64748b', fontWeight: '500', marginTop: '4px' }}>
                      Student ID: <span style={{ color: '#0f172a', fontWeight: '700' }}>{getStudentId()}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button className="btn-ghost" onClick={() => setShowPaperFormsModal(true)} style={{ padding: '10px 20px', border: '1px solid #e2e8f0', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Ic.Download size={14} /> Download Paper Forms
                    </button>
                    <button className="btn-primary" onClick={() => handleNavClick('admission')} style={{ borderRadius: '8px' }}>+ Start Your Application</button>
                  </div>
                </div>
                <div className="view-body">
                  {/* {applications.length === 0 && (
                    <div className="welcome-alert">
                      <div className="welcome-alert-main">
                        <div className="welcome-icon-wrap"><Icons.Info /></div>
                        <div className="welcome-text">
                          <div className="welcome-title">Welcome to the DGG Student Portal</div>
                          <div className="welcome-desc">To begin, please establish your student file by completing the <strong>Admission Application</strong> below. If your information has changed, please report it immediately.</div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '12px' }}>
                        <button className="btn-primary welcome-btn" onClick={() => handleNavClick('admission')}>Get Started</button>
                        <button className="btn-ghost welcome-btn" style={{ borderColor: '#bee3f8', color: '#2b6cb0', fontWeight: '700' }} onClick={() => handleNavClick('information-update')}>Report a Change</button>
                      </div>
                    </div>
                  )} */}


                  <div className="journey-progress-bar fade-in">
                    <div className="phase-info">
                      <div className="phase-status">
                        <div className="phase-label">Current Phase</div>
                        <div className="phase-title">{stage.title}</div>
                      </div>
                      <div className="progress-pips">
                        <div className={`pip ${stage.pips[0] ? 'completed' : ''}`}></div>
                        <div className={`progress-line ${stage.pips[1] ? 'partial' : ''}`}></div>
                        <div className={`pip ${stage.pips[1] ? 'completed' : ''}`}></div>
                        <div className={`progress-line ${stage.pips[2] ? 'partial' : ''}`}></div>
                        <div className={`pip ${stage.pips[2] ? 'completed' : ''}`}></div>
                      </div>
                    </div>
                    <div className="next-milestone">
                      <div className="milestone-label">Next Milestone</div>
                      <div className="milestone-val">{stage.milestone}</div>
                    </div>
                  </div>

                  <div className="journey-section">
                    <div className="journey-header">
                      <div className="journey-num">01</div>
                      <div>
                        <div className="journey-title">Get Started</div>
                        <div className="journey-sub">Establish your file and secure initial funding eligibility</div>
                      </div>
                    </div>
                    <div className="form-cards-grid">
                      {/* Only show Form A card if not submitted OR if rejected */}
                      {(() => {
                        const admissionApp = applications.find((a: any) => {
                          const title = (a.form_title || '').toLowerCase();
                          const type = (a.form_type || '').toLowerCase();
                          return title.includes('admission') || title.includes('form a') || type.includes('psssp') || type.includes('form a');
                        });
                        const isRejected = admissionApp?.status === 'rejected';
                        const shouldShow = !admissionApp || isRejected;

                        if (!shouldShow) {
                          // Form A already submitted and not rejected - don't show the card
                          return null;
                        }

                        return (
                          <div
                            className={`form-card primary-card active-step`}
                            onClick={() => handleNavClick('admission')}
                          >
                            <div className="form-card-inner">
                              <div className="form-card-header">
                                <span className="form-tag">New File</span>
                                {!admissionApp && <span className="recommended-tag"><Icons.Star /> RECOMMENDED NEXT STEP</span>}
                                {isRejected && <span className="form-tag" style={{ background: '#fef2f2', color: '#991b1b', borderColor: '#fecaca' }}>✕ REJECTED — REAPPLY</span>}
                              </div>
                              <div className="form-card-title">Admission Application</div>
                              <div className="form-card-desc">
                                {isRejected
                                  ? 'Your previous application was rejected. You may submit a new application.'
                                  : 'Your gateway to all DGG funding. Complete this first to map your eligibility.'}
                              </div>
                              <div style={{ fontSize: '9px', color: '#718096', marginBottom: '12px' }}>Required once per program · Establishes your stream</div>
                              {isRejected ? (
                                <button className="btn-auth-primary form-btn" style={{ background: '#dc2626' }}>Reapply Now &nbsp;<Icons.ChevronRight /></button>
                              ) : (
                                <button className="btn-auth-primary form-btn">Start Application &nbsp;<Icons.ChevronRight /></button>
                              )}
                            </div>
                          </div>
                        );
                      })()}
                      <div className="form-card" style={{ borderLeft: '3px solid #3182ce', opacity: 0.9 }}>
                        <div className="form-card-inner">
                          <div className="form-card-header">
                            <span className="form-tag" style={{ background: '#ebf8ff', color: '#2b6cb0', border: '1px solid #bee3f8' }}>Enrolment</span>
                            <span style={{ fontSize: '11px', color: '#dd6b20', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '4px' }}><Ic.Clock size={11} /> Tracking Active</span>
                          </div>
                          <div className="form-card-title">Enrolment Verification</div>
                          <div className="form-card-desc">Registrar verification. Generated automatically after your application is submitted.</div>
                          <div style={{ fontSize: '9px', color: '#718096', marginBottom: '12px' }}>Auto-generated from application · Sent to Registrar</div>
                          <button className="btn-ghost form-btn" onClick={() => handleNavClick('applications')}>Manage Tracking &nbsp;<Icons.ChevronRight /></button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="journey-section">
                    <div className="journey-header">
                      <div className="journey-num">02</div>
                      <div>
                        <div className="journey-title">My Recent Activity</div>
                        <div className="journey-sub">Track your latest submissions and status updates</div>
                      </div>
                    </div>
                    {applications.length > 0 ? (
                      <div className="activity-list" style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '20px' }}>
                        {applications.slice(0, 3).map(app => (
                          <div
                            key={app.id}
                            className="activity-item"
                            onClick={() => handleViewApplication(app)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '16px',
                              background: '#fff',
                              padding: '16px',
                              borderRadius: '12px',
                              border: '1px solid #e2e8f0',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }}
                          >
                            <div className="activity-icon" style={{ background: '#f8fafc', padding: '10px', borderRadius: '10px', color: '#64748b' }}>
                              <Icons.Files />
                            </div>
                            <div className="activity-info" style={{ flex: 1 }}>
                              <div className="activity-name" style={{ fontWeight: '600', color: '#1e293b' }}>{app.form_title}</div>
                              <div className="activity-meta" style={{ fontSize: '12px', color: '#64748b' }}>
                                Submitted on {new Date(app.submitted_at).toLocaleDateString()} ·
                                <span style={{
                                  marginLeft: '8px',
                                  color: app.status === 'accepted' ? '#166534' : app.status === 'rejected' ? '#991b1b' : '#075985',
                                  fontWeight: '700'
                                }}>
                                  {app.status.toUpperCase()}
                                </span>
                              </div>
                            </div>
                            <div className="activity-link" style={{ fontSize: '12px', color: '#3182ce', fontWeight: '600' }}>View Details →</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-state" style={{ padding: '40px 0', background: '#f8fafc', borderRadius: '12px', border: '1px dashed #cbd5e1' }}>
                        <Icons.Files />
                        <div className="empty-title">No Recent Activity</div>
                        <div className="empty-desc">Once you submit an application, it will appear here for quick tracking.</div>
                      </div>
                    )}
                  </div>
                  <div className="paper-forms-alert fade-in">
                    <div className="paper-icon"><Ic.Printer size={24} /></div>
                    <div className="paper-text">
                      <div className="paper-text-title">Refer to Paper Forms?</div>
                      <div className="paper-text-desc">
                        You can download printable versions of all DGG forms to fill out by hand.
                        Once completed, you can mail them to the DGG office or drop them off in person.
                      </div>
                      <button 
                        className="btn-ghost" 
                        style={{ fontWeight: 700, color: '#2b6cb0', borderColor: '#bee3f8' }}
                        onClick={() => setShowPaperFormsModal(true)}
                      >
                        Download Printable Forms Packet (PDF) →
                      </button>
                      <div className="paper-meta">
                        Note: Paper forms may take 5–7 business days longer to process.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ── APPLICATIONS VIEW ── */}
            {currentView === 'applications' && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <div className="view-title">My Applications</div>
                  <button className="btn-primary" onClick={() => handleNavClick('admission')}>+ New Application</button>
                </div>
                <div className="view-body">
                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Active & Recent Submissions</span></div>
                    {isLoading ? (
                      <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading applications...</div>
                    ) : applications.length > 0 ? (
                      <div className="table-wrap">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Ref #</th>
                              <th>Form Type</th>
                              <th>Status</th>
                              <th>Decision</th>
                              <th>Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {applications.map((app) => (
                              <tr key={app.id}>
                                <td style={{ fontSize: '11px' }}>{new Date(app.submitted_at).toLocaleDateString()}</td>
                                <td style={{ fontWeight: '700' }}>#{app.id.toString().padStart(6, '0')}</td>
                                <td style={{ fontWeight: '600' }}>{app.form_title}</td>
                                <td>
                                  <span style={{
                                    padding: '4px 10px',
                                    borderRadius: '4px',
                                    fontSize: '9px',
                                    fontWeight: '800',
                                    background: app.status === 'accepted' ? '#f0fdf4'
                                      : app.status === 'sent_to_finance' ? '#e0f2fe'
                                        : app.status === 'rejected' ? '#fef2f2'
                                          : app.status === 'more_info_required' ? '#fff7ed'
                                            : '#f0f9ff',
                                    color: app.status === 'accepted' ? '#166534'
                                      : app.status === 'sent_to_finance' ? '#0369a1'
                                        : app.status === 'rejected' ? '#991b1b'
                                          : app.status === 'more_info_required' ? '#c2410c'
                                            : '#075985',
                                    border: `1px solid ${app.status === 'accepted' ? '#bbf7d0'
                                      : app.status === 'sent_to_finance' ? '#7dd3fc'
                                        : app.status === 'rejected' ? '#fecaca'
                                          : app.status === 'more_info_required' ? '#fed7aa'
                                            : '#bae6fd'}`
                                  }}>
                                    {app.status === 'more_info_required' ? 'ACTION REQUIRED'
                                      : app.status === 'sent_to_finance' ? 'SENT TO FINANCE'
                                        : app.status.toUpperCase()}
                                  </span>
                                </td>
                                <td style={{ fontSize: '10px', color: '#64748b' }}>
                                  {app.status === 'pending' ? 'Under Review'
                                    : app.status === 'accepted' ? 'Funds Authorized'
                                      : app.status === 'sent_to_finance' ? 'Payment Processing (2–5 days)'
                                        : app.status === 'reviewed' ? 'SSW Reviewed'
                                          : app.status === 'forwarded' ? 'Awaiting Director'
                                            : app.status === 'more_info_required' ? 'Info Requested'
                                              : 'Policy Non-Compliance'}
                                </td>
                                <td>
                                  <div style={{ display: 'flex', gap: '8px' }}>
                                    <button
                                      className="btn-ghost"
                                      style={{ padding: '4px 8px', fontSize: '10px' }}
                                      onClick={() => handleViewApplication(app)}
                                    >
                                      View Details
                                    </button>
                                    <button
                                      className="btn-ghost"
                                      style={{ padding: '4px 8px', fontSize: '10px', color: '#2b6cb0', borderColor: '#bee3f8' }}
                                      onClick={async () => {
                                        try {
                                          const blob = await API.downloadSubmissionPDF(app.id);
                                          const url = URL.createObjectURL(blob);
                                          const link = document.createElement('a');
                                          link.href = url;
                                          link.download = `Submission_${app.id}.pdf`;
                                          document.body.appendChild(link);
                                          link.click();
                                          document.body.removeChild(link);
                                          URL.revokeObjectURL(url);
                                          setShowToast('✓ PDF downloaded');
                                        } catch (err: any) {
                                          setErrorPopup(err.message || 'Failed to download PDF');
                                        }
                                      }}
                                    >
                                      <Ic.Download size={12} /> PDF
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="empty-state">
                        <Icons.Files />
                        <div className="empty-title">No Submissions Yet</div>
                        <div className="empty-desc">Once you submit a form, you can track its progress and approval status here.</div>
                        <button className="btn-primary" onClick={() => handleNavClick('dashboard')}>Browse Forms</button>
                      </div>
                    )}
                  </div>

                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Situation vs Required Form</span></div>
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Situation</th>
                            <th>Required Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr><td>First time applying for funding</td><td>Complete <strong>Admission Application</strong></td></tr>
                          <tr><td>Returning for a new semester</td><td>Complete <strong>Continuing Funding</strong></td></tr>
                          <tr><td>Changed school or program</td><td>Complete <strong>Information Update</strong></td></tr>
                          <tr><td>Claiming travel reimbursement</td><td>Complete <strong>Travel Claim</strong></td></tr>
                          <tr><td>Reporting graduation</td><td>Complete <strong>Graduation Award</strong></td></tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ── PAYMENTS VIEW ── */}
            {currentView === 'payments' && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <div className="view-title">My Payments</div>
                </div>
                <div className="view-body">
                  {(() => {
                    const paidPayments = payments.filter((p: any) => p.status === 'paid' || p.status === 'issued');
                    const pendingPayments = payments.filter((p: any) => p.status === 'pending' || p.status === 'scheduled');
                    const paidTotal = paidPayments.reduce((s: number, p: any) => s + parseFloat(p.amount || 0), 0);
                    const pendingTotal = pendingPayments.reduce((s: number, p: any) => s + parseFloat(p.amount || 0), 0);
                    const authorizedTotal = getApprovedTotal();
                    const remaining = Math.max(0, authorizedTotal - paidTotal);
                    const kpiVal = (v: number) => isPaymentsLoading
                      ? <span className="skeleton skeleton-line-lg" style={{ width: '80%' }} aria-hidden>·</span>
                      : `$${v.toLocaleString()}`;
                    return (
                      <>
                        <div className="kpi-row">
                          <div className="kpi-card"><div className="kpi-val">{kpiVal(authorizedTotal)}</div><div className="kpi-label">Authorized Total</div></div>
                          <div className="kpi-card"><div className="kpi-val">{kpiVal(paidTotal)}</div><div className="kpi-label">Paid To Date</div></div>
                          <div className="kpi-card"><div className="kpi-val">{kpiVal(remaining)}</div><div className="kpi-label">Remaining Balance</div></div>
                          <div className="kpi-card"><div className="kpi-val">{kpiVal(pendingTotal)}</div><div className="kpi-label">Upcoming Scheduled</div></div>
                        </div>
                        <div className="sec-card">
                          <div className="sec-head">
                            <span className="sec-title">Payment History & Schedule</span>
                            {isPaymentsLoading && (
                              <span className="ui-loading-inline"><span className="ui-spinner ui-spinner-sm" /> Loading…</span>
                            )}
                          </div>
                          {isPaymentsLoading ? (
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }} aria-busy="true">
                              <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', color: '#64748b', fontSize: '11px', textTransform: 'uppercase' }}>
                                  <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '700' }}>Date</th>
                                  <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '700' }}>Type</th>
                                  <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: '700' }}>Amount</th>
                                  <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '700' }}>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {[0, 1, 2, 3].map(i => (
                                  <tr key={`skel-${i}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                    <td style={{ padding: '12px' }}><span className="skeleton skeleton-line-sm" style={{ width: '70%' }} aria-hidden>·</span></td>
                                    <td style={{ padding: '12px' }}><span className="skeleton skeleton-line" style={{ width: `${55 + (i * 11) % 30}%` }} aria-hidden>·</span></td>
                                    <td style={{ padding: '12px', textAlign: 'right' }}><span className="skeleton skeleton-line" style={{ width: '55%' }} aria-hidden>·</span></td>
                                    <td style={{ padding: '12px' }}><span className="skeleton skeleton-badge" style={{ width: '60px' }} aria-hidden>·</span></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : payments.length === 0 ? (
                            <div className="empty-state">
                              <Icons.Payments />
                              <div className="empty-title">No Payments Yet</div>
                              <div className="empty-desc">Your payment schedule will appear here after your application is approved by the Director.</div>
                            </div>
                          ) : (
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                              <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0', color: '#64748b', fontSize: '11px', textTransform: 'uppercase' }}>
                                  <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '700' }}>Date</th>
                                  <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '700' }}>Type</th>
                                  <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: '700' }}>Amount</th>
                                  <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: '700' }}>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {payments.map((p: any) => (
                                  <tr key={p.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                    <td style={{ padding: '12px' }}>{p.date_issued ? new Date(p.date_issued).toLocaleDateString() : '—'}</td>
                                    <td style={{ padding: '12px', color: '#475569' }}>{p.payment_type || 'Bursary'}</td>
                                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600' }}>${parseFloat(p.amount || 0).toLocaleString()}</td>
                                    <td style={{ padding: '12px' }}>
                                      <span style={{
                                        padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700',
                                        background: p.status === 'paid' || p.status === 'issued' ? '#dcfce7' : p.status === 'pending' ? '#fef9c3' : '#f1f5f9',
                                        color: p.status === 'paid' || p.status === 'issued' ? '#166534' : p.status === 'pending' ? '#854d0e' : '#475569'
                                      }}>{(p.status || 'pending').toUpperCase()}</span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </>
                    );
                  })()}
                </div>
              </div>
            )}

            {/* ── NOTIFICATIONS VIEW ── */}
            {currentView === 'notifications' && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <div className="view-title">Notifications</div>
                  <button className="btn-ghost" onClick={handleMarkAllRead}>Mark All Read</button>
                </div>
                <div className="view-body">
                  {notifications.length > 0 ? (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        className={`notif-item ${!notif.is_read ? 'unread' : ''}`}
                        onClick={() => handleMarkRead(notif.id)}
                      >
                        <div className="notif-icon-wrap"><Icons.Bell /></div>
                        <div className="notif-body">
                          <div className="notif-title">{notif.title}</div>
                          <div className="notif-detail">{notif.message}</div>
                          <div className="notif-time">
                            {new Date(notif.created_at).toLocaleDateString()} {new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                          {/* No action links */}
                        </div>
                        {!notif.is_read && <div className="unread-pip"></div>}
                      </div>
                    ))
                  ) : (
                    <div className="empty-state">
                      <Icons.Bell />
                      <div className="empty-title">No Notifications</div>
                      <div className="empty-desc">You're all caught up! New alerts will appear here.</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {currentView === 'application-detail' && selectedApplication && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <button className="btn-ghost" onClick={() => handleNavClick('applications')}>← Back to Applications</button>
                  <div className="view-title">Application Details</div>
                  <button 
                    className="btn-ghost" 
                    style={{ marginLeft: 'auto', fontWeight: '700', color: '#2b6cb0', borderColor: '#bee3f8' }}
                    onClick={async () => {
                      try {
                        const blob = await API.downloadSubmissionPDF(selectedApplication.id);
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = `Submission_${selectedApplication.id}_${selectedApplication.form_title?.replace(/\s+/g, '_') || 'Application'}.pdf`;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        URL.revokeObjectURL(url);
                        setShowToast('✓ PDF downloaded successfully');
                      } catch (err: any) {
                        setErrorPopup(err.message || 'Failed to download PDF');
                      }
                    }}
                  >
                    <Ic.Download size={14} /> Download PDF
                  </button>
                </div>
                <div className="view-body">
                  <div className="sec-card">
                    <div className="sec-head">
                      <span className="sec-title">Submission Summary</span>
                      <span style={{
                        padding: '4px 10px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: '800',
                        marginLeft: '12px',
                        background: selectedApplication.status === 'accepted' ? '#f0fdf4' : selectedApplication.status === 'rejected' ? '#fef2f2' : '#f0f9ff',
                        color: selectedApplication.status === 'accepted' ? '#166534' : selectedApplication.status === 'rejected' ? '#991b1b' : '#075985',
                      }}>
                        {selectedApplication.status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ padding: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
                      <div>
                        <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Reference Number</div>
                        <div style={{ fontWeight: '600' }}>#{selectedApplication.id.toString().padStart(6, '0')}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Form Type</div>
                        <div style={{ fontWeight: '600' }}>{selectedApplication.form_title}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Submission Date</div>
                        <div style={{ fontWeight: '600' }}>{new Date(selectedApplication.submitted_at).toLocaleDateString()}</div>
                      </div>
                      {selectedApplication.amount && (
                        <div>
                          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '4px' }}>Authorized Amount</div>
                          <div style={{ fontWeight: '700', color: '#166534' }}>${parseFloat(selectedApplication.amount).toLocaleString()}</div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ── More Info Required Banner + Response Form ── */}
                  {selectedApplication.status === 'more_info_required' && (
                    <div className="sec-card" style={{ borderLeft: '4px solid #f97316' }}>
                      <div className="sec-head">
                        <span className="sec-title" style={{ color: '#c2410c', display: 'flex', alignItems: 'center', gap: '6px' }}><Ic.AlertTriangle size={14} /> Action Required — Additional Information Needed</span>
                      </div>
                      <div style={{ padding: '0 20px 20px' }}>

                        {/* What was requested */}
                        <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
                          <div style={{ fontSize: '11px', fontWeight: '700', color: '#9a3412', textTransform: 'uppercase', marginBottom: '8px' }}>
                            Information Requested by Staff
                            {selectedApplication.more_info_requested_at && (
                              <span style={{ fontWeight: '400', marginLeft: '8px', textTransform: 'none' }}>
                                · {new Date(selectedApplication.more_info_requested_at).toLocaleDateString('en-CA', { month: 'long', day: 'numeric', year: 'numeric' })}
                              </span>
                            )}
                          </div>
                          <p style={{ fontSize: '14px', color: '#7c2d12', lineHeight: '1.7', margin: 0 }}>
                            {selectedApplication.more_info_request_notes || 'Your Student Support Worker has requested additional information. Please provide the details below.'}
                          </p>
                        </div>

                        {/* Already responded */}
                        {(selectedApplication.more_info_responded_at || infoResponseSuccess) ? (
                          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
                            <div style={{ marginBottom: '8px', color: '#166534' }}><Ic.CheckCircle size={16} /></div>
                            <div style={{ fontWeight: '700', color: '#166534', marginBottom: '4px' }}>Response Submitted</div>
                            <div style={{ fontSize: '12px', color: '#4ade80' }}>
                              Your information has been sent to the Education Department. Your application is now back under review.
                            </div>
                          </div>
                        ) : (
                          /* Response form */
                          <div>
                            <div style={{ fontSize: '12px', fontWeight: '700', color: '#374151', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Your Response *
                            </div>
                            <textarea
                              value={infoResponseText}
                              onChange={e => setInfoResponseText(e.target.value)}
                              placeholder="Explain or provide the requested information here..."
                              style={{ width: '100%', minHeight: '100px', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '13px', lineHeight: '1.6', resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit', marginBottom: '16px' }}
                            />

                            <div style={{ fontSize: '12px', fontWeight: '700', color: '#374151', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Upload Supporting Documents (optional)
                            </div>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px', border: '2px dashed #d1d5db', borderRadius: '8px', cursor: 'pointer', marginBottom: '8px', background: '#f9fafb' }}>
                              <Ic.Paperclip size={20} />
                              <span style={{ fontSize: '13px', color: '#6b7280' }}>
                                {infoResponseFiles.length > 0 ? `${infoResponseFiles.length} file(s) selected` : 'Click to attach files (PDF, JPG, PNG)'}
                              </span>
                              <input
                                type="file"
                                multiple
                                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                                style={{ display: 'none' }}
                                onChange={e => setInfoResponseFiles(Array.from(e.target.files || []))}
                              />
                            </label>
                            {infoResponseFiles.length > 0 && (
                              <div style={{ marginBottom: '16px' }}>
                                {infoResponseFiles.map((f, i) => (
                                  <div key={i} style={{ fontSize: '11px', color: '#374151', padding: '4px 8px', background: '#f3f4f6', borderRadius: '4px', marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Ic.FileText size={11} /> {f.name}</span>
                                    <button
                                      onClick={() => setInfoResponseFiles(prev => prev.filter((_, idx) => idx !== i))}
                                      style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '12px' }}
                                    >✕</button>
                                  </div>
                                ))}
                              </div>
                            )}

                            <button
                              className="btn-primary"
                              style={{ width: '100%', padding: '14px', fontSize: '14px', fontWeight: '700', opacity: (!infoResponseText.trim() && infoResponseFiles.length === 0) ? 0.5 : 1 }}
                              disabled={infoResponseLoading || (!infoResponseText.trim() && infoResponseFiles.length === 0)}
                              onClick={handleInfoResponse}
                            >
                              {infoResponseLoading ? 'Submitting...' : 'Submit Response to Staff →'}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Application Content</span></div>
                    <div style={{ padding: '0 20px 20px' }}>
                      {isDetailLoading ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} aria-busy="true">
                          {[0, 1, 2, 3, 4].map(i => (
                            <div key={`detail-skel-${i}`} style={{ borderBottom: '1px solid #f1f5f9', paddingBottom: '12px' }}>
                              <span className="skeleton skeleton-line-xs" style={{ width: `${22 + (i * 13) % 30}%`, display: 'block', marginBottom: '8px' }} aria-hidden>·</span>
                              <span className="skeleton skeleton-line" style={{ width: `${48 + (i * 17) % 40}%`, display: 'block' }} aria-hidden>·</span>
                            </div>
                          ))}
                        </div>
                      ) : selectedApplication.answers && selectedApplication.answers.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                          {selectedApplication.answers.map((ans: any) => (
                            <div key={ans.id} style={{ borderBottom: '1px solid #f1f5f9', paddingBottom: '12px' }}>
                              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '6px', fontWeight: '500' }}>
                                {ans.label || ans.field_label}
                              </div>
                              <div style={{ fontSize: '14px', color: '#1e293b', lineHeight: '1.5' }}>
                                {ans.answer_text ? renderAnswerText(ans.answer_text) : (ans.answer_file ? 'Attachment Provided' : 'N/A')}
                                {ans.answer_file && (
                                  <div style={{ marginTop: '8px' }}>
                                    <a
                                      href={ans.answer_file}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="btn-ghost"
                                      style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                                    >
                                      View Attachment
                                    </a>
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ padding: '20px', textAlign: 'center', color: '#64748b' }}>No answer data found for this submission.</div>
                      )}
                    </div>
                  </div>

                  {selectedApplication.status === 'rejected' && (
                    <div className="sec-card" style={{ borderLeft: '4px solid #ef4444' }}>
                      <div className="sec-head">
                        <span className="sec-title" style={{ color: '#991b1b', display: 'flex', alignItems: 'center', gap: '6px' }}><Ic.XCircle size={14} /> Application Rejected</span>
                      </div>
                      <div style={{ padding: '0 20px 20px' }}>
                        {selectedApplication.decision_reason ? (
                          <>
                            <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px', fontWeight: '600', textTransform: 'uppercase' }}>Reason for Rejection</div>
                            <div style={{ fontSize: '14px', color: '#1e293b', fontStyle: 'italic', lineHeight: '1.6', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', padding: '12px 16px' }}>
                              "{selectedApplication.decision_reason}"
                            </div>
                          </>
                        ) : (
                          <div style={{ fontSize: '13px', color: '#64748b' }}>No reason was provided. Contact the DGG Education Department for details.</div>
                        )}
                        <div style={{ marginTop: '16px', fontSize: '12px', color: '#64748b' }}>
                          If you believe this decision was made in error, you may submit an appeal or contact the Education Department directly.
                        </div>
                        {selectedApplication.form_title?.toLowerCase().includes('admission') && (
                          <button className="btn-primary" style={{ marginTop: '16px' }} onClick={() => handleNavClick('admission')}>
                            Submit New Admission Application →
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                  {selectedApplication.decision_reason && selectedApplication.status !== 'rejected' && (
                    <div className="sec-card" style={{ borderLeft: '4px solid #3b82f6' }}>
                      <div className="sec-head"><span className="sec-title">Decision Notes from Staff</span></div>
                      <div style={{ padding: '0 20px 20px', fontSize: '14px', color: '#1e293b', fontStyle: 'italic' }}>
                        "{selectedApplication.decision_reason}"
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── DOCUMENTS VIEW ── */}
            {currentView === 'documents' && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <div className="view-title">My Documents</div>
                  <div className="view-actions">
                    <label className={`btn-primary ${isUploading ? 'loading' : ''}`} style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                      {isUploading ? 'Uploading...' : '+ Upload Document'}
                      <input type="file" onChange={handleFileUpload} style={{ display: 'none' }} disabled={isUploading} />
                    </label>
                  </div>
                </div>
                <div className="view-body">
                  <div className="sec-card">
                    <div className="sec-head">
                      <span className="sec-title">Uploaded Files</span>
                      <span className="sec-meta">
                        {isDocumentsLoading
                          ? <span className="ui-loading-inline"><span className="ui-spinner ui-spinner-sm" /> Loading…</span>
                          : `${documents.length} document(s)`}
                      </span>
                    </div>
                    <div className="table-wrap">
                      {isDocumentsLoading ? (
                        <table className="data-table" aria-busy="true">
                          <thead>
                            <tr>
                              <th>Name</th>
                              <th>Category</th>
                              <th>Uploaded</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[0, 1, 2, 3].map(i => (
                              <tr key={`skel-${i}`}>
                                <td>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <span className="skeleton" style={{ width: '18px', height: '18px', borderRadius: '4px' }} aria-hidden>·</span>
                                    <span className="skeleton skeleton-line" style={{ width: `${55 + (i * 9) % 35}%` }} aria-hidden>·</span>
                                  </div>
                                </td>
                                <td><span className="skeleton skeleton-badge" style={{ width: '62px' }} aria-hidden>·</span></td>
                                <td><span className="skeleton skeleton-line-xs" style={{ width: '60%' }} aria-hidden>·</span></td>
                                <td>
                                  <div style={{ display: 'flex', gap: '10px' }}>
                                    <span className="skeleton" style={{ width: '40px', height: '22px', borderRadius: '4px' }} aria-hidden>·</span>
                                    <span className="skeleton" style={{ width: '48px', height: '22px', borderRadius: '4px' }} aria-hidden>·</span>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : documents.length > 0 ? (
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Name</th>
                              <th>Category</th>
                              <th>Uploaded</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {documents.map((doc) => (
                              <tr key={doc.id}>
                                <td style={{ fontWeight: '600' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Icons.Documents />
                                    {doc.name}
                                  </div>
                                </td>
                                <td><span className="form-tag" style={{ fontSize: '10px' }}>{doc.category || 'General'}</span></td>
                                <td style={{ fontSize: '11px', color: '#64748b' }}>{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                                <td>
                                  <div style={{ display: 'flex', gap: '12px' }}>
                                    <a href={doc.file} target="_blank" rel="noopener noreferrer" className="btn-ghost" style={{ fontSize: '11px', padding: '4px 8px' }}>View</a>
                                    <button onClick={() => handleDeleteDocument(doc.id)} className="btn-ghost" style={{ fontSize: '11px', padding: '4px 8px', color: '#ef4444', borderColor: 'transparent' }}>Delete</button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div className="empty-state" style={{ padding: '60px 0' }}>
                          <Icons.Documents />
                          <div className="empty-title">No Documents Found</div>
                          <div className="empty-desc">Upload important documents like Transcripts, ID, or Void Checks here for easy access during applications.</div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="sec-card" style={{ background: '#f8fafc', border: '1px dashed #cbd5e1' }}>
                    <div className="sec-head"><span className="sec-title">Document Requirements</span></div>
                    <div style={{ padding: '0 20px 20px 20px', fontSize: '13px', color: '#475569' }}>
                      <p>For faster application processing, please ensure your documents meet these criteria:</p>
                      <ul style={{ marginTop: '10px', paddingLeft: '20px' }}>
                        <li style={{ marginBottom: '6px' }}>Files must be in PDF, JPG, or PNG format</li>
                        <li style={{ marginBottom: '6px' }}>Maximum file size per document is 10MB</li>
                        <li style={{ marginBottom: '6px' }}>Ensure all text is clearly legible in scanned copies</li>
                        <li style={{ marginBottom: '6px' }}>Include your name and date on unofficial transcripts</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ── HELP & FAQ VIEW ── */}
            {currentView === 'help' && (
              <div className="view-content fade-in">
                <div className="view-header"><div className="view-title">Help & FAQ</div></div>
                <div className="view-body">
                  <div className="sec-card contact-card">
                    <div className="sec-head"><span className="sec-title">Contact Support</span></div>
                    <div className="contact-grid">
                      <div className="contact-item">
                        <div className="contact-label">Email Support</div>
                        <div className="contact-val">{sysConfig['contact_email'] || 'education.support@gov.deline.ca'}</div>
                      </div>
                      <div className="contact-item">
                        <div className="contact-label">Phone</div>
                        <div className="contact-val">{sysConfig['contact_phone'] || '(867) 589-3515 ext. 1110'}</div>
                      </div>
                      <div className="contact-item">
                        <div className="contact-label">Mailing Address</div>
                        <div className="contact-val">{sysConfig['contact_address'] || 'P.O. Box 156, Délı̨nę, NT X0E 0G0'}</div>
                      </div>
                    </div>
                  </div>

                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Frequently Asked Questions</span></div>
                    {[
                      { q: "How is my enrollment verified?", a: "Enrollment verification is requested from your registrar automatically once your application or renewal is submitted." },
                      { q: "How do I claim travel?", a: `Submit a Travel Claim within ${sysConfig['travel_claim_days'] || '30'} days of travel and include all receipts.` }
                    ].map((item, i) => (
                      <div className="faq-item" key={i}>
                        <div className="faq-q" onClick={() => setOpenFaqIndex(openFaqIndex === i ? null : i)}>
                          {item.q}
                          <span className={`faq-chevron ${openFaqIndex === i ? 'open' : ''}`}><Icons.ChevronRight /></span>
                        </div>
                        <div className={`faq-a ${openFaqIndex === i ? 'open' : ''}`}>
                          {item.a}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── ADMISSION APPLICATION VIEW ── */}
            {currentView === 'admission' && (() => {
              if (isLoading && applications.length === 0) {
                return <div className="view-content fade-in" style={{ padding: '40px', textAlign: 'center' }}>Loading your application status...</div>;
              }

              const admissionApp = applications.find((a: any) => {
                const title = (a.form_title || '').toLowerCase();
                const type = (a.form_type || '').toLowerCase();
                return title.includes('admission') || title.includes('form a') || type.includes('psssp') || type.includes('form a');
              });
              const isRejected = admissionApp?.status === 'rejected';
              const isActive = admissionApp && !isRejected;

              if (isActive) {
                return (
                  <div className="view-content fade-in">
                    <div className="view-header">
                      <button className="btn-ghost" onClick={() => handleNavClick('dashboard')}>← Back</button>
                      <div className="view-title">Admission Application</div>
                    </div>
                    <div className="view-body">
                      <div className="sec-card" style={{ borderLeft: '4px solid #3182ce' }}>
                        <div className="sec-head">
                          <span className="sec-title">Application Already Submitted</span>
                          <span style={{ padding: '4px 10px', borderRadius: '4px', fontSize: '9px', fontWeight: '800', background: '#f0f9ff', color: '#075985', border: '1px solid #bae6fd' }}>
                            {admissionApp.status.toUpperCase()}
                          </span>
                        </div>
                        <div style={{ padding: '20px', fontSize: '14px', color: '#1e293b', lineHeight: '1.6' }}>
                          <p>You have already submitted an Admission Application (Ref #{admissionApp.id.toString().padStart(6, '0')}). Only one active admission application is permitted at a time.</p>
                          <p style={{ marginTop: '12px', color: '#64748b', fontSize: '13px' }}>You may submit a new Admission Application only after your current application has been reviewed and a decision rendered. If your application is denied, you will be able to reapply.</p>
                        </div>
                        <div style={{ padding: '0 20px 20px', display: 'flex', gap: '12px' }}>
                          <button className="btn-primary" onClick={() => handleViewApplication(admissionApp)}>View My Application →</button>
                          <button className="btn-ghost" onClick={() => handleNavClick('applications')}>All Applications</button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              }

              return (
                <div className="view-content fade-in">
                  {isRejected && (
                    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderLeft: '4px solid #ef4444', borderRadius: '8px', padding: '20px', marginBottom: '24px' }}>
                      <div style={{ fontWeight: '800', fontSize: '13px', color: '#991b1b', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}><Ic.AlertTriangle size={13} /> Previous Application Rejected</div>
                      <div style={{ fontSize: '13px', color: '#7f1d1d', lineHeight: '1.6' }}>
                        Your previous Admission Application (Ref #{admissionApp.id.toString().padStart(6, '0')}) was rejected by the Director.
                      </div>
                      {admissionApp.decision_reason && (
                        <div style={{ marginTop: '12px', background: '#fff', border: '1px solid #fecaca', borderRadius: '6px', padding: '12px 16px' }}>
                          <div style={{ fontSize: '11px', fontWeight: '700', color: '#991b1b', textTransform: 'uppercase', marginBottom: '4px' }}>Reason for Rejection</div>
                          <div style={{ fontSize: '13px', color: '#1e293b', fontStyle: 'italic' }}>"{admissionApp.decision_reason}"</div>
                        </div>
                      )}
                      <div style={{ marginTop: '12px', fontSize: '12px', color: '#64748b' }}>
                        You may submit a new Admission Application below. Please address the reason above before reapplying.
                      </div>
                    </div>
                  )}
                  <FormA
                    profile={profile}
                    onBack={() => handleNavClick('dashboard')}
                    onComplete={() => handleFormComplete('Admission Application')}
                  />
                </div>
              );
            })()}

            {/* ── CONTINUING FUNDING VIEW ── */}
            {currentView === 'continuing-funding' && (
              <FormC
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Continuing Funding')}
              />
            )}

            {/* ── INFORMATION UPDATE VIEW ── */}
            {currentView === 'information-update' && (
              <FormD
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Information Update')}
                onNavigate={(view: any) => handleNavClick(view)}
              />
            )}

            {/* ── TRAVEL CLAIM VIEW ── */}
            {currentView === 'travel-claim' && (
              <FormE
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Travel Claim')}
              />
            )}

            {/* ── PRACTICUM REPORT VIEW ── */}
            {currentView === 'practicum-report' && (
              <FormF
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Practicum Report')}
              />
            )}

            {/* \u2500\u2500 PROFILE VIEW \u2500\u2500 */}
            {currentView === 'profile' && (
              <StudentProfile profile={profile} />
            )}

            {/* ── GRADUATION AWARD VIEW ── */}
            {currentView === 'graduation-award' && (
              <FormG
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Graduation Award')}
              />
            )}

            {/* ── SCHOLARSHIP VIEW ── */}
            {currentView === 'scholarship' && (
              <AcademicScholarship
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Scholarship')}
              />
            )}

            {/* ── HARDSHIP BURSARY VIEW ── */}
            {currentView === 'hardship' && (
              <HardshipBursary
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Hardship Bursary')}
              />
            )}

            {/* ── APPEAL REQUEST VIEW ── */}
            {currentView === 'appeal-request' && (
              <FormH
                profile={profile}
                onBack={() => handleNavClick('dashboard')}
                onComplete={() => handleFormComplete('Appeal Request')}
              />
            )}

          </div>
        </div>
      </div>

      {/* Error Popup Modal */}
      {errorPopup && (
        <div className="error-popup-overlay" onClick={() => setErrorPopup(null)}>
          <div className="error-popup" onClick={e => e.stopPropagation()}>
            <div className="error-popup-icon"><Ic.AlertTriangle size={24} /></div>
            <div className="error-popup-title">Upload Failed</div>
            <div className="error-popup-message">{errorPopup}</div>
            <button className="error-popup-close" onClick={() => setErrorPopup(null)}>Dismiss</button>
          </div>
        </div>
      )}


      {/* Submitted Form Restriction Modal */}
      {submittedFormPopup && (
        <div className="modal-overlay" style={{ zIndex: 3000 }}>
          <div className="modal-card" style={{ maxWidth: '450px', textAlign: 'center', padding: '40px 32px' }}>
             <div style={{ marginBottom: '20px', color: '#1e293b' }}><Ic.FileText size={48} /></div>
             <h2 style={{ fontSize: '20px', fontWeight: '800', color: '#1e293b', marginBottom: '12px' }}>Already Submitted</h2>
             <p style={{ fontSize: '14px', color: '#64748b', lineHeight: '1.6', marginBottom: '24px' }}>
               Your <strong>{submittedFormPopup}</strong> has already been submitted and is currently being reviewed by DGG staff. You cannot submit another until a decision has been reached.
             </p>
             <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
               <button className="btn-primary" style={{ width: '100%' }} onClick={() => {
                 const app = applications.find(a => a.form_title?.includes(submittedFormPopup));
                 if (app) handleViewApplication(app);
                 setSubmittedFormPopup(null);
               }}>Track Application Status</button>
               <button className="btn-ghost" style={{ width: '100%' }} onClick={() => setSubmittedFormPopup(null)}>Dismiss</button>
             </div>
          </div>
        </div>
      )}

      {/* Paper Forms Download Center Modal */}
      {showPaperFormsModal && (
        <div className="modal-overlay" style={{ zIndex: 3000 }} onClick={() => setShowPaperFormsModal(false)}>
          <div className="modal-card" style={{ maxWidth: '700px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', position: 'relative', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setShowPaperFormsModal(false)}
              style={{ 
                position: 'absolute', 
                top: '12px', 
                right: '12px', 
                background: '#f1f5f9', 
                border: 'none', 
                borderRadius: '6px', 
                width: '32px', 
                height: '32px', 
                cursor: 'pointer',
                fontSize: '18px',
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 10
              }}
            >✕</button>
            
            <div className="modal-body" style={{ flex: 1, overflowY: 'auto', padding: 0 }}>
              <div style={{ 
                padding: '16px', 
                background: '#eff6ff', 
                borderRadius: '8px', 
                border: '1px solid #bfdbfe',
                marginBottom: '20px' 
              }}>
                <div style={{ fontSize: '12px', color: '#1e40af', lineHeight: '1.6' }}>
                  <strong>Mail or deliver completed forms to:</strong><br />
                  <div style={{ marginTop: '8px', paddingLeft: '20px' }}>
                    Department of Education, Délı̨nę Got'ı̨nę Government<br />
                    P.O. Box 156 Délı̨nę, NT X0E 0G0<br />
                    Ph: (867) 589-3515 ext. 1110
                  </div>
                </div>
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {availableForms.length > 0 ? (
                  availableForms.map(form => (
                    <div 
                      key={form.id} 
                      style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center', 
                        padding: '14px 16px', 
                        background: '#ffffff', 
                        borderRadius: '8px', 
                        border: '1px solid #e2e8f0',
                        transition: 'all 0.2s',
                        cursor: 'pointer'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#3b82f6';
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(59, 130, 246, 0.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#e2e8f0';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: '700', fontSize: '14px', color: '#1e293b', marginBottom: '2px' }}>{form.title}</div>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>{form.description || 'Download this form'}</div>
                      </div>
                      <button
                        className="btn-ghost" 
                        style={{ 
                          padding: '8px 16px', 
                          fontSize: '12px', 
                          fontWeight: '700', 
                          color: '#3b82f6', 
                          background: '#eff6ff',
                          border: '1px solid #bfdbfe',
                          whiteSpace: 'nowrap'
                        }}
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            // Download PDF from backend API
                            const blob = await API.downloadFormPDF(form.id);
                            const url = URL.createObjectURL(blob);
                            const link = document.createElement('a');
                            link.href = url;
                            link.download = `${form.title.replace(/\s+/g, '_')}.pdf`;
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                            URL.revokeObjectURL(url);
                            setShowToast(`✓ ${form.title} downloaded`);
                          } catch (err: any) {
                            console.error('PDF download failed:', err);
                            setShowToast(`✕ Failed to download ${form.title}`);
                          }
                        }}
                      >
                        <Ic.Download size={14} /> Download PDF
                      </button>
                    </div>
                  ))
                ) : (
                  <div style={{ padding: '20px', textAlign: 'center', color: '#64748b' }}>
                    Loading forms...
                  </div>
                )}
              </div>
            </div>
            
            <div className="modal-footer" style={{ 
              borderTop: '1px solid #e2e8f0', 
              paddingTop: '16px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic' }}>
                PDFs are pre-formatted for standard letter paper
              </div>
              <button 
                className="btn-primary" 
                onClick={() => setShowPaperFormsModal(false)}
                style={{ padding: '10px 24px' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Popup */}
      <div className={`toast ${showToast ? 'show' : ''} ${showToast && !showToast.includes('fail') && !showToast.includes('Error') && !showToast.includes('DENIED') ? 'toast-success' : showToast ? 'toast-error' : ''}`}>
        {showToast && showToast.includes('fail') ? '✕ ' : showToast ? '✓ ' : ''}{showToast}
      </div>
    </div>
  );
};

export default Dashboard;
