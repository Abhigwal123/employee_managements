import React, { useEffect, useState } from 'react';
import { scheduleService } from '../../services/scheduleService';
import { userService } from '../../services/userService';
import { useAuth } from '../../context/AuthContext';
import LoadingSpinner from '../../components/LoadingSpinner';

const PermissionMaintenance = () => {
  const [permissionsData, setPermissionsData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [scheduleHeaders, setScheduleHeaders] = useState([]);
  const [scheduleMap, setScheduleMap] = useState(new Map()); // Map<scheduleName, scheduleDefID>
  const [existingPermissionsMap, setExistingPermissionsMap] = useState(new Map()); // Map<`${userID}_${scheduleDefID}`, permission>
  const { user } = useAuth();
  const role = user?.role || '';

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError('');
      setSuccessMessage('');

      console.log('[TRACE] PermissionMaintenance: Loading data...');

      // Load users, schedules, and permissions
      const [userResponse, scheduleResponse, permissionResponse] = await Promise.all([
        userService.getAll(1, 1000),
        scheduleService.getDefinitions(1, 1000, { active: 'true' }),
        scheduleService.getPermissions(1, 1000),
      ]);

      console.log('[TRACE] PermissionMaintenance: Responses:', {
        userResponse,
        scheduleResponse,
        permissionResponse,
      });

      // Handle different response structures
      const allUsers = userResponse?.data || userResponse?.items || userResponse || [];
      const allSchedules = scheduleResponse?.items || scheduleResponse?.data || scheduleResponse || [];
      const allPermissions = permissionResponse?.data || permissionResponse?.items || permissionResponse || [];

      // Extract schedule headers dynamically from active schedules
      const activeScheduleNames = allSchedules
        .filter(s => s.is_active !== false && s.scheduleName)
        .map(s => s.scheduleName)
        .sort(); // Sort for consistent ordering
      
      setScheduleHeaders(activeScheduleNames);
      
      // Build schedule name to ID map for quick lookup
      const nameToIdMap = new Map();
      allSchedules.forEach(schedule => {
        if (schedule.scheduleName && schedule.scheduleDefID) {
          nameToIdMap.set(schedule.scheduleName, schedule.scheduleDefID);
        }
      });
      setScheduleMap(nameToIdMap);

      console.log('[TRACE] PermissionMaintenance: Data counts:', {
        users: allUsers.length,
        schedules: allSchedules.length,
        permissions: allPermissions.length,
      });

      // Filter users who can be schedule managers
      const usersWithPermissions = new Set();
      allPermissions.forEach(perm => {
        if (perm.userID) {
          usersWithPermissions.add(perm.userID);
        }
      });

      // Filter users who can be schedule managers or have permissions
      // Include: ScheduleManager, ClientAdmin (who can manage permissions), and users with existing permissions
      const managers = allUsers.filter(u => {
        // Include ScheduleManager role users
        if (u.role === 'ScheduleManager' || 
            u.role === 'Schedule_Manager' ||
            (u.roles && Array.isArray(u.roles) && u.roles.includes('ScheduleManager'))) {
          return true;
        }
        // Include users who already have permissions (they should be visible)
        if (usersWithPermissions.has(u.userID)) {
          return true;
        }
        // Include ClientAdmin (they can manage permissions)
        if (u.role === 'ClientAdmin' || u.role === 'Client_Admin') {
          return true;
        }
        // Include ClientAdmin (they can manage permissions)
        if (u.role === 'ClientAdmin' || u.role === 'admin') {
          return true;
        }
        return false;
      });

      // Use filtered managers, or if empty, show all active users (for initial setup)
      const displayUsers = managers.length > 0 ? managers : allUsers.filter(u => u.status === 'active');

      // Build permission map: Map<`${userID}_${scheduleDefID}`, permission>
      // Use scheduleDefID for more reliable matching
      const permissionMap = new Map();
      allPermissions.forEach(perm => {
        // Check if permission is active (is_active !== false means active)
        if (perm.is_active !== false && (perm.canRunJob || perm.can_view || perm.canView)) {
          const key = `${perm.userID}_${perm.scheduleDefID}`;
          permissionMap.set(key, perm);
        }
      });
      
      // Store existing permissions map for quick lookup during updates
      setExistingPermissionsMap(permissionMap);

      // Transform to match the expected format
      const transformedData = displayUsers.map(user => {
        const userPermissions = {};
        // Use activeScheduleNames if scheduleHeaders state hasn't updated yet
        const headersToUse = activeScheduleNames.length > 0 ? activeScheduleNames : scheduleHeaders;
        headersToUse.forEach(header => {
          // Check if this user has permission for this schedule using scheduleDefID
          const schedule = allSchedules.find(s => s.scheduleName === header);
          if (schedule) {
            const key = `${user.userID}_${schedule.scheduleDefID}`;
            userPermissions[header] = permissionMap.has(key);
          } else {
            userPermissions[header] = false;
          }
        });

        return {
          id: user.userID,
          userID: user.userID,
          name: getUserDisplayName(user),
          username: user.username,
          department: getUserDepartment(user),
          permissions: userPermissions,
          // Store original data for API calls
          _original: user,
        };
      });

      console.log('[TRACE] PermissionMaintenance: Transformed data:', transformedData);
      setPermissionsData(transformedData);
    } catch (err) {
      console.error('[ERROR] PermissionMaintenance: Error loading data:', err);
      
      // Provide more detailed error message
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
      setPermissionsData([]);
    } finally {
      setLoading(false);
    }
  };

  const getUserDepartment = (user) => {
    return user.departmentName || 
           user.department?.departmentName || 
           user.department?.name ||
           user.department_name ||
           '未指定';
  };

  const getUserDisplayName = (user) => {
    const name = user.full_name || 
                 user.fullName || 
                 user.name || 
                 user.username || 
                 '未命名使用者';
    const username = user.username || '';
    return username ? `${name} (${username})` : name;
  };

  const handleCheckboxChange = async (userId, scheduleName, event) => {
    const canEdit = role === 'ClientAdmin' || role === 'Client_Admin' || role === 'ClientAdmin' || role === 'admin';
    if (!canEdit) return;

    // Get the user and schedule IDs
    const userData = permissionsData.find(u => u.id === userId);
    if (!userData) return;

    const scheduleDefID = scheduleMap.get(scheduleName);
    if (!scheduleDefID) {
      console.error(`[ERROR] Schedule ID not found for: ${scheduleName}`);
      setError(`找不到班表 ID: ${scheduleName}`);
      return;
    }

    const newCheckedState = !userData.permissions[scheduleName];
    const permissionKey = `${userData.userID}_${scheduleDefID}`;
    const existingPermission = existingPermissionsMap.get(permissionKey);

    // Optimistic update - update UI immediately
    const updated = permissionsData.map((user) =>
      user.id === userId
        ? {
            ...user,
            permissions: {
              ...user.permissions,
              [scheduleName]: newCheckedState,
            },
          }
        : user
    );
    setPermissionsData(updated);
    setSuccessMessage(''); // Clear success message when changes are made
    setError(''); // Clear any previous errors

    // Immediately save to database
    try {
      if (newCheckedState) {
        // Checkbox checked - enable permission
        if (existingPermission) {
          // Update existing permission
          const permissionId = existingPermission.permissionID || existingPermission.id;
          await scheduleService.updatePermission(permissionId, {
            canRunJob: true,
            can_view: true,
            canView: true,
            is_active: true,
          });
          
          // Update existing permissions map
          const updatedPerm = { ...existingPermission, is_active: true, canRunJob: true };
          setExistingPermissionsMap(prev => {
            const newMap = new Map(prev);
            newMap.set(permissionKey, updatedPerm);
            return newMap;
          });
        } else {
          // Create new permission
          const newPermission = await scheduleService.createPermission({
            userID: userData.userID,
            scheduleDefID: scheduleDefID,
            canRunJob: true,
            can_view: true,
            canView: true,
            is_active: true,
          });
          
          // Add to existing permissions map
          const permData = newPermission?.data || newPermission;
          if (permData) {
            setExistingPermissionsMap(prev => {
              const newMap = new Map(prev);
              newMap.set(permissionKey, {
                permissionID: permData.permissionID || permData.id,
                userID: userData.userID,
                scheduleDefID: scheduleDefID,
                is_active: true,
                canRunJob: true,
              });
              return newMap;
            });
          }
        }
      } else {
        // Checkbox unchecked - disable permission
        if (existingPermission) {
          const permissionId = existingPermission.permissionID || existingPermission.id;
          await scheduleService.updatePermission(permissionId, {
            canRunJob: false,
            can_view: false,
            canView: false,
            is_active: false,
          });
          
          // Update existing permissions map
          const updatedPerm = { ...existingPermission, is_active: false, canRunJob: false };
          setExistingPermissionsMap(prev => {
            const newMap = new Map(prev);
            newMap.set(permissionKey, updatedPerm);
            return newMap;
          });
        }
      }
      
      console.log('[TRACE] PermissionMaintenance: Permission updated successfully', {
        userId: userData.userID,
        scheduleName,
        scheduleDefID,
        checked: newCheckedState,
      });
    } catch (err) {
      console.error('[ERROR] PermissionMaintenance: Error updating permission:', err);
      
      // Revert optimistic update on error
      const reverted = permissionsData.map((user) =>
        user.id === userId
          ? {
              ...user,
              permissions: {
                ...user.permissions,
                [scheduleName]: !newCheckedState, // Revert to previous state
              },
            }
          : user
      );
      setPermissionsData(reverted);
      
      // Provide more detailed error message
      let errorMsg = '更新權限失敗，請稍後再試';
      if (err.response) {
        errorMsg = err.response.data?.error || err.response.data?.details || errorMsg;
      } else if (err.message) {
        if (err.message.includes('Network Error') || err.message.includes('timeout')) {
          errorMsg = '網路連線錯誤，請檢查網路連線或稍後再試';
        } else {
          errorMsg = err.message;
        }
      }
      setError(errorMsg);
    }
  };

  const handleSave = async () => {
    const canEdit = role === 'ClientAdmin' || role === 'Client_Admin' || role === 'ClientAdmin' || role === 'admin';
    if (!canEdit) return;

    try {
      setSaving(true);
      setError('');
      setSuccessMessage('');

      console.log('[TRACE] PermissionMaintenance: Validating and syncing all permissions...');

      // Get all schedules to map schedule names to IDs
      const scheduleResponse = await scheduleService.getDefinitions(1, 1000, { active: 'true' });
      const allSchedules = scheduleResponse?.items || scheduleResponse?.data || scheduleResponse || [];

      // Create a map of schedule name to schedule ID
      const scheduleNameToId = new Map();
      allSchedules.forEach(schedule => {
        if (schedule.scheduleName) {
          scheduleNameToId.set(schedule.scheduleName, schedule.scheduleDefID);
        }
      });

      // Get active schedule names for iteration (use state if available, otherwise derive from API)
      let activeScheduleNames = scheduleHeaders.length > 0 
        ? scheduleHeaders 
        : allSchedules
            .filter(s => s.is_active !== false && s.scheduleName)
            .map(s => s.scheduleName)
            .sort();

      // Get all existing permissions
      const permissionResponse = await scheduleService.getPermissions(1, 1000);
      const allExistingPerms = permissionResponse?.data || permissionResponse?.items || permissionResponse || [];
      
      const existingPermMap = new Map();
      allExistingPerms.forEach(perm => {
        const key = `${perm.userID}_${perm.scheduleDefID}`;
        existingPermMap.set(key, perm);
      });

      // Collect all permission operations
      const permissionOperations = [];

      // Process each user's permissions
      permissionsData.forEach(user => {
        activeScheduleNames.forEach(scheduleName => {
          const scheduleDefID = scheduleNameToId.get(scheduleName);
          if (!scheduleDefID) {
            console.warn(`[WARN] Schedule not found: ${scheduleName}`);
            return;
          }

          const hasPermission = user.permissions[scheduleName] || false;
          const key = `${user.userID}_${scheduleDefID}`;
          const existing = existingPermMap.get(key);

          if (hasPermission) {
            // Permission should be active
            if (existing) {
              // Update existing permission
              if (existing.permissionID || existing.id) {
                permissionOperations.push(
                  scheduleService.updatePermission(existing.permissionID || existing.id, {
                    canRunJob: true,
                    can_view: true,
                    canView: true,
                    is_active: true,
                  }).catch(err => {
                    console.error(`[ERROR] Failed to update permission ${existing.permissionID}:`, err);
                    throw err;
                  })
                );
              }
            } else {
              // Create new permission
              permissionOperations.push(
                scheduleService.createPermission({
                  userID: user.userID,
                  scheduleDefID: scheduleDefID,
                  canRunJob: true,
                  can_view: true,
                  canView: true,
                  is_active: true,
                }).catch(err => {
                  console.error(`[ERROR] Failed to create permission for ${key}:`, err);
                  if (err.response?.status === 409 || err.response?.status === 400) {
                    // Try to find and update
                    return scheduleService.getPermissions(1, 1000, {
                      user_id: user.userID,
                      schedule_def_id: scheduleDefID,
                    }).then(response => {
                      const existingPerms = response.data || response.items || [];
                      const found = existingPerms.find(p => 
                        p.userID === user.userID && p.scheduleDefID === scheduleDefID
                      );
                      if (found && (found.permissionID || found.id)) {
                        return scheduleService.updatePermission(found.permissionID || found.id, {
                          canRunJob: true,
                          can_view: true,
                          canView: true,
                          is_active: true,
                        });
                      }
                      throw err;
                    });
                  }
                  throw err;
                })
              );
            }
          } else {
            // Permission should be inactive
            if (existing && existing.is_active !== false) {
              // Deactivate permission
              if (existing.permissionID || existing.id) {
                permissionOperations.push(
                  scheduleService.updatePermission(existing.permissionID || existing.id, {
                    canRunJob: false,
                    can_view: false,
                    canView: false,
                    is_active: false,
                  }).catch(err => {
                    console.error(`[ERROR] Failed to deactivate permission ${existing.permissionID}:`, err);
                    // Don't throw - continue with other operations
                  })
                );
              }
            }
          }
        });
      });

      // Execute all operations
      await Promise.all(permissionOperations);

      console.log('[TRACE] PermissionMaintenance: All permissions saved successfully');
      setSuccessMessage('✅ 所有權限已同步！變更已立即反映在儀表板。');

      // Reload data to reflect changes and ensure dashboard sync
      await fetchData();
      
      // Show toast notification (if available) or use browser notification
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('權限已更新', {
          body: '排班權限已成功儲存並同步至儀表板',
          icon: '/favicon.ico',
        });
      }
    } catch (err) {
      console.error('[ERROR] PermissionMaintenance: Error saving permissions:', err);
      
      // Provide more detailed error message
      let errorMsg = '❌ 儲存失敗，請稍後再試！';
      if (err.response) {
        errorMsg = err.response.data?.error || err.response.data?.details || errorMsg;
        if (err.response.status === 403) {
          errorMsg = '權限不足，無法儲存變更。請確認您有管理權限。';
        } else if (err.response.status === 401) {
          errorMsg = '登入已過期，請重新登入。';
        }
      } else if (err.message) {
        if (err.message.includes('Network Error') || err.message.includes('timeout')) {
          errorMsg = '❌ 網路連線錯誤，請檢查網路連線或稍後再試！';
        } else {
          errorMsg = err.message;
        }
      }
      setError(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  if (loading && permissionsData.length === 0) {
    return (
      <div className="bg-[#FAFAFA] min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  // Check if user has permission to edit
  const canEdit = role === 'ClientAdmin' || role === 'Client_Admin' || role === 'ClientAdmin' || role === 'admin';
  
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
        <button
          onClick={handleSave}
          disabled={saving || !canEdit}
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
                      key={header}
                      className="px-6 py-3 text-center text-xs font-bold text-[#333333] uppercase tracking-wider"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-[#E5E5E5]">
                {permissionsData.length === 0 ? (
                  <tr>
                    <td
                      colSpan={scheduleHeaders.length + 1}
                      className="px-6 py-8 text-center text-sm text-[#B0BEC5]"
                    >
                      目前沒有排班主管
                    </td>
                  </tr>
                ) : (
                  permissionsData.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                      <td 
                        className="sticky left-0 z-5 bg-white px-6 py-4 whitespace-nowrap border-r border-[#E5E5E5]"
                        style={{ position: 'sticky', left: 0 }}
                      >
                        <div className="text-sm font-bold text-[#333333]">{user.name}</div>
                        <div className="text-sm text-[#B0BEC5] mt-1">{user.department}</div>
                      </td>
                      {scheduleHeaders.map((header) => (
                        <td
                          key={header}
                          className="px-6 py-4 whitespace-nowrap text-center"
                        >
                          <input
                            type="checkbox"
                            className="h-5 w-5 text-[#1E88E5] border-[#E5E5E5] rounded focus:ring-[#1E88E5] focus:ring-2 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                            checked={user.permissions[header] || false}
                            onChange={(e) => handleCheckboxChange(user.id, header, e)}
                            disabled={!canEdit}
                            aria-label={`${user.name} - ${header} 權限`}
                            aria-checked={user.permissions[header] || false}
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
            {role === 'ScheduleManager' || role === 'Schedule_Manager' 
              ? '排班主管無法修改權限設定' 
              : role === 'Employee' || role === 'Department_Employee' || role === 'employee'
              ? '員工無權限修改權限設定'
              : '無權限修改權限設定'}
          </p>
        </div>
      )}
    </div>
  );
};

export default PermissionMaintenance;
