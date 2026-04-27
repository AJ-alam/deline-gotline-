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
import AcademicScholarship from './Forms/AcademicScholarship';
import StudentProfile from './StudentProfile';

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
  | 'graduation-award'
  | 'appeal-request'
  | 'scholarship';

// SVG Icons for professional look
const Icons = {
  Home: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>
  ),
  Files: () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14.5 2 14.5 7.5 20 7.5" /></svg>
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
  const [profile, setProfile] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [documents, setDocuments] = useState<any[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedApplication, setSelectedApplication] = useState<any>(null);

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
        }
      }
    } else if (segments.length === 1 && segments[0] === 'dashboard') {
      setCurrentView('dashboard');
    }
  }, [location.pathname, location.search, applications.length]);

  const handleViewApplication = (app: any) => {
    setSelectedApplication(app);
    setCurrentView('application-detail');
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
    const subsPromise = API.getSubmissions().then((resp: any) => {
      console.log('Submissions loaded:', resp);
      if (Array.isArray(resp)) {
        setApplications(resp);
      } else if (resp && resp.results && Array.isArray(resp.results)) {
        setApplications(resp.results);
      } else {
        setApplications([]);
      }
    });

    const userPromise = API.getMe().then((resp: any) => {
      setProfile(resp);
    });

    const notifsPromise = API.getNotifications().then((resp: any) => {
      setNotifications(Array.isArray(resp) ? resp : []);
    });

    try {
      // Wait for at least the essential profile/submissions to finish the loading state
      // but let them all run in parallel
      await Promise.allSettled([subsPromise, userPromise, notifsPromise]);
    } catch (err: any) {
      console.error('Failed to fetch dashboard data:', err);
      if (err.status === 401) {
        handleLogout();
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ── POLLING FOR REAL-TIME UPDATES ──
  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 15000); // 15-second polling
    return () => clearInterval(interval);
  }, []);

  const fetchDocuments = async () => {
    try {
      const resp = await API.getUserDocuments();
      setDocuments(Array.isArray(resp) ? resp : []);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
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
      return { title: '1. Getting Started', milestone: '📄 Start Admission Application to begin', pips: [true, false, false] };
    }

    const latest = applications[0]; // Ordered by -submitted_at in backend

    if (latest.status === 'accepted') return { title: '4. Funding Active', milestone: '✅ Disbursement Phase', pips: [true, true, true] };
    if (latest.status === 'rejected') return { title: 'Policy Notice', milestone: '❌ Application Rejected', pips: [true, true, true] };
    if (latest.status === 'forwarded') return { title: '3. Final Approval', milestone: '⚖️ In Director Queue', pips: [true, true, true] };
    if (latest.status === 'reviewed') return { title: '2. Review Process', milestone: '⏳ SSW Reviewed', pips: [true, true, false] };

    return { title: '1. Submitted', milestone: '📄 Awaiting Staff Review', pips: [true, false, false] };
  };

  const stage = getJourneyStage();

  const handleLogout = () => {
    localStorage.removeItem('dgg_token');
    localStorage.removeItem('dgg_refresh');
    navigate('/signin');
  };

  useEffect(() => {
    if (showToast) {
      const timer = setTimeout(() => setShowToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [showToast]);

  const handleFormComplete = (_label?: string) => {
    setShowToast(`✓ Submission successful · You will receive an email confirmation`);
    navigate('/dashboard/applications');
    setIsMobileMenuOpen(false);
    fetchDashboardData();
  };

  const handleNavClick = (view: DashboardView) => {
    console.log('Navigating to:', view);
    setIsMobileMenuOpen(false);

    // Always clear selected application when moving to a non-detail view
    if (view !== 'application-detail') {
      setSelectedApplication(null);
    }

    navigate(`/dashboard/${view}`);
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
          <div className="user-meta">{profile?.beneficiary_number ? `ID: ${profile.beneficiary_number}` : 'ID: Pending'} · Student</div>
        </div>

        <div className="sidebar-section-title">Main</div>
        {renderSidebarNav('dashboard', 'Dashboard', <Icons.Home />)}
        {renderSidebarNav('profile', 'My Profile', <Icons.Info />)}
        {renderSidebarNav('applications', 'My Applications', <Icons.Files />)}
        {renderSidebarNav('payments', 'My Payments', <Icons.Payments />)}
        {renderSidebarNav('documents', 'My Documents', <Icons.Documents />)}
        {renderSidebarNav('notifications', 'Notifications', <Icons.Bell />)}

        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Applications</div>
        {renderSidebarNav('admission', 'Admission Application', <Icons.Files />)}
        {renderSidebarNav('continuing-funding', 'Continuing Funding', <Icons.Files />)}
        {renderSidebarNav('information-update', 'Information Update', <Icons.Files />)}

        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Claims</div>
        {renderSidebarNav('travel-claim', 'Travel Claim', <Icons.Files />)}
        {renderSidebarNav('practicum-report', 'Practicum Report', <Icons.Files />)}
        {renderSidebarNav('graduation-award', 'Graduation Award', <Icons.Files />)}
        {renderSidebarNav('appeal-request', 'Appeal Request', <Icons.Files />)}

        <div className="sidebar-divider"></div>

        <div className="sidebar-section-title">Special</div>
        {renderSidebarNav('scholarship', 'Academic Scholarship', <Icons.Files />)}

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
            <span className="top-nav-link" onClick={() => handleNavClick('payments')}>Payments</span>
            <span className="top-nav-link" onClick={() => handleNavClick('notifications')}>
              Notifications {unreadCount > 0 && <span className="nav-badge">{unreadCount}</span>}
            </span>
          </div>
        </div>

        <div className="main-content">
          <div className="deadline-bar">
            <span className="dl-item"><span className="dl-label">Fall deadline</span><span className="dl-date">Aug 1</span></span>
            <span className="dl-sep">·</span>
            <span className="dl-item"><span className="dl-label">Winter</span><span className="dl-date">Dec 1</span></span>
            <span className="dl-sep">·</span>
            <span className="dl-item"><span className="dl-label">Travel claims</span><span className="dl-urgent">within 30 days of travel</span></span>
          </div>

          <div className="view-container">

            {/* ── DASHBOARD VIEW ── */}
            {currentView === 'dashboard' && (
              <div className="view-content fade-in">
                <div className="view-header">
                  <div className="view-title">Dashboard</div>
                  <button className="btn-primary" onClick={() => handleNavClick('admission')}>+ Start Your Application</button>
                </div>
                <div className="view-body">
                  {applications.length === 0 && (
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
                  )}


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
                      <div
                        className={`form-card primary-card ${!applications.some(a => a.form_title?.toLowerCase().includes('admission')) ? 'active-step' : ''}`}
                        onClick={() => {
                          const admissionApp = applications.find(a => a.form_title?.toLowerCase().includes('admission'));
                          if (admissionApp) {
                            handleViewApplication(admissionApp);
                          } else {
                            handleNavClick('admission');
                          }
                        }}
                      >
                        <div className="form-card-inner">
                          <div className="form-card-header">
                            <span className="form-tag">New File</span>
                            {!applications.some(a => a.form_title?.toLowerCase().includes('admission')) && (
                              <span className="recommended-tag"><Icons.Star /> RECOMMENDED NEXT STEP</span>
                            )}
                            {applications.some(a => a.form_title?.toLowerCase().includes('admission')) && (
                              <span className="form-tag" style={{ background: '#f0fdf4', color: '#166534', borderColor: '#bbf7d0' }}>✓ SUBMITTED</span>
                            )}
                          </div>
                          <div className="form-card-title">Admission Application</div>
                          <div className="form-card-desc">
                            {applications.some(a => a.form_title?.toLowerCase().includes('admission'))
                              ? 'Your admission application has been received and is currently being processed by staff.'
                              : 'Your gateway to all DGG funding. Complete this first to map your eligibility.'}
                          </div>
                          <div style={{ fontSize: '9px', color: '#718096', marginBottom: '12px' }}>Required once per program · Establishes your stream</div>
                          {applications.some(a => a.form_title?.toLowerCase().includes('admission')) ? (
                            <button className="btn-ghost form-btn" style={{ background: '#fff', borderColor: '#e2e8f0' }}>View Application &nbsp;<Icons.ChevronRight /></button>
                          ) : (
                            <button className="btn-auth-primary form-btn">Start Application &nbsp;<Icons.ChevronRight /></button>
                          )}
                        </div>
                      </div>
                      <div className="form-card" style={{ borderLeft: '3px solid #3182ce', opacity: 0.9 }}>
                        <div className="form-card-inner">
                          <div className="form-card-header">
                            <span className="form-tag" style={{ background: '#ebf8ff', color: '#2b6cb0', border: '1px solid #bee3f8' }}>Enrolment</span>
                            <span style={{ fontSize: '8px', color: '#dd6b20', fontWeight: '700' }}>⏳ Tracking Active</span>
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
                    <div className="paper-icon">🖨️</div>
                    <div className="paper-text">
                      <div className="paper-text-title">Prefer paper forms?</div>
                      <div className="paper-text-desc">
                        You can download printable versions of all DGG forms to fill out by hand.
                        Once completed, you can mail them to the DGG office or drop them off in person.
                      </div>
                      <button className="btn-ghost" style={{ fontWeight: 700, color: '#2b6cb0', borderColor: '#bee3f8' }}>
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
                                    background: app.status === 'accepted' ? '#f0fdf4' : app.status === 'rejected' ? '#fef2f2' : '#f0f9ff',
                                    color: app.status === 'accepted' ? '#166534' : app.status === 'rejected' ? '#991b1b' : '#075985',
                                    border: `1px solid ${app.status === 'accepted' ? '#bbf7d0' : app.status === 'rejected' ? '#fecaca' : '#bae6fd'}`
                                  }}>
                                    {app.status.toUpperCase()}
                                  </span>
                                </td>
                                <td style={{ fontSize: '10px', color: '#64748b' }}>
                                  {app.status === 'pending' ? 'Under Review' : app.status === 'accepted' ? 'Funds Authorized' : app.status === 'reviewed' ? 'SSW Reviewed' : 'Policy Non-Compliance'}
                                </td>
                                <td>
                                  <button
                                    className="btn-ghost"
                                    style={{ padding: '4px 8px', fontSize: '10px' }}
                                    onClick={() => handleViewApplication(app)}
                                  >
                                    View Details
                                  </button>
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
                  <div className="kpi-row">
                    <div className="kpi-card"><div className="kpi-val">${getApprovedTotal().toLocaleString()}</div><div className="kpi-label">Authorized Total</div></div>
                    <div className="kpi-card"><div className="kpi-val">${getApprovedTotal().toLocaleString()}</div><div className="kpi-label">Paid To Date</div></div>
                    <div className="kpi-card"><div className="kpi-val">$0</div><div className="kpi-label">Remaining Balance</div></div>
                    <div className="kpi-card"><div className="kpi-val">$0</div><div className="kpi-label">Upcoming Scheduled</div></div>
                  </div>
                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Payment History & Schedule</span></div>
                    <div className="empty-state">
                      <Icons.Payments />
                      <div className="empty-title">No Payments Scheduled</div>
                      <div className="empty-desc">Your payment schedule will appear here after your application is approved by the Director.</div>
                    </div>
                  </div>
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

                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Application Content</span></div>
                    <div style={{ padding: '0 20px 20px' }}>
                      {selectedApplication.answers && selectedApplication.answers.length > 0 ? (
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

                  {selectedApplication.decision_notes && (
                    <div className="sec-card" style={{ borderLeft: '4px solid #3b82f6' }}>
                      <div className="sec-head"><span className="sec-title">Decision Notes from Staff</span></div>
                      <div style={{ padding: '0 20px 20px', fontSize: '14px', color: '#1e293b', fontStyle: 'italic' }}>
                        "{selectedApplication.decision_notes}"
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
                      <span className="sec-meta">{documents.length} document(s)</span>
                    </div>
                    <div className="table-wrap">
                      {documents.length > 0 ? (
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
                        <div className="contact-val">education.support@gov.deline.ca</div>
                      </div>
                      <div className="contact-item">
                        <div className="contact-label">Phone</div>
                        <div className="contact-val">(867) 589-3515 ext. 1110</div>
                      </div>
                      <div className="contact-item">
                        <div className="contact-label">Mailing Address</div>
                        <div className="contact-val">P.O. Box 156, Délı̨nę, NT X0E 0G0</div>
                      </div>
                    </div>
                  </div>

                  <div className="sec-card">
                    <div className="sec-head"><span className="sec-title">Frequently Asked Questions</span></div>
                    {[
                      { q: "How is my enrollment verified?", a: "Enrollment verification is requested from your registrar automatically once your application or renewal is submitted." },
                      { q: "How do I claim travel?", a: "Submit a Travel Claim within 30 days of travel and include all receipts." }
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
            {currentView === 'admission' && (
              <FormA
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Admission Application')}
              />
            )}

            {/* ── CONTINUING FUNDING VIEW ── */}
            {currentView === 'continuing-funding' && (
              <FormC
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Continuing Funding')}
              />
            )}

            {/* ── INFORMATION UPDATE VIEW ── */}
            {currentView === 'information-update' && (
              <FormD
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Information Update')}
                onNavigate={(view: any) => setCurrentView(view)}
              />
            )}

            {/* ── TRAVEL CLAIM VIEW ── */}
            {currentView === 'travel-claim' && (
              <FormE
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Travel Claim')}
              />
            )}

            {/* ── PRACTICUM REPORT VIEW ── */}
            {currentView === 'practicum-report' && (
              <FormF
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Practicum Report')}
              />
            )}

            {/* ── GRADUATION AWARD VIEW ── */}
            {currentView === 'graduation-award' && (
              <FormG
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Graduation Award')}
              />
            )}

            {/* ── APPEAL REQUEST VIEW ── */}
            {currentView === 'appeal-request' && (
              <FormH
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Appeal Request')}
              />
            )}

            {/* \u2500\u2500 ACADEMIC SCHOLARSHIP VIEW \u2500\u2500 */}

            {/* \u2500\u2500 SCHOLARSHIP VIEW \u2500\u2500 */}
            {currentView === 'scholarship' && (
              <AcademicScholarship
                profile={profile}
                onBack={() => setCurrentView('dashboard')}
                onComplete={() => handleFormComplete('Scholarship')}
              />
            )}

            {/* \u2500\u2500 PROFILE VIEW \u2500\u2500 */}
            {currentView === 'profile' && (
              <StudentProfile profile={profile} />
            )}

          </div>
        </div>
      </div>

      {/* Error Popup Modal */}
      {errorPopup && (
        <div className="error-popup-overlay" onClick={() => setErrorPopup(null)}>
          <div className="error-popup" onClick={e => e.stopPropagation()}>
            <div className="error-popup-icon">⚠️</div>
            <div className="error-popup-title">Upload Failed</div>
            <div className="error-popup-message">{errorPopup}</div>
            <button className="error-popup-close" onClick={() => setErrorPopup(null)}>Dismiss</button>
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
