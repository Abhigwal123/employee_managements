import { useState, useEffect } from 'react';
import { scheduleService } from '../../services/scheduleService';
import { tenantService } from '../../services/tenantService';
import { departmentService } from '../../services/departmentService';
import LoadingSpinner from '../../components/LoadingSpinner';
import Modal from '../../components/Modal';
import Button from '../../components/Button';
import { normalizeApiError, ensureString } from '../../utils/apiError';

export default function ScheduleListMaintenance() {
  const [schedules, setSchedules] = useState([]);
  const [filteredSchedules, setFilteredSchedules] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedTenant, setSelectedTenant] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [formData, setFormData] = useState({
    tenantID: '',
    departmentID: '',
    scheduleName: '',
    paramsSheetURL: '',
    prefsSheetURL: '',
    resultsSheetURL: '',
    schedulingAPI: '',
    remarks: '',
  });
  const [saving, setSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [runningScheduleId, setRunningScheduleId] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    // Filter schedules
    let filtered = schedules;
    
    if (selectedTenant) {
      filtered = filtered.filter(s => s.tenantID === selectedTenant);
    }
    
    if (selectedDepartment) {
      filtered = filtered.filter(s => s.departmentID === selectedDepartment);
    }
    
    setFilteredSchedules(filtered);
  }, [selectedTenant, selectedDepartment, schedules]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      console.log('[TRACE] Frontend: Loading schedule list data');

      const [schedulesResponse, tenantsResponse, departmentsResponse] = await Promise.all([
        scheduleService.getDefinitions(1, 100),
        tenantService.getAll(1, 100),
        departmentService.getAll(1, 100),
      ]);

      console.log('[TRACE] Frontend: Schedules response:', schedulesResponse);
      console.log('[TRACE] Frontend: Tenants response:', tenantsResponse);
      console.log('[TRACE] Frontend: Departments response:', departmentsResponse);

      const schedulesData = schedulesResponse.items || schedulesResponse.data || [];
      const tenantsData = tenantsResponse.data || [];
      const departmentsData = departmentsResponse.data || [];
      
      console.log('[TRACE] Frontend: Schedules count:', schedulesData.length);
      console.log('[TRACE] Frontend: Tenants count:', tenantsData.length);
      console.log('[TRACE] Frontend: Departments count:', departmentsData.length);
      
      // Map schedules with tenant and department names
      const tenantMap = new Map();
      tenantsData.forEach(t => tenantMap.set(t.tenantID, t.tenantName));
      
      const departmentMap = new Map();
      departmentsData.forEach(d => departmentMap.set(d.departmentID, d.departmentName));

      const schedulesWithNames = schedulesData.map(schedule => ({
        ...schedule,
        tenantName: tenantMap.get(schedule.tenantID) || '未知客戶',
        departmentName: departmentMap.get(schedule.departmentID) || '未知部門',
      }));

      console.log('[TRACE] Frontend: Mapped schedules:', schedulesWithNames.length);
      if (schedulesWithNames.length > 0) {
        console.log('[TRACE] Frontend: First schedule:', schedulesWithNames[0]);
      }

      setSchedules(schedulesWithNames);
      setFilteredSchedules(schedulesWithNames);
      setTenants(tenantsData);
      setDepartments(departmentsData);
    } catch (err) {
      console.error('[TRACE] Frontend: Error loading schedules:', err);
      console.error('[TRACE] Frontend: Error details:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status,
        config: err.config?.url
      });
      
      let errorMsg = '載入班表資料失敗';
      if (err.response?.status === 403) {
        errorMsg = '無權限存取班表資料，請確認您的角色權限';
      } else if (err.response?.status === 401) {
        errorMsg = '登入已過期，請重新登入';
      } else if (!err.response) {
        errorMsg = '無法連接到伺服器，請確認後端服務是否正在運行';
      } else {
        // Use normalizeApiError to ensure we always get a string
        errorMsg = normalizeApiError(err);
      }
      
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingSchedule(null);
    setFormData({
      tenantID: '',
      departmentID: '',
      scheduleName: '',
      paramsSheetURL: '',
      prefsSheetURL: '',
      resultsSheetURL: '',
      schedulingAPI: '',
      remarks: '',
    });
    setIsModalOpen(true);
  };

  const handleEdit = (schedule) => {
    setEditingSchedule(schedule);
    setFormData({
      tenantID: schedule.tenantID || '',
      departmentID: schedule.departmentID || '',
      scheduleName: schedule.scheduleName || '',
      paramsSheetURL: schedule.paramsSheetURL || '',
      prefsSheetURL: schedule.prefsSheetURL || '',
      resultsSheetURL: schedule.resultsSheetURL || '',
      schedulingAPI: schedule.schedulingAPI || '',
      remarks: schedule.remarks || '',
    });
    setIsModalOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    
    try {
      setSaving(true);
      setError('');
      setSuccessMessage('');

      if (!formData.tenantID || !formData.departmentID || !formData.scheduleName) {
        setError('請填寫所有必要欄位');
        setSaving(false);
        return;
      }

      const saveData = {
        tenantID: formData.tenantID,
        departmentID: formData.departmentID,
        scheduleName: formData.scheduleName,
        paramsSheetURL: formData.paramsSheetURL,
        prefsSheetURL: formData.prefsSheetURL,
        resultsSheetURL: formData.resultsSheetURL,
        schedulingAPI: formData.schedulingAPI,
        remarks: formData.remarks,
      };

      if (editingSchedule) {
        await scheduleService.updateDefinition(editingSchedule.scheduleDefID, saveData);
        setSuccessMessage('班表已成功更新');
      } else {
        await scheduleService.createDefinition(saveData);
        setSuccessMessage('班表已成功新增');
      }

      setIsModalOpen(false);
      await loadData();
      
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      setError(normalizeApiError(err) || '儲存班表失敗');
      console.error('Error saving schedule:', err);
    } finally {
      setSaving(false);
    }
  };

  // Get departments for selected tenant
  const getDepartmentsForTenant = () => {
    if (!selectedTenant) return departments;
    return departments.filter(d => d.tenantID === selectedTenant);
  };

  const handleRunSchedule = async (schedule) => {
    try {
      setRunningScheduleId(schedule.scheduleDefID);
      setError('');
      setSuccessMessage('');

      console.log('[TRACE] Frontend: Running schedule:', schedule.scheduleDefID);

      const response = await scheduleService.runJob({
        scheduleDefID: schedule.scheduleDefID,
      });

      // Get the job log ID from the response
      const jobLogId = response.data?.logID || response.data?.jobLogID || response.data?.log_id;
      
      if (jobLogId) {
        // Poll the job status for a few seconds to check if it fails quickly
        // This catches errors that happen during execution (e.g., "Error loading input data")
        let pollCount = 0;
        const maxPolls = 10; // Poll for up to 5 seconds (10 * 500ms)
        const pollInterval = 500; // Check every 500ms
        
        const checkJobStatus = async () => {
          try {
            const jobLogResponse = await scheduleService.getJobLogById(jobLogId);
            const jobLog = jobLogResponse.data || jobLogResponse;
            const status = jobLog.status;
            const errorMessage = jobLog.error_message || jobLog.errorMessage;
            
            console.log('[TRACE] Frontend: Job status check:', { status, errorMessage, pollCount });
            
            if (status === 'failed') {
              // Job failed - show the actual error message
              let errorMsg = errorMessage || '排班作業執行失敗';
              // Extract the actual error if it's in a specific format
              if (errorMessage) {
                // Clean up error message - remove system prefixes and timestamps if present
                let cleanError = errorMessage;
                // Remove common prefixes like "[System] 'system' " or similar
                cleanError = cleanError.replace(/^\[System\]\s*['"]?system['"]?\s*/i, '');
                // Remove trailing timestamps like "5 小時前" or similar patterns
                cleanError = cleanError.replace(/\s*\d+\s*(小時前|分鐘前|秒前|hours? ago|minutes? ago|seconds? ago).*$/i, '');
                
                if (cleanError.includes('Error loading input data')) {
                  errorMsg = `載入輸入資料時發生錯誤: ${cleanError}`;
                } else {
                  errorMsg = cleanError;
                }
              }
              setError(errorMsg);
              setTimeout(() => setError(''), 10000); // Show error for 10 seconds
              setSuccessMessage(''); // Clear any success message
              return true; // Stop polling
            } else if (status === 'completed' || status === 'success') {
              // Job completed successfully
              setSuccessMessage(`班表 "${schedule.scheduleName}" 排班作業已完成`);
              setTimeout(() => setSuccessMessage(''), 5000);
              return true; // Stop polling
            } else if (status === 'running' || status === 'pending') {
              // Job is still running - continue polling
              if (pollCount < maxPolls) {
                pollCount++;
                setTimeout(checkJobStatus, pollInterval);
              } else {
                // Max polls reached, show that job was started
                setSuccessMessage(`班表 "${schedule.scheduleName}" 排班作業已啟動（執行中）`);
                setTimeout(() => setSuccessMessage(''), 5000);
              }
              return false; // Continue polling
            }
          } catch (pollErr) {
            console.error('[TRACE] Frontend: Error polling job status:', pollErr);
            // If polling fails, just show the start message
            setSuccessMessage(`班表 "${schedule.scheduleName}" 排班作業已啟動`);
            setTimeout(() => setSuccessMessage(''), 5000);
            return true; // Stop polling on error
          }
        };
        
        // Start polling after a short delay
        setTimeout(checkJobStatus, pollInterval);
      } else {
        // No job log ID - just show start message
        setSuccessMessage(`班表 "${schedule.scheduleName}" 排班作業已啟動`);
        setTimeout(() => setSuccessMessage(''), 5000);
      }
    } catch (err) {
      console.error('[TRACE] Frontend: Error running schedule:', err);
      let errorMsg = '啟動排班作業失敗';
      if (err.response?.status === 403) {
        errorMsg = '無權限執行此排班作業';
      } else if (err.response?.status === 404) {
        errorMsg = '找不到指定的班表';
      } else if (err.response?.data?.error) {
        errorMsg = err.response.data.error;
      } else if (err.response?.data?.details) {
        errorMsg = err.response.data.details;
      }
      setError(errorMsg);
      setTimeout(() => setError(''), 10000); // Show error for 10 seconds
    } finally {
      setRunningScheduleId(null);
    }
  };

  if (loading && schedules.length === 0) {
    return <LoadingSpinner />;
  }

  return (
    <div className="bg-gray-100 p-4 md:p-8">
      {/* B3.1: 頂部操作列 */}
      <div className="flex flex-col md:flex-row justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">班表清單維護</h1>
        <div className="flex flex-wrap items-center gap-2 mt-4 md:mt-0">
          {/* 篩選器 */}
          <select
            value={selectedTenant}
            onChange={(e) => {
              setSelectedTenant(e.target.value);
              setSelectedDepartment(''); // Reset department when tenant changes
            }}
            className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          >
            <option value="">所有客戶機構</option>
            {tenants.map((tenant) => (
              <option key={tenant.tenantID} value={tenant.tenantID}>
                {tenant.tenantName}
              </option>
            ))}
          </select>
          <select
            value={selectedDepartment}
            onChange={(e) => setSelectedDepartment(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          >
            <option value="">所有部門</option>
            {getDepartmentsForTenant().map((dept) => (
              <option key={dept.departmentID} value={dept.departmentID}>
                {dept.departmentName}
              </option>
            ))}
          </select>
          {/* 新增按鈕 */}
          <button
            onClick={handleCreate}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none"
          >
            <svg className="h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
            新增班表
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {ensureString(error)}
        </div>
      )}

      {successMessage && (
        <div className="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
          {successMessage}
        </div>
      )}

      {/* B3.2: 班表列表 (Table) */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  客戶名稱
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  部門
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  班表名稱
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  排班參數表
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  員工預排班表
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  排班結果及分析表
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  AI排班服務API
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredSchedules.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-6 py-4 text-center text-sm text-gray-500">
                    目前無班表資料
                  </td>
                </tr>
              ) : (
                filteredSchedules.map((schedule) => (
                  <tr key={schedule.scheduleDefID} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {schedule.tenantName}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {schedule.departmentName}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {schedule.scheduleName}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <a
                        href={schedule.paramsSheetURL || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900 text-sm"
                      >
                        開啟
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <a
                        href={schedule.prefsSheetURL || schedule.paramsSheetURL || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900 text-sm"
                      >
                        開啟
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <a
                        href={schedule.resultsSheetURL || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900 text-sm"
                      >
                        開啟
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 truncate max-w-xs" title={schedule.schedulingAPI}>
                      {schedule.schedulingAPI || '--'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
                      <div className="flex items-center justify-center gap-3">
                        <button
                          onClick={() => handleRunSchedule(schedule)}
                          disabled={runningScheduleId === schedule.scheduleDefID}
                          className={`inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md shadow-sm text-white ${
                            runningScheduleId === schedule.scheduleDefID
                              ? 'bg-gray-400 cursor-not-allowed'
                              : 'bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500'
                          }`}
                        >
                          {runningScheduleId === schedule.scheduleDefID ? (
                            <>
                              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              執行中...
                            </>
                          ) : (
                            'Run'
                          )}
                        </button>
                        <button
                          onClick={() => handleEdit(schedule)}
                          className="edit-schedule-btn text-indigo-600 hover:text-indigo-900"
                        >
                          編輯
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* B3.3: 新增/編輯 Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingSchedule(null);
        }}
        title=""
        size="xl"
      >
        <form id="schedule-form" onSubmit={handleSave}>
          {/* Modal 標題 */}
          <div className="flex justify-between items-center p-5 border-b rounded-t">
            <h3 className="text-xl font-semibold text-gray-900">
              {editingSchedule ? '編輯班表' : '新增班表'}
            </h3>
            <button
              type="button"
              onClick={() => {
                setIsModalOpen(false);
                setEditingSchedule(null);
              }}
              className="close-schedule-modal-btn text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm p-1.5 ml-auto inline-flex items-center"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>

          {/* Modal 表單內容 */}
          <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="sched-tenant" className="block mb-2 text-sm font-medium text-gray-900">
                  客戶名稱*
                </label>
                <select
                  id="sched-tenant"
                  value={formData.tenantID}
                  onChange={(e) => {
                    setFormData({ ...formData, tenantID: e.target.value, departmentID: '' });
                  }}
                  className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                  required
                >
                  <option value="" disabled>請選擇客戶</option>
                  {tenants.map((tenant) => (
                    <option key={tenant.tenantID} value={tenant.tenantID}>
                      {tenant.tenantName}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="sched-department" className="block mb-2 text-sm font-medium text-gray-900">
                  部門*
                </label>
                <select
                  id="sched-department"
                  value={formData.departmentID}
                  onChange={(e) => setFormData({ ...formData, departmentID: e.target.value })}
                  className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                  required
                  disabled={!formData.tenantID}
                >
                  <option value="" disabled>請先選擇客戶</option>
                  {departments
                    .filter(d => !formData.tenantID || d.tenantID === formData.tenantID)
                    .map((dept) => (
                      <option key={dept.departmentID} value={dept.departmentID}>
                        {dept.departmentName}
                      </option>
                    ))}
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="sched-name" className="block mb-2 text-sm font-medium text-gray-900">
                班表名稱*
              </label>
              <input
                type="text"
                id="sched-name"
                value={formData.scheduleName}
                onChange={(e) => setFormData({ ...formData, scheduleName: e.target.value })}
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                placeholder="例如: 急診護理站班表"
                required
              />
            </div>
            <div>
              <label htmlFor="sched-url-params" className="block mb-2 text-sm font-medium text-gray-900">
                GoogleSheet排班參數表URL*
              </label>
              <input
                type="url"
                id="sched-url-params"
                value={formData.paramsSheetURL}
                onChange={(e) => setFormData({ ...formData, paramsSheetURL: e.target.value })}
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                placeholder="https://docs.google.com/spreadsheets/d/..."
                required
              />
            </div>
            <div>
              <label htmlFor="sched-url-pre" className="block mb-2 text-sm font-medium text-gray-900">
                GoogleSheet員工預排班表URL*
              </label>
              <input
                type="url"
                id="sched-url-pre"
                value={formData.prefsSheetURL}
                onChange={(e) => setFormData({ ...formData, prefsSheetURL: e.target.value })}
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                placeholder="https://docs.google.com/spreadsheets/d/..."
                required
              />
            </div>
            <div>
              <label htmlFor="sched-url-result" className="block mb-2 text-sm font-medium text-gray-900">
                GoogleSheet排班結果及分析表URL*
              </label>
              <input
                type="url"
                id="sched-url-result"
                value={formData.resultsSheetURL}
                onChange={(e) => setFormData({ ...formData, resultsSheetURL: e.target.value })}
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                placeholder="https://docs.google.com/spreadsheets/d/..."
                required
              />
            </div>
            <div>
              <label htmlFor="sched-api" className="block mb-2 text-sm font-medium text-gray-900">
                AI排班服務API*
              </label>
              <input
                type="url"
                id="sched-api"
                value={formData.schedulingAPI}
                onChange={(e) => setFormData({ ...formData, schedulingAPI: e.target.value })}
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                placeholder="https://api.sched.com/v1/..."
                required
              />
            </div>
            <div>
              <label htmlFor="sched-remarks" className="block mb-2 text-sm font-medium text-gray-900">
                備註
              </label>
              <textarea
                id="sched-remarks"
                rows="3"
                value={formData.remarks}
                onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
                className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2.5"
                placeholder="內部備註..."
              />
            </div>
          </div>

          {/* Modal 尾部 (按鈕) */}
          <div className="flex items-center p-6 space-x-2 border-t border-gray-200 rounded-b">
            <Button type="submit" loading={saving}>
              儲存
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsModalOpen(false);
                setEditingSchedule(null);
              }}
            >
              取消
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
