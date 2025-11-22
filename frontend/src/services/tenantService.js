import api from './api';

export const tenantService = {
  getAll: async (page = 1, perPage = 20) => {
    const response = await api.get('/tenants/', {  // Add trailing slash to avoid 308 redirect
      params: { page, per_page: perPage },
    });
    return response.data;
  },

  getById: async (id) => {
    const response = await api.get(`/tenants/${id}`);
    return response.data;
  },

  create: async (data) => {
    const response = await api.post('/tenants', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await api.put(`/tenants/${id}`, data);
    return response.data;
  },

  delete: async (id) => {
    const response = await api.delete(`/tenants/${id}`);
    return response.data;
  },

  getStats: async (id) => {
    const response = await api.get(`/tenants/${id}/stats`);
    return response.data;
  },
};

