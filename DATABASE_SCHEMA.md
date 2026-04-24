# Database Schema - Supabase PostgreSQL

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USERS SYSTEM                             │
├─────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────┐
│  │     users        │ (CustomUser)
│  ├──────────────────┤
│  │ id (PK)          │
│  │ email (UNIQUE)   │
│  │ full_name        │
│  │ role             │
│  │ is_active        │
│  │ date_joined      │
│  └──────────────────┘
│         │
│         ├─────────────────────────────────────────┐
│         │                                         │
│         ▼                                         ▼
│  ┌──────────────────┐                  ┌──────────────────┐
│  │ user_profiles    │                  │ user_documents   │
│  ├──────────────────┤                  ├──────────────────┤
│  │ id (PK)          │                  │ id (PK)          │
│  │ user_id (FK)     │                  │ user_id (FK)     │
│  │ phone_number     │                  │ name             │
│  │ date_of_birth    │                  │ file             │
│  │ mailing_address  │                  │ category         │
│  │ institute        │                  │ uploaded_at      │
│  └──────────────────┘                  └──────────────────┘
│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATIONS SYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────────┐
│  │ student_applications     │ (Application)
│  ├──────────────────────────┤
│  │ id (PK)                  │
│  │ student_id (FK → users)  │
│  │ form_type                │
│  │ status                   │
│  │ amount                   │
│  │ created_at               │
│  │ updated_at               │
│  └──────────────────────────┘
│         │
│         ├──────────────────────────────────────────┐
│         │                                          │
│         ▼                                          ▼
│  ┌──────────────────────┐            ┌──────────────────────┐
│  │application_documents │            │     payments         │
│  ├──────────────────────┤            ├──────────────────────┤
│  │ id (PK)              │            │ id (PK)              │
│  │ application_id (FK)  │            │ user_id (FK)         │
│  │ name                 │            │ application_id (FK)  │
│  │ file                 │            │ amount               │
│  │ is_verified          │            │ payment_type         │
│  │ uploaded_at          │            │ status               │
│  └──────────────────────┘            │ reference_number     │
│                                      └──────────────────────┘
│         │
│         ▼
│  ┌──────────────────────┐
│  │     appeals          │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ user_id (FK)         │
│  │ application_id (FK)  │
│  │ reason               │
│  │ status               │
│  │ decision             │
│  │ created_at           │
│  └──────────────────────┘
│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      FORMS SYSTEM                                │
├─────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────┐
│  │    programs      │
│  ├──────────────────┤
│  │ id (PK)          │
│  │ title            │
│  │ description      │
│  │ is_active        │
│  │ created_at       │
│  └──────────────────┘
│         │
│         ▼
│  ┌──────────────────┐
│  │     forms        │
│  ├──────────────────┤
│  │ id (PK)          │
│  │ program_id (FK)  │
│  │ title            │
│  │ purpose          │
│  │ is_active        │
│  │ created_at       │
│  └──────────────────┘
│         │
│         ├──────────────────────────────────────────┐
│         │                                          │
│         ▼                                          ▼
│  ┌──────────────────┐                  ┌──────────────────────┐
│  │  form_fields     │                  │ form_submissions     │
│  ├──────────────────┤                  ├──────────────────────┤
│  │ id (PK)          │                  │ id (PK)              │
│  │ form_id (FK)     │                  │ form_id (FK)         │
│  │ label            │                  │ student_id (FK)      │
│  │ field_type       │                  │ status               │
│  │ is_required      │                  │ amount               │
│  │ order            │                  │ submitted_at         │
│  └──────────────────┘                  │ reviewed_at          │
│                                        │ decided_at           │
│                                        └──────────────────────┘
│                                                 │
│                                    ┌────────────┼────────────┐
│                                    │            │            │
│                                    ▼            ▼            ▼
│                          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│                          │submission_   │ │submission_   │ │mid_semester_ │
│                          │answers       │ │notes         │ │changes       │
│                          ├──────────────┤ ├──────────────┤ ├──────────────┤
│                          │ id (PK)      │ │ id (PK)      │ │ id (PK)      │
│                          │ submission_  │ │ submission_  │ │ submission_  │
│                          │ id (FK)      │ │ id (FK)      │ │ id (FK)      │
│                          │ field_id (FK)│ │ author_id(FK)│ │ change_type  │
│                          │ answer_text  │ │ text         │ │ old_value    │
│                          │ answer_file  │ │ created_at   │ │ new_value    │
│                          └──────────────┘ └──────────────┘ │ status       │
│                                                             └──────────────┘
│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    POLICY SYSTEM                                 │
├─────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────┐
│  │ policy_settings      │
│  ├──────────────────────┤
│  │ id (UUID, PK)        │
│  │ section              │
│  │ field_key            │
│  │ field_label          │
│  │ value                │
│  │ unit                 │
│  │ last_updated_at      │
│  └──────────────────────┘
│         │
│         ▼
│  ┌──────────────────────┐
│  │ policy_history       │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ setting_id (FK)      │
│  │ user_name            │
│  │ field_changed        │
│  │ old_value            │
│  │ new_value            │
│  │ timestamp            │
│  └──────────────────────┘
│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                  UTILITY TABLES                                  │
├─────────────────────────────────────────────────────────────────┤
│
│  ┌──────────────────────┐
│  │ shareable_links      │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ token (UNIQUE)       │
│  │ application_id (FK)  │
│  │ submission_id (FK)   │
│  │ created_at           │
│  │ expires_at           │
│  │ is_active            │
│  └──────────────────────┘
│
│  ┌──────────────────────┐
│  │ audit_logs           │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ action               │
│  │ performed_by_id (FK) │
│  │ application_id (FK)  │
│  │ details              │
│  │ timestamp            │
│  └──────────────────────┘
│
│  ┌──────────────────────┐
│  │ duplicate_detection_ │
│  │ logs                 │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ submission_id (FK)   │
│  │ identifier_hash      │
│  │ is_flagged           │
│  │ reviewed_by_id (FK)  │
│  │ created_at           │
│  └──────────────────────┘
│
│  ┌──────────────────────┐
│  │ notifications        │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ user_id (FK)         │
│  │ title                │
│  │ message              │
│  │ is_read              │
│  │ created_at           │
│  └──────────────────────┘
│
│  ┌──────────────────────┐
│  │application_deadlines │
│  ├──────────────────────┤
│  │ id (PK)              │
│  │ funding_stream       │
│  │ semester             │
│  │ deadline_date        │
│  │ late_application_    │
│  │ allowed              │
│  │ created_at           │
│  └──────────────────────┘
│
└─────────────────────────────────────────────────────────────────┘
```

## Table Statistics

| Category | Count | Tables |
|----------|-------|--------|
| **User Management** | 3 | users, user_profiles, user_documents |
| **Applications** | 4 | student_applications, application_documents, payments, appeals |
| **Forms** | 7 | programs, forms, form_fields, form_submissions, submission_answers, submission_notes, mid_semester_changes |
| **Policies** | 2 | policy_settings, policy_history |
| **Utilities** | 5 | shareable_links, audit_logs, duplicate_detection_logs, notifications, application_deadlines |
| **Django System** | 8+ | auth_user, auth_group, auth_permission, django_session, django_migrations, django_content_type, etc. |
| **TOTAL** | 30+ | All tables |

## Key Indexes

### Performance Indexes
```sql
-- User lookups
CREATE INDEX idx_users_email ON users(email);

-- Application queries
CREATE INDEX idx_student_applications_student_id ON student_applications(student_id);
CREATE INDEX idx_student_applications_status ON student_applications(status);

-- Form submissions
CREATE INDEX idx_form_submissions_student_id ON form_submissions(student_id);
CREATE INDEX idx_form_submissions_status ON form_submissions(status);

-- Duplicate detection
CREATE INDEX idx_duplicate_detection_logs_identifier_hash ON duplicate_detection_logs(identifier_hash);
CREATE INDEX idx_duplicate_detection_logs_is_flagged ON duplicate_detection_logs(is_flagged);

-- Audit trail
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_performed_by_id ON audit_logs(performed_by_id);
```

## Constraints

### Unique Constraints
- `users.email` - Email must be unique
- `policy_settings` - (section, field_key) combination must be unique
- `application_deadlines` - (funding_stream, semester) combination must be unique
- `shareable_links.token` - Token must be unique

### Foreign Key Constraints
- All relationships are enforced at database level
- Cascade delete for related records (e.g., deleting user deletes their profile)
- Set NULL for optional relationships (e.g., reviewed_by can be NULL)

## Data Types

| Type | Usage | Examples |
|------|-------|----------|
| **BIGINT** | Primary keys | id |
| **UUID** | Unique identifiers | policy_settings.id |
| **VARCHAR** | Text fields | email, name, title |
| **TEXT** | Long text | description, reason, notes |
| **DECIMAL(12,2)** | Money | amount, value |
| **BOOLEAN** | Flags | is_active, is_verified |
| **TIMESTAMP** | Dates/times | created_at, updated_at |
| **DATE** | Dates only | date_of_birth, deadline_date |
| **JSON** | Flexible data | form_data, office_use_data |

## Connection Details

```
Host: db.whxqwxwznrsqahsjrfih.supabase.co
Port: 5432 (Direct) or 6543 (Pooler)
Database: postgres
User: postgres
SSL: Required (sslmode=require)
```

## Backup Strategy

- Supabase provides automatic daily backups
- Manual backups can be created in dashboard
- Point-in-time recovery available
- Backup retention: 7 days (free tier)

## Performance Considerations

✅ All tables have primary keys
✅ Foreign keys are indexed
✅ Frequently queried fields are indexed
✅ Timestamps use UTC
✅ JSON fields for flexible data
✅ Decimal for precise money values

## Security

✅ SSL/TLS encryption in transit
✅ Row-level security available
✅ Audit logs for compliance
✅ Password hashing for users
✅ No sensitive data in logs
