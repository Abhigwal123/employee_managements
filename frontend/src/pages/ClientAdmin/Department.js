import React, { useState, useEffect } from 'react';
import { departmentService } from '../../services/departmentService';
import { useAuth } from '../../context/AuthContext';
import { userService } from '../../services/userService';
import { tenantService } from '../../services/tenantService';
import LoadingSpinner from '../../components/LoadingSpinner';

const formatDeptId = (deptId) => {
  if (!deptId) return 'DEPT-000';
  const str = String(deptId);
  return str.length > 8 ? `DEPT-${str.substring(str.length - 3)}` : `DEPT-${str.padStart(3, '0')}`;
};

const getStatusBadge = (isActive) => {
  if (isActive) {
    return (
      <span className="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
        啟用
      </span>
    );
  }
  return (
    <span className="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
      停用
    </span>
  );
};

export default function Department() {
  const { user, tenant } = useAuth();
  const [departments, setDepartments] = useState([]);
  const [users, setUsers] = useState([]);
  const [tenantName, setTenantName] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [accessDenied, setAccessDenied] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState(null);
  const [formData, setFormData] = useState({
    departmentID: '',
    departmentName: '',
    managerID: '',
    managerName: '',
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  // Check permissions
  useEffect(() => {
    const checkAccess = () => {
      const userRole = user?.role || '';
      const allowedRoles = ['ClientAdmin', 'Client_Admin', 'ScheduleManager', 'Schedule_Manager'];
      
      if (!user || !allowedRoles.includes(userRole)) {
        setAccessDenied(true);
        setError('需要管理員或排班主管權限才能存取此頁面');
        setLoading(false);
        return false;
      }
      return true;
    };

    if (user) {
      if (checkAccess()) {
        loadData();
      }
    }
  }, [user]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      
      console.log('[TRACE] Department: Loading data...');
      
      // Load tenant name if tenant ID is available
      let fetchedTenantName = '';
      if (tenant?.tenantID) {
        try {
          const tenantResponse = await tenantService.getById(tenant.tenantID);
          fetchedTenantName = tenantResponse?.data?.tenantName || tenantResponse?.tenantName || '';
        } catch (err) {
          console.warn('[WARN] Department: Could not fetch tenant name:', err);
        }
      }
      setTenantName(fetchedTenantName || tenant?.tenantName || '機構');
      
      const [deptResponse, userResponse] = await Promise.all([
        departmentService.getAll(1, 100),
        userService.getAll(1, 100),
      ]);

      console.log('[TRACE] Department: Responses:', {
        deptResponse,
        userResponse,
      });

      const depts = deptResponse?.data || deptResponse?.items || deptResponse || [];
      const allUsers = userResponse?.data || userResponse?.items || userResponse || [];
      
      console.log('[TRACE] Department: Data counts:', {
        departments: depts.length,
        users: allUsers.length,
      });

      // Map departments with managers using manager_id if available
      const departmentsWithManagers = depts.map(dept => {
        // Try to find manager by manager_id first, then fallback to role-based search
        let manager = null;
        if (dept.manager_id || dept.managerID) {
          manager = allUsers.find(u => u.userID === (dept.manager_id || dept.managerID));
        }
        if (!manager) {
          // Fallback: find manager by department and role
          manager = allUsers.find(u => 
            u.departmentID === dept.departmentID && 
            (u.role === 'ScheduleManager' || u.role === 'Schedule_Manager' || u.role === 'ClientAdmin' || u.role === 'Client_Admin')
          ) || allUsers.find(u => u.departmentID === dept.departmentID);
        }
        
        return {
          ...dept,
          managerID: dept.manager_id || dept.managerID || (manager?.userID || null),
          managerName: manager?.full_name || manager?.fullName || manager?.name || manager?.username || '未指定',
        };
      });

      setDepartments(departmentsWithManagers);
      setUsers(allUsers);
    } catch (err) {
      console.error('[ERROR] Department: Error loading data:', err);
      setError(err.response?.data?.error || err.message || '載入部門資料失敗');
    } finally {
      setLoading(false);
    }
  };

  const toggleModal = (show, dept = null) => {
    if (show && dept) {
      // Edit mode
      setEditingDepartment(dept);
      setFormData({
        departmentID: dept.departmentID,
        departmentName: dept.departmentName || '',
        managerID: dept.managerID || dept.manager_id || '',
        managerName: dept.managerName || '',
        is_active: dept.is_active !== undefined ? dept.is_active : true,
      });
    } else if (show) {
      // Add mode
      setEditingDepartment(null);
      setFormData({
        departmentID: '',
        departmentName: '',
        managerID: '',
        managerName: '',
        is_active: true,
      });
    }
    setIsModalOpen(show);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');

      const saveData = {
        departmentName: formData.departmentName,
        is_active: formData.is_active,
      };

      // Add manager_id if provided
      if (formData.managerID) {
        saveData.manager_id = formData.managerID;
        saveData.managerID = formData.managerID;
      }

      if (editingDepartment) {
        await departmentService.update(editingDepartment.departmentID, saveData);
      } else {
        await departmentService.create(saveData);
      }

      setIsModalOpen(false);
      setEditingDepartment(null);
      await loadData();
    } catch (err) {
      console.error('[ERROR] Department: Error saving:', err);
      setError(err.response?.data?.error || err.message || '儲存部門失敗');
    } finally {
      setSaving(false);
    }
  };

  // Show access denied message
  if (accessDenied) {
    return (
      <div className="bg-gray-100 p-4 md:p-8 min-h-screen flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full">
          <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full mb-4">
            <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 text-center mb-2">存取被拒絕</h2>
          <p className="text-gray-600 text-center mb-6">{error || '需要管理員或排班主管權限才能存取此頁面'}</p>
          <button
            onClick={() => window.history.back()}
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  if (loading && departments.length === 0) {
    return (
      <div className="bg-gray-100 p-4 md:p-8 min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }


  return (
    <div className="bg-gray-100 p-4 md:p-8 font-[Inter,sans-serif]">
      {/* C2.1: 頂部操作列 - Exact match to HTML */}
      <div className="flex flex-col md:flex-row justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">部門管理</h1>
          <p className="mt-1 text-sm text-gray-600">管理貴機構 ({tenantName}) 內的所有部門。</p>
        </div>
        <button
          onClick={() => toggleModal(true)}
          className="mt-4 md:mt-0 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none"
        >
          <svg className="h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
          新增部門
        </button>
      </div>

      {/* Error Message */}
      {error && !accessDenied && (
        <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {typeof error === 'string' ? error : (error?.message || error?.error || String(error) || '發生錯誤')}
        </div>
      )}

      {/* C2.2: 部門列表表格 - Exact match to HTML */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <div className="w-full overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">部門 ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">部門名稱</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">部門主管</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">狀態</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {departments.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-4 text-center text-sm text-gray-500">
                    目前沒有部門資料
                  </td>
                </tr>
              ) : (
                departments.map((dept) => (
                  <tr key={dept.departmentID}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDeptId(dept.departmentID)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {dept.departmentName}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {dept.managerName}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(dept.is_active)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          toggleModal(true, dept);
                        }}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        編輯
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* C2.3: 新增/編輯部門 Modal - Exact match to HTML */}
      <div
        id="department-modal"
        className={isModalOpen ? 'fixed z-10 inset-0 overflow-y-auto' : 'hidden'}
        aria-labelledby="modal-title"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
          {/* Modal 背景遮罩 */}
          <div
            className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
            aria-hidden="true"
            onClick={() => toggleModal(false)}
          ></div>
          {/* 容器：使 Modal 垂直置中 */}
          <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">
            &#8203;
          </span>
          {/* Modal 內容 */}
          <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
            <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
              <div className="sm:flex sm:items-start">
                <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-indigo-100 sm:mx-0 sm:h-10 sm:w-10">
                  <svg
                    className="h-6 w-6 text-indigo-600"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
                    />
                  </svg>
                </div>
                <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    {editingDepartment ? '編輯部門' : '新增部門'}
                  </h3>
                  <div className="mt-4 space-y-4">
                    <div>
                      <label htmlFor="modal-dept-id" className="block text-sm font-medium text-gray-700">
                        部門 ID
                      </label>
                      <input
                        type="text"
                        name="dept-id"
                        id="modal-dept-id"
                        value={formatDeptId(formData.departmentID)}
                        readOnly={!!editingDepartment}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm bg-gray-50"
                        placeholder="DEPT-005"
                      />
                    </div>
                    <div>
                      <label htmlFor="modal-dept-name" className="block text-sm font-medium text-gray-700">
                        部門名稱
                      </label>
                      <input
                        type="text"
                        name="dept-name"
                        id="modal-dept-name"
                        value={formData.departmentName}
                        onChange={(e) => setFormData({ ...formData, departmentName: e.target.value })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        placeholder="請輸入部門名稱"
                        required
                      />
                    </div>
                    <div>
                      <label htmlFor="modal-dept-manager" className="block text-sm font-medium text-gray-700">
                        部門主管
                      </label>
                      <select
                        id="modal-dept-manager"
                        value={formData.managerID}
                        onChange={(e) => {
                          const selectedUserId = e.target.value;
                          const selectedUser = users.find(u => String(u.userID) === String(selectedUserId));
                          setFormData({ 
                            ...formData, 
                            managerID: selectedUserId,
                            managerName: selectedUser ? (selectedUser.full_name || selectedUser.fullName || selectedUser.name || selectedUser.username) : ''
                          });
                        }}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                      >
                        <option value="">請選擇主管</option>
                        {users
                          .filter(u => u.role === 'ScheduleManager' || u.role === 'Schedule_Manager' || u.role === 'ClientAdmin' || u.role === 'Client_Admin')
                          .map((user) => (
                            <option key={user.userID} value={String(user.userID)}>
                              {user.full_name || user.fullName || user.name || user.username}
                            </option>
                          ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">狀態</label>
                      <select
                        id="modal-dept-status"
                        value={formData.is_active ? 'active' : 'inactive'}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.value === 'active' })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                      >
                        <option value="active">啟用</option>
                        <option value="inactive">停用</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            {/* Modal 按鈕 */}
            <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? '儲存中...' : '儲存'}
              </button>
              <button
                type="button"
                onClick={() => toggleModal(false)}
                className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
