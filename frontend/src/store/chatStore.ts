import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ChatAPI } from '@/services/api';
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

export const useChatStore = create<ChatState>()(
    persist(
        (set, get) => ({
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

                    await ChatAPI.sendMessage(
                        content,
                        // On chunk
                        (chunk) => {
                            assistantContent += chunk;
                            set({ currentStreamingMessage: assistantContent });
                        },
                        // On complete
                        (meta) => {
                            metadata = meta;
                        },
                        // On error
                        (error) => {
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

                    // Notify if task was created
                    if (metadata.task_created) {
                        toast.success(`Task ${metadata.task_id} created and sent to Council for deliberation`);
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