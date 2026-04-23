# Student Funding Application Management System (SFAP) - Design Document

## System Architecture Overview

### Technology Stack
- **Frontend**: React 19 + TypeScript + Vite
- **Backend**: Django 5.2 + Django REST Framework
- **Database**: PostgreSQL (production) / SQLite (development)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Hosting**: Vercel (frontend) + Heroku/Railway (backend)

### Core Components

#### 1. Frontend Architecture
```
src/
├── pages/
│   ├── SignIn.tsx (Student login)
│   ├── SignUp.tsx (Student registration)
│   ├── Dashboard.tsx (Student dashboard)
│   ├── StaffDashboard.tsx (Staff/Director dashboard)
│   ├── InternalSignIn.tsx (Staff login)
│   └── Forms/
│       ├── FormA.tsx (New Student Application)
│       ├── FormC.tsx (Continuing Student)
│       ├── FormD.tsx (Change of Information)
│       ├── FormE.tsx (Travel Reimbursement)
│       ├── FormF.tsx (Summer/Practicum Award)
│       ├── FormG.tsx (Graduation Award)
│       ├── FormH.tsx (Appeal)
│       ├── HardshipBursary.tsx
│       └── AcademicScholarship.tsx
├── components/
│   ├── Auth/
│   │   ├── ProtectedRoute.tsx
│   │   └── AdminErrorBoundary.tsx
│   └── Forms/
│       ├── FormWizard.tsx
│       └── StandaloneFormWrapper.tsx
├── api/
│   └── client.ts (Axios API client)
├── styles/
│   ├── index.css (Global styles)
│   ├── dashboard.css (Student dashboard)
│   └── staff.css (Staff dashboard)
└── config/
    └── api.ts (API configuration)
```

#### 2. Backend Architecture
```
backend/
├── core/ (Django settings)
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── users/ (User management)
│   ├── models.py (CustomUser)
│   ├── views.py
│   └── serializers.py
├── api/ (Core API)
│   ├── models.py (Profile, Application, AuditLog, PolicySetting, etc.)
│   ├── controllers/ (ViewSets)
│   │   ├── form_controller.py
│   │   ├── policy_controller.py
│   │   └── auth_controller.py
│   ├── services/ (Business logic)
│   │   ├── form_service.py
│   │   ├── calculation_service.py
│   │   ├── eligibility_service.py
│   │   └── duplicate_detection_service.py
│   ├── serializers.py
│   └── utils/
│       └── responses.py
├── forms/ (Form management)
│   ├── models.py (Form, FormField, FormSubmission, SubmissionAnswer, MidSemesterChange, ApplicationDeadline)
│   ├── views.py
│   └── serializers.py
├── notifications/ (Notification system)
│   ├── models.py
│   └── views.py
└── programs/ (Program management)
    ├── models.py
    └── views.py
```

#### 3. Database Schema

**Core Models**:
- `CustomUser`: Student/Staff/Director accounts
- `Profile`: Extended user profile information
- `Form`: Form definitions
- `FormField`: Form field definitions
- `FormSubmission`: Student form submissions
- `SubmissionAnswer`: Individual form answers
- `SubmissionNote`: Internal staff notes
- `PolicySetting`: Configurable policy rules
- `PolicyHistory`: Policy change audit trail
- `Payment`: Payment records
- `AuditLog`: Complete action audit trail
- `Notification`: User notifications
- `ShareableLink`: Shareable application links
- `Appeal`: Application appeals
- `DuplicateDetectionLog`: Duplicate detection tracking
- `MidSemesterChange`: Mid-semester change tracking
- `ApplicationDeadline`: Application deadline management

---

## Design Patterns & Principles

### 1. User Interface Design
- **Color Scheme**: Warm beige/tan (#fcfaf8, #e5a662) with dark text (#1e293b)
- **Typography**: Inter font family, 13px base size
- **Spacing**: 8px grid system
- **Responsive**: Mobile-first, works on all devices
- **Accessibility**: WCAG 2.1 Level AA compliant

### 2. API Design
- **RESTful**: Standard HTTP methods (GET, POST, PUT, DELETE)
- **Response Format**: `{ success: boolean, data: any, message: string }`
- **Authentication**: JWT Bearer tokens
- **Pagination**: 10 items per page by default
- **Error Handling**: Consistent error responses with status codes

### 3. State Management
- **Frontend**: React hooks (useState, useEffect, useContext)
- **Backend**: Django ORM with transaction support
- **Caching**: Browser localStorage for tokens and user preferences

### 4. Security
- **Authentication**: JWT with 60-minute access token lifetime
- **Authorization**: Role-based access control (student, admin/ssw, director)
- **Data Protection**: HTTPS/TLS encryption in transit
- **Privacy**: SHA-256 hashing for duplicate detection identifiers
- **Audit Trail**: Complete logging of all actions

---

## Feature Implementation Plan

### Phase 1: Core Application (Weeks 1-2) ✅ COMPLETE
- [x] User authentication (sign up, sign in, password reset)
- [x] Student profile management
- [x] Online application forms (Forms A-H)
- [x] Form submission and storage
- [x] Automatic funding calculation
- [x] Payment processing
- [x] Audit logging

### Phase 2: Staff Dashboard & Eligibility (Weeks 3-4) 🔄 IN PROGRESS
- [x] Eligibility rules engine (backend)
- [x] Duplicate detection with privacy protection (backend)
- [x] Application deadlines (backend)
- [x] Mid-semester changes (backend)
- [x] Director banking access control (backend)
- [ ] Staff dashboard UI enhancements (frontend)
  - [ ] Applications list with sorting/filtering/pagination
  - [ ] Application detail view
  - [ ] Eligibility determination display
  - [ ] Duplicate flag display
  - [ ] Banking details display (director only)
  - [ ] Audit trail display
  - [ ] Status badges with colors

### Phase 3: Notifications & Reporting (Weeks 5-6) ⏳ PENDING
- [ ] Email notification system (SMTP integration)
- [ ] Quarterly and annual reporting
- [ ] Report generation and export (PDF/CSV)
- [ ] Finance notification system
- [ ] Payment confirmation workflow

### Phase 4: Integration & Polish (Weeks 7-8) ⏳ PENDING
- [ ] deline.ca website integration
- [ ] Mobile optimization
- [ ] Performance optimization
- [ ] Security hardening
- [ ] User acceptance testing

---

## Staff Dashboard Design

### Layout Structure
```
┌─────────────────────────────────────────────────────────┐
│ SIDEBAR (240px)          │ MAIN CONTENT AREA            │
├─────────────────────────────────────────────────────────┤
│ • Dashboard              │ TOPBAR                       │
│ • Applications           │ View Title | Notifications   │
│ • Payments               │                              │
│ • Reports                ├──────────────────────────────┤
│ • Policy Settings        │ CONTENT                      │
│ • Appeals                │                              │
│                          │ [Filters & Search]           │
│ [Sign Out]               │ [Applications Table]         │
│                          │ [Pagination]                 │
└─────────────────────────────────────────────────────────┘
```

### Applications List View
**Columns**:
- ID (sortable)
- Student Name (sortable)
- Form Type (sortable)
- Status (sortable, with color badges)
- Amount (sortable)
- Submitted Date (sortable)

**Filters**:
- Search by name or ID
- Filter by status (All, Pending, Reviewed, Forwarded, Approved, Rejected)
- Filter by funding stream (All, PSSSP, UCEPP, DGGR)

**Pagination**: 10 items per page with Previous/Next buttons

### Application Detail View
**Sections**:
1. **Eligibility Determination**
   - Eligible funding streams (green badges)
   - Ineligible streams with reasons (red badges)

2. **Duplicate Flag** (if flagged)
   - Warning message
   - Mark as Legitimate / Confirm Duplicate buttons

3. **Submitted Information**
   - All form answers in readable format
   - File uploads with download links

4. **Funding Breakdown**
   - Tuition amount
   - Living allowance
   - Books & supplies
   - Special awards
   - Total amount

5. **Audit Trail**
   - Timeline of all actions
   - Who performed each action
   - When each action occurred

6. **Banking Details** (Director only)
   - Account holder name
   - Bank name
   - Account number
   - Transit number

7. **Action Buttons**
   - Approve / Reject
   - Request Info
   - Add Note
   - Share Link
   - Export PDF

---

## API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/refresh/` - Refresh JWT token
- `GET /api/auth/me/` - Get current user
- `PUT /api/auth/me/` - Update current user

### Forms
- `GET /api/forms/forms/` - List all forms
- `POST /api/forms/forms/{id}/submit/` - Submit form
- `GET /api/forms/submissions/` - List submissions
- `PUT /api/forms/submissions/{id}/status/` - Update submission status
- `POST /api/forms/submissions/{id}/notes/` - Add internal note
- `POST /api/forms/submissions/{id}/share/` - Generate shareable link
- `POST /api/forms/submissions/{id}/check-eligibility/` - Check eligibility
- `POST /api/forms/submissions/{id}/check-duplicates/` - Check for duplicates
- `POST /api/forms/submissions/{id}/mark-legitimate/` - Mark as legitimate
- `POST /api/forms/submissions/{id}/mark-duplicate/` - Confirm duplicate

### Applications
- `GET /api/applications/` - List applications
- `POST /api/applications/` - Create application
- `GET /api/applications/{id}/` - Get application details
- `PUT /api/applications/{id}/` - Update application

### Policy
- `GET /api/policy/` - Get all policy settings
- `POST /api/policy/bulk_update/` - Bulk update policy settings

### Payments
- `GET /api/payments/` - List payments
- `POST /api/payments/` - Create payment

### Audit
- `GET /api/audit-logs/` - Get audit logs

---

## Data Flow Diagrams

### Student Application Flow
```
Student → Fill Form → Submit → Eligibility Check → Duplicate Check
  ↓
Calculation → Payment Record → Staff Review → Director Approval
  ↓
Payment Processing → Student Notification → Finance Notification
```

### Staff Review Flow
```
Staff Dashboard → View Applications → Select Application → Review Details
  ↓
Check Eligibility → Check Duplicates → Add Notes → Approve/Reject
  ↓
Forward to Director → Director Reviews → Director Approves → Payment
```

### Director Approval Flow
```
Director Queue → View Pending Applications → Review Details
  ↓
View Banking Details → Approve/Reject → Send to Finance
  ↓
Finance Processes Payment → Student Notified
```

---

## Performance Targets

- Form loading: < 3 seconds
- Form submission: < 5 seconds
- Dashboard loading: < 3 seconds
- Application list: < 2 seconds
- Application detail: < 2 seconds
- 99.5% uptime during business hours

---

## Security Considerations

### Data Protection
- All data encrypted in transit (HTTPS/TLS)
- Personal information encrypted at rest
- Privacy-protected identifiers (SHA-256 hashing)
- No sensitive data in logs or exports

### Access Control
- Role-based access control (RBAC)
- Banking details restricted to Director only
- Audit trail for all sensitive operations
- Re-authentication for sensitive operations

### Compliance
- PIPEDA compliant
- NWT privacy legislation compliant
- WCAG 2.1 Level AA accessibility
- Canadian data residency

---

## Testing Strategy

### Unit Tests
- Eligibility logic with various scenarios
- Calculation service with different inputs
- Duplicate detection without exposing identifiers
- Banking details access control

### Integration Tests
- End-to-end application submission
- Eligibility check with real form data
- Duplicate detection workflow
- Director approval workflow
- Payment processing

### Security Tests
- Banking details not exposed to non-directors
- Duplicate detection method not exposed
- Audit trail completeness
- Re-authentication for sensitive operations

### Performance Tests
- Load testing with 1000+ concurrent users
- Database query optimization
- API response time monitoring
- Frontend rendering performance

---

## Deployment Strategy

### Development Environment
- Local development with SQLite
- Hot module reloading for frontend
- Django development server

### Staging Environment
- PostgreSQL database
- Vercel preview deployments
- Full testing before production

### Production Environment
- PostgreSQL on managed database service
- Vercel for frontend hosting
- Railway/Heroku for backend
- CDN for static assets
- Email service for notifications

---

## Maintenance & Support

### Post-Launch Support (6 months)
- Bug fixes and patches
- Performance optimization
- Security updates
- User support and training

### Ongoing Maintenance
- Monthly security updates
- Quarterly feature enhancements
- Annual infrastructure review
- Continuous monitoring and alerting

---

## Success Metrics

- 100% of applications submitted online (zero email submissions)
- Average application processing time reduced by 50%
- 100% accuracy in eligibility and funding calculations
- 100% compliance with policy rules
- Staff satisfaction score > 4.5/5
- Student satisfaction score > 4.5/5
- Zero data breaches or security incidents
- 99.5% system uptime

---

**Document Version**: 1.0
**Last Updated**: April 2026
**Status**: In Progress (Phase 2)
