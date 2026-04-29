-- ============================================================
-- Row Level Security (RLS) Migration for DGG Student Portal
-- Run this in Supabase SQL Editor
-- 
-- Strategy: Enable RLS on all tables, then add a BYPASS policy
-- for the Django backend (postgres role) so the app works normally.
-- Direct PostgREST/anon access is blocked by default.
-- ============================================================

-- ── 1. APPLICATION TABLES ──────────────────────────────────

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appeals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shareable_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.duplicate_detection_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- ── 2. FORMS TABLES ───────────────────────────────────────

ALTER TABLE public.forms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mid_semester_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_deadlines ENABLE ROW LEVEL SECURITY;

-- ── 3. PROGRAMS & OTHER TABLES ────────────────────────────

ALTER TABLE public.programs ENABLE ROW LEVEL SECURITY;

-- ── 4. DJANGO SYSTEM TABLES ───────────────────────────────

ALTER TABLE public.django_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.django_content_type ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.django_admin_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.django_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_permission ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_group ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_group_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users_user_permissions ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- BYPASS POLICIES FOR DJANGO BACKEND (postgres role)
-- Django connects as the 'postgres' superuser which bypasses
-- RLS by default, so these policies are a safety net.
-- They allow full access for the service role only.
-- ============================================================

-- Helper: create bypass policy for a table
-- Pattern: allow ALL operations for the postgres/service_role

-- ── Application Tables ────────────────────────────────────

CREATE POLICY "django_backend_access" ON public.users
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.user_profiles
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.user_documents
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.student_applications
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.application_documents
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.payments
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.appeals
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.audit_logs
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.policy_settings
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.policy_history
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.shareable_links
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.duplicate_detection_logs
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.notifications
    FOR ALL TO postgres USING (true) WITH CHECK (true);

-- ── Forms Tables ──────────────────────────────────────────

CREATE POLICY "django_backend_access" ON public.forms
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.form_fields
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.form_submissions
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.submission_answers
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.submission_notes
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.mid_semester_changes
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.application_deadlines
    FOR ALL TO postgres USING (true) WITH CHECK (true);

-- ── Programs ──────────────────────────────────────────────

CREATE POLICY "django_backend_access" ON public.programs
    FOR ALL TO postgres USING (true) WITH CHECK (true);

-- ── Django System Tables ──────────────────────────────────

CREATE POLICY "django_backend_access" ON public.django_migrations
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.django_content_type
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.django_admin_log
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.django_session
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.auth_permission
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.auth_group
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.auth_group_permissions
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.users_groups
    FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE POLICY "django_backend_access" ON public.users_user_permissions
    FOR ALL TO postgres USING (true) WITH CHECK (true);

-- ============================================================
-- VERIFY: Check RLS is enabled on all tables
-- Run this after applying the above to confirm
-- ============================================================
-- SELECT tablename, rowsecurity 
-- FROM pg_tables 
-- WHERE schemaname = 'public'
-- ORDER BY tablename;
