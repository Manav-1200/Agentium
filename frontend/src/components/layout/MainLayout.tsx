// src/components/layout/MainLayout.tsx
import { useAuthStore } from '@/store/authStore';
import { useWebSocketStore } from '@/store/websocketStore';
import { NavLink, useNavigate, useLocation, useOutlet } from 'react-router-dom';
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
    Radio,
    Shield,
    Gavel,
    Inbox,
    FlaskConical,
} from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
// ── Voice Bridge addition ─────────────────────────────────────────────────────
import { VoiceIndicator } from '@/components/VoiceIndicator';

// ── Nav order used to determine slide direction ───────────────────────────────
const NAV_ORDER = [
    '/',
    '/chat',
    '/agents',
    '/tasks',
    '/monitoring',
    '/voting',
    '/constitution',
    '/models',
    '/channels',
    '/message-log',
    '/ab-testing',
    '/settings',
    '/sovereign',
];

// ── Page transition variants ──────────────────────────────────────────────────
// Subtle vertical slide + fade — keeps the sidebar perfectly static while only
// the content area animates. "mode=wait" ensures the exit finishes before the
// enter begins, preventing any visual overlap between pages.
const pageVariants = {
    initial: (direction: number) => ({
        opacity: 0,
        y: direction >= 0 ? 10 : -10,
        scale: 0.995,
    }),
    animate: {
        opacity: 1,
        y: 0,
        scale: 1,
    },
    exit: (direction: number) => ({
        opacity: 0,
        y: direction >= 0 ? -6 : 6,
        scale: 0.998,
    }),
};

const pageTransition = {
    duration: 0.22,
    ease: [0.25, 0.1, 0.25, 1] as const, // CSS "ease" — snappy & natural
};

// ── AnimatedOutlet ────────────────────────────────────────────────────────────
// Wraps React Router's <Outlet /> with direction-aware animated transitions.
// The key prop (location.pathname) tells AnimatePresence exactly when to swap
// pages. The layout (sidebar, header) is never involved.
function AnimatedOutlet() {
    const location = useLocation();
    const currentOutlet = useOutlet();

    // Track navigation direction based on nav item order
    const prevPath = useRef(location.pathname);
    const [direction, setDirection] = useState(0);

    useEffect(() => {
        const prevIndex = NAV_ORDER.findIndex(p =>
            prevPath.current === '/' ? p === '/' : prevPath.current.startsWith(p) && p !== '/'
        );
        const currIndex = NAV_ORDER.findIndex(p =>
            location.pathname === '/' ? p === '/' : location.pathname.startsWith(p) && p !== '/'
        );
        setDirection(currIndex >= prevIndex ? 1 : -1);
        prevPath.current = location.pathname;
    }, [location.pathname]);

    return (
        <AnimatePresence mode="wait" initial={false} custom={direction}>
            <motion.div
                key={location.pathname}
                custom={direction}
                variants={pageVariants}
                initial="initial"
                animate="animate"
                exit="exit"
                transition={pageTransition}
                // fill the entire <main> container and scroll independently
                style={{ position: 'absolute', inset: 0, overflowY: 'auto' }}
            >
                {currentOutlet}
            </motion.div>
        </AnimatePresence>
    );
}

// ── MainLayout ────────────────────────────────────────────────────────────────
export function MainLayout() {
    const { user, logout } = useAuthStore();
    const navigate = useNavigate();
    const unreadCount = useWebSocketStore(state => state.unreadCount);
    const [isDark, setIsDark] = useState(() => {
        if (typeof window !== 'undefined') {
            return document.documentElement.classList.contains('dark');
        }
        return false;
    });
    // Updated: Check both isSovereign and is_admin
    const isAdmin = user?.isSovereign || user?.is_admin || false;

    const handleLogout = () => {
        window.dispatchEvent(new Event('logout'));
        logout();
        navigate('/login');
    };

    const toggleTheme = () => {
        const newDark = !isDark;
        setIsDark(newDark);
        if (newDark) {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        }
    };

    type NavItem = {
        path: string;
        label: string;
        icon: React.ComponentType<{ className?: string }>;
        badge?: number;
        variant?: 'default' | 'danger';
        adminOnly?: boolean;
    };

    const navItems: NavItem[] = [
        { path: '/', label: 'Dashboard', icon: LayoutDashboard },
        {
            path: '/chat',
            label: 'Command Interface',
            icon: Crown,
            badge: unreadCount > 0 ? unreadCount : undefined,
        },
        { path: '/agents', label: 'Agents', icon: Users },
        { path: '/tasks', label: 'Tasks', icon: ClipboardList },
        { path: '/monitoring', label: 'Monitoring', icon: Activity },
        { path: '/voting', label: 'Voting', icon: Gavel },
        { path: '/constitution', label: 'Constitution', icon: BookOpen },
        { path: '/models', label: 'Models', icon: Cpu },
        { path: '/channels', label: 'Channels', icon: Radio },
        { path: '/message-log', label: 'Message Log', icon: Inbox },
        { path: '/ab-testing', label: 'A/B Testing', icon: FlaskConical, adminOnly: true },
        { path: '/settings', label: 'Settings', icon: Settings },
        ...(isAdmin
            ? [{ path: '/sovereign', label: 'Sovereign Control', icon: Shield, variant: 'danger' as const }]
            : []),
    ];

    // Filter nav items based on admin status
    const visibleNavItems = navItems.filter(item => !item.adminOnly || isAdmin);

    return (
        <div className="h-screen bg-gray-50 dark:bg-[#0f1117] flex">
            <aside className="w-64 bg-white dark:bg-[#161b27] border-r border-gray-200 dark:border-[#1e2535] flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-gray-200 dark:border-[#1e2535] flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <button
                            onClick={toggleTheme}
                            className="group relative p-2 rounded-xl transition-all duration-300 hover:bg-gray-100 dark:hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                        >
                            <Shield className="w-8 h-8 text-blue-600 transition-all duration-300 rotate-0 scale-100 dark:rotate-90 dark:scale-0 dark:opacity-0" />
                            <Shield className="w-8 h-8 absolute inset-0 m-auto text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.5)] transition-all duration-300 rotate-90 scale-0 opacity-0 dark:rotate-0 dark:scale-100 dark:opacity-100" />
                        </button>
                        <div>
                            <h1 className="text-xl font-bold text-gray-900 dark:text-white">Agentium</h1>
                            <p className="text-xs text-gray-500 dark:text-blue-400/70">AI Governance</p>
                        </div>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
                    {visibleNavItems.map((item) => (
                        <div key={item.path}>
                            {item.variant === 'danger' && (
                                <div className="my-2 border-t border-gray-200 dark:border-[#1e2535]" />
                            )}
                            <NavLink
                                to={item.path}
                                end={item.path === '/'}
                                className={({ isActive }) =>
                                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 ${
                                        item.variant === 'danger'
                                            ? isActive
                                                ? 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300 border border-red-200 dark:border-red-500/20'
                                                : 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 bg-red-50/50 dark:bg-red-500/5'
                                            : isActive
                                                ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
                                                : 'text-gray-700 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/5'
                                    }`
                                }
                            >
                                <item.icon className={`w-4 h-4 flex-shrink-0 ${item.variant === 'danger' ? 'text-red-500' : ''}`} />
                                <span className="flex-1">{item.label}</span>
                                {item.badge !== undefined && (
                                    <span className="bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                                        {item.badge > 9 ? '9+' : item.badge}
                                    </span>
                                )}
                            </NavLink>
                        </div>
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
                        {/* ── Voice Bridge status indicator (icon only) ── */}
                        <VoiceIndicator iconOnly />
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

            {/* Main content — position:relative is required so the absolutely-
                positioned AnimatedOutlet fills this container correctly.       */}
            <main className="flex-1 min-h-0 overflow-hidden relative">
                <AnimatedOutlet />
            </main>
        </div>
    );
}