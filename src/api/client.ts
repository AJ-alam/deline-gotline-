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
            delete config.headers['Content-Type'];
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
            return response.data.data;
        }

        // Handle DRF global pagination wrappers invisibly
        if (response.data && response.data.hasOwnProperty('results') && Array.isArray(response.data.results)) {
            return response.data.results;
        }

        return response.data;
    },
    (error) => {
        // Handle 401: Unauthorized (Token expired or missing)
        if (error.response && error.response.status === 401) {
            console.error('Unauthorized session detected. Redirecting to login.');
            
            // Avoid infinite redirect loop if already on login page
            if (!window.location.pathname.includes('/signin') && !window.location.pathname.includes('/internal/login')) {
                localStorage.removeItem('dgg_token');
                localStorage.removeItem('dgg_role');
                window.location.href = window.location.pathname.startsWith('/staff') ? '/internal/login' : '/signin';
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
        });
    }

    static register(data: any) {
        const payload = {
            email: data.email,
            password: data.password,
            full_name: `${data.firstName} ${data.lastName}`,
            phone: data.phone || '',
            role: data.role || 'student',
            dob: data.dob || '',
            beneficiary_number: data.beneficiaryNo || '',
            treaty_number: data.treatyNum || ''
        };
        return apiClient.post('/auth/register/', payload);
    }

    static getMe() {
        return apiClient.get('/auth/me/');
    }

    static updateMe(data: any) {
        return apiClient.put('/auth/me/', data);
    }

    // Programs
    static getPrograms() {
        return apiClient.get('/programs/');
    }

    static getProgram(id: number) {
        return apiClient.get(`/programs/${id}/`);
    }

    // Forms
    static getForms() {
        return apiClient.get('/forms/forms/');
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

    static getSubmission(id: number) {
        return apiClient.get(`/forms/submissions/${id}/`);
    }

    static updateSubmissionStatus(id: number, status: string, additionalData: any = {}) {
        return apiClient.put(`/forms/submissions/${id}/status/`, { status, ...additionalData });
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

    static getReportStats(fundingType: string = 'all') {
        return apiClient.get('/dashboard/stats/', { params: { funding_type: fundingType } });
    }

    static dispatchFinanceReport() {
        return apiClient.post('/payments/dispatch_report/');
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

    // Support for complex wizards
    static async submitApplication(data: any) {
        const forms = await this.getForms() as unknown as any[];
        // More robust matching: strip spaces and compare lowercase
        const normalize = (s: string) => s.toLowerCase().replace(/\s+/g, '');
        const target = normalize(data.form_type);
        
        const form = forms.find((f: any) => {
            const title = normalize(f.title);
            return title.includes(target) || target.includes(title);
        });
        
        if (!form) {
            throw new Error(`Form template '${data.form_type}' not found. Registered forms: ${forms.map(f => f.title).join(', ')}`);
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
}

export default API;
