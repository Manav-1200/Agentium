import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User } from '@/types';

interface AuthState {
    user: User | null;
    login: (username: string, password: string) => Promise<boolean>;
    logout: () => void;
    changePassword: (oldPassword: string, newPassword: string) => Promise<boolean>;
    isLoading: boolean;
    error: string | null;
}

const INITIAL_CREDENTIALS = {
    username: 'admin',
    password: 'admin'
};

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            isLoading: false,
            error: null,

            login: async (username: string, password: string) => {
                set({ isLoading: true, error: null });

                // Simulate API call delay
                await new Promise(resolve => setTimeout(resolve, 500));

                if (username === get().user?.username || (username === INITIAL_CREDENTIALS.username && password === INITIAL_CREDENTIALS.password)) {
                    set({
                        user: {
                            id: '1',
                            username: username,
                            role: 'sovereign',
                            isAuthenticated: true
                        },
                        isLoading: false
                    });
                    return true;
                }

                set({ error: 'Invalid credentials', isLoading: false });
                return false;
            },

            logout: () => {
                set({ user: null, error: null });
            },

            changePassword: async (oldPassword: string, newPassword: string) => {
                set({ isLoading: true, error: null });

                await new Promise(resolve => setTimeout(resolve, 500));

                // In reality, verify oldPassword against stored hash
                const currentUser = get().user;
                if (!currentUser) {
                    set({ error: 'Not authenticated', isLoading: false });
                    return false;
                }

                // Update stored credentials (in memory for this demo, would be API call)
                INITIAL_CREDENTIALS.password = newPassword;

                set({ isLoading: false });
                return true;
            }
        }),
        {
            name: 'auth-storage',
            partialize: (state) => ({ user: state.user })
        }
    )
);