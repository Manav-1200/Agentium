import axios, { AxiosInstance } from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api: AxiosInstance = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export class ChatAPI {
    static async sendMessage(
        message: string,
        onChunk: (chunk: string) => void,
        onComplete: (metadata: any) => void,
        onError: (error: string) => void
    ): Promise<void> {
        const response = await fetch(`${API_URL}/chat/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message, stream: true }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('No reader available');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Process all complete lines
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            switch (data.type) {
                                case 'content':
                                    onChunk(data.content);
                                    break;
                                case 'status':
                                    // Could show status updates
                                    console.log('Status:', data.content);
                                    break;
                                case 'complete':
                                    onComplete(data.metadata);
                                    break;
                                case 'error':
                                    onError(data.content);
                                    break;
                                case 'done':
                                    // Stream complete
                                    break;
                            }
                        } catch (e) {
                            console.error('Failed to parse SSE data:', line);
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }

    static async getHistory() {
        const response = await api.get('/chat/history');
        return response.data;
    }
}