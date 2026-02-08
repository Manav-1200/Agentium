import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '@/store/authStore';

interface WebSocketMessage {
    type: 'message' | 'status' | 'error' | 'system';
    role?: 'sovereign' | 'head_of_council' | 'system';
    content: string;
    metadata?: any;
    timestamp?: string;
}

interface UseWebSocketChatReturn {
    isConnected: boolean;
    isConnecting: boolean;
    error: string | null;
    connect: () => void;
    disconnect: () => void;
    sendMessage: (content: string) => boolean;
    reconnect: () => void;  // 🔑 Added for ChatPage
}

export function useWebSocketChat(onMessage: (msg: WebSocketMessage) => void): UseWebSocketChatReturn {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const ws = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const maxReconnectAttempts = 5;

    // 🔑 FIX #1: Get user and extract isAuthenticated properly
    const user = useAuthStore(state => state.user);
    const isAuthenticated = user?.isAuthenticated ?? false;

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (ws.current) {
            ws.current.onclose = null;  // Prevent auto-reconnect
            ws.current.close();
            ws.current = null;
        }

        setIsConnected(false);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
    }, []);

    const connect = useCallback(() => {
        if (!isAuthenticated) {
            setError('Not authenticated');
            return;
        }

        // 🔑 FIX #3: Prevent multiple simultaneous connections
        if (ws.current?.readyState === WebSocket.CONNECTING) {
            console.log('[WebSocket] Already connecting...');
            return;
        }

        if (ws.current?.readyState === WebSocket.OPEN) {
            console.log('[WebSocket] Already connected');
            return;
        }

        const token = localStorage.getItem('access_token');
        if (!token) {
            setError('No access token');
            return;
        }

        setIsConnecting(true);
        setError(null);

        const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
        const wsUrl = `${WS_URL}/ws/chat?token=${encodeURIComponent(token)}`;

        console.log('[WebSocket] Connecting...');

        try {
            ws.current = new WebSocket(wsUrl);

            ws.current.onopen = () => {
                console.log('[WebSocket] ✅ Connected');
                setIsConnected(true);
                setIsConnecting(false);
                reconnectAttemptsRef.current = 0;
            };

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    onMessage(data);
                } catch (e) {
                    console.error('[WebSocket] Parse error:', e);
                }
            };

            ws.current.onerror = () => {
                setError('Connection error');
                setIsConnected(false);
            };

            ws.current.onclose = (event) => {
                console.log(`[WebSocket] Closed: ${event.code}`);
                setIsConnected(false);
                setIsConnecting(false);

                if (event.code === 4001) {
                    setError('Authentication failed');
                    return;
                }

                // Auto-reconnect with backoff
                if (reconnectAttemptsRef.current < maxReconnectAttempts) {
                    reconnectAttemptsRef.current += 1;
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
                    setError(`Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);

                    reconnectTimeoutRef.current = setTimeout(() => {
                        connect();
                    }, delay);
                } else {
                    setError('Max retries reached. Click Reconnect.');
                }
            };
        } catch (err) {
            setError('Failed to connect');
            setIsConnecting(false);
        }
    }, [isAuthenticated, onMessage]);

    // 🔑 FIX #2: Manual reconnect function
    const reconnect = useCallback(() => {
        console.log('[WebSocket] Manual reconnect');
        reconnectAttemptsRef.current = 0;
        disconnect();
        setTimeout(connect, 100);
    }, [connect, disconnect]);

    const sendMessage = useCallback((content: string): boolean => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({
                type: 'message',
                content,
                timestamp: new Date().toISOString()
            }));
            return true;
        }
        return false;
    }, []);

    // 🔑 FIX #1: Stable dependencies - only depend on isAuthenticated boolean
    useEffect(() => {
        if (isAuthenticated && !isConnected && !isConnecting && !ws.current) {
            connect();
        }

        return () => {
            disconnect();
        };
    }, [isAuthenticated]);  // ✅ Only re-run when auth state changes

    // Listen for token changes from other tabs
    useEffect(() => {
        const handleStorage = (e: StorageEvent) => {
            if (e.key === 'access_token') {
                if (e.newValue) {
                    disconnect();
                    setTimeout(connect, 100);
                } else {
                    disconnect();
                    setError('Logged out in another tab');
                }
            }
        };

        window.addEventListener('storage', handleStorage);
        return () => window.removeEventListener('storage', handleStorage);
    }, [connect, disconnect]);

    return {
        isConnected,
        isConnecting,
        error,
        connect,
        disconnect,
        sendMessage,
        reconnect  // 🔑 Now available for ChatPage
    };
}