import axios from 'axios';
import toast from 'react-hot-toast';

const API_URL = '';

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add JWT token to requests
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Handle errors globally
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error.response?.status;
        const message = error.response?.data?.detail || error.message || 'An unexpected error occurred';

        if (status === 401) {
            if (!window.location.pathname.includes('/login')) {
                localStorage.removeItem('access_token');
                delete api.defaults.headers.common['Authorization'];
                window.location.href = '/login';
            }
        } else if (status === 403) {
            toast.error(`Permission Denied: ${message}`);
        } else if (status === 404) {
            if (error.config?.method !== 'get') {
                toast.error(`Not Found: ${message}`);
            }
        } else if (status >= 500) {
            toast.error(`Server Error: ${message}`);
        } else if (status !== 401) {
            toast.error(message);
        }

        return Promise.reject(error);
    }
);