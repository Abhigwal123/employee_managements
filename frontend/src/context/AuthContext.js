import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { authService } from '../services/authService';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  // Start with loading=false so login page renders immediately
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(false); // Changed: false by default
  
  const initializedRef = useRef(false);
  const mountedRef = useRef(true);
  const verificationInProgressRef = useRef(false);

  // Logout function
  const logout = useCallback(async () => {
    console.log('[AuthContext] 🔴 Logout triggered');
    
    try {
      await authService.logout();
    } catch (error) {
      console.error('[AuthContext] Logout error:', error);
    } finally {
      // Always clear local state
      setIsAuthenticated(false);
      setUser(null);
      setTenant(null);
      setLoading(false);
      
      // Clear localStorage
      localStorage.removeItem('token');
      localStorage.removeItem('access_token');
      localStorage.removeItem('auth');
      
      console.log('[AuthContext] ✅ Logout complete');
    }
  }, []);

  // Initialize auth state - non-blocking
  useEffect(() => {
    if (initializedRef.current) {
      return;
    }
    
    initializedRef.current = true;
    mountedRef.current = true;

    console.log('[AuthContext] Initializing authentication state...');

    const initializeAuth = () => {
      const token = localStorage.getItem('token') || localStorage.getItem('access_token');
      const storedAuth = localStorage.getItem('auth');

      // No token = not authenticated - render login immediately
      if (!token || !storedAuth) {
        console.log('[AuthContext] No stored auth - user not authenticated');
        setIsAuthenticated(false);
        setUser(null);
        setTenant(null);
        return;
      }

      // Token exists - restore from localStorage immediately, verify in background
      try {
        const authData = JSON.parse(storedAuth);
        
        // Restore state immediately for instant UI
        setIsAuthenticated(authData.isAuthenticated || false);
        setUser(authData.user || null);
        setTenant(authData.tenant || null);
        
        console.log('[AuthContext] Restored auth state from localStorage');

        // Verify token in background (non-blocking)
        if (!verificationInProgressRef.current) {
          verificationInProgressRef.current = true;
          
          // Small delay to avoid blocking render
          setTimeout(async () => {
            try {
              const response = await authService.getCurrentUser();
              
              if (!mountedRef.current) return;

              if (response && response.success) {
                console.log('[AuthContext] ✅ Token verified');
                setIsAuthenticated(true);
                setUser(response.user);
                setTenant(response.tenant);
                
                // Update localStorage
                localStorage.setItem('auth', JSON.stringify({
                  isAuthenticated: true,
                  user: response.user,
                  tenant: response.tenant,
                }));
              }
            } catch (error) {
              if (!mountedRef.current) return;
              
              // Token invalid - clear silently
              console.warn('[AuthContext] ⚠️ Token verification failed - clearing auth');
              setIsAuthenticated(false);
              setUser(null);
              setTenant(null);
              localStorage.removeItem('token');
              localStorage.removeItem('access_token');
              localStorage.removeItem('auth');
            } finally {
              if (mountedRef.current) {
                verificationInProgressRef.current = false;
              }
            }
          }, 100);
        }
      } catch (error) {
        console.error('[AuthContext] Error parsing stored auth:', error);
        // Clear invalid data
        setIsAuthenticated(false);
        setUser(null);
        setTenant(null);
        localStorage.removeItem('token');
        localStorage.removeItem('access_token');
        localStorage.removeItem('auth');
      }
    };

    // Initialize immediately (synchronous check)
    initializeAuth();

    return () => {
      mountedRef.current = false;
      verificationInProgressRef.current = false;
    };
  }, []);

  // Login function
  const login = async (username, password) => {
    console.log('[AuthContext] Login attempt...');
    
    try {
      const response = await authService.login(username, password);
      
      if (response.success) {
        console.log('[AuthContext] ✅ Login successful');
        
        // Set auth state immediately
        setIsAuthenticated(true);
        setUser(response.user);
        setTenant(response.tenant);
        setLoading(false);
        
        return { success: true, user: response.user };
      }
      
      console.warn('[AuthContext] Login failed:', response.error);
      return { success: false, error: response.error || 'Login failed' };
    } catch (error) {
      console.error('[AuthContext] Login error:', error);
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Login failed',
      };
    }
  };

  const getToken = useCallback(() => {
    return (
      localStorage.getItem('token') ||
      localStorage.getItem('access_token') ||
      localStorage.getItem('jwt')
    );
  }, []);

  const value = {
    isAuthenticated,
    user,
    tenant,
    login,
    logout,
    loading,
    getToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
