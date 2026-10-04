/**
 * API Client Utility for Agent Manager
 * Provides safe HTTP fetching with robust content-type validation and error parsing.
 * Prevents JSON parse errors (e.g. Unexpected token 'I' on 500 Internal Server Error).
 */

(function (global) {
  /**
   * Safely fetch a JSON resource from the server.
   * Ensures response.ok and Content-Type are validated before invoking response.json().
   *
   * @param {string} url - Request URL
   * @param {RequestInit} [options={}] - Standard fetch options
   * @returns {Promise<any>} Parsed JSON response or null
   * @throws {Error} Descriptive error on non-ok status or network failure
   */
  async function safeFetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.toLowerCase().includes('application/json');

    if (!res.ok) {
      let errorMessage = `HTTP ${res.status}`;
      if (isJson) {
        try {
          const errObj = await res.json();
          if (errObj && typeof errObj === 'object') {
            errorMessage = errObj.detail || errObj.error || errObj.message || JSON.stringify(errObj);
          }
        } catch {
          errorMessage = `HTTP ${res.status}: Failed to parse JSON error`;
        }
      } else {
        try {
          const rawText = await res.text();
          const cleanText = rawText ? rawText.trim().replace(/\s+/g, ' ') : '';
          errorMessage = cleanText ? `HTTP ${res.status}: ${cleanText.slice(0, 300)}` : `HTTP ${res.status} ${res.statusText || 'Error'}`;
        } catch {
          errorMessage = `HTTP ${res.status} ${res.statusText || 'Error'}`;
        }
      }
      const error = new Error(errorMessage);
      error.status = res.status;
      error.response = res;
      throw error;
    }

    if (res.status === 204 || res.headers.get('content-length') === '0') {
      return null;
    }

    if (isJson) {
      return await res.json();
    }

    const rawText = await res.text();
    try {
      return JSON.parse(rawText);
    } catch {
      return rawText;
    }
  }

  /**
   * Extracts a user-facing error message from any caught error.
   *
   * @param {any} err - Caught error or exception
   * @param {string} [fallback='An unexpected error occurred']
   * @returns {string} Clean error string
   */
  function extractErrorMessage(err, fallback = 'An unexpected error occurred') {
    if (!err) return fallback;
    if (typeof err === 'string') return err;
    if (err.message) return err.message;
    if (err.detail) return err.detail;
    if (typeof err === 'object') {
      try {
        return JSON.stringify(err);
      } catch {
        return fallback;
      }
    }
    return String(err);
  }

  global.safeFetchJson = safeFetchJson;
  global.extractErrorMessage = extractErrorMessage;
})(typeof window !== 'undefined' ? window : globalThis);
