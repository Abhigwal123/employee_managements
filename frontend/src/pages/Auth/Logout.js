import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ROUTES } from '../../utils/constants';

export default function Logout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const performLogout = async () => {
      try {
        await logout();
        // Use replace to avoid adding logout to history
        navigate(ROUTES.LOGIN, { replace: true });
      } catch (error) {
        console.error('Logout error:', error);
        // Even if logout fails, navigate to login
        navigate(ROUTES.LOGIN, { replace: true });
      }
    };
    
    performLogout();
  }, [logout, navigate]);

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="text-center">
        <p className="text-gray-600">Logging out...</p>
      </div>
    </div>
  );
}



