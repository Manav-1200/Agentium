// services/admin.ts
import { api } from './api';

// Budget data matching BudgetControl.tsx expectations
export interface BudgetData {
    current_limits: {
        daily_token_limit: number;
        daily_cost_limit: number;
    };
    usage: {
        tokens_used_today: number;
        tokens_remaining: number;
        cost_used_today_usd: number;
        cost_remaining_usd: number;  // Note: frontend expects this name
        cost_percentage_used: number;
        cost_percentage_tokens: number;
    };
    can_modify: boolean;
    optimizer_status: {
        idle_mode_active: boolean;
        time_since_last_activity_seconds: number;
    };
}

export interface User {
    id: number;
    username: string;
    email: string;
    is_active: boolean;
    is_admin: boolean;
    is_pending: boolean;
    created_at?: string;
    updated_at?: string;
}

export interface UserListResponse {
    users: User[];
    total: number;
}

// Default budget data to prevent undefined errors
const defaultBudgetData: BudgetData = {
    current_limits: {
        daily_token_limit: 200000,
        daily_cost_limit: 100
    },
    usage: {
        tokens_used_today: 0,
        tokens_remaining: 200000,
        cost_used_today_usd: 0,
        cost_remaining_usd: 100,
        cost_percentage_used: 0,
        cost_percentage_tokens: 0
    },
    can_modify: false,
    optimizer_status: {
        idle_mode_active: false,
        time_since_last_activity_seconds: 0
    }
};

export const adminService = {
    async getBudget(): Promise<BudgetData> {
        try {
            const response = await api.get(`/api/v1/admin/budget`);

            // Ensure we have data
            if (!response.data) {
                console.warn('Budget endpoint returned empty data');
                return defaultBudgetData;
            }

            // Merge with defaults to ensure all nested fields exist
            const mergedData: BudgetData = {
                current_limits: {
                    ...defaultBudgetData.current_limits,
                    ...response.data.current_limits
                },
                usage: {
                    ...defaultBudgetData.usage,
                    ...response.data.usage
                },
                can_modify: response.data.can_modify ?? defaultBudgetData.can_modify,
                optimizer_status: {
                    ...defaultBudgetData.optimizer_status,
                    ...response.data.optimizer_status
                }
            };

            return mergedData;
        } catch (error: any) {
            console.warn('Budget endpoint error:', error.message);
            return defaultBudgetData;
        }
    },

    async getPendingUsers(): Promise<UserListResponse> {
        try {
            const response = await api.get(`/api/v1/admin/users/pending`);
            return response.data || { users: [], total: 0 };
        } catch (error) {
            console.error('Failed to fetch pending users:', error);
            return { users: [], total: 0 };
        }
    },

    async getAllUsers(includePending = false): Promise<UserListResponse> {
        try {
            const response = await api.get(`/api/v1/admin/users`, {
                params: { include_pending: includePending }
            });
            return response.data || { users: [], total: 0 };
        } catch (error) {
            console.error('Failed to fetch users:', error);
            return { users: [], total: 0 };
        }
    },

    async approveUser(userId: number): Promise<{ success: boolean; message: string }> {
        const response = await api.post(`/api/v1/admin/users/${userId}/approve`);
        return response.data;
    },

    async rejectUser(userId: number): Promise<{ success: boolean; message: string }> {
        const response = await api.post(`/api/v1/admin/users/${userId}/reject`);
        return response.data;
    },

    async deleteUser(userId: number): Promise<{ success: boolean; message: string }> {
        const response = await api.delete(`/api/v1/admin/users/${userId}`);
        return response.data;
    },

    async changeUserPassword(userId: number, newPassword: string): Promise<{ success: boolean; message: string }> {
        const response = await api.post(
            `/api/v1/admin/users/${userId}/change-password`,
            { new_password: newPassword }
        );
        return response.data;
    }
};