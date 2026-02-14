/**
 * Voice processing service for speech-to-text and text-to-speech.
 * Checks for OpenAI provider availability before enabling features.
 */

import { api } from './api';
import toast from 'react-hot-toast';

export interface VoiceStatus {
    available: boolean;
    message: string;
    provider: string | null;
    action_required?: 'add_openai_provider' | 'add_any_provider';
}

export interface TranscriptionResponse {
    success: boolean;
    text: string;
    language: string;
    duration_seconds: number;
    audio_size_bytes: number;
    transcribed_at: string;
}

export interface SynthesisResponse {
    success: boolean;
    audio_url: string;
    duration_estimate: number;
    voice: string;
    speed: number;
    generated_at: string;
}

export interface VoiceLanguage {
    code: string;
    name: string;
}

export interface TTSVoice {
    id: string;
    name: string;
    description: string;
}

const API_BASE = '/api/v1/voice';

// Cache status to avoid repeated checks
let cachedStatus: VoiceStatus | null = null;
let statusCacheTime: number = 0;
const STATUS_CACHE_TTL = 60000; // 1 minute

export const voiceApi = {
    /**
     * Check if voice features are available.
     * Caches result for 1 minute.
     */
    checkStatus: async (forceRefresh = false): Promise<VoiceStatus> => {
        const now = Date.now();
        
        if (!forceRefresh && cachedStatus && (now - statusCacheTime) < STATUS_CACHE_TTL) {
            return cachedStatus;
        }

        try {
            const response = await api.get<VoiceStatus>(`${API_BASE}/status`);
            cachedStatus = response.data;
            statusCacheTime = now;
            return response.data;
        } catch (error: any) {
            return {
                available: false,
                message: error.response?.data?.detail?.message || 'Voice service unavailable',
                provider: null
            };
        }
    },

    /**
     * Clear status cache (call after adding new provider).
     */
    clearStatusCache: (): void => {
        cachedStatus = null;
        statusCacheTime = 0;
    },

    /**
     * Check availability and show toast notification if not available.
     * Returns true if available, false otherwise.
     */
    checkAvailability: async (): Promise<boolean> => {
        const status = await voiceApi.checkStatus();
        
        if (!status.available) {
            // Show appropriate message based on action required
            if (status.action_required === 'add_openai_provider') {
                toast.error('OpenAI API Key Required: Add an OpenAI provider in Models page to enable voice features.', { duration: 5000 });
            } else if (status.action_required === 'add_any_provider') {
                toast.error('AI Provider Required: Please configure an OpenAI provider in Models page first.', { duration: 5000 });
            } else {
                toast.error(status.message, { duration: 5000 });
            }
            
            return false;
        }
        
        return true;
    },

    /**
     * Transcribe audio to text using Whisper.
     * Automatically checks availability first.
     */
    transcribe: async (audioBlob: Blob, language?: string): Promise<TranscriptionResponse> => {
        // Check availability first
        const isAvailable = await voiceApi.checkAvailability();
        if (!isAvailable) {
            throw new Error('Voice features not available. Please add OpenAI provider in Models page.');
        }

        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        if (language) {
            formData.append('language', language);
        }

        try {
            const response = await api.post<TranscriptionResponse>(
                `${API_BASE}/transcribe`,
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                    timeout: 60000,
                }
            );
            return response.data;
        } catch (error: any) {
            // Handle specific error for missing provider
            if (error.response?.status === 503) {
                const detail = error.response.data?.detail;
                if (detail?.needs_provider) {
                    voiceApi.clearStatusCache(); // Clear cache to recheck
                    throw new Error(detail.message || 'OpenAI provider required for voice features');
                }
            }
            throw error;
        }
    },

    /**
     * Synthesize text to speech.
     * Automatically checks availability first.
     */
    synthesize: async (text: string, voice: string = 'alloy', speed: number = 1.0): Promise<SynthesisResponse> => {
        // Check availability first
        const isAvailable = await voiceApi.checkAvailability();
        if (!isAvailable) {
            throw new Error('Voice features not available. Please add OpenAI provider in Models page.');
        }

        const formData = new FormData();
        formData.append('text', text);
        formData.append('voice', voice);
        formData.append('speed', speed.toString());

        try {
            const response = await api.post<SynthesisResponse>(
                `${API_BASE}/synthesize`,
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                }
            );
            return response.data;
        } catch (error: any) {
            // Handle specific error for missing provider
            if (error.response?.status === 503) {
                const detail = error.response.data?.detail;
                if (detail?.needs_provider) {
                    voiceApi.clearStatusCache();
                    throw new Error(detail.message || 'OpenAI provider required for voice features');
                }
            }
            throw error;
        }
    },

    /**
     * Get audio file URL.
     */
    getAudioUrl: (userId: string, filename: string): string => {
        return `${API_BASE}/audio/${userId}/${filename}`;
    },

    /**
     * Play audio from URL.
     */
    playAudio: async (url: string): Promise<void> => {
        const audio = new Audio(url);
        await audio.play();
    },

    /**
     * Download audio file.
     */
    downloadAudio: async (url: string, filename: string): Promise<void> => {
        const response = await api.get(url, {
            responseType: 'blob',
        });

        const blob = new Blob([response.data], { type: 'audio/mpeg' });
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
     * Get supported languages.
     */
    getLanguages: async (): Promise<VoiceLanguage[]> => {
        const response = await api.get<{ languages: VoiceLanguage[] }>(`${API_BASE}/languages`);
        return response.data.languages;
    },

    /**
     * Get available TTS voices.
     */
    getVoices: async (): Promise<TTSVoice[]> => {
        const response = await api.get<{ voices: TTSVoice[]; default: string }>(`${API_BASE}/voices`);
        return response.data.voices;
    },

    /**
     * Start recording audio from microphone.
     */
    startRecording: async (): Promise<{ recorder: MediaRecorder; stream: MediaStream }> => {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : MediaRecorder.isTypeSupported('audio/webm')
                ? 'audio/webm'
                : 'audio/mp4';

        const recorder = new MediaRecorder(stream, { mimeType });
        
        return { recorder, stream };
    },

    /**
     * Stop recording and get audio blob.
     */
    stopRecording: (recorder: MediaRecorder, stream: MediaStream): Promise<Blob> => {
        return new Promise((resolve) => {
            const chunks: BlobPart[] = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunks.push(e.data);
                }
            };

            recorder.onstop = () => {
                const blob = new Blob(chunks, { type: recorder.mimeType });
                stream.getTracks().forEach(track => track.stop());
                resolve(blob);
            };

            recorder.stop();
        });
    }
};

export default voiceApi;