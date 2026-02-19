// src/components/layout/MainLayout.tsx
import { useAuthStore } from '@/store/authStore';
import { useWebSocketStore } from '@/store/websocketStore';
import { NavLink, useNavigate, Outlet } from 'react-router-dom';
import { 
    LayoutDashboard, 
    Crown, 
    Users, 
    ClipboardList, 
    Activity, 
    BookOpen, 
    Settings, 
    LogOut,
    Cpu,
    Radio
} from 'lucide-react';

export function MainLayout() {
    const { user, logout } = useAuthStore();
    const navigate = useNavigate();
    const unreadCount = useWebSocketStore(state => state.unreadCount);
    
    const handleLogout = () => {
        // Dispatch logout event for WebSocket cleanup
        window.dispatchEvent(new Event('logout'));
        logout();
        navigate('/login');
    };

    const navItems = [
        { path: '/', label: 'Dashboard', icon: LayoutDashboard },
        { 
            path: '/chat', 
            label: 'Command Interface', 
            icon: Crown,
            badge: unreadCount > 0 ? unreadCount : undefined
        },
        { path: '/agents', label: 'Agents', icon: Users },
        { path: '/tasks', label: 'Tasks', icon: ClipboardList },
        { path: '/monitoring', label: 'Monitoring', icon: Activity },
        { path: '/constitution', label: 'Constitution', icon: BookOpen },
        { path: '/models', label: 'Models', icon: Cpu },
        { path: '/channels', label: 'Channels', icon: Radio },
        { path: '/settings', label: 'Settings', icon: Settings },
    ];

    return (
        <div className="h-screen bg-gray-50 dark:bg-[#0f1117] flex overflow-hidden">
            <aside className="w-64 bg-white dark:bg-[#161b27] border-r border-gray-200 dark:border-[#1e2535] flex flex-col">
                {/* Header */}
                <div className="p-4 border-b border-gray-200 dark:border-[#1e2535]">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center">
                            <Crown className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="font-bold text-gray-900 dark:text-white">Agentium</h1>
                            <p className="text-xs text-gray-500 dark:text-gray-400">AI Governance</p>
                        </div>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                                    isActive
                                        ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
                                        : 'text-gray-700 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/5'
                                }`
                            }
                        >
                            <item.icon className="w-5 h-5 flex-shrink-0" />
                            <span className="flex-1">{item.label}</span>
                            {item.badge && (
                                <span className="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full min-w-[20px] text-center">
                                    {item.badge > 9 ? '9+' : item.badge}
                                </span>
                            )}
                        </NavLink>
                    ))}
                </nav>

                {/* User section */}
                <div className="p-4 border-t border-gray-200 dark:border-[#1e2535]">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-bold">
                            {user?.username?.charAt(0).toUpperCase() || 'U'}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                                {user?.username || 'User'}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                                {user?.role || 'Member'}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                    >
                        <LogOut className="w-4 h-4" />
                        Logout
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <main className="flex-1 overflow-hidden">
                <Outlet />
            </main>
        </div>
    );
}