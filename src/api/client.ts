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

import { API_BASE_URL } from './config';
import type {
  AnswersFor,
  ApplicationSchema,
  ApplicationStatus,
  ApplicationType,
  FundingStream,
  SchemaField,
  TransitionAction,
} from './schema.generated';

export type {
  ApplicationSchema, ApplicationType, AnswersFor, SchemaField,
  // Backend enums, emitted rather than restated. Written out here by hand they
  // drifted from the workflow: the server began accepting an approval straight
  // from review and the client went on believing it could not.
  ApplicationStatus, TransitionAction, FundingStream,
};

// ── Wire types ───────────────────────────────────────────────────────────────

/**
 * What can be applied for without an account.
 *
 * Both are one-off awards claimed after the fact — a summer placement and a
 * finished credential — where insisting on a portal account first is what kept
 * the claim from being made at all.
 */
export type GuestApplicationType = 'practicum' | 'graduation_bursary';

/** All a guest gets back: there is no application page for them to open. */
export interface GuestReceipt {
  reference: string;
  detail: string;
}

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
/**
 * Where the institution's confirmation has got to.
 *
 * On the summary as well as the detail: an admission application cannot be
 * forwarded or approved until the registrar answers, so the queue has to say
 * so before anyone opens the row and tries.
 */
export interface EnrolmentState {
  required: boolean;
  /**
   * `not_requested` is not the same as `not_required`. It means this form does
   * need the institution and nobody has asked yet — which is a dead end until
   * somebody does: tuition cannot be confirmed, so the application cannot be
   * forwarded or approved. Both were once reported as 'not_required'.
   */
  status: 'not_required' | 'not_requested' | 'requested' | 'completed' | 'expired';
  label: string;
  confirmed?: boolean;
  registrar_email?: string;
  requested_at?: string;
  responded_at?: string | null;
}

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
  enrolment: EnrolmentState;
}

export interface Application extends ApplicationSummary {
  schema_slug: ApplicationType;
  answers: Record<string, unknown>;
  office_notes: Record<string, unknown>;
  events: ApplicationEvent[];
  decision: AwardDecision | null;
  /** What the institution declared, once it has. Null until then. */
  enrolment_answers: Record<string, unknown> | null;
  /**
   * Government identifiers, masked. The server never sends the whole number —
   * reading one is a separate, audited act.
   */
  identifiers: Record<string, string>;
  /**
   * Whether an award can be paid, and nothing more.
   *
   * `account` is the last four digits. The bank details are asked for on the
   * form and kept out of `answers` entirely — they live on the account record
   * finance pays from, and only the payment file carries the whole number.
   */
  /** Everything attached, so a reviewer can open it. */
  documents: AttachedDocument[];
  /** Whether the person reading this may edit it — the student it belongs to,
   *  and only while the office is waiting for something. */
  can_revise: boolean;
  /** Null unless the office has asked for something. */
  information_requested: InformationRequest | null;
  banking: {
    on_file: boolean;
    /** Masked, e.g. '••••3210'. Empty when nothing is on file. */
    account: string;
    holder: string;
    /** A guest application's details, waiting to be attached to an account. */
    held: boolean;
  };
}

/** Contact details and the questions the office is asked most. */
export interface Help {
  contact: { email: string; phone: string; address: string };
  faq: Array<{ question: string; answer: string }>;
}

/** A file attached to an application, as a screen needs it. */
export interface AttachedDocument {
  id: number;
  field_key: string;
  original_name: string;
  uploaded_at: string;
  /** Served by Django, permission-checked. Not a MEDIA_URL path. */
  url: string;
}

/** What the office asked for, and who asked. */
export interface InformationRequest {
  note: string;
  asked_by: string;
  asked_at: string;
}

/** One line of a hand-set breakdown, as the office types it. */
export interface AwardLineInput {
  category: string;
  description: string;
  amount: string;
}

export interface UploadedDocument {
  id: number;
  field_key: string;
  original_name: string;
  uploaded_at: string;
  /** What the answer becomes: the schema stores a pointer, not the file. */
  reference: string;
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
  student?: { name: string; reference: string };
  /**
   * The one thing this student should do next, decided server-side.
   *
   * The rule for "what comes next" is funding policy, not presentation: it
   * belongs where the statuses are, not restated in a component that cannot
   * see an outstanding enrolment request.
   */
  next_step?: {
    key: string;
    title: string;
    detail: string;
    /** Empty when there is nothing for them to do but wait. */
    action: string;
    href: string;
  };
  recent?: Array<{
    id: number;
    type: ApplicationType;
    type_label: string;
    status: ApplicationStatus;
    status_label: string;
    awarded_total: string;
    submitted_at: string;
  }>;
  /**
   * The next cut-offs, one per term, soonest first.
   *
   * Empty when the office has set none, and the screen then shows no dates
   * rather than inventing them. Deduplicated server-side: the same date is set
   * for every stream, so the rows would otherwise repeat each date three times.
   */
  deadlines?: Array<{
    semester: string;
    academic_year: string;
    closes_at: string;
    late_allowed: boolean;
  }>;
}

/**
 * What kind of thing happened.
 *
 * Recorded by the server, not inferred from the title. Matching on words in a
 * display string is how a reworded label used to change behaviour.
 */
export type NotificationKind =
  | 'received'
  | 'action_needed'
  | 'approved'
  | 'declined'
  | 'general';

export interface Notification {
  id: number;
  kind: NotificationKind;
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

export type UserRole = 'student' | 'support_worker' | 'director' | 'finance' | 'admin';

export interface DirectoryPerson {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  role_label: string;
  is_active: boolean;
  beneficiary_number: string;
  date_joined: string;
}

export interface Directory {
  roles: Array<{ value: UserRole; label: string }>;
  results: DirectoryPerson[];
}

export interface EligibilityQuestion {
  key: string;
  text: string;
  help: string;
  choices: Array<{ value: string; label: string }>;
}

/** The office's decision on whether someone may apply, and what to tell them. */
export interface EligibilityOutcome {
  eligible: boolean;
  streams: string[];
  title: string;
  message: string;
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

// No global Content-Type. Axios sets 'application/json' for a plain object by
// itself, and setting it here applied it to file uploads too: a FormData body
// labelled application/json never gets a multipart boundary, so Django parses
// no file and DRF answers 'The submitted data was not a file. Check the
// encoding type on the form.'
// Exported so tests can inspect what is actually put on the wire. Prefer the
// named endpoints below over reaching for this directly.
export const http: AxiosInstance = axios.create({ baseURL: API_BASE_URL });

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokens.access;
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Belt and braces: if anything ever sets a JSON content type on a request
  // carrying FormData, drop it so the browser can supply the boundary.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    delete config.headers['Content-Type'];
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

  /**
   * What this student's copy of a form opens with.
   *
   * Their own answers, so unlike the schema it is never cached. Only the
   * continuing-funding renewal has much to say here: it exists to be confirmed
   * rather than filled in.
   */
  async formPrefill(type: ApplicationType): Promise<Record<string, string | number | boolean>> {
    const { data } = await http.get<{ answers: Record<string, string | number | boolean> }>(
      `/form-prefill/${type}/`,
    );
    return data.answers;
  },

  /** The screening questions. Public: someone checks before they have an account. */
  async eligibilityQuestions(): Promise<EligibilityQuestion[]> {
    const { data } = await http.get<{ questions: EligibilityQuestion[] }>(
      '/auth/eligibility/',
    );
    return data.questions;
  },

  async checkEligibility(answers: Record<string, string>): Promise<EligibilityOutcome> {
    const { data } = await http.post<EligibilityOutcome>('/auth/eligibility/', {
      answers,
    });
    return data;
  },

  async register(input: {
    email: string;
    password: string;
    confirm_password: string;
    first_name: string;
    last_name: string;
    phone?: string;
    eligibility: Record<string, string>;
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
  /**
   * Submit an application.
   *
   * No stream: it follows from the eligibility answers given at sign-up and the
   * SFA answer on this form, and the server decides it. It gates which tuition
   * and living-allowance rules apply, so a client that could choose it could
   * choose one the applicant does not qualify for.
   */
  async submit<T extends ApplicationType>(
    type: T,
    answers: AnswersFor<T>,
  ): Promise<Application> {
    const { data } = await http.post<Application>('/applications/', { type, answers });
    return data;
  },

  /**
   * The forms that can be filled in without an account.
   *
   * Which types those are is the server's decision, not a list duplicated here:
   * a client-side list would drift, and widening it here would widen nothing —
   * the endpoint refuses anything else.
   */
  async guestSchemas(): Promise<ApplicationSchema[]> {
    const { data } = await http.get<ApplicationSchema[]>('/guest-applications/');
    return data;
  },

  /** Submit one of them. There is no session, and no application to return to. */
  async submitGuest(
    type: GuestApplicationType,
    // Whatever the schema says the answers are. Two field types hold a list —
    // several receipts, or the rows of an expense breakdown — so narrowing this
    // to scalars would have described the wire wrongly.
    answers: Record<string, unknown>,
  ): Promise<GuestReceipt> {
    const { data } = await http.post<GuestReceipt>('/guest-applications/', {
      type,
      answers,
    });
    return data;
  },

  /**
   * Attach a document.
   *
   * Sent as multipart and stored server-side; the answer keeps a reference, not
   * the file. May be uploaded before the application exists — the form is
   * filled in over several sittings — and claimed on submission.
   */
  /**
   * The help page.
   *
   * No token attached deliberately: somebody who cannot sign in is exactly who
   * needs the phone number, and this is served without a session.
   */
  async help(): Promise<Help> {
    const { data } = await http.get<Help>('/help/');
    return data;
  },

  /**
   * Answer a request for more information.
   *
   * The whole answer set, not a patch: the server validates a revision by the
   * same schema that validated the original, and recording that the
   * information was provided is part of the same act.
   */
  async revise(id: number, answers: Record<string, unknown>, note = '') {
    const { data } = await http.post<Application>(
      `/applications/${id}/revise/`, { answers, note });
    return data;
  },

  /**
   * The office correcting a filed application on the applicant's behalf.
   *
   * Administrators only, refused on anything already decided, and the applicant
   * is notified by the server every time. Sends the whole answer set for the
   * same reason `revise` does: a partial update needs a second, weaker notion
   * of complete, and the weaker one is the one that lets something through.
   */
  async amend(id: number, answers: Record<string, unknown>, note = '') {
    const { data } = await http.post<Application>(
      `/applications/${id}/amend/`, { answers, note });
    return data;
  },

  /**
   * Ask the institution to confirm an enrolment, or ask again.
   *
   * Submission does this by itself when a registrar address is already known.
   * It is not, for a renewal by somebody whose earlier applications are not in
   * the portal — and for an address that bounced or a request that expired,
   * this is the only way back.
   */
  async requestEnrolment(id: number, registrarEmail = '') {
    const { data } = await http.post<Application>(
      `/applications/${id}/request-enrolment/`,
      registrarEmail ? { registrar_email: registrarEmail } : {});
    return data;
  },

  /**
   * Set the funding breakdown by hand.
   *
   * The rules price the ordinary case. They cannot know an institution charges
   * a fee no rate covers, or that the office agreed something at the counter —
   * and the alternatives were to edit a policy rate, which changes what
   * everyone is paid, or to pay the wrong amount. Recorded as a decision like
   * any other: it supersedes, and every line says who entered it.
   */
  async setAward(id: number, lines: AwardLineInput[], note = '') {
    const { data } = await http.post<AwardDecision>(
      `/applications/${id}/award/`, { lines, note });
    return data;
  },

  async awardCategories(id: number) {
    const { data } = await http.get<Array<{ value: string; label: string }>>(
      `/applications/${id}/award-categories/`);
    return data;
  },

  async uploadDocument(
    file: File,
    fieldKey: string,
    applicationId?: number,
  ): Promise<UploadedDocument> {
    const form = new FormData();
    form.append('file', file);
    form.append('field_key', fieldKey);
    if (applicationId !== undefined) form.append('application', String(applicationId));

    const { data } = await http.post<UploadedDocument>('/documents/', form);
    return data;
  },

  /**
   * Open an attached document.
   *
   * It cannot be an ordinary link. The endpoint is permission-checked and
   * authorised by the bearer token, which a browser navigation does not carry:
   * a plain `<a href>` opened the API's 401 page instead of the transcript, for
   * every role. Fetched here so the token goes with it, then handed to the tab
   * as a blob.
   */
  async openDocument(url: string): Promise<Blob> {
    const { data } = await http.get<Blob>(url.replace(/^\/api/, ''), {
      responseType: 'blob',
    });
    return data;
  },

  /**
   * The enrolment verification as the registrar will receive it.
   *
   * Rendered from the same schema and the same pre-fill the server would send,
   * so what a student previews is what actually goes.
   */
  async enrolmentPreview(type: ApplicationType, answers: Record<string, unknown>) {
    const { data } = await http.post<{
      schema: ApplicationSchema;
      prefill: Record<string, string | number | boolean>;
      note_to_registrar: string;
      registrar_email: string;
    }>('/enrolment-preview/', { type, answers });
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

  /** Everyone with an account. Staff may read it; only an admin may change it. */
  async directory(params?: {
    search?: string;
    role?: string;
    include_inactive?: boolean;
  }): Promise<Directory> {
    const { data } = await http.get<Directory>('/people/', {
      params: {
        ...(params?.search ? { search: params.search } : {}),
        ...(params?.role ? { role: params.role } : {}),
        ...(params?.include_inactive ? { include_inactive: 'true' } : {}),
      },
    });
    return data;
  },

  async changeRole(id: number, role: UserRole): Promise<DirectoryPerson> {
    const { data } = await http.patch<DirectoryPerson>(`/people/${id}/`, { role });
    return data;
  },

  async setAccountActive(id: number, isActive: boolean): Promise<DirectoryPerson> {
    const { data } = await http.patch<DirectoryPerson>(`/people/${id}/`, {
      is_active: isActive,
    });
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
