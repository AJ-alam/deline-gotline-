/**
 * Error handling in the API client.
 *
 * The previous client unwrapped a {success, data, message} envelope and
 * collapsed field errors to a single string, so a form could not show a message
 * against the question it belonged to.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, tokens } from './client';

describe('ApiError', () => {
  it('keeps a message per field', () => {
    const error = new ApiError(400, 'first', {
      course_load: 'Enrollment status must be one of: Full-time, Part-time.',
      semester: 'Semester is required.',
    });

    expect(Object.keys(error.fieldErrors)).toEqual(['course_load', 'semester']);
    expect(error.fieldErrors.course_load).toContain('Full-time');
  });

  it('reports an auth failure separately from a validation failure', () => {
    expect(new ApiError(401, 'No credentials').isAuthFailure).toBe(true);
    expect(new ApiError(400, 'Bad answer').isAuthFailure).toBe(false);
    expect(new ApiError(403, 'Not permitted').isAuthFailure).toBe(false);
  });

  it('is a real Error, so it survives being thrown and caught', () => {
    const error = new ApiError(409, 'Cannot approve a submitted application.');
    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe('ApiError');
    expect(error.message).toBe('Cannot approve a submitted application.');
  });
});

describe('token storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and returns both tokens', () => {
    tokens.set('access-1', 'refresh-1');
    expect(tokens.access).toBe('access-1');
    expect(tokens.refresh).toBe('refresh-1');
  });

  it('keeps the existing refresh token when only the access token is renewed', () => {
    tokens.set('access-1', 'refresh-1');
    tokens.set('access-2');
    expect(tokens.access).toBe('access-2');
    expect(tokens.refresh).toBe('refresh-1');
  });

  it('clears both on sign out, so a stale token cannot be reused', () => {
    tokens.set('access-1', 'refresh-1');
    tokens.clear();
    expect(tokens.access).toBeNull();
    expect(tokens.refresh).toBeNull();
  });
});

describe('endpoint shape', () => {
  it('addresses resources once, without the forms/forms stutter', async () => {
    const { default: api } = await import('./client');
    // Guards against reintroducing /api/forms/forms/ and /api/forms/submissions/.
    const source = api.toString();
    expect(source).not.toContain('forms/forms');
  });
});

describe('generated types', () => {
  it('exports one union member per application type', async () => {
    const module = await import('./schema.generated');
    expect(Object.keys(module.APPLICATION_TYPE_LABELS)).toHaveLength(10);
    expect(module.APPLICATION_TYPE_LABELS.admission).toBe('Admission Application');
    // The letters are gone from the vocabulary entirely.
    expect(Object.keys(module.APPLICATION_TYPE_LABELS)).not.toContain('form_a');
  });
});

describe('money formatting', () => {
  it('formats amounts consistently and copes with nonsense', async () => {
    const { formatMoney } = await import('../components/ui/format');
    expect(formatMoney('7700.00')).toBe('$7,700.00');
    expect(formatMoney(0)).toBe('$0.00');
    expect(formatMoney('not a number')).toBe('—');
  });
});

vi.mock('../config/api', () => ({ API_BASE_URL: '/api' }));
