import React, { useState, useEffect, useRef } from 'react';
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
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showRequestInfoModal, setShowRequestInfoModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectReasonError, setRejectReasonError] = useState<string | null>(null);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [reportFundingType, setReportFundingType] = useState('all');
  const [reportSubFilter, setReportSubFilter] = useState('students');
  const [showFinanceModal, setShowFinanceModal] = useState(false);
  const [financeEmail, setFinanceEmail] = useState('finance@organization.com');
  const [isExporting, setIsExporting] = useState(false);
  const [isPdfExporting, setIsPdfExporting] = useState(false);
  const [showShareLinkModal, setShowShareLinkModal] = useState(false);
  const [shareLinkUrl, setShareLinkUrl] = useState('');
  const [isGeneratingShareLink, setIsGeneratingShareLink] = useState(false);
  const [shareLinkCopied, setShareLinkCopied] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const navigate = useNavigate();

  // ── TOAST HELPER ──
  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

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

  // â”€â”€ FORCE STOP LOADER AFTER 3 SECONDS FOR UI RESPONSIVENESS â”€â”€
  useEffect(() => {
    const timer = setTimeout(() => {
      if (isLoading) setIsLoading(false);
    }, 3000);
    return () => clearTimeout(timer);
  }, [isLoading]);

  // â”€â”€ POLLING FOR REAL-TIME UPDATES â”€â”€
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
      showToast('Export failed', 'error');
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
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const noteTextareaRef = useRef<HTMLTextAreaElement>(null);

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
      const statusLabel = status === 'accepted' ? 'approved' : status === 'rejected' ? 'rejected' : 'forwarded to director';
      showToast(`✓ Application #${selectedAppId} ${statusLabel} successfully`);
      setCurrentView(role === 'director' ? 'director-queue' : 'applications');
      fetchApplications();
    } catch (err: any) {
      showToast(err.message || 'Action failed', 'error');
    }
  };

  const handleRejectWithReason = async () => {
    if (!selectedAppId) return;
    if (!rejectReason.trim()) {
      setRejectReasonError('A reason for rejection is required.');
      return;
    }
    try {
      await API.updateSubmissionStatus(Number(selectedAppId), 'rejected', {
        decision_notes: rejectReason.trim(),
      });
      setShowRejectModal(false);
      setRejectReason('');
      setRejectReasonError(null);
      showToast(`✓ Application #${selectedAppId} rejected`);
      setCurrentView(role === 'director' ? 'director-queue' : 'applications');
      fetchApplications();
    } catch (err: any) {
      showToast(err.message || 'Rejection failed', 'error');
    }
  };

  const handleShareView = async () => {
    if (!selectedAppId) return;
    setIsGeneratingShareLink(true);
    setShareLinkUrl('');
    setShareLinkCopied(false);
    setShowShareLinkModal(true);
    try {
       const resp = await API.generateShareLink(Number(selectedAppId)) as any;
       const url = `${window.location.origin}/shared/${resp.token}`;
       setShareLinkUrl(url);
    } catch (err: any) {
       setShowShareLinkModal(false);
       showToast('Share failed: ' + err.message, 'error');
    } finally {
       setIsGeneratingShareLink(false);
    }
  };

  const handleCopyShareLink = async () => {
    if (!shareLinkUrl) return;
    try {
      await navigator.clipboard.writeText(shareLinkUrl);
      setShareLinkCopied(true);
      setTimeout(() => setShareLinkCopied(false), 3000);
    } catch {
      // Fallback for browsers that don't support clipboard API
      const input = document.createElement('input');
      input.value = shareLinkUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      setShareLinkCopied(true);
      setTimeout(() => setShareLinkCopied(false), 3000);
    }
  };

  const handleRequestInfo = async () => {
    if (!selectedAppId) return;
    try {
       await API.requestMoreInfo(Number(selectedAppId));
       setShowRequestInfoModal(false);
       showToast(`✓ More information requested from student for application #${selectedAppId}`);
       fetchApplications();
    } catch (err: any) {
       showToast('Action failed: ' + err.message, 'error');
    }
  };

  const handlePDFExport = () => {
    if (!selectedAppId || isPdfExporting) return;
    const app = applications.find(a => String(a.id) === String(selectedAppId));
    if (!app) {
      alert('Application data not found. Please refresh.');
      return;
    }

    setIsPdfExporting(true);
    try {
      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const marginLeft = 20;
      const marginRight = 20;
      const contentWidth = pageWidth - marginLeft - marginRight;
      let y = 20;

      // Helper: check if we need a new page
      const checkPageBreak = (neededHeight: number = 10) => {
        if (y + neededHeight > pageHeight - 20) {
          doc.addPage();
          y = 20;
        }
      };

      // Helper: draw a section header
      const drawSectionHeader = (title: string) => {
        checkPageBreak(14);
        doc.setFillColor(30, 41, 59);
        doc.rect(marginLeft, y, contentWidth, 8, 'F');
        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text(title.toUpperCase(), marginLeft + 4, y + 5.5);
        doc.setTextColor(30, 41, 59);
        y += 12;
      };

      // Helper: draw a key-value field
      const drawField = (label: string, value: string, colOffset: number = 0, colWidth: number = contentWidth) => {
        checkPageBreak(10);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(100, 116, 139);
        doc.text(label.toUpperCase(), marginLeft + colOffset, y);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(30, 41, 59);
        doc.setFontSize(8);
        const valueLines = doc.splitTextToSize(value || 'N/A', colWidth - 4);
        doc.text(valueLines, marginLeft + colOffset, y + 4);
        y += 4 + (valueLines.length * 4);
      };

      // Helper: draw fields side by side
      const drawFieldRow = (fields: Array<{ label: string; value: string }>) => {
        const colWidth = contentWidth / fields.length;
        const startY = y;
        let maxY = y;
        fields.forEach((f, i) => {
          y = startY;
          drawField(f.label, f.value, i * colWidth, colWidth);
          if (y > maxY) maxY = y;
        });
        y = maxY + 4;
      };

      // HEADER
      doc.setFillColor(252, 250, 248);
      doc.rect(0, 0, pageWidth, 28, 'F');
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(30, 41, 59);
      doc.text('Deline Got\u02bcine Government', marginLeft, 12);
      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(100, 116, 139);
      doc.text('Student Funding Application \u2014 Official Summary', marginLeft, 19);
      doc.setDrawColor(229, 166, 98);
      doc.setLineWidth(1);
      doc.line(marginLeft, 24, pageWidth - marginRight, 24);
      y = 32;

      doc.setFontSize(7);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(100, 116, 139);
      const exportDate = new Date().toLocaleString('en-CA', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      doc.text(`Reference: #${app.id}   |   Exported: ${exportDate}   |   Role: ${role === 'director' ? 'Director' : 'Staff'}`, marginLeft, y);
      y += 10;

      // 1. STUDENT INFORMATION
      drawSectionHeader('1. Student Information');
      const student = app.student_details || {};
      drawFieldRow([
        { label: 'Full Name', value: student.full_name || 'N/A' },
        { label: 'Beneficiary #', value: student.beneficiary_number || 'N/A' },
      ]);
      drawFieldRow([
        { label: 'Email', value: student.email || 'N/A' },
        { label: 'Phone', value: student.phone || 'N/A' },
      ]);
      drawFieldRow([
        { label: 'Date of Birth', value: student.dob || 'N/A' },
        { label: 'Enrollment Status', value: student.enrollment_status || 'N/A' },
      ]);
      y += 2;

      // 2. APPLICATION DETAILS
      drawSectionHeader('2. Application Details');
      drawFieldRow([
        { label: 'Form Type', value: getFormDisplayName(app.form_title || app.form?.title || 'N/A') },
        { label: 'Status', value: (app.status || 'pending').toUpperCase() },
      ]);
      drawFieldRow([
        { label: 'Submitted', value: app.submitted_at ? new Date(app.submitted_at).toLocaleDateString('en-CA') : 'N/A' },
        { label: 'Decided', value: app.decided_at ? new Date(app.decided_at).toLocaleDateString('en-CA') : 'Pending' },
      ]);
      if (app.decision_notes) {
        drawField('Decision Notes', app.decision_notes);
      }
      y += 2;

      // 3. FORM SUBMISSION DATA
      const answers: any[] = app.answers || [];
      if (answers.length > 0) {
        drawSectionHeader('3. Form Submission Data');
        const isFileAns = (a: any) => {
          const text = a.answer_text || '';
          return a.answer_file || text.startsWith('http') || text.startsWith('/media/') || /\.(pdf|doc|docx|jpg|jpeg|png|gif|xlsx|xls|csv)$/i.test(text);
        };
        const textAnswers = answers.filter((a: any) => !isFileAns(a) && (a.answer_text || '').trim() !== '');
        const fileAnswers = answers.filter((a: any) => isFileAns(a));

        for (let i = 0; i < textAnswers.length; i += 2) {
          const pair = textAnswers.slice(i, i + 2);
          if (pair.length === 2) {
            drawFieldRow([
              { label: pair[0].field?.label || pair[0].field_label || `Field ${i + 1}`, value: pair[0].answer_text || 'N/A' },
              { label: pair[1].field?.label || pair[1].field_label || `Field ${i + 2}`, value: pair[1].answer_text || 'N/A' },
            ]);
          } else {
            drawField(pair[0].field?.label || pair[0].field_label || `Field ${i + 1}`, pair[0].answer_text || 'N/A');
          }
        }

        if (fileAnswers.length > 0) {
          checkPageBreak(8);
          doc.setFontSize(7);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(100, 116, 139);
          doc.text('ATTACHED DOCUMENTS', marginLeft, y);
          y += 5;
          fileAnswers.forEach((a: any) => {
            checkPageBreak(6);
            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(30, 41, 59);
            const label = a.field?.label || a.field_label || 'Document';
            doc.text(`\u2022 ${label}: [File attached \u2014 view in system]`, marginLeft + 2, y);
            y += 5;
          });
        }
        y += 2;
      }

      // 4. ELIGIBILITY DETERMINATION
      if (eligibilityResult) {
        drawSectionHeader('4. Eligibility Determination');
        if (eligibilityResult.eligible_streams?.length > 0) {
          checkPageBreak(8);
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(26, 107, 58);
          doc.text('ELIGIBLE FOR:', marginLeft, y);
          y += 5;
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(30, 41, 59);
          eligibilityResult.eligible_streams.forEach((stream: string) => {
            checkPageBreak(5);
            doc.text(`\u2713 ${stream}`, marginLeft + 4, y);
            y += 5;
          });
        }
        if (eligibilityResult.ineligible_streams?.length > 0) {
          checkPageBreak(8);
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(204, 51, 51);
          doc.text('NOT ELIGIBLE FOR:', marginLeft, y);
          y += 5;
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(30, 41, 59);
          eligibilityResult.ineligible_streams.forEach((stream: string) => {
            checkPageBreak(5);
            doc.text(`\u2717 ${stream}`, marginLeft + 4, y);
            y += 5;
            const reasons = eligibilityResult.details?.[stream]?.reasons || [];
            reasons.forEach((reason: string) => {
              checkPageBreak(5);
              doc.setFontSize(7);
              doc.setTextColor(100, 116, 139);
              const lines = doc.splitTextToSize(`  - ${reason}`, contentWidth - 8);
              doc.text(lines, marginLeft + 8, y);
              y += lines.length * 4;
              doc.setFontSize(8);
              doc.setTextColor(30, 41, 59);
            });
          });
        }
        y += 2;
      }

      // 5. FUNDING BREAKDOWN
      const fundingData = calculateAutoFunding(app);
      if (fundingData && !fundingData.ineligible) {
        drawSectionHeader('5. Funding Breakdown');
        const fundingRows = [
          { label: 'Tuition', amount: fundingData.tuition?.system ?? 0, note: fundingData.tuition?.rule },
          { label: 'Living Allowance', amount: fundingData.living?.system ?? 0, note: fundingData.living?.rule },
          { label: 'Books & Supplies', amount: fundingData.books?.system ?? 500, note: fundingData.books?.rule },
        ];
        if ((fundingData.special?.system ?? 0) > 0) {
          fundingRows.push({ label: 'Special Awards', amount: fundingData.special?.system ?? 0, note: fundingData.special?.rule });
        }

        fundingRows.forEach((row, idx) => {
          checkPageBreak(12);
          const bg = idx % 2 === 0 ? [248, 250, 252] as const : [255, 255, 255] as const;
          doc.setFillColor(bg[0], bg[1], bg[2]);
          doc.rect(marginLeft, y - 3, contentWidth, row.note ? 11 : 8, 'F');
          doc.setFontSize(8);
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(30, 41, 59);
          doc.text(row.label, marginLeft + 2, y + 2);
          if (row.note) {
            doc.setFontSize(7);
            doc.setTextColor(100, 116, 139);
            doc.text(row.note, marginLeft + 2, y + 6);
            doc.setFontSize(8);
            doc.setTextColor(30, 41, 59);
          }
          doc.setFont('helvetica', 'bold');
          const amtStr = '$' + row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          doc.text(amtStr, pageWidth - marginRight - doc.getTextWidth(amtStr), y + 2);
          y += row.note ? 12 : 9;
        });

        checkPageBreak(12);
        doc.setFillColor(30, 41, 59);
        doc.rect(marginLeft, y - 2, contentWidth, 10, 'F');
        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text('TOTAL FUNDING', marginLeft + 2, y + 5);
        doc.setTextColor(229, 166, 98);
        const totalStr = '$' + (fundingData.total ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        doc.text(totalStr, pageWidth - marginRight - doc.getTextWidth(totalStr), y + 5);
        y += 14;

        if (app.amount > 0 && app.status === 'accepted') {
          checkPageBreak(8);
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(26, 107, 58);
          const approvedStr = 'Approved Amount: $' + parseFloat(app.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          doc.text(approvedStr, marginLeft, y);
          y += 8;
        }
        y += 2;
      }

      // 6. AUDIT TRAIL SUMMARY
      const timelineEntries: Array<{ action: string; performer: string; timestamp: string }> = [];
      if (app.submitted_at) {
        timelineEntries.push({ action: 'Application Submitted', performer: student.full_name || 'Student', timestamp: app.submitted_at });
      }
      if (app.reviewed_at) {
        timelineEntries.push({ action: 'Application Reviewed', performer: app.reviewed_by_name || 'Staff Member', timestamp: app.reviewed_at });
      }
      if (app.forwarded_at) {
        timelineEntries.push({ action: 'Forwarded to Director', performer: app.forwarded_by_name || 'Staff Member', timestamp: app.forwarded_at });
      }
      if (app.decided_at) {
        timelineEntries.push({ action: `Application ${app.status === 'accepted' ? 'Approved' : 'Rejected'}`, performer: app.decided_by_name || 'Director', timestamp: app.decided_at });
      }
      auditLogs.forEach((log: any) => {
        if (log.timestamp) {
          timelineEntries.push({ action: log.action || 'Action Recorded', performer: log.performed_by_details?.full_name || log.role || 'System', timestamp: log.timestamp });
        }
      });
      timelineEntries.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

      if (timelineEntries.length > 0) {
        drawSectionHeader('6. Audit Trail Summary');
        timelineEntries.forEach((entry) => {
          checkPageBreak(9);
          doc.setFontSize(8);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(30, 41, 59);
          doc.text(entry.action, marginLeft + 2, y);
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(100, 116, 139);
          const ts = new Date(entry.timestamp).toLocaleString('en-CA', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
          doc.text(entry.performer + '  \u00b7  ' + ts, marginLeft + 2, y + 4);
          y += 9;
        });
        y += 2;
      }

      // 7. BANKING DETAILS (Director only - not shown to staff)
      if (role === 'director' && student) {
        drawSectionHeader('7. Banking Details (Director Only \u2014 Confidential)');
        drawFieldRow([
          { label: 'Account Holder', value: student.account_holder_name || student.full_name || 'N/A' },
          { label: 'Bank Name', value: student.bank_name || 'N/A' },
        ]);
        drawFieldRow([
          { label: 'Account Number', value: student.account_number || 'N/A' },
          { label: 'Transit Number', value: student.transit_number || 'N/A' },
        ]);
        y += 2;
      }

      // FOOTER on every page
      const totalPagesCount = (doc.internal as any).getNumberOfPages();
      for (let i = 1; i <= totalPagesCount; i++) {
        doc.setPage(i);
        doc.setDrawColor(229, 166, 98);
        doc.setLineWidth(0.5);
        doc.line(marginLeft, pageHeight - 14, pageWidth - marginRight, pageHeight - 14);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 116, 139);
        doc.text('Deline Got\u02bcine Government \u2014 Student Funding Application Management System', marginLeft, pageHeight - 9);
        doc.text(`Page ${i} of ${totalPagesCount}`, pageWidth - marginRight - 20, pageHeight - 9);
        doc.text('CONFIDENTIAL \u2014 For authorized staff use only', marginLeft, pageHeight - 5);
      }

      doc.save(`DGG_Application_${app.id}_${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (err: any) {
      console.error('PDF Export Error:', err);
      showToast('PDF generation failed: ' + err.message, 'error');
    } finally {
      setIsPdfExporting(false);
    }
  };

  const handleAddNote = async () => {
    if (!selectedAppId || !staffNote.trim()) return;
    setIsAddingNote(true);
    setNoteError(null);
    try {
      await API.addSubmissionNote(Number(selectedAppId), staffNote);
      setStaffNote('');
      showToast('✓ Note added successfully');
      fetchApplications(); // Refresh list to get new notes
    } catch (err: any) {
      setNoteError(err.message || 'Failed to add note');
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleMarkLegitimate = async () => {
    if (!selectedAppId) return;
    try {
      await API.markLegitimate(Number(selectedAppId), 'Marked as legitimate by staff');
      setDuplicateStatus(null);
      fetchApplications();
      showToast('✓ Application marked as legitimate');
    } catch (err: any) {
      showToast(err.message || 'Failed to mark as legitimate', 'error');
    }
  };

  const handleMarkDuplicate = async () => {
    if (!selectedAppId) return;
    try {
      await API.markDuplicate(Number(selectedAppId), 'Confirmed as duplicate by staff');
      setDuplicateStatus(null);
      fetchApplications();
      showToast('✓ Application confirmed as duplicate');
    } catch (err: any) {
      showToast(err.message || 'Failed to mark as duplicate', 'error');
    }
  };

  const handleAppClick = (appId: number) => {
    setSelectedAppId(String(appId));
    setCurrentView(role === 'director' ? 'director-detail' : 'detail');
  };

  const [officeUseInputs, setOfficeUseInputs] = useState({ dateReceived: '', approvedBy: '', commitmentNum: '' });
  const [isSavingOffice, setIsSavingOffice] = useState(false);

  // â”€â”€ POLICY SETTINGS STATE â”€â”€
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
     // Reset note state when switching applications
     setStaffNote('');
     setNoteError(null);
  }, [selectedAppId, applications]);

  // â”€â”€ ELIGIBILITY CHECK: Fetch when detail view opens for a selected application â”€â”€
  useEffect(() => {
    if (!selectedAppId || (currentView !== 'detail' && currentView !== 'director-detail')) {
      // Reset eligibility state when leaving detail view
      setEligibilityResult(null);
      setEligibilityError(null);
      return;
    }

    let cancelled = false;

    const fetchEligibility = async () => {
      setIsEligibilityLoading(true);
      setEligibilityError(null);
      setEligibilityResult(null);
      try {
        const result = await API.checkEligibility(Number(selectedAppId));
        if (!cancelled) {
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

  // â”€â”€ DUPLICATE CHECK: Fetch when detail view opens for a selected application â”€â”€
  useEffect(() => {
    if (!selectedAppId || (currentView !== 'detail' && currentView !== 'director-detail')) {
      // Reset duplicate state when leaving detail view
      setDuplicateStatus(null);
      setDuplicateError(null);
      return;
    }

    let cancelled = false;

    const fetchDuplicateStatus = async () => {
      setIsDuplicateLoading(true);
      setDuplicateError(null);
      setDuplicateStatus(null);
      try {
        const result = await API.checkDuplicates(Number(selectedAppId));
        if (!cancelled) {
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

  // â”€â”€ AUDIT TRAIL: Fetch when detail view opens for a selected application â”€â”€
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
          // Audit logs are supplementary â€” don't block the UI on error
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

  // â”€â”€ BANKING DETAILS ACCESS LOG: Log when director views banking details (Requirement 12.3) â”€â”€
  useEffect(() => {
    if (!selectedAppId || role !== 'director' || (currentView !== 'detail' && currentView !== 'director-detail')) {
      return;
    }

    // Fire-and-forget: log the access without blocking the UI
    API.logBankingDetailsAccess(Number(selectedAppId)).catch(() => {
      // Silently ignore logging errors â€” don't disrupt the director's workflow
    });
  }, [selectedAppId, currentView, role]);

  const handleSaveOfficeUse = async () => {
     if (!selectedAppId) return;
     setIsSavingOffice(true);
     try {
       const app = applications.find(a => Number(a.id) === Number(selectedAppId));
       if (!app) throw new Error("Application not found in state");
       await API.updateSubmissionStatus(Number(selectedAppId), app.status, { office_use_data: officeUseInputs });
       showToast('✓ Office use data saved successfully');
       fetchApplications();
     } catch (err: any) {
       showToast(err.message || 'Failed to save office use data', 'error');
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

  // â”€â”€ AUDIT TRAIL STATE â”€â”€
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isAuditLoading, setIsAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

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
      (app.form_title || '').includes(fundingStreamFilter);
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
    const statusClassMap: Record<string, string> = {
      pending: 'badge-pending',
      reviewed: 'badge-reviewed',
      forwarded: 'badge-forwarded',
      accepted: 'badge-accepted',
      rejected: 'badge-rejected'
    };

    const badgeClass = statusClassMap[status] || '';

    return (
      <span className={`admin-badge ${badgeClass}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };


  // Eligibility result rendering
  const renderEligibilityResult = () => {
    if (!eligibilityResult) return null;
    
    return (
      <div className="admin-chart-card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>
          âœ“ ELIGIBILITY DETERMINATION
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
          âš ï¸ DUPLICATE FLAG
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
            âœ“ Mark as Legitimate
          </button>
          <button 
            className="admin-input"
            style={{ background: '#cc3333', color: '#fff', border: 'none', cursor: 'pointer', padding: '8px 16px', borderRadius: '6px' }}
            onClick={handleMarkDuplicate}
          >
            âœ• Confirm Duplicate
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
            <h3 style={{ fontSize: '14px', fontWeight: '800' }}>ðŸ’° FUNDING BREAKDOWN</h3>
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
            <h3 style={{ fontSize: '14px', fontWeight: '800', color: '#b91c1c' }}>ðŸ’° FUNDING BREAKDOWN</h3>
            <span className="admin-badge" style={{ background: '#fee2e2', color: '#b91c1c', fontSize: '9px', padding: '2px 8px' }}>INELIGIBLE</span>
          </div>
          <p style={{ fontSize: '13px', color: '#991b1b' }}>{autoSuggested.reason || 'Student does not meet eligibility criteria for this funding stream.'}</p>
        </div>
      );
    }

    const tuitionAmount = autoSuggested.tuition?.system ?? 0;
    const livingAmount = autoSuggested.living?.system ?? 0;
    const booksAmount = autoSuggested.books?.system ?? 500;
    const specialAmount = autoSuggested.special?.system ?? 0;
    const totalAmount = autoSuggested.total ?? 0;

    const breakdownRows: Array<{ label: string; amount: number; note?: string; icon: string }> = [
      {
        icon: 'ðŸŽ“',
        label: 'Tuition',
        amount: tuitionAmount,
        note: autoSuggested.tuition?.rule,
      },
      {
        icon: 'ðŸ ',
        label: 'Living Allowance',
        amount: livingAmount,
        note: autoSuggested.living?.rule,
      },
      {
        icon: 'ðŸ“š',
        label: 'Books & Supplies',
        amount: booksAmount,
        note: autoSuggested.books?.rule,
      },
    ];

    if (specialAmount > 0) {
      breakdownRows.push({
        icon: 'â­',
        label: 'Special Awards',
        amount: specialAmount,
        note: autoSuggested.special?.rule || 'Academic or graduation award',
      });
    }

    return (
      <div className="admin-chart-card" style={{ marginTop: '32px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '800' }}>ðŸ’° FUNDING BREAKDOWN</h3>
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
                ${row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
              <span style={{ fontSize: '16px', width: '24px', textAlign: 'center' }}>ðŸ’µ</span>
              <div style={{ fontSize: '14px', fontWeight: '800', color: '#fff', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Total Funding
              </div>
            </div>
            <div style={{ fontSize: '18px', fontWeight: '900', color: '#e5a662' }}>
              ${totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Approved amount comparison (if already decided) */}
        {selectedApp?.amount > 0 && selectedApp?.status === 'accepted' && (
          <div style={{ marginTop: '16px', padding: '12px 16px', background: '#f0fdf4', borderRadius: '8px', border: '1px solid #dcfce7', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: '12px', fontWeight: '700', color: '#166534' }}>âœ“ Approved Amount</div>
            <div style={{ fontSize: '14px', fontWeight: '800', color: '#166534' }}>
              ${parseFloat(selectedApp.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
      <div className="admin-chart-card" style={{ background: '#f0fdf4', border: '1px solid #dcfce7', marginBottom: '24px', marginTop: '32px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#166534' }}>
          ðŸ”’ BANKING DETAILS (DIRECTOR ONLY)
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

  // â”€â”€ STAFF NOTES SECTION â”€â”€
  const renderStaffNotes = () => {
    const app = applications.find(a => Number(a.id) === Number(selectedAppId));
    const notes: any[] = app?.notes || [];

    return (
      <div className="admin-chart-card">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: '#64748b', margin: 0 }}>
            STAFF NOTES (INTERNAL ONLY)
          </h3>
          {notes.length > 0 && (
            <span
              className="admin-badge"
              style={{ background: '#f0f9ff', color: '#0369a1', border: '1px solid #bae6fd', fontSize: '9px' }}
            >
              {notes.length} NOTE{notes.length !== 1 ? 'S' : ''}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* Notes list */}
          <div
            className="staff-notes-list"
            style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto', paddingRight: '4px' }}
            aria-label="Staff notes list"
            aria-live="polite"
          >
            {notes.length > 0 ? (
              notes.map((note: any) => (
                <div
                  key={note.id}
                  className="staff-note-item"
                  style={{ background: '#fcfaf8', padding: '10px 12px', borderRadius: '8px', border: '1px solid #e5d5c0' }}
                >
                  <div style={{ fontSize: '12px', color: '#1e293b', lineHeight: '1.5' }}>{note.text}</div>
                  <div
                    style={{
                      fontSize: '10px',
                      color: '#64748b',
                      marginTop: '6px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontWeight: '600' }}>
                      {note.author_name || note.added_by_name || 'Staff Member'}
                    </span>
                    <span>
                      {new Date(note.created_at).toLocaleString('en-CA', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div
                style={{
                  fontSize: '11px',
                  color: '#94a3b8',
                  fontStyle: 'italic',
                  padding: '12px',
                  textAlign: 'center',
                  background: '#f8fafc',
                  borderRadius: '8px',
                  border: '1px dashed #cbd5e1',
                }}
              >
                No internal notes yet.
              </div>
            )}
          </div>

          {/* Error display */}
          {noteError && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#991b1b',
              }}
              role="alert"
            >
              <span>âš ï¸</span>
              <span>{noteError}</span>
              <button
                onClick={() => setNoteError(null)}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b', fontSize: '14px', lineHeight: 1 }}
                aria-label="Dismiss error"
              >
                âœ•
              </button>
            </div>
          )}

          {/* Add note input */}
          <div style={{ background: '#fcfaf8', padding: '12px', borderRadius: '8px', border: '1px solid #e5d5c0' }}>
            <label
              htmlFor="staff-note-textarea"
              style={{ display: 'block', fontSize: '10px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', marginBottom: '6px' }}
            >
              New Note
            </label>
            <textarea
              id="staff-note-textarea"
              ref={noteTextareaRef}
              className="admin-input"
              placeholder="Add internal note â€” not visible to student..."
              style={{ fontSize: '12px', border: 'none', background: 'transparent', resize: 'none', padding: '0', width: '100%', minHeight: '60px' }}
              value={staffNote}
              onChange={(e) => { setStaffNote(e.target.value); if (noteError) setNoteError(null); }}
              disabled={isAddingNote}
              aria-label="Internal staff note"
              onKeyDown={(e) => {
                // Ctrl+Enter or Cmd+Enter submits the note
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && staffNote.trim() && !isAddingNote) {
                  e.preventDefault();
                  handleAddNote();
                }
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
              <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                {staffNote.length > 0 ? `${staffNote.length} chars Â· Ctrl+Enter to save` : 'Ctrl+Enter to save'}
              </span>
              <button
                className="admin-badge badge-review"
                style={{
                  cursor: !staffNote.trim() || isAddingNote ? 'not-allowed' : 'pointer',
                  border: 'none',
                  opacity: !staffNote.trim() || isAddingNote ? 0.5 : 1,
                  padding: '6px 14px',
                }}
                onClick={handleAddNote}
                disabled={!staffNote.trim() || isAddingNote}
                aria-label="Save internal note"
              >
                {isAddingNote ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        width: '10px',
                        height: '10px',
                        border: '2px solid #e2e8f0',
                        borderTopColor: '#475569',
                        borderRadius: '50%',
                        display: 'inline-block',
                        animation: 'spin 1s linear infinite',
                      }}
                    ></span>
                    Saving...
                  </span>
                ) : (
                  'Save Note'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // â”€â”€ AUDIT TRAIL TIMELINE â”€â”€
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
          icon: 'ðŸ“‹',
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
          icon: 'ðŸ”',
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
          icon: 'ðŸ“¤',
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
          icon: isApproved ? 'âœ…' : 'âŒ',
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
              icon: 'ðŸ“',
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
          icon: 'ðŸ”’',
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
          <h3 style={{ fontSize: '14px', fontWeight: '800', margin: 0 }}>ðŸ• AUDIT TRAIL</h3>
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
            <span>âš ï¸</span>
            <span>Could not load additional audit entries: {auditError}</span>
          </div>
        )}

        {/* Empty state */}
        {!isAuditLoading && timelineEntries.length === 0 && (
          <div className="audit-trail-empty">
            <div className="audit-trail-empty-icon">ðŸ“‹</div>
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
                    <span className="audit-timeline-separator">Â·</span>
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

  // â”€â”€ SUBMITTED INFORMATION SECTION â”€â”€
  // Converts snake_case or camelCase field labels to human-readable format
  const formatFieldLabel = (label: string): string => {
    if (!label) return '';
    // Replace underscores and hyphens with spaces
    let formatted = label.replace(/[_-]/g, ' ');
    // Insert space before capital letters (camelCase â†’ words)
    formatted = formatted.replace(/([a-z])([A-Z])/g, '$1 $2');
    // Capitalize first letter of each word
    formatted = formatted.replace(/\b\w/g, (c) => c.toUpperCase());
    return formatted.trim();
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
      const label = (answer.field?.label || answer.field_label || '').toLowerCase();

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
      'Personal Information': 'ðŸ‘¤',
      'Program & Enrollment': 'ðŸŽ“',
      'Financial Information': 'ðŸ’°',
      'Documents & Files': 'ðŸ“Ž',
      'Other Information': 'ðŸ“‹',
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
                <span style={{ marginRight: '8px' }}>{groupIcons[groupName] || 'ðŸ“‹'}</span>
                {groupName}
              </div>
              <div className="submitted-info-grid">
                {groupAnswers.map((answer: any, idx: number) => {
                  const fieldLabel = answer.field?.label || answer.field_label || `Field ${idx + 1}`;
                  const displayLabel = formatFieldLabel(fieldLabel);
                  const fileUrl = answer.answer_file || (isFileAnswer(answer) ? answer.answer_text : null);
                  const textValue = answer.answer_text;

                  return (
                    <div key={answer.id || idx} className="submitted-info-field">
                      <div className="submitted-info-label">{displayLabel}</div>
                      {fileUrl ? (
                        <div className="submitted-info-file">
                          <span style={{ fontSize: '16px', marginRight: '8px' }}>
                            {fileUrl.toLowerCase().endsWith('.pdf') ? 'ðŸ“„' :
                             /\.(jpg|jpeg|png|gif)$/i.test(fileUrl) ? 'ðŸ–¼ï¸' : 'ðŸ“Ž'}
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
                          {textValue && textValue.trim() !== '' ? textValue : (
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
            ðŸšª Sign Out
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="staff-main">
        <header className="staff-topbar">
          {/* Hamburger menu button â€” visible on mobile only */}
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
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>â€”</span>
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
                        <span style={{ fontSize: '18px' }}>ðŸ“œ</span>
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
                        key={app.id}
                        className="clickable-row"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleAppClick(app.id)}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                        role="button"
                        aria-label={`View application ${app.id} for ${app.student_details?.full_name || 'Anonymous Student'}`}
                      >
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
                        REF # {sortColumn === 'id' && (sortDirection === 'asc' ? 'â†‘' : 'â†“')}
                      </th>
                      <th 
                        onClick={() => handleSort('student_name')} 
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        APPLICANT {sortColumn === 'student_name' && (sortDirection === 'asc' ? 'â†‘' : 'â†“')}
                      </th>
                      <th 
                        onClick={() => handleSort('form_title')} 
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        INSTITUTION / PROGRAM {sortColumn === 'form_title' && (sortDirection === 'asc' ? 'â†‘' : 'â†“')}
                      </th>
                      <th 
                        onClick={() => handleSort('submitted_at')} 
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        SUBMITTED {sortColumn === 'submitted_at' && (sortDirection === 'asc' ? 'â†‘' : 'â†“')}
                      </th>
                      <th 
                        onClick={() => handleSort('status')} 
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        STATUS {sortColumn === 'status' && (sortDirection === 'asc' ? 'â†‘' : 'â†“')}
                      </th>
                      <th>VERIFICATION</th>
                      <th 
                        onClick={() => handleSort('amount')} 
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                      >
                        FUNDING $ {sortColumn === 'amount' && (sortDirection === 'asc' ? 'â†‘' : 'â†“')}
                      </th>
                      <th>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedApps.map(app => (
                      <tr
                        key={app.id}
                        className="clickable-row"
                        onClick={() => handleAppClick(app.id)}
                        style={{ cursor: 'pointer' }}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(app.id); } }}
                        role="button"
                        aria-label={`View application ${app.id} for ${app.student_details?.full_name || 'Student'}`}
                      >
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
                        <td><strong>{app.amount > 0 ? `$${parseFloat(app.amount).toLocaleString()}` : 'â€”'}</strong></td>
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
                            {app.status === 'forwarded' && role === 'director' ? 'DECIDE â†’' : 'Review â†’'}
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
                      â† Previous
                    </button>
                    <span style={{ fontSize: '12px', color: '#64748b', fontWeight: '600' }}>
                      Page {currentPage} of {totalPages}
                    </span>
                    <button
                      className="pagination-btn"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >
                      Next â†’
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Detail View (Shared by Staff and Director) */}
          {((currentView === 'detail' || currentView === 'director-detail') && selectedAppId) && (
            <div className="fade-in">
              {/* Header Actions */}
              <div className="admin-detail-header">
                <div style={{ fontSize: '11px', color: '#64748b' }}>
                  All Applications / <span style={{ fontWeight: '700', color: '#1e293b' }}>{selectedAppId}</span>
                </div>
                <div className="admin-detail-actions">
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: isPdfExporting ? '#f8fafc' : '#fff', cursor: isPdfExporting ? 'not-allowed' : 'pointer', opacity: isPdfExporting ? 0.7 : 1, display: 'flex', alignItems: 'center', gap: '6px' }} onClick={handlePDFExport} disabled={isPdfExporting} aria-label="Export application as PDF">{isPdfExporting ? (<><span style={{ width: '10px', height: '10px', border: '2px solid #e2e8f0', borderTopColor: '#475569', borderRadius: '50%', display: 'inline-block', animation: 'spin 1s linear infinite' }}></span>Generating...</>) : ('Export PDF')}</button>
                  <button className="admin-badge" style={{ border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }} onClick={handleShareView}>Share Link</button>
                  <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={() => setShowRequestInfoModal(true)}>REQUEST MORE INFO</button>
                  <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700' }} onClick={() => { noteTextareaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); noteTextareaRef.current?.focus(); }}>ADD NOTE</button>
                  {role === 'director' ? (
                    <>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: '#1a6b3a', color: '#fff', border: 'none' }} onClick={() => setShowConfirmModal(true)}>APPROVE APPLICATION</button>
                      <button className="admin-input" style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: '#ef4444', color: '#fff', border: 'none' }} onClick={() => { setRejectReason(''); setRejectReasonError(null); setShowRejectModal(true); }}>REJECT</button>
                    </>
                  ) : (
                    <button 
                      className="admin-input" 
                      style={{ width: 'auto', fontSize: '11px', fontWeight: '700', background: 'var(--admin-accent)', color: '#000', border: 'none' }}
                      onClick={() => handleDecision('forwarded')}
                    >
                      SEND TO DIRECTOR â†’
                    </button>
                  )}
                </div>
              </div>

              <div className="admin-detail-grid">
                {/* Left: Detail Forms */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{selectedAppId}</div>
                        <h2 style={{ fontSize: '20px', fontWeight: '800' }}>{applications.find(a => String(a.id) === String(selectedAppId))?.name} â€” Post-Secondary Application</h2>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Submitted Mar 3, 2025 Â· Admission Application</div>
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
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>{getStatusBadge(applications.find(a => String(a.id) === String(selectedAppId))?.status || 'pending')}</div>
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
                            <span style={{ fontSize: '16px' }}>âš ï¸</span>
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
                            <span style={{ fontSize: '16px' }}>âš ï¸</span>
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

                    {/* Banking Details Section (Director only - Requirement 12) */}
                    {renderBankingDetails()}

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
                                          showToast('✓ System suggested total applied');
                                        } catch (er) { showToast('Failed to apply total', 'error'); }
                                      }
                                    }}
                                  >
                                    APPLY SYSTEM TOTAL â†’
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
                              <span style={{ fontSize: '18px' }}>{doc.file?.toLowerCase().endsWith('.pdf') ? 'ðŸ“„' : 'ðŸ–¼ï¸'}</span>
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
                    {renderAuditTrail()}
                  </div>

                  <div className="admin-chart-card">
                    {renderStaffNotes()}
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
                        { id: 'psssp_tuition', title: 'PSSSP â€” Tuition Bursary', desc: 'Maximum tuition coverage per semester for PSSSP students.' },
                        { id: 'psssp_living', title: 'PSSSP â€” Living Allowance', desc: 'Monthly living allowance rates based on enrollment and dependents.' },
                        { id: 'psssp_travel', title: 'PSSSP â€” Travel Bursary', desc: 'Limits and eligibility for student travel reimbursements.' },
                        { id: 'psssp_graduation_travel', title: 'PSSSP â€” Graduation Travel', desc: 'Assistance for students traveling to attend graduation ceremonies.' },
                        { id: 'ucepp_tuition', title: 'UCEPP â€” Tuition Bursary', desc: 'Maximum tuition coverage per semester for UCEPP students.' },
                        { id: 'ucepp_living', title: 'UCEPP â€” Living Allowance', desc: 'Monthly living allowance rates for UCEPP students.' },
                        { id: 'dggr_tuition', title: 'DGGR â€” Tuition Bursary', desc: 'Tuition rates for DGGR-funded programs.' },
                        { id: 'dggr_extra_tuition', title: 'DGGR â€” Extra Tuition Bursary', desc: 'Top-up bursary for tuition exceeding standard limits.' },
                        { id: 'dggr_living', title: 'DGGR â€” Living Allowance', desc: 'Monthly living allowance rates for DGGR students.' },
                        { id: 'dggr_practicum_award', title: 'DGGR â€” Practicum Award', desc: 'Awards for placements and practicum completions.' },
                        { id: 'dggr_grad_bursary', title: 'DGGR â€” Graduation Bursary', desc: 'One-time bursaries for completing degrees or certificates.' },
                        { id: 'dggr_academic_scholarship', title: 'DGGR â€” Academic Scholarship', desc: 'Achievement awards based on GPA thresholds.' },
                        { id: 'dggr_hardship', title: 'DGGR â€” Hardship Bursary', desc: 'Emergency funding caps for students in financial distress.' },
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
                                <span style={{ fontSize: '18px', color: '#64748b' }}>{isExpanded ? 'âˆ’' : '+'}</span>
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
                      <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '12px', textTransform: 'uppercase' }}>Level 1 â€” Funding Type</label>
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
                      <label style={{ fontSize: '11px', fontWeight: '800', color: '#64748b', display: 'block', marginBottom: '12px', textTransform: 'uppercase' }}>Level 2 â€” Sub-Filters</label>
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
                              Review â†’
                            </button>
                            <button className="director-decision-icon-btn approve" aria-label="Quick approve application" onClick={() => { setSelectedAppId(String(app.id)); setShowConfirmModal(true); }}><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
                            <button className="director-decision-icon-btn deny" aria-label="Quick reject application" onClick={() => { setSelectedAppId(String(app.id)); setRejectReason(''); setRejectReasonError(null); setShowRejectModal(true); }}><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
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
                            {getStatusBadge(app.status)}
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

              <div className="admin-detail-grid">
                {/* Left: Application Content */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="admin-chart-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{selectedAppId}</div>
                        <h2 style={{ fontSize: '20px', fontWeight: '800' }}>{applications.find(a => a.id === selectedAppId)?.name} â€” Post-Secondary Application</h2>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>SSW forwarded {applications.find(a => a.id === selectedAppId)?.date} Â· J. Villeneuve</div>
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
                                  <td><span style={{ fontSize: '10px', color: '#64748b' }}>â€”</span></td>
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
                        Recommend Approval â€” amounts as calculated. Tuition confirmed at $5,000 per institutional invoice.
                      </p>
                      <div style={{ marginTop: '12px', fontSize: '11px', color: '#3b82f6' }}>â€” J. Villeneuve Â· Today Â· 9:45am</div>
                    </div>

                    <div style={{ background: '#fff9f2', border: '1px solid #fef3c7', borderRadius: '10px', padding: '20px', marginBottom: '32px' }}>
                      <h4 style={{ fontSize: '11px', fontWeight: '800', color: '#92400e', textTransform: 'uppercase', marginBottom: '8px' }}>âš ï¸ EXCEPTION / OVERRIDE DETAILS</h4>
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
                                  <span style={{ fontSize: '16px' }}>ðŸ“„</span>
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
                          <option>â€” Select â€”</option>
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
                        <button className="director-main-btn approve" onClick={() => setShowConfirmModal(true)}>âœ“ APPROVE APPLICATION</button>
                        <button className="director-main-btn deny" onClick={() => { setRejectReason(''); setRejectReasonError(null); setShowRejectModal(true); }}>âœ• DENY APPLICATION</button>
                      </div>
                    </div>
                  </div>

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
          )}

          {/* Confirm Approval Modal */}
          {showConfirmModal && (
            <div className="modal-overlay">
              <div className="modal-card">
                <div className="modal-header">
                  <h3>CONFIRM APPROVAL</h3>
                  <button onClick={() => { setShowConfirmModal(false); setDecisionNotes(''); }}>âœ•</button>
                </div>
                <div className="modal-body">
                  <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#475569', marginBottom: '20px' }}>
                    You are approving <strong>#{selectedAppId} â€” {applications.find(a => Number(a.id) === Number(selectedAppId))?.student_details?.full_name}</strong>.<br/>
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
                  <button className="btn-secondary" onClick={() => { setShowConfirmModal(false); setDecisionNotes(''); }}>Cancel</button>
                  <button className="btn-confirm-approval" onClick={() => handleDecision('accepted')}>âœ“ CONFIRM APPROVAL</button>
                </div>
              </div>
            </div>
          )}

          {/* Reject Application Modal */}
          {showRejectModal && (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="reject-modal-title">
              <div className="modal-card">
                <div className="modal-header">
                  <h3 id="reject-modal-title">REJECT APPLICATION</h3>
                  <button
                    onClick={() => { setShowRejectModal(false); setRejectReason(''); setRejectReasonError(null); }}
                    aria-label="Close rejection dialog"
                  >âœ•</button>
                </div>
                <div className="modal-body">
                  <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#475569', marginBottom: '20px' }}>
                    You are rejecting <strong>#{selectedAppId} â€” {applications.find(a => Number(a.id) === Number(selectedAppId))?.student_details?.full_name}</strong>.
                  </p>
                  <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px' }}>
                    This decision will be recorded in the audit trail and the student will be notified with the reason provided.
                  </p>

                  <div className="field-group">
                    <label
                      htmlFor="reject-reason-textarea"
                      className="field-label"
                      style={{ fontSize: '11px', fontWeight: '800', display: 'block', marginBottom: '6px' }}
                    >
                      REASON FOR REJECTION <span style={{ color: '#ef4444' }}>*</span>
                    </label>
                    <textarea
                      id="reject-reason-textarea"
                      className="admin-input"
                      placeholder="Provide a clear reason for rejection (required)..."
                      style={{
                        height: '100px',
                        resize: 'none',
                        borderColor: rejectReasonError ? '#ef4444' : undefined,
                        boxShadow: rejectReasonError ? '0 0 0 3px rgba(239, 68, 68, 0.1)' : undefined,
                      }}
                      value={rejectReason}
                      onChange={(e) => {
                        setRejectReason(e.target.value);
                        if (rejectReasonError && e.target.value.trim()) {
                          setRejectReasonError(null);
                        }
                      }}
                      aria-required="true"
                      aria-describedby={rejectReasonError ? 'reject-reason-error' : undefined}
                    />
                    {rejectReasonError && (
                      <div
                        id="reject-reason-error"
                        role="alert"
                        style={{ fontSize: '12px', color: '#ef4444', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}
                      >
                        <span>âš </span> {rejectReasonError}
                      </div>
                    )}
                  </div>
                </div>
                <div className="modal-footer">
                  <button
                    className="btn-secondary"
                    onClick={() => { setShowRejectModal(false); setRejectReason(''); setRejectReasonError(null); }}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn-confirm-rejection"
                    onClick={handleRejectWithReason}
                    disabled={!rejectReason.trim()}
                  >
                    âœ• CONFIRM REJECTION
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Request More Info Modal */}
          {showRequestInfoModal && (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="request-info-modal-title">
              <div className="modal-card">
                <div className="modal-header">
                  <h3 id="request-info-modal-title">REQUEST MORE INFORMATION</h3>
                  <button onClick={() => setShowRequestInfoModal(false)} aria-label="Close request info dialog">âœ•</button>
                </div>
                <div className="modal-body">
                  <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#475569', marginBottom: '16px' }}>
                    You are requesting additional information from the student for application{' '}
                    <strong>#{selectedAppId} â€” {applications.find(a => Number(a.id) === Number(selectedAppId))?.student_details?.full_name}</strong>.
                  </p>
                  <p style={{ fontSize: '13px', color: '#64748b' }}>
                    The application status will be updated to <strong>More Info Required</strong> and the student will be notified via email to log in and provide the requested details.
                  </p>
                </div>
                <div className="modal-footer">
                  <button className="btn-secondary" onClick={() => setShowRequestInfoModal(false)}>Cancel</button>
                  <button
                    style={{ background: 'var(--admin-accent)', color: '#000', border: 'none', padding: '12px 24px', borderRadius: '8px', fontSize: '13px', fontWeight: '800', cursor: 'pointer' }}
                    onClick={handleRequestInfo}
                  >
                    âœ‰ SEND REQUEST
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Share Link Modal */}
          {showShareLinkModal && (
            <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="share-link-modal-title">
              <div style={{ position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
              <div className="modal-card" style={{ maxWidth: '480px', width: '100%' }}>
                <div className="modal-header">
                  <h3 id="share-link-modal-title">SHARE APPLICATION LINK</h3>
                  <button onClick={() => { setShowShareLinkModal(false); setShareLinkUrl(''); setShareLinkCopied(false); }} aria-label="Close share link dialog">âœ•</button>
                </div>
                <div className="modal-body">
                  <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px', lineHeight: '1.6' }}>
                    Generate a secure, read-only link that allows the student to view their application status without logging in. The link is valid for <strong>7 days</strong>.
                  </p>
                  {isGeneratingShareLink ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px', gap: '12px', color: '#64748b', fontSize: '13px' }}>
                      <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>âŸ³</span>
                      Generating secure linkâ€¦
                    </div>
                  ) : shareLinkUrl ? (
                    <div>
                      <label style={{ fontSize: '9px', fontWeight: '800', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '6px' }}>
                        Shareable Link
                      </label>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'stretch' }}>
                        <input
                          readOnly
                          value={shareLinkUrl}
                          onClick={e => (e.target as HTMLInputElement).select()}
                          style={{
                            flex: 1,
                            padding: '10px 12px',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            border: '1px solid #e2e8f0',
                            borderRadius: '8px',
                            background: '#f8fafc',
                            color: '#1e293b',
                            outline: 'none',
                            cursor: 'text',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}
                          aria-label="Shareable link URL"
                        />
                        <button
                          onClick={handleCopyShareLink}
                          style={{
                            padding: '10px 16px',
                            fontSize: '12px',
                            fontWeight: '700',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            background: shareLinkCopied ? '#10b981' : 'var(--admin-accent, #e5a662)',
                            color: shareLinkCopied ? '#fff' : '#000',
                            transition: 'background 0.2s, color 0.2s',
                            whiteSpace: 'nowrap',
                            flexShrink: 0
                          }}
                          aria-label={shareLinkCopied ? 'Link copied' : 'Copy link to clipboard'}
                        >
                          {shareLinkCopied ? 'âœ“ Copied!' : 'âŽ˜ Copy'}
                        </button>
                      </div>
                      {shareLinkCopied && (
                        <p style={{ fontSize: '11px', color: '#10b981', marginTop: '8px', fontWeight: '600' }}>
                          âœ“ Link copied to clipboard
                        </p>
                      )}
                    </div>
                  ) : null}
                </div>
                <div className="modal-footer">
                  <button className="btn-secondary" onClick={() => { setShowShareLinkModal(false); setShareLinkUrl(''); setShareLinkCopied(false); }}>Close</button>
                </div>
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
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>ðŸ“§</div>
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
                      <tr
                        key={a.id}
                        className="clickable-row"
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleAppClick(a.submission)}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleAppClick(a.submission); } }}
                        role="button"
                        aria-label={`View appeal ${a.id} for ${a.student_details?.full_name || 'Student'}`}
                      >
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

      {/* Toast Notification */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          style={{
            position: 'fixed',
            bottom: '32px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: toast.type === 'error' ? '#991b1b' : '#166534',
            color: '#fff',
            padding: '12px 24px',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: '600',
            boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
            zIndex: 9999,
            border: toast.type === 'error' ? '1px solid #fecaca' : '1px solid #bbf7d0',
            maxWidth: '480px',
            textAlign: 'center',
            animation: 'fadeInUp 0.2s ease',
          }}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
};

export default StaffDashboard;
