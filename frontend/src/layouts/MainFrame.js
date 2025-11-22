import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import TopNav from '../components/TopNav';

export default function MainFrame({ role, title }) {
  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <Sidebar role={role} />
      
      {/* 主內容區 */}
      <div className="md:ml-64 flex flex-col flex-1">
        <TopNav title={title} />
        
        {/* 頁面內容 */}
        <main className="flex-1 overflow-y-auto p-6 md:p-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
