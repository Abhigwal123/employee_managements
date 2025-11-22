import api from './api';

export const userService = {
  getAll: async (page = 1, perPage = 20, filters = {}) => {
    const response = await api.get('/users/', {  // Add trailing slash
      params: { page, per_page: perPage, ...filters },
    });
    return response.data;
  },

  getById: async (id) => {
    const response = await api.get(`/users/${id}`);
    return response.data;
  },

  create: async (data) => {
    const response = await api.post('/users', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await api.put(`/users/${id}`, data);
    return response.data;
  },

  delete: async (id) => {
    const response = await api.delete(`/users/${id}`);
    return response.data;
  },

  updateRole: async (id, role) => {
    const response = await api.put(`/users/${id}/role`, { role });
    return response.data;
  },

  getPermissions: async (id) => {
    const response = await api.get(`/users/${id}/permissions`);
    return response.data;
  },

  updatePermissions: async (id, data) => {
    const response = await api.put(`/users/${id}/permissions`, data);
    return response.data;
  },
};

