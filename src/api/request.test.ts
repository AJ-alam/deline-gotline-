/**
 * What the client puts on the wire.
 *
 * These exist because of a bug the whole test suite and three live API audits
 * missed: the axios instance set `Content-Type: application/json` for every
 * request, so a file upload went out as JSON, no multipart boundary was
 * generated, and Django parsed no file — "The submitted data was not a file.
 * Check the encoding type on the form."
 *
 * The server tests could not catch it because they build their own requests
 * correctly. The only place the mistake exists is in how the client asks, so
 * that is what these inspect: the request config, captured by a stub adapter,
 * without a server involved.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import type { InternalAxiosRequestConfig } from 'axios';

import api, { http, tokens } from './client';

let sent: InternalAxiosRequestConfig[] = [];

/** Answers every request without a network, keeping what was asked. */
function capture() {
  sent = [];
  http.defaults.adapter = async (config) => {
    sent.push(config as InternalAxiosRequestConfig);
    return {
      data: {},
      status: 200,
      statusText: 'OK',
      headers: {},
      config: config as InternalAxiosRequestConfig,
    };
  };
}

const contentType = (config: InternalAxiosRequestConfig) =>
  String(config.headers?.['Content-Type'] ?? config.headers?.['content-type'] ?? '');

describe('what the client sends', () => {
  beforeEach(() => {
    capture();
    tokens.set('test-access', 'test-refresh');
  });

  it('does not label a file upload as JSON', async () => {
    // The bug. A FormData body with an application/json content type never
    // gets a boundary, and the server sees no file at all.
    await api.uploadDocument(
      new File(['%PDF'], 'transcript.pdf', { type: 'application/pdf' }),
      'doc_transcript',
    );

    expect(sent).toHaveLength(1);
    expect(contentType(sent[0])).not.toContain('application/json');
  });

  it('sends a file upload as FormData carrying the file and its field', async () => {
    const file = new File(['%PDF'], 'transcript.pdf', { type: 'application/pdf' });
    await api.uploadDocument(file, 'doc_transcript');

    const body = sent[0].data as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get('field_key')).toBe('doc_transcript');
    expect(body.get('file')).toBe(file);
  });

  it('names the application when one is given', async () => {
    await api.uploadDocument(
      new File(['%PDF'], 'x.pdf', { type: 'application/pdf' }),
      'doc_transcript',
      42,
    );
    expect((sent[0].data as FormData).get('application')).toBe('42');
  });

  it('still sends ordinary requests as JSON', async () => {
    await api.submit('admission', { first_name: 'Sara' } as never);

    // Either explicitly set, or left for axios to infer from a plain object —
    // what must not happen is multipart, or a body that is not serialised.
    expect(sent[0].data).not.toBeInstanceOf(FormData);
    expect(contentType(sent[0])).not.toContain('multipart');
  });

  it('carries the token on every request', async () => {
    await api.applications();
    expect(String(sent[0].headers.Authorization)).toBe('Bearer test-access');
  });
});

/**
 * Every endpoint the client calls, checked against the routes the server
 * actually publishes.
 *
 * This is the class of mistake that produced the upload bug and, earlier, an
 * audit script pointed at /directory/ when the route is /people/. Nothing on
 * the server can catch a client that asks the wrong way; only this can.
 *
 * The expected paths below were read off `manage.py show_urls` equivalents —
 * if one changes, this fails at the moment of the change rather than in the
 * browser.
 */
describe('the endpoints the client calls', () => {
  beforeEach(() => {
    capture();
    tokens.set('test-access', 'test-refresh');
  });

  const asked = () => ({
    method: String(sent[0].method).toLowerCase(),
    url: String(sent[0].url),
  });

  it.each([
    ['schemas', () => api.schemas(), 'get', '/schemas/'],
    ['schema', () => api.schema('admission'), 'get', '/schemas/admission/'],
    ['eligibilityQuestions', () => api.eligibilityQuestions(), 'get', '/auth/eligibility/'],
    ['checkEligibility', () => api.checkEligibility({}), 'post', '/auth/eligibility/'],
    ['me', () => api.me(), 'get', '/me/'],
    ['updateMe', () => api.updateMe({}), 'patch', '/me/'],
    ['applications', () => api.applications(), 'get', '/applications/'],
    ['application', () => api.application(7), 'get', '/applications/7/'],
    ['transition', () => api.transition(7, 'reviewed'), 'post', '/applications/7/transition/'],
    ['previewDecision', () => api.previewDecision(7), 'get', '/applications/7/decision-preview/'],
    ['recordDecision', () => api.recordDecision(7), 'post', '/applications/7/price/'],
    ['decisionHistory', () => api.decisionHistory(7), 'get', '/applications/7/decisions/'],
    ['guestSchemas', () => api.guestSchemas(), 'get', '/guest-applications/'],
    ['uploadDocument', () => api.uploadDocument(
      new File(['x'], 'a.pdf', { type: 'application/pdf' }), 'doc_transcript'),
      'post', '/documents/'],
    ['enrolmentPreview', () => api.enrolmentPreview('admission', {}),
      'post', '/enrolment-preview/'],
    ['policyRates', () => api.policyRates(), 'get', '/policy/rates/'],
    ['policyRate', () => api.policyRate(3), 'get', '/policy/rates/3/'],
    ['ruleSets', () => api.ruleSets(), 'get', '/policy/rule-sets/'],
    ['directory', () => api.directory(), 'get', '/people/'],
    ['notifications', () => api.notifications(), 'get', '/notifications/'],
    ['markNotificationsRead', () => api.markNotificationsRead(), 'post', '/notifications/'],
    ['dashboard', () => api.dashboard(), 'get', '/dashboard/'],
    ['paymentRun', () => api.paymentRun(), 'get', '/finance/pending/'],
    ['dispatchPaymentRun', () => api.dispatchPaymentRun(), 'post', '/finance/dispatch/'],
  ])('%s asks the right way', async (_name, callIt, method, url) => {
    await callIt();
    expect(asked()).toEqual({ method, url });
  });

  it('sends nothing to a path the server does not publish', async () => {
    // The paths above are the whole surface. A typo in one of them is the bug
    // this file exists for, so they are asserted exactly rather than by prefix.
    await api.application(7);
    expect(asked().url).not.toContain('undefined');
    expect(asked().url).not.toContain('[object');
  });
});
