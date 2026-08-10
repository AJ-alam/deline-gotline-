/**
 * Talking to the funding API.
 *
 * Replaces a 553-line client that fuzzy-matched form titles to find a template,
 * hand-mapped camelCase state onto display-string labels, and unwrapped a
 * {success, data, message} envelope that flattened field errors to one string.
 *
 * Answers are typed from the backend schemas (see schema.generated.ts), so a
 * renamed field is a build error here rather than a silent runtime mismatch.
 */

import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

import { API_BASE_URL } from '../config/api';
import type { ApplicationSchema, ApplicationType, AnswersFor } from './schema.generated';

export type { ApplicationSchema, ApplicationType, AnswersFor };

// ── Wire types ───────────────────────────────────────────────────────────────

export type ApplicationStatus =
  | 'draft'
  | 'submitted'
  | 'under_review'
  | 'info_requested'
  | 'awaiting_decision'
  | 'approved'
  | 'declined'
  | 'sent_to_finance';

export type TransitionAction =
  | 'submitted'
  | 'reviewed'
  | 'info_requested'
  | 'info_provided'
  | 'forwarded'
  | 'approved'
  | 'declined'
  | 'sent_to_finance';

export type FundingStream = 'psssp' | 'ucepp' | 'dggr';

export interface ApplicationEvent {
  id: number;
  action: TransitionAction;
  action_label: string;
  actor_name: string | null;
  note: string;
  occurred_at: string;
}

export interface AwardLine {
  id: number;
  category: string;
  category_label: string;
  amount: string;
  status: string;
  rule_code: string;
  reference: string | null;
  created_at: string;
}

/** Why an amount is what it is. Shown to staff, and to an applicant on appeal. */
export interface DecisionTrace {
  rule_set: string;
  priced_on: string | null;
  total: string;
  missing_rates: string[];
  rules: Array<{
    code: string;
    description: string;
    category: string;
    applied: boolean;
    amount: string;
    reason: string;
  }>;
}

export interface AwardDecision {
  id: number;
  total: string;
  rule_set_version: number;
  priced_on: string | null;
  is_complete: boolean;
  is_current: boolean;
  trace: DecisionTrace;
  lines: AwardLine[];
  created_at: string;
}

/** The shape the staff queue reads — deliberately without answers or history. */
export interface ApplicationSummary {
  id: number;
  type: ApplicationType;
  type_label: string;
  stream: FundingStream;
  status: ApplicationStatus;
  status_label: string;
  student_name: string | null;
  awarded_total: string;
  submitted_at: string;
  submitted_after_deadline: boolean;
  residency_flag: string;
}

export interface Application extends ApplicationSummary {
  schema_slug: ApplicationType;
  answers: Record<string, unknown>;
  office_notes: Record<string, unknown>;
  events: ApplicationEvent[];
  decision: AwardDecision | null;
}

export interface PolicyRate {
  id: number;
  section: string;
  key: string;
  label: string;
  value: string;
  unit: string;
  is_active: boolean;
  updated_at: string;
}

export interface PolicySection {
  section: string;
  settings: PolicyRate[];
}

export interface PolicyChange {
  previous_value: string;
  new_value: string;
  effective_date: string;
  changed_at: string;
  changed_by: string | null;
}

export interface RuleSetSummary {
  id: number;
  name: string;
  version: number;
  status: 'draft' | 'published' | 'superseded';
  effective_from: string;
  effective_to: string | null;
  notes: string;
  published_at: string | null;
  rule_count: number;
}

export interface PayableAward {
  id: number;
  student: string;
  application_id: number;
  category: string;
  amount: string;
}

export interface BlockedAward {
  award_id: number;
  application_id: number;
  reason: string;
}

export interface PaymentRun {
  count: number;
  total: string;
  awards: PayableAward[];
  blocked: BlockedAward[];
}

export interface DispatchResult {
  filename: string;
  csv: string;
  count: number;
  total: string;
  blocked: number;
}

export interface DashboardSummary {
  scope: 'student' | 'staff';
  applications: {
    total: number;
    open: number;
    by_status: Record<ApplicationStatus, number>;
  };
  money: Record<string, string>;
  /** Staff only. */
  queues?: {
    to_review: number;
    awaiting_decision: number;
    awaiting_enrolment_confirmation: number;
  };
  attention?: { submitted_late: number; residency_mismatch: number };
  /** Student only. */
  waiting_on_you?: number;
}

export interface Notification {
  id: number;
  title: string;
  message: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationList {
  /** Everything unread, not just what is on this page. */
  unread: number;
  results: Notification[];
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CurrentUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  display_name: string;
  role: 'student' | 'support_worker' | 'director' | 'finance' | 'admin';
  role_label: string;
  beneficiary_number: string;
  bank_account: { account_number: string; account_holder: string } | null;
}

// ── Errors ───────────────────────────────────────────────────────────────────

/**
 * An API failure, with per-field messages preserved.
 *
 * The previous client collapsed everything to a single string, so a form could
 * not show a message against the question it belonged to.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fieldErrors = fieldErrors;
  }

  /** True when the caller should re-authenticate rather than show a message. */
  get isAuthFailure(): boolean {
    return this.status === 401;
  }
}

function flatten(value: unknown): string {
  if (Array.isArray(value)) return value.map(flatten).join(' ');
  if (value && typeof value === 'object') return Object.values(value).map(flatten).join(' ');
  return String(value ?? '');
}

function toApiError(error: AxiosError): ApiError {
  const status = error.response?.status ?? 0;
  const body = error.response?.data as Record<string, unknown> | undefined;

  if (!body || typeof body !== 'object') {
    return new ApiError(status, error.message || 'The server could not be reached.');
  }

  if (typeof body.detail === 'string') {
    return new ApiError(status, body.detail);
  }

  // Answer-level errors arrive nested under `answers`, one message per field key.
  const fieldErrors: Record<string, string> = {};
  const answers = body.answers;
  if (answers && typeof answers === 'object' && !Array.isArray(answers)) {
    for (const [key, value] of Object.entries(answers)) fieldErrors[key] = flatten(value);
  } else {
    for (const [key, value] of Object.entries(body)) fieldErrors[key] = flatten(value);
  }

  const first = Object.values(fieldErrors)[0] ?? 'The request could not be completed.';
  return new ApiError(status, first, fieldErrors);
}

// ── Tokens ───────────────────────────────────────────────────────────────────

const ACCESS_KEY = 'dgg_access';
const REFRESH_KEY = 'dgg_refresh';

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokens.access;
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Concurrent 401s share one refresh.
 *
 * The backend rotates and blacklists refresh tokens, so a second refresh with
 * the same token fails and signs the user out mid-session.
 */
let refreshing: Promise<string> | null = null;

function refreshAccess(): Promise<string> {
  if (!refreshing) {
    refreshing = axios
      .post(`${API_BASE_URL}/auth/token/refresh/`, { refresh: tokens.refresh })
      .then((response) => {
        const access = response.data?.access;
        if (!access) throw new Error('Refresh response contained no access token');
        tokens.set(access, response.data?.refresh);
        return access as string;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };

    if (error.response?.status === 401 && original && !original._retried && tokens.refresh) {
      original._retried = true;
      try {
        const access = await refreshAccess();
        original.headers.Authorization = `Bearer ${access}`;
        return http(original);
      } catch {
        tokens.clear();
      }
    }
    return Promise.reject(toApiError(error));
  },
);

// ── Endpoints ────────────────────────────────────────────────────────────────

export const api = {
  /** What each application type asks. Served with an ETag, so repeats are 304s. */
  async schemas(): Promise<ApplicationSchema[]> {
    const { data } = await http.get<ApplicationSchema[]>('/schemas/');
    return data;
  },

  async schema(type: ApplicationType): Promise<ApplicationSchema> {
    const { data } = await http.get<ApplicationSchema>(`/schemas/${type}/`);
    return data;
  },

  async register(input: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    phone?: string;
  }): Promise<CurrentUser> {
    const { data } = await http.post<CurrentUser>('/auth/register/', input);
    return data;
  },

  async signIn(email: string, password: string): Promise<CurrentUser> {
    const { data } = await axios.post(`${API_BASE_URL}/auth/token/`, { email, password });
    tokens.set(data.access, data.refresh);
    return api.me();
  },

  signOut() {
    tokens.clear();
  },

  async me(): Promise<CurrentUser> {
    const { data } = await http.get<CurrentUser>('/me/');
    return data;
  },

  async updateMe(patch: Partial<CurrentUser>): Promise<CurrentUser> {
    const { data } = await http.patch<CurrentUser>('/me/', patch);
    return data;
  },

  async applications(params?: {
    page?: number;
    status?: ApplicationStatus;
    type?: ApplicationType;
  }): Promise<Page<ApplicationSummary>> {
    const { data } = await http.get<Page<ApplicationSummary>>('/applications/', { params });
    return data;
  },

  async application(id: number): Promise<Application> {
    const { data } = await http.get<Application>(`/applications/${id}/`);
    return data;
  },

  /** Answers are typed against the schema for `type`. */
  async submit<T extends ApplicationType>(
    type: T,
    stream: FundingStream,
    answers: AnswersFor<T>,
  ): Promise<Application> {
    const { data } = await http.post<Application>('/applications/', { type, stream, answers });
    return data;
  },

  async transition(id: number, action: TransitionAction, note = ''): Promise<Application> {
    const { data } = await http.post<Application>(`/applications/${id}/transition/`, {
      action,
      note,
    });
    return data;
  },

  /** What would be awarded, without recording anything. */
  async previewDecision(id: number): Promise<DecisionTrace> {
    const { data } = await http.get<DecisionTrace>(`/applications/${id}/decision-preview/`);
    return data;
  },

  async recordDecision(id: number): Promise<AwardDecision> {
    const { data } = await http.post<AwardDecision>(`/applications/${id}/price/`);
    return data;
  },

  /** Every pricing this application has had. What an appeal is argued from. */
  async decisionHistory(id: number): Promise<AwardDecision[]> {
    const { data } = await http.get<AwardDecision[]>(`/applications/${id}/decisions/`);
    return data;
  },

  /** The rates every award is computed from. */
  async policyRates(): Promise<PolicySection[]> {
    const { data } = await http.get<PolicySection[]>('/policy/rates/');
    return data;
  },

  async policyRate(id: number): Promise<{ setting: PolicyRate; history: PolicyChange[] }> {
    const { data } = await http.get(`/policy/rates/${id}/`);
    return data;
  },

  /**
   * Change a rate. Administrators only, and it never alters a decision already
   * made — an application is priced with the rates in force when it was
   * submitted.
   */
  async changePolicyRate(
    id: number,
    value: string,
    effectiveFrom?: string,
  ): Promise<PolicyRate> {
    const { data } = await http.patch<PolicyRate>(`/policy/rates/${id}/`, {
      value,
      ...(effectiveFrom ? { effective_from: effectiveFrom } : {}),
    });
    return data;
  },

  async setPolicyRateActive(id: number, isActive: boolean): Promise<PolicyRate> {
    const { data } = await http.patch<PolicyRate>(`/policy/rates/${id}/`, {
      is_active: isActive,
    });
    return data;
  },

  async ruleSets(): Promise<RuleSetSummary[]> {
    const { data } = await http.get<RuleSetSummary[]>('/policy/rule-sets/');
    return data;
  },

  /** A person's own notices. Never anyone else's. */
  async notifications(unreadOnly = false): Promise<NotificationList> {
    const { data } = await http.get<NotificationList>('/notifications/', {
      params: unreadOnly ? { unread: 'true' } : undefined,
    });
    return data;
  },

  /** Mark notices read. With no ids, marks everything read. */
  async markNotificationsRead(ids?: number[]): Promise<{ marked: number; unread: number }> {
    const { data } = await http.post('/notifications/', ids ? { ids } : {});
    return data;
  },

  /** Everything the opening screen needs, in one request. */
  async dashboard(): Promise<DashboardSummary> {
    const { data } = await http.get<DashboardSummary>('/dashboard/');
    return data;
  },

  /** What is ready to pay, and what is blocking anything from being paid. */
  async paymentRun(): Promise<PaymentRun> {
    const { data } = await http.get<PaymentRun>('/finance/pending/');
    return data;
  },

  /**
   * Send the batch. Returns the file itself, because a payment run that a
   * finance officer cannot hold in their hand is not much use.
   */
  async dispatchPaymentRun(): Promise<DispatchResult> {
    const response = await http.post('/finance/dispatch/', null, {
      responseType: 'text',
      transformResponse: [(body: string) => body],
    });
    const disposition = String(response.headers['content-disposition'] ?? '');
    return {
      filename: disposition.match(/filename="([^"]+)"/)?.[1] ?? 'awards.csv',
      csv: response.data as string,
      count: Number(response.headers['x-award-count'] ?? 0),
      total: String(response.headers['x-award-total'] ?? '0'),
      blocked: Number(response.headers['x-blocked-count'] ?? 0),
    };
  },
};

export default api;
