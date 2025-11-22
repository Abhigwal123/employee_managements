import { Routes, Route } from 'react-router-dom';
import SysAdminLayout from '../layouts/SysAdminLayout';
import ProtectedRoute from './ProtectedRoute';
import {
  Dashboard,
  OrganizationMaintenance,
  ScheduleListMaintenance,
} from '../pages/SysAdmin';

export default function SysAdminRoutes() {
  return (
    <ProtectedRoute requiredRole="SysAdmin">
      <Routes>
        <Route path="/*" element={<SysAdminLayout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="org" element={<OrganizationMaintenance />} />
          <Route path="schedule" element={<ScheduleListMaintenance />} />
          <Route index element={<Dashboard />} />
        </Route>
      </Routes>
    </ProtectedRoute>
  );
}

