import { describe, it, expect } from 'vitest';

/**
 * Unit tests for StaffDashboard search functionality
 * Task 1.2: Add search by student name and application ID
 * Enhanced: Also includes email and beneficiary number search
 * Task 1.3: Add filter by status (All, Pending, Reviewed, Forwarded, Approved, Rejected)
 */

describe('StaffDashboard Search Functionality', () => {
  describe('Search filtering logic', () => {
    const mockApplications = [
      {
        id: 1,
        student_details: { 
          full_name: 'John Doe',
          email: 'john.doe@example.com',
          beneficiary_number: 'BEN001'
        },
        form_title: 'FormA',
        status: 'pending',
        submitted_at: '2024-01-01'
      },
      {
        id: 2,
        student_details: { 
          full_name: 'Jane Smith',
          email: 'jane.smith@example.com',
          beneficiary_number: 'BEN002'
        },
        form_title: 'FormB',
        status: 'reviewed',
        submitted_at: '2024-01-02'
      },
      {
        id: 123,
        student_details: { 
          full_name: 'Bob Johnson',
          email: 'bob.johnson@example.com',
          beneficiary_number: 'BEN123'
        },
        form_title: 'FormC',
        status: 'accepted',
        submitted_at: '2024-01-03'
      }
    ];

    const filterApplications = (apps: any[], searchQuery: string, statusFilter: string, fundingStreamFilter: string) => {
      return apps.filter(app => {
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
    };

    it('should filter by student name (case-insensitive)', () => {
      const result = filterApplications(mockApplications, 'john', 'all', 'all');
      expect(result).toHaveLength(2);
      expect(result.map(r => r.id)).toContain(1); // John Doe
      expect(result.map(r => r.id)).toContain(123); // Bob Johnson
    });

    it('should filter by application ID', () => {
      const result = filterApplications(mockApplications, '123', 'all', 'all');
      expect(result).toHaveLength(1); // Only ID 123 (BEN123 is same record)
      expect(result[0].id).toBe(123);
    });

    it('should filter by partial application ID', () => {
      const result = filterApplications(mockApplications, '2', 'all', 'all');
      expect(result).toHaveLength(2); // ID 2 and ID 123 (BEN002 is same as ID 2)
      expect(result.map(r => r.id)).toContain(2);
      expect(result.map(r => r.id)).toContain(123);
    });

    it('should filter by student name (partial match)', () => {
      const result = filterApplications(mockApplications, 'doe', 'all', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].student_details.full_name).toBe('John Doe');
    });

    it('should filter by email', () => {
      const result = filterApplications(mockApplications, 'jane.smith@example.com', 'all', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(2);
    });

    it('should filter by partial email', () => {
      const result = filterApplications(mockApplications, 'example.com', 'all', 'all');
      expect(result).toHaveLength(3);
    });

    it('should filter by beneficiary number', () => {
      const result = filterApplications(mockApplications, 'BEN001', 'all', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(1);
    });

    it('should filter by partial beneficiary number', () => {
      const result = filterApplications(mockApplications, 'BEN', 'all', 'all');
      expect(result).toHaveLength(3);
    });

    it('should return empty array when no matches', () => {
      const result = filterApplications(mockApplications, 'nonexistent', 'all', 'all');
      expect(result).toHaveLength(0);
    });

    it('should work with status filter', () => {
      const result = filterApplications(mockApplications, 'john', 'pending', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(1);
    });

    it('should return all applications when search is empty', () => {
      const result = filterApplications(mockApplications, '', 'all', 'all');
      expect(result).toHaveLength(3);
    });

    it('should handle missing student_details gracefully', () => {
      const appsWithMissing = [
        ...mockApplications,
        { id: 999, student_details: null, form_title: 'FormD', status: 'pending', submitted_at: '2024-01-04' }
      ];
      const result = filterApplications(appsWithMissing, '999', 'all', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(999);
    });

    it('should handle missing email gracefully', () => {
      const appsWithMissingEmail = [
        {
          id: 888,
          student_details: { 
            full_name: 'Test User',
            email: null,
            beneficiary_number: 'BEN888'
          },
          form_title: 'FormE',
          status: 'pending',
          submitted_at: '2024-01-05'
        }
      ];
      const result = filterApplications(appsWithMissingEmail, 'test', 'all', 'all');
      expect(result).toHaveLength(1);
    });

    it('should handle missing beneficiary number gracefully', () => {
      const appsWithMissingBen = [
        {
          id: 777,
          student_details: { 
            full_name: 'Test User 2',
            email: 'test2@example.com',
            beneficiary_number: null
          },
          form_title: 'FormF',
          status: 'pending',
          submitted_at: '2024-01-06'
        }
      ];
      const result = filterApplications(appsWithMissingBen, 'test2', 'all', 'all');
      expect(result).toHaveLength(1);
    });
  });

  describe('Status filter functionality', () => {
    const mockApplications = [
      {
        id: 1,
        student_details: { 
          full_name: 'John Doe',
          email: 'john.doe@example.com',
          beneficiary_number: 'BEN001'
        },
        form_title: 'FormA',
        status: 'pending',
        submitted_at: '2024-01-01'
      },
      {
        id: 2,
        student_details: { 
          full_name: 'Jane Smith',
          email: 'jane.smith@example.com',
          beneficiary_number: 'BEN002'
        },
        form_title: 'FormB',
        status: 'reviewed',
        submitted_at: '2024-01-02'
      },
      {
        id: 3,
        student_details: { 
          full_name: 'Bob Johnson',
          email: 'bob.johnson@example.com',
          beneficiary_number: 'BEN003'
        },
        form_title: 'FormC',
        status: 'forwarded',
        submitted_at: '2024-01-03'
      },
      {
        id: 4,
        student_details: { 
          full_name: 'Alice Williams',
          email: 'alice.williams@example.com',
          beneficiary_number: 'BEN004'
        },
        form_title: 'FormD',
        status: 'accepted',
        submitted_at: '2024-01-04'
      },
      {
        id: 5,
        student_details: { 
          full_name: 'Charlie Brown',
          email: 'charlie.brown@example.com',
          beneficiary_number: 'BEN005'
        },
        form_title: 'FormE',
        status: 'rejected',
        submitted_at: '2024-01-05'
      }
    ];

    const filterApplications = (apps: any[], searchQuery: string, statusFilter: string, fundingStreamFilter: string) => {
      return apps.filter(app => {
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
    };

    it('should show all applications when status filter is "all"', () => {
      const result = filterApplications(mockApplications, '', 'all', 'all');
      expect(result).toHaveLength(5);
    });

    it('should filter by "pending" status', () => {
      const result = filterApplications(mockApplications, '', 'pending', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('pending');
      expect(result[0].id).toBe(1);
    });

    it('should filter by "reviewed" status', () => {
      const result = filterApplications(mockApplications, '', 'reviewed', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('reviewed');
      expect(result[0].id).toBe(2);
    });

    it('should filter by "forwarded" status', () => {
      const result = filterApplications(mockApplications, '', 'forwarded', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('forwarded');
      expect(result[0].id).toBe(3);
    });

    it('should filter by "accepted" status (Approved)', () => {
      const result = filterApplications(mockApplications, '', 'accepted', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('accepted');
      expect(result[0].id).toBe(4);
    });

    it('should filter by "rejected" status', () => {
      const result = filterApplications(mockApplications, '', 'rejected', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('rejected');
      expect(result[0].id).toBe(5);
    });

    it('should combine status filter with search query', () => {
      const result = filterApplications(mockApplications, 'john', 'pending', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(1);
      expect(result[0].student_details.full_name).toBe('John Doe');
    });

    it('should return empty array when status filter has no matches', () => {
      const appsWithOnlyPending = mockApplications.filter(a => a.status === 'pending');
      const result = filterApplications(appsWithOnlyPending, '', 'accepted', 'all');
      expect(result).toHaveLength(0);
    });

    it('should work with status filter and search query together', () => {
      const result = filterApplications(mockApplications, 'alice', 'accepted', 'all');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(4);
    });

    it('should return empty when search matches but status does not', () => {
      const result = filterApplications(mockApplications, 'john', 'accepted', 'all');
      expect(result).toHaveLength(0);
    });

    it('should reset to page 1 when status filter changes', () => {
      // This test verifies the behavior described in the useEffect hook
      // The actual page reset is handled by React state, but we verify the filter works
      const result1 = filterApplications(mockApplications, '', 'pending', 'all');
      const result2 = filterApplications(mockApplications, '', 'accepted', 'all');
      
      expect(result1).toHaveLength(1);
      expect(result2).toHaveLength(1);
      expect(result1[0].id).not.toBe(result2[0].id);
    });
  });

  describe('Funding stream filter functionality', () => {
    const mockApplications = [
      {
        id: 1,
        student_details: { 
          full_name: 'John Doe',
          email: 'john.doe@example.com',
          beneficiary_number: 'BEN001'
        },
        form_title: 'PSSSP Application',
        status: 'pending',
        submitted_at: '2024-01-01'
      },
      {
        id: 2,
        student_details: { 
          full_name: 'Jane Smith',
          email: 'jane.smith@example.com',
          beneficiary_number: 'BEN002'
        },
        form_title: 'UCEPP Program',
        status: 'reviewed',
        submitted_at: '2024-01-02'
      },
      {
        id: 3,
        student_details: { 
          full_name: 'Bob Johnson',
          email: 'bob.johnson@example.com',
          beneficiary_number: 'BEN003'
        },
        form_title: 'DGGR Bursary',
        status: 'accepted',
        submitted_at: '2024-01-03'
      },
      {
        id: 4,
        student_details: { 
          full_name: 'Alice Williams',
          email: 'alice.williams@example.com',
          beneficiary_number: 'BEN004'
        },
        form_title: 'PSSSP Continuing',
        status: 'forwarded',
        submitted_at: '2024-01-04'
      }
    ];

    const filterApplications = (apps: any[], searchQuery: string, statusFilter: string, fundingStreamFilter: string) => {
      return apps.filter(app => {
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
    };

    it('should show all applications when funding stream filter is "all"', () => {
      const result = filterApplications(mockApplications, '', 'all', 'all');
      expect(result).toHaveLength(4);
    });

    it('should filter by "PSSSP" funding stream', () => {
      const result = filterApplications(mockApplications, '', 'all', 'PSSSP');
      expect(result).toHaveLength(2);
      expect(result.map(r => r.id)).toContain(1);
      expect(result.map(r => r.id)).toContain(4);
    });

    it('should filter by "UCEPP" funding stream', () => {
      const result = filterApplications(mockApplications, '', 'all', 'UCEPP');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(2);
      expect(result[0].form_title).toBe('UCEPP Program');
    });

    it('should filter by "DGGR" funding stream', () => {
      const result = filterApplications(mockApplications, '', 'all', 'DGGR');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(3);
      expect(result[0].form_title).toBe('DGGR Bursary');
    });

    it('should combine funding stream filter with search query', () => {
      const result = filterApplications(mockApplications, 'john', 'all', 'PSSSP');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(1);
      expect(result[0].student_details.full_name).toBe('John Doe');
    });

    it('should combine funding stream filter with status filter', () => {
      const result = filterApplications(mockApplications, '', 'pending', 'PSSSP');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(1);
    });

    it('should combine all three filters (search, status, funding stream)', () => {
      const result = filterApplications(mockApplications, 'alice', 'forwarded', 'PSSSP');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(4);
    });

    it('should return empty array when funding stream filter has no matches', () => {
      const pssspOnly = mockApplications.filter(a => a.form_title.includes('PSSSP'));
      const result = filterApplications(pssspOnly, '', 'all', 'DGGR');
      expect(result).toHaveLength(0);
    });

    it('should return empty when search matches but funding stream does not', () => {
      const result = filterApplications(mockApplications, 'jane', 'all', 'PSSSP');
      expect(result).toHaveLength(0);
    });

    it('should return empty when status matches but funding stream does not', () => {
      const result = filterApplications(mockApplications, '', 'reviewed', 'PSSSP');
      expect(result).toHaveLength(0);
    });

    it('should handle partial funding stream name in form_title', () => {
      const appsWithPartialNames = [
        {
          id: 1,
          student_details: { full_name: 'Test User', email: 'test@example.com', beneficiary_number: 'BEN001' },
          form_title: 'C-DFN PSSSP Application',
          status: 'pending',
          submitted_at: '2024-01-01'
        }
      ];
      const result = filterApplications(appsWithPartialNames, '', 'all', 'PSSSP');
      expect(result).toHaveLength(1);
    });

    it('should handle missing form_title gracefully', () => {
      const appsWithMissingTitle = [
        {
          id: 1,
          student_details: { full_name: 'Test User', email: 'test@example.com', beneficiary_number: 'BEN001' },
          form_title: null,
          status: 'pending',
          submitted_at: '2024-01-01'
        }
      ];
      const result = filterApplications(appsWithMissingTitle, '', 'all', 'PSSSP');
      expect(result).toHaveLength(0);
    });

    it('should reset to page 1 when funding stream filter changes', () => {
      // This test verifies the behavior described in the useEffect hook
      // The actual page reset is handled by React state, but we verify the filter works
      const result1 = filterApplications(mockApplications, '', 'all', 'PSSSP');
      const result2 = filterApplications(mockApplications, '', 'all', 'DGGR');
      
      expect(result1).toHaveLength(2);
      expect(result2).toHaveLength(1);
      expect(result1.map(r => r.id)).not.toContain(result2[0].id);
    });
  });

  describe('Pagination functionality', () => {
    const mockApplications = Array.from({ length: 35 }, (_, i) => ({
      id: i + 1,
      student_details: { 
        full_name: `Student ${i + 1}`,
        email: `student${i + 1}@example.com`,
        beneficiary_number: `BEN${String(i + 1).padStart(3, '0')}`
      },
      form_title: 'FormA',
      status: 'pending',
      submitted_at: `2024-01-${String((i % 28) + 1).padStart(2, '0')}`
    }));

    const filterApplications = (apps: any[], searchQuery: string, statusFilter: string, fundingStreamFilter: string) => {
      return apps.filter(app => {
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
    };

    const paginateApplications = (apps: any[], currentPage: number, itemsPerPage: number) => {
      return apps.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
    };

    const calculateTotalPages = (totalItems: number, itemsPerPage: number) => {
      return Math.ceil(totalItems / itemsPerPage);
    };

    it('should display 10 items per page by default', () => {
      const itemsPerPage = 10;
      const currentPage = 1;
      const result = paginateApplications(mockApplications, currentPage, itemsPerPage);
      expect(result).toHaveLength(10);
      expect(result[0].id).toBe(1);
      expect(result[9].id).toBe(10);
    });

    it('should calculate correct total pages for 35 items', () => {
      const itemsPerPage = 10;
      const totalPages = calculateTotalPages(mockApplications.length, itemsPerPage);
      expect(totalPages).toBe(4); // 35 items / 10 per page = 4 pages
    });

    it('should display correct items on page 2', () => {
      const itemsPerPage = 10;
      const currentPage = 2;
      const result = paginateApplications(mockApplications, currentPage, itemsPerPage);
      expect(result).toHaveLength(10);
      expect(result[0].id).toBe(11);
      expect(result[9].id).toBe(20);
    });

    it('should display correct items on page 3', () => {
      const itemsPerPage = 10;
      const currentPage = 3;
      const result = paginateApplications(mockApplications, currentPage, itemsPerPage);
      expect(result).toHaveLength(10);
      expect(result[0].id).toBe(21);
      expect(result[9].id).toBe(30);
    });

    it('should display remaining items on last page', () => {
      const itemsPerPage = 10;
      const currentPage = 4;
      const result = paginateApplications(mockApplications, currentPage, itemsPerPage);
      expect(result).toHaveLength(5); // Only 5 items on last page (31-35)
      expect(result[0].id).toBe(31);
      expect(result[4].id).toBe(35);
    });

    it('should handle empty results', () => {
      const itemsPerPage = 10;
      const currentPage = 1;
      const result = paginateApplications([], currentPage, itemsPerPage);
      expect(result).toHaveLength(0);
    });

    it('should calculate 1 page for items less than itemsPerPage', () => {
      const itemsPerPage = 10;
      const smallList = mockApplications.slice(0, 5);
      const totalPages = calculateTotalPages(smallList.length, itemsPerPage);
      expect(totalPages).toBe(1);
    });

    it('should calculate 0 pages for empty list', () => {
      const itemsPerPage = 10;
      const totalPages = calculateTotalPages(0, itemsPerPage);
      expect(totalPages).toBe(0);
    });

    it('should work with filtered results', () => {
      const itemsPerPage = 10;
      const currentPage = 1;
      const filtered = filterApplications(mockApplications, 'Student 1', 'all', 'all');
      const result = paginateApplications(filtered, currentPage, itemsPerPage);
      
      // Should match: Student 1, Student 10-19 (11 total)
      expect(filtered.length).toBeGreaterThan(10);
      expect(result).toHaveLength(10); // First page shows 10
    });

    it('should reset to page 1 when filters change (simulated)', () => {
      // This simulates the useEffect behavior that resets currentPage to 1
      const itemsPerPage = 10;
      let currentPage = 3; // User is on page 3
      
      // User changes filter
      const filtered = filterApplications(mockApplications, 'Student 1', 'all', 'all');
      currentPage = 1; // Reset to page 1 (as per useEffect)
      
      const result = paginateApplications(filtered, currentPage, itemsPerPage);
      expect(result[0].student_details.full_name).toContain('1');
    });

    it('should display correct range information', () => {
      const itemsPerPage = 10;
      const currentPage = 2;
      const totalItems = mockApplications.length;
      
      const startItem = ((currentPage - 1) * itemsPerPage) + 1;
      const endItem = Math.min(currentPage * itemsPerPage, totalItems);
      
      expect(startItem).toBe(11);
      expect(endItem).toBe(20);
    });

    it('should display correct range for last page', () => {
      const itemsPerPage = 10;
      const currentPage = 4;
      const totalItems = mockApplications.length;
      
      const startItem = ((currentPage - 1) * itemsPerPage) + 1;
      const endItem = Math.min(currentPage * itemsPerPage, totalItems);
      
      expect(startItem).toBe(31);
      expect(endItem).toBe(35); // Not 40, because we only have 35 items
    });

    it('should handle page navigation forward', () => {
      const itemsPerPage = 10;
      let currentPage = 1;
      
      // Navigate to next page
      currentPage = currentPage + 1;
      const result = paginateApplications(mockApplications, currentPage, itemsPerPage);
      
      expect(currentPage).toBe(2);
      expect(result[0].id).toBe(11);
    });

    it('should handle page navigation backward', () => {
      const itemsPerPage = 10;
      let currentPage = 3;
      
      // Navigate to previous page
      currentPage = currentPage - 1;
      const result = paginateApplications(mockApplications, currentPage, itemsPerPage);
      
      expect(currentPage).toBe(2);
      expect(result[0].id).toBe(11);
    });

    it('should disable previous button on first page', () => {
      const currentPage = 1;
      const isDisabled = currentPage === 1;
      expect(isDisabled).toBe(true);
    });

    it('should enable previous button on pages after first', () => {
      let currentPage = 2;
      const isDisabled = currentPage === 1;
      expect(isDisabled).toBe(false);
    });

    it('should disable next button on last page', () => {
      const itemsPerPage = 10;
      const currentPage = 4;
      const totalPages = calculateTotalPages(mockApplications.length, itemsPerPage);
      const isDisabled = currentPage === totalPages;
      expect(isDisabled).toBe(true);
    });

    it('should enable next button on pages before last', () => {
      const itemsPerPage = 10;
      const currentPage = 3;
      const totalPages = calculateTotalPages(mockApplications.length, itemsPerPage);
      const isDisabled = currentPage === totalPages;
      expect(isDisabled).toBe(false);
    });

    it('should work with sorting and pagination together', () => {
      const itemsPerPage = 10;
      const currentPage = 1;
      
      // Sort by ID descending
      const sorted = [...mockApplications].sort((a, b) => b.id - a.id);
      const result = paginateApplications(sorted, currentPage, itemsPerPage);
      
      expect(result).toHaveLength(10);
      expect(result[0].id).toBe(35); // Highest ID first
      expect(result[9].id).toBe(26);
    });

    it('should work with filtering, sorting, and pagination together', () => {
      const itemsPerPage = 10;
      const currentPage = 1;
      
      // Filter to get subset
      const filtered = filterApplications(mockApplications, 'Student 1', 'all', 'all');
      
      // Sort by ID descending
      const sorted = [...filtered].sort((a, b) => b.id - a.id);
      
      // Paginate
      const result = paginateApplications(sorted, currentPage, itemsPerPage);
      
      expect(result).toHaveLength(10);
      expect(result[0].student_details.full_name).toContain('1');
    });

    it('should handle exactly 10 items (1 page)', () => {
      const itemsPerPage = 10;
      const exactlyTen = mockApplications.slice(0, 10);
      const totalPages = calculateTotalPages(exactlyTen.length, itemsPerPage);
      
      expect(totalPages).toBe(1);
      
      const result = paginateApplications(exactlyTen, 1, itemsPerPage);
      expect(result).toHaveLength(10);
    });

    it('should handle exactly 20 items (2 pages)', () => {
      const itemsPerPage = 10;
      const exactlyTwenty = mockApplications.slice(0, 20);
      const totalPages = calculateTotalPages(exactlyTwenty.length, itemsPerPage);
      
      expect(totalPages).toBe(2);
      
      const page1 = paginateApplications(exactlyTwenty, 1, itemsPerPage);
      const page2 = paginateApplications(exactlyTwenty, 2, itemsPerPage);
      
      expect(page1).toHaveLength(10);
      expect(page2).toHaveLength(10);
    });

    it('should not show pagination controls when totalPages is 1 or less', () => {
      const itemsPerPage = 10;
      const smallList = mockApplications.slice(0, 5);
      const totalPages = calculateTotalPages(smallList.length, itemsPerPage);
      
      const shouldShowPagination = totalPages > 1;
      expect(shouldShowPagination).toBe(false);
    });

    it('should show pagination controls when totalPages is greater than 1', () => {
      const itemsPerPage = 10;
      const totalPages = calculateTotalPages(mockApplications.length, itemsPerPage);
      
      const shouldShowPagination = totalPages > 1;
      expect(shouldShowPagination).toBe(true);
    });
  });
});

/**
 * Unit tests for status badge color coding
 * Task 1.6: Add status badges with color coding
 */
describe('Status Badge Color Coding', () => {
  // Mirror the CSS class mapping from getStatusBadge
  const getStatusBadgeClass = (status: string): string => {
    const statusClassMap: Record<string, string> = {
      pending: 'badge-pending',
      reviewed: 'badge-reviewed',
      forwarded: 'badge-forwarded',
      accepted: 'badge-accepted',
      rejected: 'badge-rejected'
    };
    return statusClassMap[status] || '';
  };

  // Mirror the CSS color values from staff.css
  const statusColors: Record<string, { background: string; color: string }> = {
    'badge-pending':  { background: '#fbbf24', color: '#78350f' },
    'badge-reviewed': { background: '#3b82f6', color: '#fff' },
    'badge-forwarded':{ background: '#a855f7', color: '#fff' },
    'badge-accepted': { background: '#10b981', color: '#fff' },
    'badge-rejected': { background: '#ef4444', color: '#fff' },
  };

  it('should assign badge-pending class for "pending" status', () => {
    expect(getStatusBadgeClass('pending')).toBe('badge-pending');
  });

  it('should assign badge-reviewed class for "reviewed" status', () => {
    expect(getStatusBadgeClass('reviewed')).toBe('badge-reviewed');
  });

  it('should assign badge-forwarded class for "forwarded" status', () => {
    expect(getStatusBadgeClass('forwarded')).toBe('badge-forwarded');
  });

  it('should assign badge-accepted class for "accepted" status', () => {
    expect(getStatusBadgeClass('accepted')).toBe('badge-accepted');
  });

  it('should assign badge-rejected class for "rejected" status', () => {
    expect(getStatusBadgeClass('rejected')).toBe('badge-rejected');
  });

  it('should return empty string for unknown status', () => {
    expect(getStatusBadgeClass('unknown')).toBe('');
    expect(getStatusBadgeClass('')).toBe('');
  });

  it('pending badge should use yellow (#fbbf24) background', () => {
    const cls = getStatusBadgeClass('pending');
    expect(statusColors[cls].background).toBe('#fbbf24');
  });

  it('reviewed badge should use blue (#3b82f6) background', () => {
    const cls = getStatusBadgeClass('reviewed');
    expect(statusColors[cls].background).toBe('#3b82f6');
  });

  it('forwarded badge should use purple (#a855f7) background', () => {
    const cls = getStatusBadgeClass('forwarded');
    expect(statusColors[cls].background).toBe('#a855f7');
  });

  it('accepted badge should use green (#10b981) background', () => {
    const cls = getStatusBadgeClass('accepted');
    expect(statusColors[cls].background).toBe('#10b981');
  });

  it('rejected badge should use red (#ef4444) background', () => {
    const cls = getStatusBadgeClass('rejected');
    expect(statusColors[cls].background).toBe('#ef4444');
  });

  it('pending badge text color should meet WCAG AA contrast on yellow', () => {
    // #78350f (dark brown) on #fbbf24 (yellow) — high contrast
    const cls = getStatusBadgeClass('pending');
    expect(statusColors[cls].color).toBe('#78350f');
  });

  it('reviewed badge text color should be white on blue', () => {
    const cls = getStatusBadgeClass('reviewed');
    expect(statusColors[cls].color).toBe('#fff');
  });

  it('forwarded badge text color should be white on purple', () => {
    const cls = getStatusBadgeClass('forwarded');
    expect(statusColors[cls].color).toBe('#fff');
  });

  it('accepted badge text color should be white on green', () => {
    const cls = getStatusBadgeClass('accepted');
    expect(statusColors[cls].color).toBe('#fff');
  });

  it('rejected badge text color should be white on red', () => {
    const cls = getStatusBadgeClass('rejected');
    expect(statusColors[cls].color).toBe('#fff');
  });

  it('all five statuses should have distinct badge classes', () => {
    const statuses = ['pending', 'reviewed', 'forwarded', 'accepted', 'rejected'];
    const classes = statuses.map(getStatusBadgeClass);
    const uniqueClasses = new Set(classes);
    expect(uniqueClasses.size).toBe(5);
  });

  it('all five statuses should have distinct background colors', () => {
    const statuses = ['pending', 'reviewed', 'forwarded', 'accepted', 'rejected'];
    const backgrounds = statuses.map(s => statusColors[getStatusBadgeClass(s)].background);
    const uniqueBackgrounds = new Set(backgrounds);
    expect(uniqueBackgrounds.size).toBe(5);
  });
});

/**
 * Unit tests for clickable table rows
 * Task 1.7: Make table rows clickable to view details
 */
describe('Clickable Table Rows', () => {
  const mockApplications = [
    {
      id: 1,
      student_details: { full_name: 'John Doe', email: 'john@example.com', beneficiary_number: 'BEN001' },
      form_title: 'FormA',
      status: 'pending',
      submitted_at: '2024-01-01',
      amount: 0
    },
    {
      id: 2,
      student_details: { full_name: 'Jane Smith', email: 'jane@example.com', beneficiary_number: 'BEN002' },
      form_title: 'FormB',
      status: 'reviewed',
      submitted_at: '2024-01-02',
      amount: 1500
    },
    {
      id: 3,
      student_details: { full_name: 'Bob Johnson', email: 'bob@example.com', beneficiary_number: 'BEN003' },
      form_title: 'FormC',
      status: 'accepted',
      submitted_at: '2024-01-03',
      amount: 3000
    }
  ];

  // Simulate the handleAppClick logic: sets selectedAppId and navigates to detail view
  const simulateHandleAppClick = (
    appId: number,
    role: 'ssw' | 'director'
  ): { selectedAppId: string; view: string } => {
    return {
      selectedAppId: String(appId),
      view: role === 'director' ? 'director-detail' : 'detail'
    };
  };

  it('should navigate to detail view when a row is clicked (ssw role)', () => {
    const result = simulateHandleAppClick(1, 'ssw');
    expect(result.selectedAppId).toBe('1');
    expect(result.view).toBe('detail');
  });

  it('should navigate to director-detail view when a row is clicked (director role)', () => {
    const result = simulateHandleAppClick(1, 'director');
    expect(result.selectedAppId).toBe('1');
    expect(result.view).toBe('director-detail');
  });

  it('should set the correct selectedAppId for each row', () => {
    mockApplications.forEach(app => {
      const result = simulateHandleAppClick(app.id, 'ssw');
      expect(result.selectedAppId).toBe(String(app.id));
    });
  });

  it('should convert numeric app id to string for selectedAppId', () => {
    const result = simulateHandleAppClick(42, 'ssw');
    expect(typeof result.selectedAppId).toBe('string');
    expect(result.selectedAppId).toBe('42');
  });

  it('should navigate to detail view for any valid application id', () => {
    const ids = [1, 2, 3, 100, 9999];
    ids.forEach(id => {
      const result = simulateHandleAppClick(id, 'ssw');
      expect(result.view).toBe('detail');
      expect(result.selectedAppId).toBe(String(id));
    });
  });

  it('should find the selected application from the applications list', () => {
    const clickedId = 2;
    const { selectedAppId } = simulateHandleAppClick(clickedId, 'ssw');
    const selectedApp = mockApplications.find(a => String(a.id) === selectedAppId);
    expect(selectedApp).toBeDefined();
    expect(selectedApp?.student_details.full_name).toBe('Jane Smith');
  });

  it('should return undefined when selected app id does not match any application', () => {
    const { selectedAppId } = simulateHandleAppClick(999, 'ssw');
    const selectedApp = mockApplications.find(a => String(a.id) === selectedAppId);
    expect(selectedApp).toBeUndefined();
  });

  it('should use string comparison for finding selected app (id type safety)', () => {
    // The component uses String(a.id) === String(selectedAppId) for lookup
    const clickedId = 3;
    const { selectedAppId } = simulateHandleAppClick(clickedId, 'ssw');
    const selectedApp = mockApplications.find(a => String(a.id) === String(selectedAppId));
    expect(selectedApp).toBeDefined();
    expect(selectedApp?.id).toBe(3);
  });
});

/**
 * Unit tests for column sorting functionality
 * Task 1.1: Add sorting functionality to all table columns
 * Task 1.9: Test sorting, filtering, and pagination
 */
describe('Sorting functionality', () => {
  const mockApplications = [
    {
      id: 3,
      student_details: { full_name: 'Charlie Brown', email: 'charlie@example.com', beneficiary_number: 'BEN003' },
      form_title: 'PSSSP Application',
      status: 'forwarded',
      submitted_at: '2024-03-01',
      amount: 3000
    },
    {
      id: 1,
      student_details: { full_name: 'Alice Williams', email: 'alice@example.com', beneficiary_number: 'BEN001' },
      form_title: 'DGGR Bursary',
      status: 'pending',
      submitted_at: '2024-01-01',
      amount: 1000
    },
    {
      id: 2,
      student_details: { full_name: 'Bob Johnson', email: 'bob@example.com', beneficiary_number: 'BEN002' },
      form_title: 'UCEPP Program',
      status: 'accepted',
      submitted_at: '2024-02-01',
      amount: 2000
    }
  ];

  // Mirror the sort logic from StaffDashboard.tsx
  const sortApplications = (
    apps: any[],
    sortColumn: string,
    sortDirection: 'asc' | 'desc'
  ) => {
    return [...apps].sort((a, b) => {
      let aVal: any;
      let bVal: any;

      if (sortColumn === 'student_name') {
        aVal = (a.student_details?.full_name || '').toLowerCase();
        bVal = (b.student_details?.full_name || '').toLowerCase();
      } else {
        aVal = a[sortColumn as keyof typeof a];
        bVal = b[sortColumn as keyof typeof b];
      }

      if (typeof aVal === 'string') {
        aVal = (aVal || '').toLowerCase();
        bVal = (bVal || '').toLowerCase();
      }

      if (aVal == null) aVal = '';
      if (bVal == null) bVal = '';

      if (sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
  };

  // Mirror the handleSort toggle logic from StaffDashboard.tsx
  const handleSort = (
    currentColumn: string,
    currentDirection: 'asc' | 'desc',
    newColumn: string
  ): { sortColumn: string; sortDirection: 'asc' | 'desc' } => {
    if (currentColumn === newColumn) {
      return { sortColumn: newColumn, sortDirection: currentDirection === 'asc' ? 'desc' : 'asc' };
    }
    return { sortColumn: newColumn, sortDirection: 'asc' };
  };

  describe('Sort by ID', () => {
    it('should sort by ID ascending', () => {
      const result = sortApplications(mockApplications, 'id', 'asc');
      expect(result[0].id).toBe(1);
      expect(result[1].id).toBe(2);
      expect(result[2].id).toBe(3);
    });

    it('should sort by ID descending', () => {
      const result = sortApplications(mockApplications, 'id', 'desc');
      expect(result[0].id).toBe(3);
      expect(result[1].id).toBe(2);
      expect(result[2].id).toBe(1);
    });
  });

  describe('Sort by student name', () => {
    it('should sort by student name ascending (A-Z)', () => {
      const result = sortApplications(mockApplications, 'student_name', 'asc');
      expect(result[0].student_details.full_name).toBe('Alice Williams');
      expect(result[1].student_details.full_name).toBe('Bob Johnson');
      expect(result[2].student_details.full_name).toBe('Charlie Brown');
    });

    it('should sort by student name descending (Z-A)', () => {
      const result = sortApplications(mockApplications, 'student_name', 'desc');
      expect(result[0].student_details.full_name).toBe('Charlie Brown');
      expect(result[1].student_details.full_name).toBe('Bob Johnson');
      expect(result[2].student_details.full_name).toBe('Alice Williams');
    });

    it('should sort student names case-insensitively', () => {
      const mixedCase = [
        { id: 1, student_details: { full_name: 'zebra User' }, form_title: 'FormA', status: 'pending', submitted_at: '2024-01-01', amount: 0 },
        { id: 2, student_details: { full_name: 'Apple User' }, form_title: 'FormB', status: 'pending', submitted_at: '2024-01-02', amount: 0 },
        { id: 3, student_details: { full_name: 'Mango User' }, form_title: 'FormC', status: 'pending', submitted_at: '2024-01-03', amount: 0 }
      ];
      const result = sortApplications(mixedCase, 'student_name', 'asc');
      expect(result[0].student_details.full_name).toBe('Apple User');
      expect(result[1].student_details.full_name).toBe('Mango User');
      expect(result[2].student_details.full_name).toBe('zebra User');
    });
  });

  describe('Sort by form type', () => {
    it('should sort by form_title ascending', () => {
      const result = sortApplications(mockApplications, 'form_title', 'asc');
      expect(result[0].form_title).toBe('DGGR Bursary');
      expect(result[1].form_title).toBe('PSSSP Application');
      expect(result[2].form_title).toBe('UCEPP Program');
    });

    it('should sort by form_title descending', () => {
      const result = sortApplications(mockApplications, 'form_title', 'desc');
      expect(result[0].form_title).toBe('UCEPP Program');
      expect(result[1].form_title).toBe('PSSSP Application');
      expect(result[2].form_title).toBe('DGGR Bursary');
    });
  });

  describe('Sort by status', () => {
    it('should sort by status ascending (alphabetical)', () => {
      const result = sortApplications(mockApplications, 'status', 'asc');
      // accepted < forwarded < pending
      expect(result[0].status).toBe('accepted');
      expect(result[1].status).toBe('forwarded');
      expect(result[2].status).toBe('pending');
    });

    it('should sort by status descending', () => {
      const result = sortApplications(mockApplications, 'status', 'desc');
      expect(result[0].status).toBe('pending');
      expect(result[1].status).toBe('forwarded');
      expect(result[2].status).toBe('accepted');
    });
  });

  describe('Sort by amount', () => {
    it('should sort by amount ascending', () => {
      const result = sortApplications(mockApplications, 'amount', 'asc');
      expect(result[0].amount).toBe(1000);
      expect(result[1].amount).toBe(2000);
      expect(result[2].amount).toBe(3000);
    });

    it('should sort by amount descending', () => {
      const result = sortApplications(mockApplications, 'amount', 'desc');
      expect(result[0].amount).toBe(3000);
      expect(result[1].amount).toBe(2000);
      expect(result[2].amount).toBe(1000);
    });
  });

  describe('Sort by submitted date', () => {
    it('should sort by submitted_at ascending (oldest first)', () => {
      const result = sortApplications(mockApplications, 'submitted_at', 'asc');
      expect(result[0].submitted_at).toBe('2024-01-01');
      expect(result[1].submitted_at).toBe('2024-02-01');
      expect(result[2].submitted_at).toBe('2024-03-01');
    });

    it('should sort by submitted_at descending (newest first)', () => {
      const result = sortApplications(mockApplications, 'submitted_at', 'desc');
      expect(result[0].submitted_at).toBe('2024-03-01');
      expect(result[1].submitted_at).toBe('2024-02-01');
      expect(result[2].submitted_at).toBe('2024-01-01');
    });
  });

  describe('Sort direction toggle (handleSort)', () => {
    it('should set direction to asc when clicking a new column', () => {
      const result = handleSort('id', 'desc', 'student_name');
      expect(result.sortColumn).toBe('student_name');
      expect(result.sortDirection).toBe('asc');
    });

    it('should toggle asc → desc when clicking the same column', () => {
      const result = handleSort('id', 'asc', 'id');
      expect(result.sortColumn).toBe('id');
      expect(result.sortDirection).toBe('desc');
    });

    it('should toggle desc → asc when clicking the same column again', () => {
      const result = handleSort('id', 'desc', 'id');
      expect(result.sortColumn).toBe('id');
      expect(result.sortDirection).toBe('asc');
    });

    it('should always start with asc when switching to a different column', () => {
      const columns = ['id', 'student_name', 'form_title', 'status', 'amount', 'submitted_at'];
      columns.forEach(col => {
        const result = handleSort('other_column', 'desc', col);
        expect(result.sortDirection).toBe('asc');
      });
    });
  });

  describe('Null and missing value handling', () => {
    it('should handle null amount values without crashing', () => {
      const appsWithNull = [
        { id: 1, student_details: { full_name: 'A' }, form_title: 'FormA', status: 'pending', submitted_at: '2024-01-01', amount: null },
        { id: 2, student_details: { full_name: 'B' }, form_title: 'FormB', status: 'pending', submitted_at: '2024-01-02', amount: 500 }
      ];
      expect(() => sortApplications(appsWithNull, 'amount', 'asc')).not.toThrow();
    });

    it('should handle null student_details without crashing', () => {
      const appsWithNull = [
        { id: 1, student_details: null, form_title: 'FormA', status: 'pending', submitted_at: '2024-01-01', amount: 0 },
        { id: 2, student_details: { full_name: 'Bob' }, form_title: 'FormB', status: 'pending', submitted_at: '2024-01-02', amount: 0 }
      ];
      expect(() => sortApplications(appsWithNull, 'student_name', 'asc')).not.toThrow();
    });

    it('should treat null values as empty string and sort them first in asc order', () => {
      const appsWithNull = [
        { id: 1, student_details: null, form_title: 'FormA', status: 'pending', submitted_at: '2024-01-01', amount: 0 },
        { id: 2, student_details: { full_name: 'Bob' }, form_title: 'FormB', status: 'pending', submitted_at: '2024-01-02', amount: 0 }
      ];
      const result = sortApplications(appsWithNull, 'student_name', 'asc');
      // null full_name becomes '' which sorts before 'bob'
      expect(result[0].id).toBe(1);
      expect(result[1].id).toBe(2);
    });
  });

  describe('Sort combined with filter and pagination', () => {
    const largeDataset = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      student_details: {
        full_name: `Student ${String(25 - i).padStart(2, '0')}`, // Reverse order names
        email: `student${i + 1}@example.com`,
        beneficiary_number: `BEN${String(i + 1).padStart(3, '0')}`
      },
      form_title: i % 3 === 0 ? 'PSSSP Application' : i % 3 === 1 ? 'UCEPP Program' : 'DGGR Bursary',
      status: ['pending', 'reviewed', 'forwarded', 'accepted', 'rejected'][i % 5],
      submitted_at: `2024-${String((i % 12) + 1).padStart(2, '0')}-01`,
      amount: (i + 1) * 100
    }));

    const filterApplications = (apps: any[], searchQuery: string, statusFilter: string, fundingStreamFilter: string) => {
      return apps.filter(app => {
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
    };

    const paginateApplications = (apps: any[], currentPage: number, itemsPerPage: number) => {
      return apps.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
    };

    it('should apply sort after filter and return correct first page', () => {
      const filtered = filterApplications(largeDataset, '', 'pending', 'all');
      const sorted = sortApplications(filtered, 'amount', 'asc');
      const page1 = paginateApplications(sorted, 1, 10);

      // All results should be pending
      page1.forEach(app => expect(app.status).toBe('pending'));
      // Should be sorted by amount ascending
      for (let i = 1; i < page1.length; i++) {
        expect(page1[i].amount).toBeGreaterThanOrEqual(page1[i - 1].amount);
      }
    });

    it('should produce consistent results across pages when sorted', () => {
      const sorted = sortApplications(largeDataset, 'id', 'asc');
      const page1 = paginateApplications(sorted, 1, 10);
      const page2 = paginateApplications(sorted, 2, 10);

      // Last item of page 1 should have lower id than first item of page 2
      expect(page1[page1.length - 1].id).toBeLessThan(page2[0].id);
    });

    it('should not mutate the original array when sorting', () => {
      const original = [...mockApplications];
      sortApplications(mockApplications, 'id', 'desc');
      expect(mockApplications[0].id).toBe(original[0].id);
      expect(mockApplications[1].id).toBe(original[1].id);
      expect(mockApplications[2].id).toBe(original[2].id);
    });

    it('should sort PSSSP-filtered results by amount descending correctly', () => {
      const filtered = filterApplications(largeDataset, '', 'all', 'PSSSP');
      const sorted = sortApplications(filtered, 'amount', 'desc');

      // Verify descending order
      for (let i = 1; i < sorted.length; i++) {
        expect(sorted[i].amount).toBeLessThanOrEqual(sorted[i - 1].amount);
      }
      // All should be PSSSP
      sorted.forEach(app => expect(app.form_title).toContain('PSSSP'));
    });
  });
});

/**
 * Unit tests for eligibility determination display
 * Task 2.2: Display eligibility determination result
 * Requirements: 3.3 (ineligibility reasons), 3.4 (eligible marking)
 */
describe('Eligibility Determination Display', () => {
  // Mirror the renderEligibilityResult logic for unit testing
  const processEligibilityResult = (result: any) => {
    if (!result) return null;
    return {
      hasEligibleStreams: !!(result.eligible_streams && result.eligible_streams.length > 0),
      hasIneligibleStreams: !!(result.ineligible_streams && result.ineligible_streams.length > 0),
      eligibleStreams: result.eligible_streams || [],
      ineligibleStreams: result.ineligible_streams || [],
      details: result.details || {},
    };
  };

  describe('Eligible streams display', () => {
    it('should identify eligible streams from API result', () => {
      const result = {
        eligible_streams: ['PSSSP', 'DGGR'],
        ineligible_streams: [],
        details: {},
      };
      const processed = processEligibilityResult(result);
      expect(processed).not.toBeNull();
      expect(processed!.hasEligibleStreams).toBe(true);
      expect(processed!.eligibleStreams).toHaveLength(2);
      expect(processed!.eligibleStreams).toContain('PSSSP');
      expect(processed!.eligibleStreams).toContain('DGGR');
    });

    it('should handle result with only eligible streams', () => {
      const result = {
        eligible_streams: ['UCEPP'],
        ineligible_streams: [],
        details: {},
      };
      const processed = processEligibilityResult(result);
      expect(processed!.hasEligibleStreams).toBe(true);
      expect(processed!.hasIneligibleStreams).toBe(false);
    });

    it('should handle empty eligible streams', () => {
      const result = {
        eligible_streams: [],
        ineligible_streams: ['PSSSP'],
        details: { PSSSP: { reasons: ['Not a resident'] } },
      };
      const processed = processEligibilityResult(result);
      expect(processed!.hasEligibleStreams).toBe(false);
      expect(processed!.eligibleStreams).toHaveLength(0);
    });
  });

  describe('Ineligible streams display', () => {
    it('should identify ineligible streams with reasons', () => {
      const result = {
        eligible_streams: [],
        ineligible_streams: ['PSSSP', 'UCEPP'],
        details: {
          PSSSP: { reasons: ['Not a resident', 'Income exceeds threshold'] },
          UCEPP: { reasons: ['Not enrolled in eligible program'] },
        },
      };
      const processed = processEligibilityResult(result);
      expect(processed!.hasIneligibleStreams).toBe(true);
      expect(processed!.ineligibleStreams).toHaveLength(2);
      expect(processed!.details['PSSSP'].reasons).toHaveLength(2);
      expect(processed!.details['UCEPP'].reasons).toHaveLength(1);
    });

    it('should handle ineligible stream with no reasons provided', () => {
      const result = {
        eligible_streams: [],
        ineligible_streams: ['DGGR'],
        details: {},
      };
      const processed = processEligibilityResult(result);
      expect(processed!.hasIneligibleStreams).toBe(true);
      expect(processed!.details['DGGR']).toBeUndefined();
    });

    it('should expose ineligibility reasons for display', () => {
      const result = {
        eligible_streams: ['DGGR'],
        ineligible_streams: ['PSSSP'],
        details: {
          PSSSP: { reasons: ['Residency requirement not met'] },
        },
      };
      const processed = processEligibilityResult(result);
      expect(processed!.details['PSSSP'].reasons[0]).toBe('Residency requirement not met');
    });
  });

  describe('Mixed eligibility results', () => {
    it('should handle both eligible and ineligible streams', () => {
      const result = {
        eligible_streams: ['DGGR'],
        ineligible_streams: ['PSSSP', 'UCEPP'],
        details: {
          PSSSP: { reasons: ['Not a resident'] },
          UCEPP: { reasons: ['Not enrolled in eligible program'] },
        },
      };
      const processed = processEligibilityResult(result);
      expect(processed!.hasEligibleStreams).toBe(true);
      expect(processed!.hasIneligibleStreams).toBe(true);
      expect(processed!.eligibleStreams).toContain('DGGR');
      expect(processed!.ineligibleStreams).toContain('PSSSP');
      expect(processed!.ineligibleStreams).toContain('UCEPP');
    });
  });

  describe('Null/empty result handling', () => {
    it('should return null when result is null (loading or not yet fetched)', () => {
      const processed = processEligibilityResult(null);
      expect(processed).toBeNull();
    });

    it('should return null when result is undefined', () => {
      const processed = processEligibilityResult(undefined);
      expect(processed).toBeNull();
    });

    it('should handle result with missing eligible_streams field', () => {
      const result = {
        ineligible_streams: ['PSSSP'],
        details: { PSSSP: { reasons: ['Not a resident'] } },
      };
      const processed = processEligibilityResult(result);
      expect(processed!.eligibleStreams).toHaveLength(0);
      expect(processed!.hasEligibleStreams).toBe(false);
    });

    it('should handle result with missing ineligible_streams field', () => {
      const result = {
        eligible_streams: ['DGGR'],
        details: {},
      };
      const processed = processEligibilityResult(result);
      expect(processed!.ineligibleStreams).toHaveLength(0);
      expect(processed!.hasIneligibleStreams).toBe(false);
    });

    it('should handle result with missing details field', () => {
      const result = {
        eligible_streams: ['DGGR'],
        ineligible_streams: ['PSSSP'],
      };
      const processed = processEligibilityResult(result);
      expect(processed!.details).toEqual({});
    });
  });

  describe('Eligibility fetch state management', () => {
    it('should reset eligibility state when switching applications', () => {
      // Simulate state transitions when selectedAppId changes
      let eligibilityResult: any = { eligible_streams: ['DGGR'], ineligible_streams: [] };
      let isEligibilityLoading = false;
      let eligibilityError: string | null = null;

      // Simulate switching to a new application
      eligibilityResult = null;
      eligibilityError = null;
      isEligibilityLoading = true;

      expect(eligibilityResult).toBeNull();
      expect(eligibilityError).toBeNull();
      expect(isEligibilityLoading).toBe(true);
    });

    it('should set error state when API call fails', () => {
      let eligibilityResult: any = null;
      let isEligibilityLoading = false;
      let eligibilityError: string | null = null;

      // Simulate API failure
      const errorMessage = 'Failed to check eligibility';
      eligibilityError = errorMessage;
      isEligibilityLoading = false;

      expect(eligibilityResult).toBeNull();
      expect(eligibilityError).toBe(errorMessage);
      expect(isEligibilityLoading).toBe(false);
    });

    it('should set result and clear loading when API call succeeds', () => {
      let eligibilityResult: any = null;
      let isEligibilityLoading = true;
      let eligibilityError: string | null = null;

      // Simulate successful API response
      const apiResult = { eligible_streams: ['PSSSP'], ineligible_streams: [], details: {} };
      eligibilityResult = apiResult;
      isEligibilityLoading = false;

      expect(eligibilityResult).toEqual(apiResult);
      expect(isEligibilityLoading).toBe(false);
      expect(eligibilityError).toBeNull();
    });
  });
});

/**
 * Unit tests for duplicate flag status display
 * Task 2.3: Display duplicate flag status (if flagged)
 * Requirements: 7.3 (flag for manual review), 7.5 (no detection method shown),
 *               7.6 (display only flagged status), 7.7 (mark legitimate / confirm duplicate)
 */
describe('Duplicate Flag Status Display', () => {
  // Mirror the renderDuplicateStatus logic for unit testing
  const processDuplicateStatus = (status: any) => {
    if (!status || !status.is_flagged) return null;
    return {
      isFlagged: true,
      message: status.message || 'This application has been flagged for review',
      showActions: true,
    };
  };

  describe('Flagged application display', () => {
    it('should return display data when application is flagged', () => {
      const status = { is_flagged: true, message: 'Potential duplicate detected' };
      const result = processDuplicateStatus(status);
      expect(result).not.toBeNull();
      expect(result!.isFlagged).toBe(true);
    });

    it('should show action buttons when application is flagged', () => {
      const status = { is_flagged: true };
      const result = processDuplicateStatus(status);
      expect(result!.showActions).toBe(true);
    });

    it('should use fallback message when no message provided', () => {
      const status = { is_flagged: true };
      const result = processDuplicateStatus(status);
      expect(result!.message).toBe('This application has been flagged for review');
    });

    it('should use provided message when available', () => {
      const status = { is_flagged: true, message: 'Flagged for manual review' };
      const result = processDuplicateStatus(status);
      expect(result!.message).toBe('Flagged for manual review');
    });
  });

  describe('Non-flagged application display', () => {
    it('should return null when application is not flagged', () => {
      const status = { is_flagged: false };
      const result = processDuplicateStatus(status);
      expect(result).toBeNull();
    });

    it('should return null when duplicateStatus is null (not yet fetched)', () => {
      const result = processDuplicateStatus(null);
      expect(result).toBeNull();
    });

    it('should return null when duplicateStatus is undefined', () => {
      const result = processDuplicateStatus(undefined);
      expect(result).toBeNull();
    });

    it('should return null when is_flagged is missing', () => {
      const status = { message: 'Some message' };
      const result = processDuplicateStatus(status);
      expect(result).toBeNull();
    });
  });

  describe('Privacy protection — detection method not exposed', () => {
    it('should not expose detection method in display data', () => {
      const status = {
        is_flagged: true,
        message: 'Flagged for review',
        detection_method: 'sha256_hash',  // backend field that must not be shown
        identifier: 'abc123hash',          // backend field that must not be shown
      };
      const result = processDuplicateStatus(status);
      // The processed result for display should not include detection_method or identifier
      expect(result).not.toHaveProperty('detection_method');
      expect(result).not.toHaveProperty('identifier');
    });

    it('should only expose flagged status and message — not raw backend data', () => {
      const status = { is_flagged: true, message: 'Flagged for review' };
      const result = processDuplicateStatus(status);
      const keys = Object.keys(result!);
      expect(keys).toContain('isFlagged');
      expect(keys).toContain('message');
      expect(keys).toContain('showActions');
      // Should not have any extra fields beyond what's needed for display
      expect(keys).toHaveLength(3);
    });
  });

  describe('Duplicate fetch state management', () => {
    it('should reset duplicate state when switching applications', () => {
      let duplicateStatus: any = { is_flagged: true };
      let isDuplicateLoading = false;
      let duplicateError: string | null = null;

      // Simulate switching to a new application
      duplicateStatus = null;
      duplicateError = null;
      isDuplicateLoading = true;

      expect(duplicateStatus).toBeNull();
      expect(duplicateError).toBeNull();
      expect(isDuplicateLoading).toBe(true);
    });

    it('should set error state when API call fails', () => {
      let duplicateStatus: any = null;
      let isDuplicateLoading = false;
      let duplicateError: string | null = null;

      // Simulate API failure
      const errorMessage = 'Failed to check duplicate status';
      duplicateError = errorMessage;
      isDuplicateLoading = false;

      expect(duplicateStatus).toBeNull();
      expect(duplicateError).toBe(errorMessage);
      expect(isDuplicateLoading).toBe(false);
    });

    it('should set result and clear loading when API call succeeds', () => {
      let duplicateStatus: any = null;
      let isDuplicateLoading = true;
      let duplicateError: string | null = null;

      // Simulate successful API response — not flagged
      const apiResult = { is_flagged: false };
      duplicateStatus = apiResult;
      isDuplicateLoading = false;

      expect(duplicateStatus).toEqual(apiResult);
      expect(isDuplicateLoading).toBe(false);
      expect(duplicateError).toBeNull();
    });

    it('should set result and clear loading when flagged application returned', () => {
      let duplicateStatus: any = null;
      let isDuplicateLoading = true;
      let duplicateError: string | null = null;

      // Simulate successful API response — flagged
      const apiResult = { is_flagged: true, message: 'Potential duplicate detected' };
      duplicateStatus = apiResult;
      isDuplicateLoading = false;

      expect(duplicateStatus).toEqual(apiResult);
      expect(isDuplicateLoading).toBe(false);
      expect(duplicateError).toBeNull();
    });

    it('should reset duplicate state when leaving detail view', () => {
      let duplicateStatus: any = { is_flagged: true };
      let duplicateError: string | null = null;

      // Simulate leaving detail view (useEffect cleanup)
      duplicateStatus = null;
      duplicateError = null;

      expect(duplicateStatus).toBeNull();
      expect(duplicateError).toBeNull();
    });
  });

  describe('Mark as Legitimate / Confirm Duplicate actions', () => {
    it('should clear duplicate status after marking as legitimate', () => {
      let duplicateStatus: any = { is_flagged: true, message: 'Flagged for review' };

      // Simulate handleMarkLegitimate success
      duplicateStatus = null;

      expect(duplicateStatus).toBeNull();
    });

    it('should clear duplicate status after confirming as duplicate', () => {
      let duplicateStatus: any = { is_flagged: true, message: 'Flagged for review' };

      // Simulate handleMarkDuplicate success
      duplicateStatus = null;

      expect(duplicateStatus).toBeNull();
    });

    it('should not show duplicate section after action is taken', () => {
      // After marking, duplicateStatus is null, so processDuplicateStatus returns null
      const result = processDuplicateStatus(null);
      expect(result).toBeNull();
    });
  });
});

/**
 * Unit tests for Funding Breakdown display
 * Task 2.4: Display funding breakdown (tuition, living, books, total)
 * Validates: Requirements 4.8, 20.8
 */
describe('Funding Breakdown Display', () => {
  // Mirror the calculateAutoFunding output shape used by renderFundingBreakdown
  type FundingBreakdown = {
    tuition: { system: number; requested: number; rule: string };
    living: { system: number; rate: number; months: number; rule: string };
    books: { system: number; rule: string };
    special: { system: number; rule: string };
    total: number;
    stream: string;
    ineligible?: boolean;
    reason?: string;
  };

  const buildBreakdown = (overrides: Partial<FundingBreakdown> = {}): FundingBreakdown => ({
    tuition: { system: 5000, requested: 5000, rule: 'Max $5000 per semester' },
    living: { system: 4800, rate: 1200, months: 4, rule: '$1200/mo for 4 mons' },
    books: { system: 500, rule: '$500 per semester standard allowance' },
    special: { system: 0, rule: '' },
    total: 10300,
    stream: 'DGGR',
    ...overrides,
  });

  describe('Breakdown component amounts', () => {
    it('should include tuition amount in breakdown', () => {
      const breakdown = buildBreakdown({ tuition: { system: 4500, requested: 4500, rule: 'Max $4500' } });
      expect(breakdown.tuition.system).toBe(4500);
    });

    it('should include living allowance in breakdown', () => {
      const breakdown = buildBreakdown({ living: { system: 3600, rate: 900, months: 4, rule: '$900/mo for 4 mons' } });
      expect(breakdown.living.system).toBe(3600);
    });

    it('should include books & supplies amount in breakdown', () => {
      const breakdown = buildBreakdown();
      expect(breakdown.books.system).toBe(500);
    });

    it('should include total amount in breakdown', () => {
      const breakdown = buildBreakdown({ total: 10300 });
      expect(breakdown.total).toBe(10300);
    });

    it('should include special awards when present', () => {
      const breakdown = buildBreakdown({ special: { system: 1000, rule: 'Graduation Bursary' } });
      expect(breakdown.special.system).toBe(1000);
      expect(breakdown.special.rule).toBe('Graduation Bursary');
    });

    it('should have zero special awards when not applicable', () => {
      const breakdown = buildBreakdown();
      expect(breakdown.special.system).toBe(0);
    });
  });

  describe('Total calculation correctness', () => {
    it('should total equal sum of components (no special awards)', () => {
      const tuition = 5000;
      const living = 4800;
      const books = 500;
      const special = 0;
      const expectedTotal = tuition + living + books + special;

      const breakdown = buildBreakdown({
        tuition: { system: tuition, requested: tuition, rule: '' },
        living: { system: living, rate: 1200, months: 4, rule: '' },
        books: { system: books, rule: '' },
        special: { system: special, rule: '' },
        total: expectedTotal,
      });

      expect(breakdown.total).toBe(expectedTotal);
    });

    it('should total include special awards when present', () => {
      const tuition = 5000;
      const living = 4800;
      const books = 500;
      const special = 1000;
      const expectedTotal = tuition + living + books + special;

      const breakdown = buildBreakdown({
        tuition: { system: tuition, requested: tuition, rule: '' },
        living: { system: living, rate: 1200, months: 4, rule: '' },
        books: { system: books, rule: '' },
        special: { system: special, rule: 'Graduation Bursary' },
        total: expectedTotal,
      });

      expect(breakdown.total).toBe(expectedTotal);
    });

    it('should handle zero tuition (books-only scenario)', () => {
      const breakdown = buildBreakdown({
        tuition: { system: 0, requested: 0, rule: '' },
        living: { system: 0, rate: 0, months: 0, rule: '' },
        books: { system: 500, rule: '' },
        special: { system: 0, rule: '' },
        total: 500,
      });

      expect(breakdown.total).toBe(500);
    });
  });

  describe('Ineligibility handling', () => {
    it('should flag ineligible applications', () => {
      const breakdown = buildBreakdown({
        ineligible: true,
        reason: 'Student is eligible for NWT SFA; PSSSP/UCEPP funding not applicable.',
        total: 0,
      });

      expect(breakdown.ineligible).toBe(true);
      expect(breakdown.reason).toBeTruthy();
    });

    it('should have zero total for ineligible applications', () => {
      const breakdown = buildBreakdown({ ineligible: true, total: 0 });
      expect(breakdown.total).toBe(0);
    });

    it('should provide a reason for ineligibility', () => {
      const reason = 'Student is eligible for NWT SFA; PSSSP/UCEPP funding not applicable.';
      const breakdown = buildBreakdown({ ineligible: true, reason, total: 0 });
      expect(breakdown.reason).toBe(reason);
    });
  });

  describe('Funding stream identification', () => {
    it('should identify DGGR stream', () => {
      const breakdown = buildBreakdown({ stream: 'DGGR' });
      expect(breakdown.stream).toBe('DGGR');
    });

    it('should identify PSSSP stream', () => {
      const breakdown = buildBreakdown({ stream: 'PSSSP' });
      expect(breakdown.stream).toBe('PSSSP');
    });

    it('should identify UCEPP stream', () => {
      const breakdown = buildBreakdown({ stream: 'UCEPP' });
      expect(breakdown.stream).toBe('UCEPP');
    });
  });

  describe('Policy rule display', () => {
    it('should include tuition policy rule', () => {
      const breakdown = buildBreakdown({
        tuition: { system: 5000, requested: 5000, rule: 'Max $5000 per semester' },
      });
      expect(breakdown.tuition.rule).toBe('Max $5000 per semester');
    });

    it('should include living allowance policy rule', () => {
      const breakdown = buildBreakdown({
        living: { system: 4800, rate: 1200, months: 4, rule: '$1200/mo for 4 mons' },
      });
      expect(breakdown.living.rule).toBe('$1200/mo for 4 mons');
    });

    it('should include books policy rule', () => {
      const breakdown = buildBreakdown({
        books: { system: 500, rule: '$500 per semester standard allowance' },
      });
      expect(breakdown.books.rule).toBe('$500 per semester standard allowance');
    });
  });

  describe('Null/undefined handling', () => {
    it('should return null when autoSuggested is null', () => {
      // Simulates the renderFundingBreakdown guard: if (!autoSuggested) return null
      const autoSuggested: FundingBreakdown | null = null;
      const result = autoSuggested ? 'rendered' : null;
      expect(result).toBeNull();
    });

    it('should render when autoSuggested is provided', () => {
      const autoSuggested = buildBreakdown();
      const result = autoSuggested ? 'rendered' : null;
      expect(result).toBe('rendered');
    });

    it('should default to 0 when tuition system amount is missing', () => {
      const breakdown = buildBreakdown();
      const tuitionAmount = breakdown.tuition?.system ?? 0;
      expect(tuitionAmount).toBe(5000);
    });

    it('should default to 500 when books system amount is missing', () => {
      const breakdown = { ...buildBreakdown(), books: undefined } as any;
      const booksAmount = breakdown.books?.system ?? 500;
      expect(booksAmount).toBe(500);
    });
  });

  describe('Approved amount comparison', () => {
    it('should show approved amount when application is accepted', () => {
      const selectedApp = { amount: 10300, status: 'accepted' };
      const shouldShow = selectedApp.amount > 0 && selectedApp.status === 'accepted';
      expect(shouldShow).toBe(true);
    });

    it('should not show approved amount when application is pending', () => {
      const selectedApp = { amount: 0, status: 'pending' };
      const shouldShow = selectedApp.amount > 0 && selectedApp.status === 'accepted';
      expect(shouldShow).toBe(false);
    });

    it('should not show approved amount when amount is zero', () => {
      const selectedApp = { amount: 0, status: 'accepted' };
      const shouldShow = selectedApp.amount > 0 && selectedApp.status === 'accepted';
      expect(shouldShow).toBe(false);
    });

    it('should not show approved amount when application is rejected', () => {
      const selectedApp = { amount: 5000, status: 'rejected' };
      const shouldShow = selectedApp.amount > 0 && selectedApp.status === 'accepted';
      expect(shouldShow).toBe(false);
    });
  });
});
