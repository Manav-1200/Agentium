import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import toast from 'react-hot-toast';

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

interface QueuedMessage {
    content: string;
    timestamp: number;
}

interface WebSocketState {
    // Connection state
    isConnected: boolean;
    isConnecting: boolean;
    error: string | null;
    connectionStats: {
        reconnectAttempts: number;
        lastPingTime: number | null;
        latencyMs: number | null;
    };
    
    // Message handling
    lastMessage: WebSocketMessage | null;
    unreadCount: number;
    messageHistory: WebSocketMessage[];
    
    // Internal refs (not persisted)
    _ws: WebSocket | null;
    _reconnectTimeout: NodeJS.Timeout | null;
    _pingInterval: NodeJS.Timeout | null;
    _pongTimeout: NodeJS.Timeout | null;
    _connectionTimeout: NodeJS.Timeout | null;
    _reconnectAttempts: number;
    _isManualDisconnect: boolean;
    _lastPingTime: number | null;
    _messageQueue: QueuedMessage[];
    
    // Actions
    connect: () => void;
    disconnect: (isManual?: boolean) => void;
    reconnect: () => void;
    sendMessage: (content: string) => boolean;
    sendPing: () => boolean;
    markAsRead: () => void;
    addMessageToHistory: (message: WebSocketMessage) => void;
    clearError: () => void;
    
    // Internal actions
    _setConnected: (connected: boolean) => void;
    _setConnecting: (connecting: boolean) => void;
    _setError: (error: string | null) => void;
    _updateStats: (stats: Partial<WebSocketState['connectionStats']>) => void;
    _setLastMessage: (message: WebSocketMessage) => void;
    _incrementUnread: () => void;
    _clearAllTimers: () => void;
    _stopHeartbeat: () => void;
    _startHeartbeat: () => void;
    _handlePong: (timestamp: string) => void;
}

// Configuration constants
const WS_CONFIG = {
    MAX_RECONNECT_ATTEMPTS: 5,
    BASE_RECONNECT_DELAY_MS: 1000,
    MAX_RECONNECT_DELAY_MS: 30000,
    PING_INTERVAL_MS: 30000,
    PONG_TIMEOUT_MS: 10000,
    CONNECTION_TIMEOUT_MS: 10000,
    MAX_HISTORY_SIZE: 100,
} as const;

export const useWebSocketStore = create<WebSocketState>()(
    persist(
        (set, get) => ({
            // Initial state
            isConnected: false,
            isConnecting: false,
            error: null,
            connectionStats: {
                reconnectAttempts: 0,
                lastPingTime: null,
                latencyMs: null,
            },
            lastMessage: null,
            unreadCount: 0,
            messageHistory: [],
            
            // Internal refs (initialized but not persisted)
            _ws: null,
            _reconnectTimeout: null,
            _pingInterval: null,
            _pongTimeout: null,
            _connectionTimeout: null,
            _reconnectAttempts: 0,
            _isManualDisconnect: false,
            _lastPingTime: null,
            _messageQueue: [],
            
            // Internal setters
            _setConnected: (connected) => set({ isConnected: connected }),
            _setConnecting: (connecting) => set({ isConnecting: connecting }),
            _setError: (error) => set({ error }),
            _updateStats: (stats) => set((state) => ({
                connectionStats: { ...state.connectionStats, ...stats }
            })),
            _setLastMessage: (message) => set({ lastMessage: message }),
            _incrementUnread: () => set((state) => ({ unreadCount: state.unreadCount + 1 })),
            
            addMessageToHistory: (message) => set((state) => {
                const newHistory = [...state.messageHistory, message];
                // Keep only last N messages
                if (newHistory.length > WS_CONFIG.MAX_HISTORY_SIZE) {
                    newHistory.shift();
                }
                return { messageHistory: newHistory };
            }),
            
            markAsRead: () => set({ unreadCount: 0 }),
            clearError: () => set({ error: null }),
            
            // Cleanup all timers
            _clearAllTimers: () => {
                const state = get();
                if (state._reconnectTimeout) {
                    clearTimeout(state._reconnectTimeout);
                    set({ _reconnectTimeout: null });
                }
                if (state._pingInterval) {
                    clearInterval(state._pingInterval);
                    set({ _pingInterval: null });
                }
                if (state._pongTimeout) {
                    clearTimeout(state._pongTimeout);
                    set({ _pongTimeout: null });
                }
                if (state._connectionTimeout) {
                    clearTimeout(state._connectionTimeout);
                    set({ _connectionTimeout: null });
                }
            },
            
            // Stop heartbeat
            _stopHeartbeat: () => {
                const state = get();
                if (state._pingInterval) {
                    clearInterval(state._pingInterval);
                    set({ _pingInterval: null });
                }
                if (state._pongTimeout) {
                    clearTimeout(state._pongTimeout);
                    set({ _pongTimeout: null });
                }
            },
            
            // Start heartbeat
            _startHeartbeat: () => {
                const state = get();
                get()._stopHeartbeat();
                
                const pingInterval = setInterval(() => {
                    const currentState = get();
                    if (currentState._ws?.readyState === WebSocket.OPEN) {
                        const pingTime = Date.now();
                        set({ _lastPingTime: pingTime });
                        get()._updateStats({ lastPingTime: pingTime });
                        currentState._ws.send(JSON.stringify({ type: 'ping', timestamp: pingTime }));
                        
                        // Set timeout for pong response
                        const pongTimeout = setTimeout(() => {
                            console.warn('[WebSocket] Pong timeout - connection may be dead');
                            currentState._ws?.close();
                        }, WS_CONFIG.PONG_TIMEOUT_MS);
                        set({ _pongTimeout: pongTimeout });
                    }
                }, WS_CONFIG.PING_INTERVAL_MS);
                
                set({ _pingInterval: pingInterval });
            },
            
            // Handle pong response
            _handlePong: (timestamp: string) => {
                const state = get();
                if (state._pongTimeout) {
                    clearTimeout(state._pongTimeout);
                    set({ _pongTimeout: null });
                }
                const latency = Date.now() - (state._lastPingTime || Date.now());
                get()._updateStats({ latencyMs: latency });
            },
            
            // Connect WebSocket
            connect: () => {
                const state = get();
                const token = localStorage.getItem('access_token');
                
                // Validate authentication
                if (!token) {
                    get()._setError('Not authenticated');
                    return;
                }
                
                // Prevent multiple simultaneous connections
                if (state._ws?.readyState === WebSocket.CONNECTING) {
                    console.log('[WebSocket] Already connecting...');
                    return;
                }
                if (state._ws?.readyState === WebSocket.OPEN) {
                    console.log('[WebSocket] Already connected');
                    return;
                }
                
                // Set connecting state
                get()._setConnecting(true);
                get()._setError(null);
                set({ _isManualDisconnect: false });
                
                // Build WebSocket URL
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws/chat?token=${encodeURIComponent(token)}`;
                
                console.log(`[WebSocket] Connecting to ${wsUrl}... (attempt ${state._reconnectAttempts + 1})`);
                
                try {
                    const ws = new WebSocket(wsUrl);
                    set({ _ws: ws });
                    
                    // Connection timeout
                    const connectionTimeout = setTimeout(() => {
                        if (ws.readyState !== WebSocket.OPEN) {
                            console.error('[WebSocket] Connection timeout');
                            ws.close();
                            get()._setError('Connection timeout');
                        }
                    }, WS_CONFIG.CONNECTION_TIMEOUT_MS);
                    set({ _connectionTimeout: connectionTimeout });
                    
                    ws.onopen = () => {
                        console.log('[WebSocket] ✅ Connected');
                        get()._clearAllTimers();
                        get()._setConnected(true);
                        get()._setConnecting(false);
                        set({ _reconnectAttempts: 0 });
                        get()._updateStats({ reconnectAttempts: 0 });
                        get()._startHeartbeat();
                        
                        // Send any queued messages
                        const queued = get()._messageQueue;
                        if (queued.length > 0) {
                            console.log(`[WebSocket] Sending ${queued.length} queued messages`);
                            queued.forEach((msg) => {
                                ws.send(JSON.stringify({
                                    type: 'message',
                                    content: msg.content,
                                    timestamp: new Date(msg.timestamp).toISOString()
                                }));
                            });
                            set({ _messageQueue: [] });
                        }
                    };
                    
                    ws.onmessage = (event) => {
                        try {
                            const data: WebSocketMessage = JSON.parse(event.data);
                            
                            // Handle pong
                            if (data.type === 'pong') {
                                get()._handlePong(data.timestamp || '');
                                return;
                            }
                            
                            // Store message and increment unread if not on chat page
                            get()._setLastMessage(data);
                            get().addMessageToHistory(data);
                            
                            // Only increment unread if it's a new message from head_of_council
                            if (data.type === 'message' && data.role === 'head_of_council') {
                                get()._incrementUnread();
                                
                                // Show toast notification if not on chat page
                                const currentPath = window.location.pathname;
                                if (currentPath !== '/chat') {
                                    toast.success(`New message from Head of Council`, {
                                        duration: 5000,
                                        icon: '👑',
                                    });
                                }
                            }
                            
                        } catch (e) {
                            console.error('[WebSocket] Parse error:', e);
                        }
                    };
                    
                    ws.onerror = (event) => {
                        console.error('[WebSocket] Error:', event);
                        get()._setError('Connection error occurred');
                        get()._setConnected(false);
                    };
                    
                    ws.onclose = (event) => {
                        console.log(`[WebSocket] Closed: ${event.code} - ${event.reason}`);
                        get()._stopHeartbeat();
                        get()._setConnected(false);
                        get()._setConnecting(false);
                        
                        // Handle specific close codes
                        let errorMsg = null;
                        switch (event.code) {
                            case 1000:
                                if (!get()._isManualDisconnect) {
                                    errorMsg = 'Connection closed';
                                }
                                break;
                            case 4001:
                                errorMsg = 'Authentication failed - please login again';
                                // Clear token and redirect
                                localStorage.removeItem('access_token');
                                window.location.href = '/login';
                                return;
                            case 1011:
                                errorMsg = 'Server error - please try again later';
                                break;
                            case 1006:
                                errorMsg = 'Connection lost';
                                break;
                            default:
                                errorMsg = `Connection closed (${event.code})`;
                        }
                        
                        if (errorMsg) {
                            get()._setError(errorMsg);
                        }
                        
                        // Auto-reconnect with exponential backoff
                        const isManual = get()._isManualDisconnect;
                        if (!isManual && event.code !== 4001) {
                            const currentAttempts = get()._reconnectAttempts;
                            if (currentAttempts < WS_CONFIG.MAX_RECONNECT_ATTEMPTS) {
                                const newAttempts = currentAttempts + 1;
                                set({ _reconnectAttempts: newAttempts });
                                get()._updateStats({ reconnectAttempts: newAttempts });
                                
                                const delay = Math.min(
                                    WS_CONFIG.BASE_RECONNECT_DELAY_MS * Math.pow(2, newAttempts),
                                    WS_CONFIG.MAX_RECONNECT_DELAY_MS
                                );
                                
                                get()._setError(`Reconnecting in ${delay / 1000}s... (${newAttempts}/${WS_CONFIG.MAX_RECONNECT_ATTEMPTS})`);
                                
                                const reconnectTimeout = setTimeout(() => {
                                    get().connect();
                                }, delay);
                                set({ _reconnectTimeout: reconnectTimeout });
                            } else {
                                get()._setError('Max retries reached. Click Reconnect to try again.');
                            }
                        }
                    };
                    
                } catch (err) {
                    console.error('[WebSocket] Failed to create connection:', err);
                    get()._setError('Failed to create WebSocket connection');
                    get()._setConnecting(false);
                }
            },
            
            // Disconnect WebSocket
            disconnect: (isManual = false) => {
                const state = get();
                set({ _isManualDisconnect: isManual });
                get()._clearAllTimers();
                
                if (state._ws) {
                    // Remove event handlers
                    state._ws.onopen = null;
                    state._ws.onclose = null;
                    state._ws.onerror = null;
                    state._ws.onmessage = null;
                    
                    if (state._ws.readyState === WebSocket.OPEN || state._ws.readyState === WebSocket.CONNECTING) {
                        state._ws.close(1000, 'Client disconnect');
                    }
                    set({ _ws: null });
                }
                
                get()._setConnected(false);
                get()._setConnecting(false);
                
                if (isManual) {
                    set({ _reconnectAttempts: 0 });
                    get()._updateStats({ reconnectAttempts: 0 });
                }
            },
            
            // Manual reconnect
            reconnect: () => {
                console.log('[WebSocket] Manual reconnect triggered');
                set({ _reconnectAttempts: 0 });
                get()._updateStats({ reconnectAttempts: 0 });
                get().disconnect(true);
                setTimeout(() => get().connect(), 100);
            },
            
            // Send chat message
            sendMessage: (content) => {
                const state = get();
                if (state._ws?.readyState === WebSocket.OPEN) {
                    try {
                        state._ws.send(JSON.stringify({
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
                
                // Queue message if not connected
                console.warn('[WebSocket] Cannot send - not connected, queuing message');
                const newQueue = [...state._messageQueue, { content, timestamp: Date.now() }];
                set({ _messageQueue: newQueue });
                return false;
            },
            
            // Send ping manually
            sendPing: () => {
                const state = get();
                if (state._ws?.readyState === WebSocket.OPEN) {
                    try {
                        state._ws.send(JSON.stringify({
                            type: 'ping',
                            timestamp: Date.now()
                        }));
                        return true;
                    } catch (e) {
                        return false;
                    }
                }
                return false;
            },
        }),
        {
            name: 'websocket-storage',
            // Only persist message history and stats, not connection state or internal refs
            partialize: (state) => ({
                messageHistory: state.messageHistory,
                unreadCount: state.unreadCount,
                connectionStats: {
                    reconnectAttempts: 0, // Reset on reload
                    lastPingTime: null,
                    latencyMs: null,
                },
            }),
        }
    )
);

// Auto-connect when auth token is available
export const initWebSocket = () => {
    const token = localStorage.getItem('access_token');
    if (token) {
        useWebSocketStore.getState().connect();
    }
};

// Listen for storage events (login/logout from other tabs)
if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
        if (e.key === 'access_token') {
            if (e.newValue) {
                // Token added - connect
                useWebSocketStore.getState().connect();
            } else {
                // Token removed - disconnect
                useWebSocketStore.getState().disconnect(true);
            }
        }
    });
}