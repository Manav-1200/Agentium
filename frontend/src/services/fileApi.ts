/**
 * File upload and download service for chat attachments.
 */

import { api } from './api';

export interface UploadedFile {
    id: string;
    original_name: string;
    stored_name: string;
    url: string;
    type: string;
    category: 'image' | 'video' | 'audio' | 'document' | 'code' | 'archive' | 'other';
    size: number;
    uploaded_at: string;
}

export interface FileUploadResponse {
    success: boolean;
    files: UploadedFile[];
    total_uploaded: number;
}

export interface FileListResponse {
    files: Array<{
        filename: string;
        url: string;
        size: number;
        category: string;
        uploaded_at: string;
    }>;
    total: number;
    storage_used_bytes: number;
}

export interface FileStats {
    total_files: number;
    total_size_bytes: number;
    by_category: Record<string, number>;
    storage_limit_bytes: number;
    storage_used_percent: number;
}

const API_BASE = '/api/v1/files';

export const fileApi = {
    /**
     * Upload one or more files.
     */
    uploadFiles: async (files: File[]): Promise<FileUploadResponse> => {
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        const response = await api.post<FileUploadResponse>(
            `${API_BASE}/upload`,
            formData,
            {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                // Longer timeout for file uploads
                timeout: 60000,
            }
        );
        return response.data;
    },

    /**
     * Get download URL for a file.
     */
    getDownloadUrl: (userId: string, filename: string): string => {
        return `${API_BASE}/download/${userId}/${filename}`;
    },

    /**
     * Download a file directly.
     */
    downloadFile: async (url: string, filename: string): Promise<void> => {
        const response = await api.get(url, {
            responseType: 'blob',
        });

        // Create download link
        const blob = new Blob([response.data]);
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(downloadUrl);
    },

    /**
     * List all files for current user.
     */
    listFiles: async (): Promise<FileListResponse> => {
        const response = await api.get<FileListResponse>(`${API_BASE}/list`);
        return response.data;
    },

    /**
     * Delete a file.
     */
    deleteFile: async (filename: string): Promise<{ success: boolean; message: string }> => {
        const response = await api.delete(`${API_BASE}/${filename}`);
        return response.data;
    },

    /**
     * Get file statistics.
     */
    getStats: async (): Promise<FileStats> => {
        const response = await api.get<FileStats>(`${API_BASE}/stats`);
        return response.data;
    },

    /**
     * Get file icon based on category.
     */
    getFileIcon: (category: string): string => {
        const icons: Record<string, string> = {
            image: '🖼️',
            video: '🎬',
            audio: '🎵',
            document: '📄',
            code: '💻',
            archive: '📦',
            other: '📎'
        };
        return icons[category] || icons.other;
    },

    /**
     * Format file size for display.
     */
    formatFileSize: (bytes: number): string => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
    },

    /**
     * Check if file type is previewable (image/video).
     */
    isPreviewable: (type: string): boolean => {
        return type.startsWith('image/') || type.startsWith('video/');
    },

    /**
     * Get file category from MIME type.
     */
    getCategoryFromType: (type: string): string => {
        if (type.startsWith('image/')) return 'image';
        if (type.startsWith('video/')) return 'video';
        if (type.startsWith('audio/')) return 'audio';
        if (type === 'application/pdf') return 'document';
        if (type.includes('text') || type.includes('json') || type.includes('javascript')) return 'code';
        if (type.includes('zip') || type.includes('compressed')) return 'archive';
        return 'other';
    }
};

export default fileApi;