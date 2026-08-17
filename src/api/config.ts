/**
 * Where the API is.
 *
 * Relative by default, so the browser talks to whatever origin served the app
 * and Vite's dev proxy forwards /api to Django. VITE_API_URL overrides it when
 * the two are deployed apart.
 *
 * This file used to also export an `apiCall` fetch helper that read a
 * 'dgg_token' key from localStorage. Nothing called it, and nothing writes that
 * key — the real client (api/client.ts) has its own token storage and refresh.
 * A second half-working HTTP path is worth deleting before someone picks it up
 * and starts sending requests with an Authorization header that is always
 * undefined.
 */

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
