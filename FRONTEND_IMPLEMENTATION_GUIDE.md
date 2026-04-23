# Frontend Implementation Guide - Staff Dashboard UI Enhancements

## Overview
This guide provides detailed instructions for implementing the Staff Dashboard UI enhancements (Priority 1) for the Student Funding Application Management System.

## Current State
- StaffDashboard.tsx exists (2043 lines) with basic structure
- Has navigation, some views, but applications list view is incomplete
- Detail view needs enhancement
- Existing CSS has color scheme defined

## Implementation Tasks

### Task 1: Enhance Applications List View

#### Location
`src/pages/StaffDashboard.tsx` - `currentView === 'applications'` section

#### Requirements
1. **Sortable Table Columns**
   - ID (sortable)
   - Student Name (sortable)
   - Form Type (sortable)
   - Status (sortable)
   - Amount (sortable)
   - Submitted Date (sortable)

2. **Status Badges with Colors**
   ```
   pending = yellow (#fbbf24)
   reviewed = blue (#3b82f6)
   forwarded = purple (#a855f7)
   accepted = green (#10b981)
   rejected = red (#ef4444)
   ```

3. **Search Functionality**
   - Search by student name
   - Search by application ID
   - Real-time filtering

4. **Filter Dropdowns**
   - Filter by status (All, Pending, Reviewed, Forwarded, Accepted, Rejected)
   - Filter by funding stream (All, PSSSP, UCEPP, DGGR)

5. **Pagination**
   - 10 items per page
   - Previous/Next buttons
   - Page indicator

6. **Row Click Action**
   - Click row to view application details
   - Navigate to detail view

#### Implementation Code Structure
```typescript
// State management
const [sortColumn, setSortColumn] = useState<string>('submitted_at');
const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
const [currentPage, setCurrentPage] = useState(1);
const [fundingStreamFilter, setFundingStreamFilter] = useState('all');

// Sorting function
const handleSort = (column: string) => {
  if (sortColumn === column) {
    setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
  } else {
    setSortColumn(column);
    setSortDirection('asc');
  }
};

// Filtering and sorting logic
const filteredAndSortedApps = useMemo(() => {
  let result = filteredApps;
  
  // Apply funding stream filter
  if (fundingStreamFilter !== 'all') {
    result = result.filter(app => 
      app.form_title?.includes(fundingStreamFilter)
    );
  }
  
  // Sort
  result.sort((a, b) => {
    let aVal = a[sortColumn];
    let bVal = b[sortColumn];
    
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase();
      bVal = bVal.toLowerCase();
    }
    
    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });
  
  return result;
}, [filteredApps, sortColumn, sortDirection, fundingStreamFilter]);

// Pagination
const itemsPerPage = 10;
const totalPages = Math.ceil(filteredAndSortedApps.length / itemsPerPage);
const paginatedApps = filteredAndSortedApps.slice(
  (currentPage - 1) * itemsPerPage,
  currentPage * itemsPerPage
);
```

#### UI Components
```jsx
{/* Filters */}
<div className="admin-filters" style={{ gridTemplateColumns: '1fr auto auto auto' }}>
  <div className="admin-search">
    <input
      type="text"
      className="admin-input"
      placeholder="Search applicant, ref #..."
      value={searchQuery}
      onChange={(e) => {
        setSearchQuery(e.target.value);
        setCurrentPage(1);
      }}
    />
  </div>
  <select 
    className="admin-input" 
    style={{ width: '160px' }}
    value={statusFilter}
    onChange={(e) => {
      setStatusFilter(e.target.value);
      setCurrentPage(1);
    }}
  >
    <option value="all">Status: All</option>
    <option value="pending">Pending</option>
    <option value="reviewed">Reviewed</option>
    <option value="forwarded">Forwarded</option>
    <option value="accepted">Accepted</option>
    <option value="rejected">Rejected</option>
  </select>
  <select 
    className="admin-input" 
    style={{ width: '160px' }}
    value={fundingStreamFilter}
    onChange={(e) => {
      setFundingStreamFilter(e.target.value);
      setCurrentPage(1);
    }}
  >
    <option value="all">Stream: All</option>
    <option value="PSSSP">PSSSP</option>
    <option value="UCEPP">UCEPP</option>
    <option value="DGGR">DGGR</option>
  </select>
</div>

{/* Table */}
<div className="admin-table-wrap">
  <table className="admin-table">
    <thead>
      <tr>
        <th onClick={() => handleSort('id')} style={{ cursor: 'pointer' }}>
          ID {sortColumn === 'id' && (sortDirection === 'asc' ? '↑' : '↓')}
        </th>
        <th onClick={() => handleSort('student_name')} style={{ cursor: 'pointer' }}>
          APPLICANT {sortColumn === 'student_name' && (sortDirection === 'asc' ? '↑' : '↓')}
        </th>
        <th onClick={() => handleSort('form_title')} style={{ cursor: 'pointer' }}>
          FORM TYPE {sortColumn === 'form_title' && (sortDirection === 'asc' ? '↑' : '↓')}
        </th>
        <th onClick={() => handleSort('status')} style={{ cursor: 'pointer' }}>
          STATUS {sortColumn === 'status' && (sortDirection === 'asc' ? '↑' : '↓')}
        </th>
        <th onClick={() => handleSort('amount')} style={{ cursor: 'pointer' }}>
          AMOUNT {sortColumn === 'amount' && (sortDirection === 'asc' ? '↑' : '↓')}
        </th>
        <th onClick={() => handleSort('submitted_at')} style={{ cursor: 'pointer' }}>
          SUBMITTED {sortColumn === 'submitted_at' && (sortDirection === 'asc' ? '↑' : '↓')}
        </th>
      </tr>
    </thead>
    <tbody>
      {paginatedApps.map(app => (
        <tr key={app.id} onClick={() => handleAppClick(app.id)} style={{ cursor: 'pointer' }}>
          <td><span style={{ fontSize: '11px', color: '#64748b' }}>#{app.id}</span></td>
          <td><strong>{app.student_details?.full_name}</strong></td>
          <td style={{ fontSize: '12px' }}>{app.form_title}</td>
          <td>{getStatusBadge(app.status)}</td>
          <td><strong>${parseFloat(app.amount || 0).toLocaleString()}</strong></td>
          <td style={{ fontSize: '12px', color: '#64748b' }}>
            {new Date(app.submitted_at).toLocaleDateString()}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>

{/* Pagination */}
<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '24px' }}>
  <div style={{ fontSize: '12px', color: '#64748b' }}>
    Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, filteredAndSortedApps.length)} of {filteredAndSortedApps.length}
  </div>
  <div style={{ display: 'flex', gap: '8px' }}>
    <button 
      className="admin-input"
      disabled={currentPage === 1}
      onClick={() => setCurrentPage(currentPage - 1)}
      style={{ opacity: currentPage === 1 ? 0.5 : 1 }}
    >
      ← Previous
    </button>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 12px' }}>
      Page {currentPage} of {totalPages}
    </div>
    <button 
      className="admin-input"
      disabled={currentPage === totalPages}
      onClick={() => setCurrentPage(currentPage + 1)}
      style={{ opacity: currentPage === totalPages ? 0.5 : 1 }}
    >
      Next →
    </button>
  </div>
</div>
```

---

### Task 2: Enhance Application Detail View

#### Location
`src/pages/StaffDashboard.tsx` - `currentView === 'detail'` section

#### Requirements
1. **Display All Submitted Form Data**
   - Show all form answers in readable format
   - Group by section if applicable
   - Display file uploads with download links

2. **Display Eligibility Determination Result**
   - Show eligible funding streams
   - Show ineligible streams with reasons
   - Show eligibility check timestamp

3. **Show Calculated Funding Breakdown**
   - Tuition amount
   - Living allowance
   - Books & supplies
   - Special awards
   - Total amount

4. **Display Audit Trail**
   - All actions/changes with timestamps
   - Show who performed each action
   - Show status changes
   - Show approval/rejection decisions

5. **Show Staff Notes**
   - Display all internal notes
   - Show note author and date
   - Allow adding new notes

6. **Action Buttons**
   - Approve
   - Reject
   - Request Info
   - Add Note
   - Share Link
   - Export PDF
   - For Director: Show banking details

#### Implementation Code Structure
```typescript
// Fetch eligibility and duplicate status
useEffect(() => {
  if (selectedAppId && currentView === 'detail') {
    // Check eligibility
    API.checkEligibility(Number(selectedAppId))
      .then(res => setEligibilityResult(res))
      .catch(err => console.error('Eligibility check failed', err));
    
    // Check for duplicates
    API.checkDuplicates(Number(selectedAppId))
      .then(res => setDuplicateStatus(res))
      .catch(err => console.error('Duplicate check failed', err));
  }
}, [selectedAppId, currentView]);

// Display eligibility result
const renderEligibilityResult = () => {
  if (!eligibilityResult) return null;
  
  return (
    <div className="admin-chart-card">
      <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>
        ELIGIBILITY DETERMINATION
      </h3>
      
      {eligibilityResult.eligible_streams.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ fontSize: '12px', fontWeight: '700', color: '#1a6b3a', marginBottom: '8px' }}>
            ✓ ELIGIBLE FOR
          </h4>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {eligibilityResult.eligible_streams.map(stream => (
              <span key={stream} className="admin-badge badge-approved">
                {stream}
              </span>
            ))}
          </div>
        </div>
      )}
      
      {eligibilityResult.ineligible_streams.length > 0 && (
        <div>
          <h4 style={{ fontSize: '12px', fontWeight: '700', color: '#cc3333', marginBottom: '8px' }}>
            ✕ NOT ELIGIBLE FOR
          </h4>
          {eligibilityResult.ineligible_streams.map(stream => (
            <div key={stream} style={{ marginBottom: '12px' }}>
              <div style={{ fontSize: '12px', fontWeight: '700', color: '#1e293b' }}>
                {stream}
              </div>
              <ul style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', paddingLeft: '20px' }}>
                {eligibilityResult.details[stream].reasons.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Display duplicate status
const renderDuplicateStatus = () => {
  if (!duplicateStatus) return null;
  
  if (!duplicateStatus.is_flagged) return null;
  
  return (
    <div className="admin-chart-card" style={{ background: '#fef2f2', border: '1px solid #fecaca' }}>
      <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#b91c1c' }}>
        ⚠️ DUPLICATE FLAG
      </h3>
      <p style={{ fontSize: '13px', color: '#991b1b', marginBottom: '16px' }}>
        {duplicateStatus.message}
      </p>
      <div style={{ display: 'flex', gap: '8px' }}>
        <button 
          className="admin-input"
          style={{ background: '#1a6b3a', color: '#fff', border: 'none', cursor: 'pointer' }}
          onClick={() => handleMarkLegitimate()}
        >
          Mark as Legitimate
        </button>
        <button 
          className="admin-input"
          style={{ background: '#cc3333', color: '#fff', border: 'none', cursor: 'pointer' }}
          onClick={() => handleMarkDuplicate()}
        >
          Confirm Duplicate
        </button>
      </div>
    </div>
  );
};
```

#### UI Components
```jsx
{/* Eligibility Result */}
{renderEligibilityResult()}

{/* Duplicate Status */}
{renderDuplicateStatus()}

{/* Form Data Display */}
<div className="admin-chart-card">
  <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>
    SUBMITTED INFORMATION
  </h3>
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '24px' }}>
    {selectedApp?.answers?.map((answer, i) => (
      <div key={i}>
        <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
          {answer.field_label}
        </label>
        <div style={{ fontSize: '13px', fontWeight: '600', color: '#1e293b' }}>
          {answer.answer_file ? (
            <a href={answer.answer_file} target="_blank" rel="noopener noreferrer">
              📎 {answer.answer_file.split('/').pop()}
            </a>
          ) : (
            answer.answer_text
          )}
        </div>
      </div>
    ))}
  </div>
</div>

{/* Funding Breakdown */}
<div className="admin-chart-card">
  <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>
    FUNDING BREAKDOWN
  </h3>
  <table className="admin-table">
    <thead>
      <tr>
        <th>COMPONENT</th>
        <th>AMOUNT</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Tuition</td>
        <td>${autoSuggested?.tuition?.system.toLocaleString()}</td>
      </tr>
      <tr>
        <td>Living Allowance</td>
        <td>${autoSuggested?.living?.system.toLocaleString()}</td>
      </tr>
      <tr>
        <td>Books & Supplies</td>
        <td>${autoSuggested?.books?.system.toLocaleString()}</td>
      </tr>
      <tr style={{ borderTop: '2px solid #e2e8f0', fontWeight: '800' }}>
        <td>TOTAL</td>
        <td>${autoSuggested?.total.toLocaleString()}</td>
      </tr>
    </tbody>
  </table>
</div>

{/* Audit Trail */}
<div className="admin-chart-card">
  <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px' }}>
    AUDIT TRAIL
  </h3>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
    {selectedApp?.audit_log?.map((log, i) => (
      <div key={i} style={{ position: 'relative', paddingLeft: '24px', borderLeft: '2px solid #e2e8f0' }}>
        <div style={{ position: 'absolute', left: '-6px', top: '0', width: '10px', height: '10px', background: '#1a6b3a', borderRadius: '50%' }}></div>
        <div style={{ fontSize: '12px', fontWeight: '700' }}>{log.action}</div>
        <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
          {new Date(log.timestamp).toLocaleString()} by {log.performed_by_name}
        </div>
      </div>
    ))}
  </div>
</div>

{/* Banking Details - Director Only */}
{role === 'director' && (
  <div className="admin-chart-card" style={{ background: '#f0fdf4', border: '1px solid #dcfce7' }}>
    <h3 style={{ fontSize: '14px', fontWeight: '800', marginBottom: '16px', color: '#166534' }}>
      🔒 BANKING DETAILS (DIRECTOR ONLY)
    </h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
      <div>
        <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
          ACCOUNT HOLDER
        </label>
        <div style={{ fontSize: '13px', fontWeight: '600' }}>
          {selectedApp?.student_details?.full_name}
        </div>
      </div>
      <div>
        <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
          BANK NAME
        </label>
        <div style={{ fontSize: '13px', fontWeight: '600' }}>
          {selectedApp?.student_details?.bank_name}
        </div>
      </div>
      <div>
        <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
          ACCOUNT NUMBER
        </label>
        <div style={{ fontSize: '13px', fontWeight: '600' }}>
          {selectedApp?.student_details?.account_number}
        </div>
      </div>
      <div>
        <label style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', display: 'block', marginBottom: '4px' }}>
          TRANSIT NUMBER
        </label>
        <div style={{ fontSize: '13px', fontWeight: '600' }}>
          {selectedApp?.student_details?.transit_number}
        </div>
      </div>
    </div>
  </div>
)}
```

---

### Task 3: Add Status Badge Colors

#### Update `getStatusBadge` function
```typescript
const getStatusBadge = (status: string) => {
  const badgeStyles = {
    pending: { background: '#fbbf24', color: '#78350f' },
    reviewed: { background: '#3b82f6', color: '#fff' },
    forwarded: { background: '#a855f7', color: '#fff' },
    accepted: { background: '#10b981', color: '#fff' },
    rejected: { background: '#ef4444', color: '#fff' }
  };
  
  const style = badgeStyles[status as keyof typeof badgeStyles] || { background: '#e2e8f0', color: '#1e293b' };
  
  return (
    <span className="admin-badge" style={style}>
      {status.toUpperCase()}
    </span>
  );
};
```

---

### Task 4: Add CSS Enhancements

#### Update `src/styles/staff.css`
```css
/* Sortable table headers */
.admin-table th {
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.admin-table th:hover {
  background-color: #f1f5f9;
}

/* Sort indicators */
.admin-table th::after {
  content: '';
  display: inline-block;
  margin-left: 4px;
  opacity: 0.5;
}

/* Pagination styles */
.pagination-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  padding: 16px 20px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.pagination-info {
  font-size: 12px;
  color: #64748b;
}

.pagination-controls {
  display: flex;
  gap: 8px;
}

.pagination-btn {
  padding: 8px 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 12px;
  transition: all 0.2s;
}

.pagination-btn:hover:not(:disabled) {
  background: var(--admin-accent);
  color: #111;
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Status badge colors */
.admin-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.badge-pending {
  background: #fbbf24;
  color: #78350f;
}

.badge-reviewed {
  background: #3b82f6;
  color: #fff;
}

.badge-forwarded {
  background: #a855f7;
  color: #fff;
}

.badge-accepted {
  background: #10b981;
  color: #fff;
}

.badge-rejected {
  background: #ef4444;
  color: #fff;
}

/* Clickable table rows */
.admin-table tbody tr {
  cursor: pointer;
  transition: background-color 0.2s;
}

.admin-table tbody tr:hover {
  background-color: #f8fafc;
}

/* Filter section */
.admin-filters {
  display: grid;
  gap: 12px;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.admin-search {
  position: relative;
}

.admin-search input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
}

.admin-search input:focus {
  outline: none;
  border-color: var(--admin-accent);
  box-shadow: 0 0 0 3px rgba(229, 166, 98, 0.1);
}
```

---

## API Integration

### Required API Methods (in `src/api/client.ts`)
```typescript
// Eligibility check
checkEligibility(submissionId: number): Promise<any> {
  return this.post(`/forms/submissions/${submissionId}/check-eligibility/`);
}

// Duplicate detection
checkDuplicates(submissionId: number): Promise<any> {
  return this.post(`/forms/submissions/${submissionId}/check-duplicates/`);
}

// Mark as legitimate
markLegitimate(submissionId: number, notes: string): Promise<any> {
  return this.post(`/forms/submissions/${submissionId}/mark-legitimate/`, { notes });
}

// Mark as duplicate
markDuplicate(submissionId: number, notes: string): Promise<any> {
  return this.post(`/forms/submissions/${submissionId}/mark-duplicate/`, { notes });
}
```

---

## Testing Checklist

- [ ] Applications list displays all applications
- [ ] Sorting works on all columns
- [ ] Search filters by name and ID
- [ ] Status filter works
- [ ] Funding stream filter works
- [ ] Pagination displays correct items
- [ ] Row click navigates to detail view
- [ ] Detail view shows all form data
- [ ] Eligibility result displays correctly
- [ ] Duplicate flag displays when flagged
- [ ] Funding breakdown shows correct amounts
- [ ] Audit trail displays all actions
- [ ] Staff notes display and can be added
- [ ] Banking details only show for directors
- [ ] All action buttons work correctly
- [ ] Responsive design works on mobile
- [ ] Performance is acceptable (< 3 seconds load)

---

## Performance Optimization Tips

1. **Memoization**: Use `useMemo` for filtered/sorted data
2. **Pagination**: Only render visible items
3. **Lazy Loading**: Load detail view data on demand
4. **Caching**: Cache eligibility and duplicate checks
5. **Debouncing**: Debounce search input
6. **Virtual Scrolling**: For large lists (if needed)

---

## Accessibility Considerations

1. **Keyboard Navigation**: All buttons and links should be keyboard accessible
2. **Screen Readers**: Use semantic HTML and ARIA labels
3. **Color Contrast**: Ensure sufficient contrast for status badges
4. **Focus Indicators**: Visible focus states for all interactive elements
5. **Alt Text**: Provide alt text for all images

---

## Next Steps

1. Implement Task 1: Applications List View
2. Implement Task 2: Application Detail View
3. Implement Task 3: Status Badge Colors
4. Implement Task 4: CSS Enhancements
5. Test all functionality
6. Optimize performance
7. Verify accessibility compliance
8. Deploy to staging environment

---

**Estimated Implementation Time**: 8-12 hours
**Difficulty Level**: Medium
**Dependencies**: Backend API endpoints (already implemented)
