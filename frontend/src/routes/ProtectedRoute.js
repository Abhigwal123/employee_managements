import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import { ROUTES } from '../utils/constants';

export default function ProtectedRoute({ children, requiredRole }) {
  const { isAuthenticated, user, loading } = useAuth();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  if (requiredRole) {
    const userRole = user?.role?.toLowerCase() || '';
    const requiredRoleLower = requiredRole.toLowerCase();
    
    // Handle role variations with better matching
    let roleMatches = userRole === requiredRoleLower;
    
    // ClientAdmin variations
    if (!roleMatches && requiredRoleLower === 'clientadmin') {
      roleMatches = userRole === 'client_admin' || userRole === 'clientadmin';
    }
    
    // ScheduleManager variations
    if (!roleMatches && requiredRoleLower === 'schedulemanager') {
      roleMatches = userRole === 'schedule_manager' || userRole === 'schedulemanager';
    }
    
    // Employee variations - most flexible matching
    if (!roleMatches && (requiredRoleLower === 'employee' || requiredRoleLower === 'department_employee')) {
      roleMatches = 
        userRole === 'employee' ||
        userRole === 'department_employee' ||
        userRole === 'department employee' ||
        userRole === 'departmentemployee';
    }
    
    if (!roleMatches) {
      console.warn(`Role mismatch: user role '${user?.role}' (normalized: '${userRole}') does not match required '${requiredRole}' (normalized: '${requiredRoleLower}')`);
      // Don't logout, just redirect to login
      return <Navigate to={ROUTES.LOGIN} replace />;
    }
  }

  return children;
}

