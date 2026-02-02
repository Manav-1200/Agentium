import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import toast from 'react-hot-toast';

export interface Message {
    id: string;
    role: 'sovereign' | 'head_of_council' | 'system';
    content: string;
    timestamp: Date;
    status?: 'sending' | 'sent' | 'error';
    metadata?: {
        agent_used?: string;
        model?: string;
        latency_ms?: number;
        task_created?: boolean;
        task_id?: string;
    };
}

interface ChatState {
    messages: Message[];
    isLoading: boolean;
    currentStreamingMessage: string;
    sendMessage: (content: string) => Promise<void>;
    clearHistory: () => void;
}

// Stub for Phase 1 - replace with real API in Phase 5
const sendMessageToCouncil = async (
    message: string,
    onChunk: (chunk: string) => void,
    onComplete: (meta: any) => void,
    onError: (error: string) => void
) => {
    // Simulate streaming response
    const response = "This is a Phase 1 test response from Head of Council.";
    const chunks = response.split(' ');
    
    for (const chunk of chunks) {
        onChunk(chunk + ' ');
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    onComplete({
        agent_id: '00001',
        model: 'gpt-4',
        task_created: false
    });
};

export const useChatStore = create<ChatState>()(
    persist(
        (set) => ({
            messages: [],
            isLoading: false,
            currentStreamingMessage: '',

            sendMessage: async (content: string) => {
                const userMessage: Message = {
                    id: crypto.randomUUID(),
                    role: 'sovereign',
                    content,
                    timestamp: new Date(),
                    status: 'sent'
                };

                set((state) => ({
                    messages: [...state.messages, userMessage],
                    isLoading: true,
                    currentStreamingMessage: ''
                }));

                try {
                    let assistantContent = '';
                    let metadata: any = {};

                    await sendMessageToCouncil(
                        content,
                        // On chunk
                        (chunk: string) => {
                            assistantContent += chunk;
                            set({ currentStreamingMessage: assistantContent });
                        },
                        // On complete
                        (meta: any) => {
                            metadata = meta;
                        },
                        // On error
                        (error: string) => {
                            throw new Error(error);
                        }
                    );

                    // Add assistant message
                    const assistantMessage: Message = {
                        id: crypto.randomUUID(),
                        role: 'head_of_council',
                        content: assistantContent,
                        timestamp: new Date(),
                        status: 'sent',
                        metadata: {
                            agent_used: metadata.agent_id,
                            model: metadata.model,
                            task_created: metadata.task_created,
                            task_id: metadata.task_id
                        }
                    };

                    set((state) => ({
                        messages: [...state.messages, assistantMessage],
                        isLoading: false,
                        currentStreamingMessage: ''
                    }));

                    if (metadata.task_created) {
                        toast.success(`Task ${metadata.task_id} created`);
                    }

                } catch (error) {
                    console.error('Chat error:', error);

                    const errorMessage: Message = {
                        id: crypto.randomUUID(),
                        role: 'system',
                        content: `Failed to reach Head of Council: ${error instanceof Error ? error.message : 'Unknown error'}`,
                        timestamp: new Date(),
                        status: 'error'
                    };

                    set((state) => ({
                        messages: [...state.messages, errorMessage],
                        isLoading: false,
                        currentStreamingMessage: ''
                    }));

                    toast.error('Failed to send message');
                }
            },

            clearHistory: () => {
                set({ messages: [], currentStreamingMessage: '' });
            }
        }),
        {
            name: 'chat-storage',
            partialize: (state) => ({ messages: state.messages })
        }
    )
);
