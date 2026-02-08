import { api } from './api';

export interface LoginCredentials {
    username: string;
    password: string;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    user: {
        username: string;
        is_admin: boolean;
        role?: string;
    };
}

export const authService = {
    async login(credentials: LoginCredentials): Promise<LoginResponse> {
        const response = await api.post('/api/v1/auth/login', credentials);

        localStorage.setItem('access_token', response.data.access_token);
        api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;

        return response.data;
    },

    async verifyToken(token: string): Promise<boolean> {
        try {
            // Send as query parameter to match backend
            const response = await api.post('/api/v1/auth/verify', null, {
                params: { token }
            });
            return response.data?.valid || false;
        } catch (error) {
            console.warn('Token verification failed:', error);
            return false;
        }
    },

    logout(): void {
        localStorage.removeItem('access_token');
        delete api.defaults.headers.common['Authorization'];
        window.location.href = '/login';
    },

    isAuthenticated(): boolean {
        return !!localStorage.getItem('access_token');
    },

    getToken(): string | null {
        return localStorage.getItem('access_token');
    },

    initAuth(): void {
        const token = localStorage.getItem('access_token');
        if (token) {
            api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        }
    }
};