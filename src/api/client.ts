import axios from 'axios';
import { API_BASE_URL } from '../config/api';

const BASE_URL = API_BASE_URL;

// Create a central axios instance
const apiClient = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// REQUEST INTERCEPTOR: Automatically attach JWT token to every request
apiClient.interceptors.request.use(
    (config: any) => {
        const token = localStorage.getItem('dgg_token');
        
        if (token && !config.headers.hasOwnProperty('Authorization')) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        // CRITICAL: If the request body is FormData, delete the manually set
        // Content-Type so the browser can set it automatically with the correct
        // multipart boundary string. Without this, file uploads fail.
        if (config.data instanceof FormData) {
            if (config.headers.delete) {
                config.headers.delete('Content-Type');
            } else {
                delete config.headers['Content-Type'];
            }
        }
        
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// RESPONSE INTERCEPTOR: Handle global errors like 401 Unauthorized
apiClient.interceptors.response.use(
    (response) => {
        // Handle the { success: true, data: ..., message: ... } wrapper from our Django backend
        if (response.data && response.data.hasOwnProperty('success')) {
            if (!response.data.success) {
                return Promise.reject({
                    message: response.data.message || 'Action failed',
                    data: response.data.data
                });
            }
            // If the wrapped data has results, return them directly (DRF pagination pattern)
            if (response.data.data && response.data.data.hasOwnProperty('results') && Array.isArray(response.data.data.results)) {
                return response.data.data.results;
            }
            return response.data.data;
        }

        // Handle DRF global pagination wrappers invisibly
        if (response.data && response.data.hasOwnProperty('results') && Array.isArray(response.data.results)) {
            return response.data.results;
        }

        return response.data;
    },
    async (error) => {
        const originalRequest = error.config;

        // Handle 401: Unauthorized (Token expired or missing)
        // Skip refresh logic for auth endpoints — a 401 there means bad credentials, not expired token.
        const isAuthEndpoint = originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh');
        if (error.response && error.response.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
            
            const refreshToken = localStorage.getItem('dgg_refresh');
            
            if (refreshToken) {
                originalRequest._retry = true;
                try {
                    // Attempt to refresh the access token
                    const response = await axios.post(`${BASE_URL}/auth/refresh/`, {
                        refresh: refreshToken
                    });
                    
                    const newToken = response.data.access;
                    localStorage.setItem('dgg_token', newToken);
                    
                    // Update header and retry original request
                    originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
                    return apiClient(originalRequest);
                } catch (refreshError) {
                    // Refresh failed, clear tokens and redirect
                    localStorage.removeItem('dgg_token');
                    localStorage.removeItem('dgg_refresh');
                    localStorage.removeItem('dgg_role');
                    if (!window.location.pathname.includes('/signin') && !window.location.pathname.includes('/internal/login')) {
                        window.location.href = window.location.pathname.startsWith('/staff') ? '/internal/login' : '/signin';
                    }
                }
            } else {
                // No refresh token available, redirect to login
                if (!window.location.pathname.includes('/signin') && !window.location.pathname.includes('/internal/login')) {
                    localStorage.removeItem('dgg_token');
                    localStorage.removeItem('dgg_role');
                    window.location.href = window.location.pathname.startsWith('/staff') ? '/internal/login' : '/signin';
                }
            }
        }
        
        return Promise.reject({
            status: error.response?.status,
            message: error.response?.data?.message || error.response?.data?.detail || 'An error occurred',
            data: error.response?.data?.data || error.response?.data
        });
    }
);

class API {
    // Auth
    static login(data: { email: string; password: string }) {
        return apiClient.post('/auth/login/', {
            email: data.email,
            password: data.password
        }).then((resp: any) => {
            // Save refresh token if present
            if (resp.refresh) {
                localStorage.setItem('dgg_refresh', resp.refresh);
            }
            if (resp.access) {
                localStorage.setItem('dgg_token', resp.access);
            }
            return resp;
        });
    }

    static refresh(refreshToken: string) {
        return apiClient.post('/auth/refresh/', { refresh: refreshToken });
    }

    static register(data: any) {
        const payload = {
            email: data.email,
            password: data.password,
            full_name: `${data.firstName} ${data.lastName}`,
            phone: data.phone || '',
            role: data.role || 'student',
            dob: data.dob || null,
            beneficiary_number: data.beneficiaryNo || '',
            treaty_number: data.treatyNum || '',
            primary_stream: data.primary_stream || '',
            secondary_stream: data.secondary_stream || '',
            financial_assistance_status: data.financial_assistance_status || '',
            num_dependents: data.num_dependents || 0,
            dependent_ages: data.dependent_ages || '',
            is_indian_act_registered: data.is_indian_act_registered ?? null,
            is_deline_beneficiary: data.is_deline_beneficiary ?? null,
            province_of_residence: data.province_of_residence || '',
        };
        return apiClient.post('/auth/register/', payload);
    }

    static getMe() {
        return apiClient.get('/auth/me/');
    }

    static forgotPassword(email: string) {
        return apiClient.post('/auth/forgot-password/', { email });
    }

    static resetPassword(token: string, password: string) {
        return apiClient.post('/auth/reset-password/', { token, password });
    }

    static getStaffUsers() {
        return apiClient.get('/auth/staff-users/');
    }

    static createStaffUser(data: { full_name: string; email: string; role: string; password: string }) {
        return apiClient.post('/auth/staff-users/', data);
    }

    static updateStaffUser(id: number, data: { full_name?: string; role?: string; password?: string; is_active?: boolean }) {
        return apiClient.put(`/auth/staff-users/${id}/`, data);
    }

    static deleteStaffUser(id: number) {
        return apiClient.delete(`/auth/staff-users/${id}/`);
    }

    static updateMe(data: any) {
        // Strip only truly read-only/file fields that fail backend validation.
        // town_city, postal_code, institute ARE sent — the backend serializer
        // captures them in to_internal_value() and writes them to the Profile model.
        const {
            id,
            role,
            date_joined,
            profile_picture,  // ImageField — can't send a URL string back
            ...payload
        } = data;
        return apiClient.patch('/auth/me/', payload);
    }

    // Programs
    static getPrograms() {
        return apiClient.get('/programs/');
    }

    static getProgram(id: number) {
        return apiClient.get(`/programs/${id}/`);
    }

    static formsCache: any[] | null = null;

    static async getForms() {
        if (API.formsCache) return API.formsCache;
        const forms: any = await apiClient.get('/forms/forms/');
        API.formsCache = forms;
        return forms;
    }

    static getForm(id: number) {
        return apiClient.get(`/forms/forms/${id}/`);
    }

    static submitForm(formId: number, answers: any[] | FormData) {
        // Remove manual Content-Type: browser will set it with the correct boundary for FormData
        return apiClient.post(`/forms/forms/${formId}/submit/`, 
            answers instanceof FormData ? answers : { answers }
        );
    }

    // Submissions
    static getSubmissions() {
        return apiClient.get('/forms/submissions/');
    }

    static getApplications() {
        return apiClient.get('/applications/');
    }

    static getSubmission(id: number) {
        return apiClient.get(`/forms/submissions/${id}/`);
    }

    static updateSubmissionStatus(id: number, status: string, additionalData: any = {}) {
        return apiClient.put(`/forms/submissions/${id}/status/`, { status, ...additionalData });
    }

    static updateApplicationStatus(id: number, status: string, notes: string = '') {
        if (status === 'accepted') return this.approveApplication(id, notes);
        if (status === 'rejected') return this.denyApplication(id, notes);
        return apiClient.patch(`/applications/${id}/`, { status });
    }

    static approveApplication(id: number, notes: string = '') {
        return apiClient.post(`/applications/${id}/approve/`, { notes });
    }

    static denyApplication(id: number, notes: string = '') {
        return apiClient.post(`/applications/${id}/deny/`, { notes });
    }

    static addSubmissionNote(id: number, text: string) {
        return apiClient.post(`/forms/submissions/${id}/notes/`, { text });
    }

    // Notifications
    static getNotifications() {
        const isInternal = window.location.pathname.startsWith('/staff');
        return apiClient.get('/notifications/notifications/', { params: { portal: isInternal ? 'internal' : 'student' } });
    }

    static markNotificationRead(id: number) {
        return apiClient.post(`/notifications/notifications/${id}/read/`);
    }

    static markAllNotificationsRead() {
        return apiClient.post('/notifications/notifications/read-all/');
    }

    // User Documents
    static getUserDocuments() {
        return apiClient.get('/user-documents/');
    }

    static uploadUserDocument(formData: FormData) {
        // Remove manual Content-Type header to let axios/browser handle the multipart boundary
        return apiClient.post('/user-documents/', formData);
    }

    static deleteUserDocument(id: number) {
        return apiClient.delete(`/user-documents/${id}/`);
    }

    static getDashboardStats() {
        return apiClient.get('/dashboard/stats/');
    }

    static getReportStats(fundingType: string = 'all', filters?: { dateFrom?: string; dateTo?: string; status?: string }) {
        return apiClient.get('/dashboard/stats/', {
            params: {
                funding_type: fundingType,
                ...(filters?.dateFrom && { date_from: filters.dateFrom }),
                ...(filters?.dateTo && { date_to: filters.dateTo }),
                ...(filters?.status && filters.status !== 'all' && { status_filter: filters.status }),
            }
        });
    }

    static dispatchFinanceReport() {
        return apiClient.post('/payments/dispatch_report/');
    }

    static dispatchFinanceCustom(payload: {
        recipients: string[];
        payment_ids: number[];
        notes?: string;
        subject?: string;
    }) {
        return apiClient.post('/payments/dispatch_custom/', payload);
    }

    static exportApprovedCSV(params?: { funding_type?: string; date_from?: string; date_to?: string }) {
        return apiClient.get('/payments/export-csv/', {
            params,
            responseType: 'blob',
        });
    }

    // New API Methods
    static getPayments() {
        return apiClient.get('/payments/');
    }

    static issuePayment(data: { application: number; amount: number; payment_type: string; user: number }) {
        return apiClient.post('/payments/', data);
    }

    static getAppeals() {
        return apiClient.get('/appeals/');
    }

    static submitAppeal(data: { application: number; reason: string }) {
        return apiClient.post('/appeals/', data);
    }

    static requestMoreInfo(id: number, notes: string = 'Staff requested more information.') {
        return apiClient.put(`/forms/submissions/${id}/status/`, { 
            status: 'more_info_required', 
            notes 
        });
    }

    static respondToInfoRequest(id: number, formData: FormData) {
        return apiClient.post(`/forms/submissions/${id}/respond-info/`, formData);
    }

    static generateShareLink(applicationId: number) {
        // Since we are using Submission ID in current frontend context
        return apiClient.post(`/forms/submissions/${applicationId}/share/`);
    }

    static getSharedApplication(token: string) {
        return apiClient.get(`/shared-view/view/${token}/`);
    }

    // Policy Settings
    static getPolicySettings() {
        return apiClient.get('/policy/all_settings/');
    }

    static updatePolicySetting(category: string, data: any) {
        if (category === 'bulk') {
            return apiClient.post('/policy/bulk_update/', data);
        }
        return apiClient.post(`/policy/${category}/update/`, data);
    }

    static getPolicyHistory(limit: number = 200) {
        return apiClient.get('/policy/history/', { params: { limit } });
    }

    static createPolicySetting(payload: { section: string; field_key: string; field_label: string; value: number | string; unit?: string }) {
        return apiClient.post('/policy/', payload);
    }

    static deletePolicySetting(id: number | string) {
        return apiClient.delete(`/policy/${id}/`);
    }

    // Support for complex wizards
    static async submitApplication(data: any) {
        const forms = await this.getForms() as unknown as any[];
        
        // Normalize: strip spaces, dashes, em-dashes, lowercase for matching
        const normalize = (s: string) => s.toLowerCase().replace(/[\s\-\u2014\u2013]+/g, '');
        
        // Map common frontend keys to match backend titles
        const typeMap: Record<string, string> = {
            'FormA': 'Form A',
            'FormC': 'Form C',
            'FormD': 'Form D',
            'FormE': 'Form E',
            'FormF': 'Form F',
            'FormG': 'Form G',
            'FormH': 'Form D', // Frontend H is Appeal, Backend D is Appeal
            'Practicum': 'Form F',
            'C-DFN PSSSP': 'Form A',
            'Scholarship': 'Scholarship',
            'Hardship': 'Hardship'
        };

        const mappedType = typeMap[data.form_type] || data.form_type;
        const target = normalize(mappedType);
        
        const form = forms.find((f: any) => {
            const title = normalize(f.title);
            return title.includes(target) || target.includes(title);
        });
        
        if (!form) {
            throw new Error(`Form template '${data.form_type}' (mapped to '${mappedType}') not found. Registered forms: ${forms.map(f => f.title).join(', ')}`);
        }

        const answers = data.form_data instanceof FormData 
            ? data.form_data 
            : this.mapFormDataToAnswers(data.form_data);

        return this.submitForm(form.id, answers);
    }

    private static mapFormDataToAnswers(formData: any) {
        return Object.entries(formData).map(([key, value]) => ({
            field_label: key,
            answer_text: typeof value === 'object' ? JSON.stringify(value) : String(value)
        }));
    }

    // Eligibility check
    static checkEligibility(submissionId: number): Promise<any> {
        return apiClient.post(`/forms/submissions/${submissionId}/check-eligibility/`, {});
    }

    // Duplicate detection
    static checkDuplicates(submissionId: number): Promise<any> {
        return apiClient.post(`/forms/submissions/${submissionId}/check-duplicates/`, {});
    }

    // Mark as legitimate
    static markLegitimate(submissionId: number, notes: string): Promise<any> {
        return apiClient.post(`/forms/submissions/${submissionId}/mark-legitimate/`, { notes });
    }

    // Mark as duplicate
    static markDuplicate(submissionId: number, notes: string): Promise<any> {
        return apiClient.post(`/forms/submissions/${submissionId}/mark-duplicate/`, { notes });
    }

    // Audit Logs
    static getAuditLogs(params?: { submission?: number; application?: number }): Promise<any> {
        return apiClient.get('/audit-logs/', { params });
    }

    // PDF Downloads
    static downloadFormPDF(formId: number): Promise<Blob> {
        return apiClient.get(`/forms/forms/${formId}/download-pdf/`, {
            responseType: 'blob',
        });
    }

    static downloadSubmissionPDF(submissionId: number): Promise<Blob> {
        return apiClient.get(`/forms/submissions/${submissionId}/download-pdf/`, {
            responseType: 'blob',
        });
    }
}

export default API;
