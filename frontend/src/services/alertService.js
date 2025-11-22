import api from './api';

export const alertService = {
  getAll: async (page = 1, perPage = 20, filters = {}) => {
    try {
      const response = await api.get('/alerts/', {
        params: { page, per_page: perPage, ...filters },
      });
      return response.data;
    } catch (error) {
      // If endpoint doesn't exist yet, return empty array
      console.warn('[alertService] Alerts endpoint not available, returning empty');
      return {
        success: true,
        data: [],
        pagination: {
          page: 1,
          per_page: perPage,
          total: 0,
          pages: 0,
        },
      };
    }
  },

  getByStatus: async (status, page = 1, perPage = 20) => {
    return alertService.getAll(page, perPage, { status });
  },

  getPending: async () => {
    const response = await alertService.getByStatus('pending');
    return response.data || response.items || [];
  },
};


