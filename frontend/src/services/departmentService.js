import api from './api';

export const departmentService = {
  getAll: async (page = 1, perPage = 20, filters = {}) => {
    const response = await api.get('/departments/', {  // Add trailing slash
      params: { page, per_page: perPage, ...filters },
    });
    // API returns { success: true, data: [...] }
    return response.data;
  },

  getById: async (id) => {
    const response = await api.get(`/departments/${id}`);
    return response.data;
  },

  create: async (data) => {
    const response = await api.post('/departments', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await api.put(`/departments/${id}`, data);
    return response.data;
  },

  delete: async (id) => {
    const response = await api.delete(`/departments/${id}`);
    return response.data;
  },
};

