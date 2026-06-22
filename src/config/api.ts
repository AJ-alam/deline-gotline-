export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export const apiCall = async (endpoint: string, options?: RequestInit) => {
  const token = localStorage.getItem('dgg_token');
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...options?.headers,
    },
    ...options,
  });
  if (!response.ok) throw new Error(`API Error: ${response.status}`);
  return response.json();
};
