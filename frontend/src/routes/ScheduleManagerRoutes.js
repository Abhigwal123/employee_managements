import { Routes, Route } from 'react-router-dom';
import ScheduleManagerLayout from '../layouts/ScheduleManagerLayout';
import ProtectedRoute from './ProtectedRoute';
import {
  Scheduling,
  Export,
} from '../pages/ScheduleManager';
import JobLogs from '../pages/ScheduleManager/JobLogs';

export default function ScheduleManagerRoutes() {
  return (
    <ProtectedRoute requiredRole="ScheduleManager">
      <Routes>
        <Route path="/*" element={<ScheduleManagerLayout />}>
          <Route path="scheduling" element={<Scheduling />} />
          <Route path="export" element={<Export />} />
          <Route path="logs" element={<JobLogs />} />
          <Route index element={<Scheduling />} />
        </Route>
      </Routes>
    </ProtectedRoute>
  );
}

