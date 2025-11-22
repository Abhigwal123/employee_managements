# Frontend Integration for Employee ID-Based Registration

## ✅ Implementation Complete

This document describes the frontend integration for Employee ID-based registration and profile display.

---

## 📋 Changes Made

### 1. Backend Endpoint (`backend/app/routes/employee_routes.py`)

**New Endpoint:** `GET /api/v1/employee/available-ids`

**Purpose:**
- Returns list of available Employee IDs from `EmployeeMapping` that are not yet linked to users
- Includes employee name and identifier information

**Response Format:**
```json
{
  "success": true,
  "available_ids": [
    {
      "employee_id": "E01",
      "employee_name": "謝○穎",
      "sheets_identifier": "E01",
      "sheets_name_id": "謝○穎/E01"
    },
    ...
  ],
  "count": 5
}
```

---

### 2. API Service (`frontend/src/services/api.js`)

**Added Function:**
```javascript
export const getAvailableEmployeeIDs = async () => {
  try {
    const res = await api.get('/employee/available-ids');
    return res.data;
  } catch (error) {
    console.error('Error fetching available Employee IDs:', error);
    throw error;
  }
};
```

---

### 3. Registration Form (`frontend/src/pages/Auth/Register.js`)

**Enhanced Features:**

1. **Employee ID Dropdown:**
   - Fetches available Employee IDs on component mount
   - Shows dropdown when role is "employee" or for public registration
   - Displays format: "E01 - 謝○穎" (ID - Name)
   - Required field with validation

2. **Form State:**
   - Added `employee_id` to form data
   - Added `availableEmployeeIDs` state
   - Added `loadingEmployeeIDs` state

3. **Validation:**
   - Validates Employee ID is selected before submission
   - Enhanced error messages for Employee ID validation errors
   - Shows helpful messages when no Employee IDs available

4. **User Experience:**
   - Loading state while fetching Employee IDs
   - Warning message if no Employee IDs available
   - Help text explaining Employee ID source

**Registration Request:**
```json
{
  "username": "john_doe",
  "password": "secure_password",
  "email": "john@example.com",
  "employee_id": "E01",
  "role": "employee",
  "full_name": "John Doe"
}
```

---

### 4. Profile Page (`frontend/src/pages/Profile/Profile.js`)

**New Component Created:**

**Features:**
- Displays Employee ID prominently in a highlighted box
- Shows all user information (username, role, email, etc.)
- Fetches user data from `/api/v1/auth/me`
- Responsive design with grid layout
- Loading and error states

**Employee ID Display:**
- Large, prominent display in blue highlighted box
- Icon for visual emphasis
- Shows Employee ID in large, bold text

**Access:**
- Route: `/profile`
- Accessible to all authenticated users
- Protected route requiring authentication

---

### 5. Routes (`frontend/src/routes/index.js`)

**Added:**
- Profile route at `/profile`
- Protected route accessible to all authenticated users

---

### 6. Constants (`frontend/src/utils/constants.js`)

**Added:**
- `PROFILE: '/profile'` route constant

---

## 🎨 UI Components

### Registration Form Employee ID Dropdown

```jsx
<select
  id="employee_id"
  name="employee_id"
  required
  value={formData.employee_id}
  onChange={handleChange}
>
  <option value="">請選擇員工編號</option>
  {availableEmployeeIDs.map(emp => (
    <option key={emp.employee_id} value={emp.employee_id}>
      {emp.employee_id} {emp.employee_name && `- ${emp.employee_name}`}
    </option>
  ))}
</select>
```

### Profile Page Employee ID Display

```jsx
<div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
  <div className="flex items-center justify-between">
    <div>
      <label className="block text-sm font-medium text-blue-900 mb-1">
        員工編號 (Employee ID)
      </label>
      <p className="text-2xl font-bold text-blue-700">
        {displayUser?.employee_id}
      </p>
    </div>
    <div className="bg-blue-100 rounded-full p-3">
      {/* Icon */}
    </div>
  </div>
</div>
```

---

## 🔄 Complete Flow

### Registration Flow

```
1. User navigates to /register
   ↓
2. Component mounts, fetches available Employee IDs
   ↓
3. Dropdown populated with Employee IDs from Google Sheets
   ↓
4. User selects Employee ID
   ↓
5. User fills other form fields
   ↓
6. User submits form
   ↓
7. Frontend validates Employee ID is selected
   ↓
8. POST /api/v1/auth/register with employee_id
   ↓
9. Backend validates Employee ID exists and not linked
   ↓
10. User created and EmployeeMapping auto-linked
   ↓
11. Registration successful
```

### Profile Display Flow

```
1. User navigates to /profile
   ↓
2. Component fetches user data from /api/v1/auth/me
   ↓
3. User data includes employee_id
   ↓
4. Employee ID displayed prominently
   ↓
5. All user information displayed
```

---

## ✅ Validation & Error Handling

### Frontend Validation

- ✅ Employee ID required for employee role
- ✅ Dropdown validation before form submission
- ✅ Loading state while fetching Employee IDs
- ✅ Error messages for missing Employee IDs

### Backend Error Handling

- ✅ 400: Employee ID required
- ✅ 404: Employee ID not found
- ✅ 409: Employee ID already registered
- ✅ 403: Tenant mismatch

### User-Friendly Error Messages

- **Employee ID not found:** "員工編號不存在。請確保 Google Sheet 已同步，或選擇其他員工編號。"
- **Employee ID already registered:** "此員工編號已被註冊。請選擇其他員工編號。"
- **Employee ID required:** "請選擇有效的員工編號。"
- **No Employee IDs available:** "沒有可用的員工編號。請確保 Google Sheet 已同步。"

---

## 🧪 Testing

### Test Registration

1. **Navigate to `/register`**
2. **Select role "employee"**
3. **Verify Employee ID dropdown appears**
4. **Select an Employee ID**
5. **Fill other fields**
6. **Submit form**
7. **Verify registration succeeds**

### Test Profile

1. **Login as registered user**
2. **Navigate to `/profile`**
3. **Verify Employee ID displayed prominently**
4. **Verify all user information displayed**

### Test Error Cases

1. **Try registration without Employee ID** → Should show validation error
2. **Try registration with invalid Employee ID** → Should show 404 error
3. **Try registration with already registered Employee ID** → Should show 409 error

---

## 📊 API Endpoints Used

### Registration
- `GET /api/v1/employee/available-ids` - Fetch available Employee IDs
- `POST /api/v1/auth/register` - Register new user with employee_id

### Profile
- `GET /api/v1/auth/me` - Get current user data (includes employee_id)

---

## 🎯 Expected Results

✅ **Registration form shows available Employee IDs from Google Sheet sync**  
✅ **Registration cannot proceed without a valid Employee ID selection**  
✅ **Employee ID appears prominently in the user profile**  
✅ **All validations and backend syncs remain consistent end-to-end**

---

## 🚀 Next Steps

1. **Test the registration flow:**
   - Ensure Google Sheets are synced
   - Register a new user with Employee ID
   - Verify EmployeeMapping is auto-linked

2. **Test the profile display:**
   - Login as registered user
   - Navigate to `/profile`
   - Verify Employee ID is displayed

3. **Add navigation link:**
   - Add Profile link to navigation menu (optional)
   - Add link in user dropdown menu (optional)

---

## ✅ Implementation Status

**Status:** ✅ **COMPLETE**

All tasks implemented:
- ✅ Backend endpoint for available Employee IDs
- ✅ API utility function
- ✅ Registration form with Employee ID dropdown
- ✅ Profile page with Employee ID display
- ✅ Routes configured
- ✅ Error handling enhanced
- ✅ Validation implemented

**Frontend is ready for testing and deployment!** 🎉

