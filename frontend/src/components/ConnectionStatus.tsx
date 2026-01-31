import { useEffect } from 'react';
import { useBackendStore } from '@/store/backendStore';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';

export function ConnectionStatus() {
    const { status, startPolling, stopPolling } = useBackendStore();

    useEffect(() => {
        startPolling();
        return () => stopPolling();
    }, [startPolling, stopPolling]);

    const getStatusColor = () => {
        switch (status.status) {
            case 'connected':
                return 'bg-green-500';
            case 'connecting':
                return 'bg-yellow-500';
            case 'disconnected':
                return 'bg-red-500';
        }
    };

    const getStatusIcon = () => {
        switch (status.status) {
            case 'connected':
                return <Wifi className="w-4 h-4" />;
            case 'connecting':
                return <Loader2 className="w-4 h-4 animate-spin" />;
            case 'disconnected':
                return <WifiOff className="w-4 h-4" />;
        }
    };

    return (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 text-sm">
            <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
            {getStatusIcon()}
            <span className="capitalize hidden sm:inline">{status.status}</span>
            {status.latency && (
                <span className="text-xs text-gray-500 hidden md:inline">
                    ({status.latency}ms)
                </span>
            )}
        </div>
    );
}