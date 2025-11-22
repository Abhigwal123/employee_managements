import { Routes, Route } from 'react-router-dom';
import EmployeeLayout from '../layouts/EmployeeLayout';
import ProtectedRoute from './ProtectedRoute';
import { MyDashboard } from '../pages/Employee';

export default function EmployeeRoutes() {
  return (
    <ProtectedRoute requiredRole="Department_Employee">
      <Routes>
        <Route path="/*" element={<EmployeeLayout />}>
          <Route path="my" element={<MyDashboard />} />
          <Route index element={<MyDashboard />} />
          <Route path="*" element={<MyDashboard />} />
        </Route>
      </Routes>
    </ProtectedRoute>
  );
}

