import { useEffect, useRef, useCallback } from 'react';
import { useBackendStore } from '@/store/backendStore';

export function useWebSocket(onMessage: (data: any) => void) {
    const ws = useRef<WebSocket | null>(null);
    const { status } = useBackendStore();

    const sendMessage = useCallback((message: any) => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(message));
        }
    }, []);

    useEffect(() => {
        if (status.status !== 'connected') {
            return;
        }

        const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
        ws.current = new WebSocket(WS_URL);

        ws.current.onopen = () => {
            console.log('WebSocket connected to Head of Council');
        };

        ws.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                onMessage(data);
            } catch (error) {
                console.error('WebSocket message error:', error);
            }
        };

        ws.current.onclose = () => {
            console.log('WebSocket disconnected');
        };

        ws.current.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        return () => {
            ws.current?.close();
        };
    }, [status.status, onMessage]);

    return { sendMessage };
}