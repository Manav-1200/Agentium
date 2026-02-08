import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '@/store/authStore';

// Message types matching backend protocol
export type WebSocketMessageType = 'message' | 'status' | 'error' | 'system' | 'pong';

export interface WebSocketMessage {
    type: WebSocketMessageType;
    role?: 'sovereign' | 'head_of_council' | 'system';
    content: string;
    metadata?: {
        agent_id?: string;
        model?: string;
        task_created?: boolean;
        task_id?: string;
        tokens_used?: number;
        connection_id?: number;
    };
    timestamp?: string;
    agent_id?: string;
}

export interface UseWebSocketChatReturn {
    isConnected: boolean;
    isConnecting: boolean;
    error: string | null;
    connect: () => void;
    disconnect: () => void;
    sendMessage: (content: string) => boolean;
    sendPing: () => boolean;
    reconnect: () => void;
    connectionStats: {
        reconnectAttempts: number;
        lastPingTime: number | null;
        latencyMs: number | null;
    };
}

// Configuration constants
const WS_CONFIG = {
    MAX_RECONNECT_ATTEMPTS: 5,
    BASE_RECONNECT_DELAY_MS: 1000,
    MAX_RECONNECT_DELAY_MS: 30000,
    PING_INTERVAL_MS: 30000,      // Send ping every 30s
    PONG_TIMEOUT_MS: 10000,       // Expect pong within 10s
    CONNECTION_TIMEOUT_MS: 10000, // Connection must establish within 10s
} as const;

export function useWebSocketChat(onMessage: (msg: WebSocketMessage) => void): UseWebSocketChatReturn {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [connectionStats, setConnectionStats] = useState({
        reconnectAttempts: 0,
        lastPingTime: null as number | null,
        latencyMs: null as number | null,
    });

    const ws = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const pongTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const connectionTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const isManualDisconnect = useRef(false);

    // Get auth state from store
    const user = useAuthStore(state => state.user);
    const isAuthenticated = user?.isAuthenticated ?? false;
    const logout = useAuthStore(state => state.logout);

    // Cleanup all timers
    const clearAllTimers = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
        }
        if (pongTimeoutRef.current) {
            clearTimeout(pongTimeoutRef.current);
            pongTimeoutRef.current = null;
        }
        if (connectionTimeoutRef.current) {
            clearTimeout(connectionTimeoutRef.current);
            connectionTimeoutRef.current = null;
        }
    }, []);

    // Stop heartbeat (ping/pong)
    const stopHeartbeat = useCallback(() => {
        if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
        }
        if (pongTimeoutRef.current) {
            clearTimeout(pongTimeoutRef.current);
            pongTimeoutRef.current = null;
        }
    }, []);

    // Start heartbeat to keep connection alive
    const startHeartbeat = useCallback(() => {
        stopHeartbeat();

        pingIntervalRef.current = setInterval(() => {
            if (ws.current?.readyState === WebSocket.OPEN) {
                const pingTime = Date.now();
                setConnectionStats(prev => ({ ...prev, lastPingTime: pingTime }));

                ws.current.send(JSON.stringify({ type: 'ping', timestamp: pingTime }));

                // Set timeout for pong response
                pongTimeoutRef.current = setTimeout(() => {
                    console.warn('[WebSocket] Pong timeout - connection may be dead');
                    // Force reconnect on pong timeout
                    ws.current?.close();
                }, WS_CONFIG.PONG_TIMEOUT_MS);
            }
        }, WS_CONFIG.PING_INTERVAL_MS);
    }, [stopHeartbeat]);

    // Handle pong response
    const handlePong = useCallback((timestamp: string) => {
        if (pongTimeoutRef.current) {
            clearTimeout(pongTimeoutRef.current);
            pongTimeoutRef.current = null;
        }

        const latency = Date.now() - (connectionStats.lastPingTime || Date.now());
        setConnectionStats(prev => ({ ...prev, latencyMs: latency }));
    }, [connectionStats.lastPingTime]);

    // Disconnect WebSocket
    const disconnect = useCallback((isManual: boolean = false) => {
        isManualDisconnect.current = isManual;
        clearAllTimers();

        if (ws.current) {
            // Remove event handlers to prevent reconnect logic firing
            ws.current.onopen = null;
            ws.current.onclose = null;
            ws.current.onerror = null;
            ws.current.onmessage = null;

            if (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING) {
                ws.current.close(1000, 'Client disconnect');
            }
            ws.current = null;
        }

        setIsConnected(false);
        setIsConnecting(false);

        if (isManual) {
            reconnectAttemptsRef.current = 0;
            setConnectionStats(prev => ({ ...prev, reconnectAttempts: 0 }));
        }
    }, [clearAllTimers]);

    // Connect WebSocket
    const connect = useCallback(() => {
        // Validate authentication
        if (!isAuthenticated) {
            setError('Not authenticated');
            return;
        }

        // Prevent multiple simultaneous connections
        if (ws.current?.readyState === WebSocket.CONNECTING) {
            console.log('[WebSocket] Already connecting...');
            return;
        }

        if (ws.current?.readyState === WebSocket.OPEN) {
            console.log('[WebSocket] Already connected');
            return;
        }

        // Get token
        const token = localStorage.getItem('access_token');
        if (!token) {
            setError('No access token - please login');
            return;
        }

        // Set connecting state
        setIsConnecting(true);
        setError(null);
        isManualDisconnect.current = false;

        // Build WebSocket URL
        const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
        const wsUrl = `${WS_URL}/ws/chat?token=${encodeURIComponent(token)}`;

        console.log(`[WebSocket] Connecting to ${WS_URL}... (attempt ${reconnectAttemptsRef.current + 1})`);

        try {
            ws.current = new WebSocket(wsUrl);

            // Connection timeout
            connectionTimeoutRef.current = setTimeout(() => {
                if (ws.current?.readyState !== WebSocket.OPEN) {
                    console.error('[WebSocket] Connection timeout');
                    ws.current?.close();
                    setError('Connection timeout');
                }
            }, WS_CONFIG.CONNECTION_TIMEOUT_MS);

            ws.current.onopen = () => {
                console.log('[WebSocket] ✅ Connected');
                clearAllTimers();
                setIsConnected(true);
                setIsConnecting(false);
                reconnectAttemptsRef.current = 0;
                setConnectionStats(prev => ({ ...prev, reconnectAttempts: 0 }));
                startHeartbeat();
            };

            ws.current.onmessage = (event) => {
                try {
                    const data: WebSocketMessage = JSON.parse(event.data);

                    // Handle pong
                    if (data.type === 'pong') {
                        handlePong(data.timestamp || '');
                        return;
                    }

                    onMessage(data);
                } catch (e) {
                    console.error('[WebSocket] Parse error:', e);
                }
            };

            ws.current.onerror = (event) => {
                console.error('[WebSocket] Error:', event);
                setError('Connection error occurred');
                setIsConnected(false);
            };

            ws.current.onclose = (event) => {
                console.log(`[WebSocket] Closed: ${event.code} - ${event.reason}`);
                stopHeartbeat();
                setIsConnected(false);
                setIsConnecting(false);

                // Handle specific close codes
                switch (event.code) {
                    case 1000: // Normal closure
                        if (!isManualDisconnect.current) {
                            setError('Connection closed');
                        }
                        break;

                    case 4001: // Authentication failed
                        setError('Authentication failed - please login again');
                        logout(); // Trigger logout to clear invalid token
                        return; // Don't reconnect

                    case 1011: // Server error
                        setError('Server error - please try again later');
                        break;

                    case 1006: // Abnormal closure (network issue)
                        setError('Connection lost');
                        break;

                    default:
                        setError(`Connection closed (${event.code})`);
                }

                // Auto-reconnect with exponential backoff (unless manual disconnect)
                if (!isManualDisconnect.current && event.code !== 4001) {
                    if (reconnectAttemptsRef.current < WS_CONFIG.MAX_RECONNECT_ATTEMPTS) {
                        reconnectAttemptsRef.current += 1;
                        const delay = Math.min(
                            WS_CONFIG.BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current),
                            WS_CONFIG.MAX_RECONNECT_DELAY_MS
                        );

                        setConnectionStats(prev => ({
                            ...prev,
                            reconnectAttempts: reconnectAttemptsRef.current
                        }));
                        setError(`Reconnecting in ${delay / 1000}s... (${reconnectAttemptsRef.current}/${WS_CONFIG.MAX_RECONNECT_ATTEMPTS})`);

                        reconnectTimeoutRef.current = setTimeout(() => {
                            connect();
                        }, delay);
                    } else {
                        setError('Max retries reached. Click Reconnect to try again.');
                    }
                }
            };

        } catch (err) {
            console.error('[WebSocket] Failed to create connection:', err);
            setError('Failed to create WebSocket connection');
            setIsConnecting(false);
        }
    }, [isAuthenticated, onMessage, clearAllTimers, startHeartbeat, handlePong, logout, stopHeartbeat]);

    // Manual reconnect
    const reconnect = useCallback(() => {
        console.log('[WebSocket] Manual reconnect triggered');
        reconnectAttemptsRef.current = 0;
        setConnectionStats(prev => ({ ...prev, reconnectAttempts: 0 }));
        disconnect(true);
        setTimeout(connect, 100);
    }, [connect, disconnect]);

    // Send chat message
    const sendMessage = useCallback((content: string): boolean => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            try {
                ws.current.send(JSON.stringify({
                    type: 'message',
                    content: content.trim(),
                    timestamp: new Date().toISOString()
                }));
                return true;
            } catch (e) {
                console.error('[WebSocket] Send error:', e);
                return false;
            }
        }
        console.warn('[WebSocket] Cannot send - not connected');
        return false;
    }, []);

    // Send ping manually
    const sendPing = useCallback((): boolean => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            try {
                ws.current.send(JSON.stringify({
                    type: 'ping',
                    timestamp: Date.now()
                }));
                return true;
            } catch (e) {
                return false;
            }
        }
        return false;
    }, []);

    // Auto-connect when authenticated
    useEffect(() => {
        if (isAuthenticated && !isConnected && !isConnecting && !ws.current) {
            connect();
        }

        return () => {
            disconnect(true);
        };
    }, [isAuthenticated]); // Only re-run when auth state changes

    // Listen for token changes from other tabs
    useEffect(() => {
        const handleStorage = (e: StorageEvent) => {
            if (e.key === 'access_token') {
                if (e.newValue) {
                    // Token added/changed - reconnect with new token
                    console.log('[WebSocket] Token changed in another tab');
                    disconnect(true);
                    setTimeout(connect, 100);
                } else {
                    // Token removed - disconnect
                    console.log('[WebSocket] Logged out in another tab');
                    disconnect(true);
                    setError('Logged out in another tab');
                }
            }
        };

        window.addEventListener('storage', handleStorage);
        return () => window.removeEventListener('storage', handleStorage);
    }, [connect, disconnect]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnect(true);
        };
    }, [disconnect]);

    return {
        isConnected,
        isConnecting,
        error,
        connect,
        disconnect: () => disconnect(true),
        sendMessage,
        sendPing,
        reconnect,
        connectionStats
    };
}