/**
 * Axios client — cookie-based auth + CSRF double-submit pattern.
 *
 * Auth strategy
 * -------------
 * - The JWT lives in an httpOnly cookie set by the backend.
 *   Axios sends it automatically with every request thanks to
 *   `withCredentials: true`. JS never touches the token value.
 *
 * - A second cookie `csrf_token` (NOT httpOnly) is also set by the
 *   backend on login. For every state-mutating request (POST, PUT,
 *   PATCH, DELETE) the request interceptor reads this cookie and injects
 *   it as the `X-CSRF-Token` header. The backend validates the match.
 *
 * - On 401 the response interceptor clears local UI state and redirects
 *   to /login.  It does NOT try to remove the httpOnly cookie (it can't);
 *   calling POST /auth/logout does that.
 */
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const CSRF_METHODS = new Set(['post', 'put', 'patch', 'delete']);

/** Read a cookie value by name from document.cookie. */
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const client = axios.create({
  baseURL: API_URL,
  withCredentials: true, // send the httpOnly JWT cookie on every request
});

// ------------------------------------------------------------------ //
// Request interceptor — inject CSRF token for mutating methods
// ------------------------------------------------------------------ //
client.interceptors.request.use(
  (config) => {
    const method = (config.method ?? '').toLowerCase();
    if (CSRF_METHODS.has(method)) {
      const csrfToken = getCookie('csrf_token');
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken;
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ------------------------------------------------------------------ //
// Response interceptor — handle global 401
// ------------------------------------------------------------------ //

// Endpoints that are allowed to return 401 without triggering a redirect.
// /auth/me is the session-check call; 401 simply means "no active session".
const NO_REDIRECT_ON_401 = new Set(['/auth/me', '/auth/login']);

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url: string = error.config?.url ?? '';
      const alreadyOnLogin = window.location.pathname === '/login';

      // Only redirect when it's a real "session expired" 401 from a
      // protected resource — not from the probing /auth/me call.
      if (!alreadyOnLogin && !NO_REDIRECT_ON_401.has(url)) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default client;
