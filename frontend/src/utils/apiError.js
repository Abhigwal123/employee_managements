/**
 * Ensure a value is always a string (for React rendering safety)
 * Prevents "Objects are not valid as a React child" errors
 * 
 * @param {unknown} value - Any value that might be rendered
 * @returns {string} - Always returns a string
 */
export function ensureString(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "object") {
    // Try to extract a meaningful string from object
    if (value.message && typeof value.message === "string") {
      return value.message;
    }
    if (value.error && typeof value.error === "string") {
      return value.error;
    }
    if (value.error_type && typeof value.error_type === "string") {
      const errorMsg = value.error ? ensureString(value.error) : "發生錯誤";
      return `${value.error_type}: ${errorMsg}`;
    }
    // Last resort: return generic message
    return "發生未知錯誤，請稍後再試";
  }
  // For other types (number, boolean, etc.), convert to string
  return String(value);
}

/**
 * API Error Normalization Utility
 * Converts various error formats (Axios errors, API responses, etc.) into user-friendly strings
 * 
 * @param {unknown} err - Error object from catch block
 * @returns {string} - Normalized error message in Chinese
 */
export function normalizeApiError(err) {
  if (!err) return "發生未知錯誤";

  const e = err;

  // Handle Axios error responses
  if (e?.response?.data) {
    const data = e.response.data;
    
    // If data is already a string, return it
    if (typeof data === "string") return data;
    
    // Check for common error message fields
    if (data.error) {
      // If error is a string, return it; if it's an object, extract message
      if (typeof data.error === "string") {
        return data.error;
      }
      if (data.error.message) {
        return data.error.message;
      }
    }
    
    if (data.message) {
      if (typeof data.message === "string") {
        return data.message;
      }
    }
    
    if (data.details) {
      if (typeof data.details === "string") {
        return data.details;
      }
    }
  }

  // Handle Error objects with message property
  if (e.message) {
    if (typeof e.message === "string") {
      return e.message;
    }
  }

  // Handle network errors
  if (e.code === 'ECONNREFUSED' || e.message?.includes('Network Error')) {
    return "無法連接到伺服器，請確認後端服務是否正在運行";
  }

  // Handle timeout errors
  if (e.code === 'ECONNABORTED' || e.message?.includes('timeout')) {
    return "請求逾時，請稍後再試";
  }

  // Fallback for unknown errors
  return "發生未知錯誤，請稍後再試";
}

/**
 * Extract error details for debugging (traceback, etc.)
 * Returns a string representation of error details, or undefined if not available
 * 
 * @param {unknown} err - Error object from catch block
 * @returns {string|undefined} - Error traceback/details for debugging
 */
export function extractErrorDetails(err) {
  if (!err) return undefined;

  const e = err;

  // Check for traceback in response data
  if (e?.response?.data?.traceback) {
    if (typeof e.response.data.traceback === "string") {
      return e.response.data.traceback;
    }
  }

  if (e?.response?.data?.trace) {
    if (typeof e.response.data.trace === "string") {
      return e.response.data.trace;
    }
  }

  // Check for stack trace in Error object
  if (e?.stack && typeof e.stack === "string") {
    return e.stack;
  }

  return undefined;
}

