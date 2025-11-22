import React, { useEffect, useState } from "react";
import api from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import LoadingSpinner from "../../components/LoadingSpinner";

export default function PermissionMatrix() {
  const { user } = useAuth();
  const [matrix, setMatrix] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [updated, setUpdated] = useState({});

  const canEdit = user?.role === "SysAdmin" || user?.role === "SysAdmin" || 
                  user?.role === "ClientAdmin" || user?.role === "admin";

  useEffect(() => {
    fetchPermissions();
  }, []);

  async function fetchPermissions() {
    try {
      setLoading(true);
      setError('');
      console.log('[TRACE] PermissionMatrix: Fetching permissions matrix...');
      const res = await api.get("/permissions/matrix");
      const fullUrl = res.config.baseURL + res.config.url;
      console.log(`[TRACE] ✅ GET ${fullUrl} ${res.status} OK`);
      console.log('[TRACE] PermissionMatrix: Response received:', res.status, res.data);
      // Backend returns array directly, not wrapped in {permissions: [...]}
      setMatrix(Array.isArray(res.data) ? res.data : (res.data?.permissions || []));
      const matrixData = Array.isArray(res.data) ? res.data : (res.data?.permissions || []);
      if (matrixData.length === 0) {
        console.log('[INFO] PermissionMatrix: No schedule managers found');
      } else {
        console.log(`[TRACE] PermissionMatrix: Loaded successfully - ${matrixData.length} managers found`);
      }
    } catch (err) {
      console.error("[ERROR] PermissionMatrix: Failed to load permissions:", err);
      console.error("[ERROR] PermissionMatrix: Error details:", {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status,
        config: err.config
      });
      
      let errorMsg = '載入權限資料失敗';
      if (err.response) {
        errorMsg = err.response.data?.error || err.response.data?.details || errorMsg;
        if (err.response.status === 401) {
          errorMsg = '登入已過期，請重新登入';
        } else if (err.response.status === 403) {
          errorMsg = '權限不足，無法載入資料';
        }
      } else if (err.message) {
        if (err.message.includes('Network Error') || err.message.includes('timeout')) {
          errorMsg = '網路連線錯誤，請檢查網路連線或稍後再試';
        } else {
          errorMsg = err.message;
        }
      }
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }

  function togglePermission(userIndex, key) {
    if (!canEdit) return; // read-only for others
    
    setMatrix((prev) =>
      prev.map((row, i) =>
        i === userIndex
          ? {
              ...row,
              permissions: {
                ...row.permissions,
                [key]: !row.permissions[key],
              },
            }
          : row
      )
    );
    setUpdated((prev) => ({ ...prev, [userIndex]: true }));
    setSuccessMessage(''); // Clear success message when changes are made
  }

  async function saveChanges() {
    if (!canEdit) return;
    
    const changedRows = matrix.filter((_, i) => updated[i]);
    if (changedRows.length === 0) {
      setSuccessMessage('沒有變更需要儲存');
      return;
    }
    
    try {
      setSaving(true);
      setError('');
      setSuccessMessage('');
      
      for (const row of changedRows) {
        await api.put("/permissions/update", {
          user_id: row.user_id,
          permissions: row.permissions,
        });
      }
      
      setSuccessMessage('✅ 儲存變更成功！所有權限已更新。');
      setUpdated({});
      
      // Reload data to ensure sync
      await fetchPermissions();
      
      // Log success
      console.log('[SUCCESS] PermissionMatrix: All permissions saved successfully');
    } catch (err) {
      console.error("[ERROR] PermissionMatrix: Failed to save permissions:", err);
      console.error("[ERROR] PermissionMatrix: Error details:", {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status,
        config: err.config
      });
      
      let errorMsg = '儲存失敗，請稍後再試';
      if (err.response) {
        errorMsg = err.response.data?.error || err.response.data?.details || errorMsg;
        if (err.response.status === 401) {
          errorMsg = '登入已過期，請重新登入';
        } else if (err.response.status === 403) {
          errorMsg = '權限不足，無法儲存變更。請確認您有管理權限。';
        }
      } else if (err.message) {
        if (err.message.includes('Network Error') || err.message.includes('timeout')) {
          errorMsg = '網路連線錯誤，請檢查網路連線或稍後再試';
        } else {
          errorMsg = err.message;
        }
      }
      setError(errorMsg);
    } finally {
      setSaving(false);
    }
  }

  // Define schedule headers in order
  const scheduleHeaders = [
    { key: 'ER', label: '急診護理站班表' },
    { key: 'OPD', label: '門診護理站班表' },
    { key: 'F6', label: '六樓護理站班表' },
    { key: 'F7', label: '七樓護理站班表' },
    { key: 'F8', label: '八樓護理站班表' },
  ];

  if (loading) {
    return (
      <div className="bg-[#FAFAFA] min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="bg-[#FAFAFA] min-h-screen">
      {/* Page Title - Exact match to Gemini C4 spec */}
      <div className="pt-4 pl-6">
        <h1 className="text-[20px] font-bold text-[#1E1E1E]" style={{ fontFamily: "'Noto Sans TC', sans-serif" }}>
          使用者帳號排班權限維護
        </h1>
      </div>

      {/* C4.1: 頂部操作列 - Exact match to HTML */}
      <div className="flex flex-col md:flex-row justify-between items-center mb-6 px-6 pt-4">
        <div>
          <p className="text-sm text-[#333333]">請勾選允許「排班主管」存取及執行「班表」的權限。</p>
        </div>
        {canEdit && (
          <button
            onClick={saveChanges}
            disabled={saving || Object.keys(updated).length === 0}
            className="mt-4 md:mt-0 inline-flex items-center px-4 py-2 border border-transparent text-sm font-semibold rounded-md shadow-sm text-white bg-[#1E88E5] hover:bg-[#1565C0] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            style={{ width: '160px', justifyContent: 'center' }}
            aria-label="儲存權限變更"
            aria-busy={saving}
          >
            <svg
              className="h-5 w-5 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            {saving ? '儲存中...' : '💾 儲存變更'}
          </button>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 mx-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {typeof error === 'string' ? error : (error?.message || error?.error || String(error) || '發生錯誤')}
        </div>
      )}

      {/* Success Message */}
      {successMessage && (
        <div className="mb-4 mx-6 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
          {successMessage}
        </div>
      )}

      {/* C4.2: 權限矩陣表格 - Exact match to Gemini C4 spec */}
      <div className="px-6 pb-6">
        <div className="w-full overflow-x-auto rounded-xl shadow-lg">
          <div className="bg-white rounded-xl overflow-hidden min-w-[800px]">
            <table className="min-w-full divide-y divide-[#E5E5E5]">
              <thead className="bg-[#F1F1F1]">
                <tr>
                  <th 
                    className="sticky left-0 z-10 bg-[#F1F1F1] px-6 py-3 text-left text-xs font-bold text-[#333333] uppercase tracking-wider border-r border-[#E5E5E5]"
                    style={{ position: 'sticky', left: 0 }}
                  >
                    排班主管 (使用者)
                  </th>
                  {scheduleHeaders.map((header) => (
                    <th
                      key={header.key}
                      className="px-6 py-3 text-center text-xs font-bold text-[#333333] uppercase tracking-wider"
                    >
                      {header.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-[#E5E5E5]">
                {matrix.length === 0 ? (
                  <tr>
                    <td
                      colSpan={scheduleHeaders.length + 1}
                      className="px-6 py-8 text-center text-sm text-[#B0BEC5]"
                    >
                      目前沒有排班主管
                    </td>
                  </tr>
                ) : (
                  matrix.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50 transition-colors">
                      <td 
                        className="sticky left-0 z-5 bg-white px-6 py-4 whitespace-nowrap border-r border-[#E5E5E5]"
                        style={{ position: 'sticky', left: 0 }}
                      >
                        <div className="text-sm font-bold text-[#333333]">{row.user}</div>
                        <div className="text-sm text-[#B0BEC5] mt-1">{row.department}</div>
                      </td>
                      {scheduleHeaders.map((header) => (
                        <td
                          key={header.key}
                          className="px-6 py-4 whitespace-nowrap text-center"
                        >
                          <input
                            type="checkbox"
                            className="h-5 w-5 text-[#1E88E5] border-[#E5E5E5] rounded focus:ring-[#1E88E5] focus:ring-2 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                            checked={row.permissions[header.key] || false}
                            disabled={!canEdit}
                            onChange={() => togglePermission(idx, header.key)}
                            aria-label={`${row.user} - ${header.label} 權限`}
                            aria-checked={row.permissions[header.key] || false}
                          />
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Role-based access message for non-editable roles */}
      {!canEdit && (
        <div className="mx-6 mt-4 p-4 bg-gray-100 border border-gray-300 rounded-md">
          <p className="text-sm text-[#B0BEC5] text-center">
            {user?.role === 'ScheduleManager' || user?.role === 'Schedule_Manager' 
              ? '排班主管無法修改權限設定' 
              : user?.role === 'Employee' || user?.role === 'Department_Employee' || user?.role === 'employee'
              ? '員工無權限修改權限設定'
              : '無權限修改權限設定'}
          </p>
        </div>
      )}
    </div>
  );
}


