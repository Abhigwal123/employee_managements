import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Return error object - we'll extract string in render
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Store error info for debugging
    this.setState({ errorInfo });
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  /**
   * Safely extract error message from error object
   * Handles various error formats: Error objects, API responses, plain objects, etc.
   * CRITICAL: Always returns a string, never an object
   */
  getErrorMessage() {
    const raw = this.state.error;

    if (!raw) {
      return "發生未知錯誤，請稍後再試";
    }

    // If error is already a string, return it
    if (typeof raw === "string") {
      return raw;
    }

    // Extract message from Error object
    if (raw.message && typeof raw.message === "string") {
      return raw.message;
    }

    // Extract from API response format - CRITICAL: ensure raw.error is a string
    if (raw.error) {
      if (typeof raw.error === "string") {
        return raw.error;
      }
      // If raw.error is an object, extract its message or stringify it
      if (typeof raw.error === "object") {
        if (raw.error.message && typeof raw.error.message === "string") {
          return raw.error.message;
        }
        // If error is an object without message, use error_type if available
        if (raw.error_type && typeof raw.error_type === "string") {
          return `${raw.error_type}: 發生錯誤`;
        }
        // Last resort: return generic message
        return "發生未知錯誤，請稍後再試";
      }
    }

    // Extract from nested error object
    if (raw.error?.message && typeof raw.error.message === "string") {
      return raw.error.message;
    }

    // Extract from details field
    if (raw.details && typeof raw.details === "string") {
      return raw.details;
    }

    // Handle object with error_type - CRITICAL: ensure all parts are strings
    if (typeof raw === "object") {
      if (raw.error_type && typeof raw.error_type === "string") {
        // Extract error message safely
        let errorMsg = "發生錯誤";
        if (raw.error) {
          if (typeof raw.error === "string") {
            errorMsg = raw.error;
          } else if (typeof raw.error === "object" && raw.error.message && typeof raw.error.message === "string") {
            errorMsg = raw.error.message;
          }
        } else if (raw.message && typeof raw.message === "string") {
          errorMsg = raw.message;
        }
        return `${raw.error_type}: ${errorMsg}`;
      }
      // If it's just a plain object without recognizable fields, return generic message
      return "發生未知錯誤，請稍後再試";
    }

    return "發生未知錯誤，請稍後再試";
  }

  /**
   * Safely extract error traceback/stack for debugging
   */
  getErrorTrace() {
    const raw = this.state.error;

    if (!raw) {
      return this.state.errorInfo?.componentStack || undefined;
    }

    // Check for traceback in error object
    if (raw.traceback && typeof raw.traceback === "string") {
      return raw.traceback;
    }

    if (raw.trace && typeof raw.trace === "string") {
      return raw.trace;
    }

    // Check for stack trace
    if (raw.stack && typeof raw.stack === "string") {
      return raw.stack;
    }

    // Check errorInfo component stack
    if (this.state.errorInfo?.componentStack) {
      return this.state.errorInfo.componentStack;
    }

    return undefined;
  }

  /**
   * Safety function to ensure a value is always a string
   * Prevents React from trying to render objects
   */
  ensureString(value) {
    if (value === null || value === undefined) {
      return "";
    }
    if (typeof value === "string") {
      return value;
    }
    if (typeof value === "object") {
      // Try to extract a meaningful string
      if (value.message && typeof value.message === "string") {
        return value.message;
      }
      if (value.error && typeof value.error === "string") {
        return value.error;
      }
      // Last resort: return generic message
      return "發生未知錯誤，請稍後再試";
    }
    // For other types (number, boolean, etc.), convert to string
    return String(value);
  }

  render() {
    if (this.state.hasError) {
      // CRITICAL: Use ensureString as final safety check
      const errorMessage = this.ensureString(this.getErrorMessage());
      const errorTrace = this.getErrorTrace();
      // Ensure trace is also a string
      const safeTrace = errorTrace ? this.ensureString(errorTrace) : null;

      return (
        <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-600 mb-4">系統錯誤</h2>
            <p className="text-gray-700 mb-4">
              {errorMessage}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null, errorInfo: null });
                window.location.href = '/login';
              }}
              className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
            >
              回到登入頁面
            </button>
            {safeTrace && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm text-gray-500">錯誤詳情</summary>
                <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-60">
                  {safeTrace}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
