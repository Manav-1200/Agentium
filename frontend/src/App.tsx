// src/App.tsx
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useOutlet } from 'react-router-dom';
import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from '@/store/authStore';
import { useBackendStore } from '@/store/backendStore';
import { GlobalWebSocketProvider } from '@/components/GlobalWebSocketProvider';
import { MainLayout } from '@/components/layout/MainLayout';
import { FlatMapAuthBackground } from '@/components/FlatMapAuthBackground';
import { LoginPage } from '@/pages/LoginPage';
import { SignupPage } from '@/pages/SignupPage';
import { Dashboard } from '@/pages/Dashboard';
import { SettingsPage } from '@/pages/SettingsPage';
import { ChatPage } from '@/pages/ChatPage';
import { ChannelsPage } from '@/pages/ChannelsPage';
import { ModelsPage } from '@/pages/ModelsPage';
import { AgentsPage } from '@/pages/AgentsPage';
import { TasksPage } from '@/pages/TasksPage';
import { MonitoringPage } from '@/pages/MonitoringPage';
import { ConstitutionPage } from '@/pages/ConstitutionPage';
import { SovereignDashboard } from '@/pages/SovereignDashboard';
import { SovereignRoute } from '@/components/SovereignRoute';
import { AnimatePresence, motion } from 'framer-motion';
import { Shield, Loader2 } from 'lucide-react';
import { useState } from 'react';

// Full-screen spinner shown while checkAuth() is in-flight on page load
function AppLoader() {
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
      </div>
    </div>
  );
}

// Auth layout — keeps background and header persistent across login/signup
function AuthLayout() {
  const location = useLocation();
  const outlet = useOutlet(); // snapshot of current route content — doesn't update mid-animation
  const isSignup = location.pathname === '/signup';
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return document.documentElement.classList.contains('dark');
    }
    return false;
  });

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

  return (
    <div className="min-h-screen relative flex flex-col items-center justify-center p-4">
      <FlatMapAuthBackground variant={isSignup ? 'signup' : 'login'} />

      <div className="text-center mb-8 relative z-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 text-white mb-4 transition-transform duration-500 hover:scale-110">
          <button
            onClick={toggleTheme}
            className="
            group relative p-2 rounded-xl
            transition-all duration-300 ease-out
            overflow-hidden

            /* LIGHT MODE BASE */
            bg-blue-600 text-white shadow-sm

            /* LIGHT MODE HOVER → PREVIEW DARK */
            hover:bg-zinc-900 hover:text-zinc-100 hover:shadow-lg

            /* DARK MODE BASE */
            dark:bg-blue-600 dark:text-zinc-900 dark:shadow-none

            /* DARK MODE HOVER → PREVIEW LIGHT */
            dark:hover:bg-white dark:hover:text-zinc-800 dark:hover:shadow-lg

            focus:outline-none focus:ring-2 focus:ring-blue-500/40
            "
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >

            {/* Light icon */}
            <Shield
              className="
              w-8 h-8
              transition-all duration-500 ease-[cubic-bezier(.22,1,.36,1)]

              rotate-0 scale-100 opacity-100

              group-hover:rotate-0 group-hover:scale-0 group-hover:opacity-0

              dark:rotate-0 dark:scale-0 dark:opacity-0
              dark:group-hover:rotate-0 dark:group-hover:scale-100 dark:group-hover:opacity-100
              "
            />

            {/* Dark icon */}
            <Shield
              className="
              w-8 h-8 absolute inset-0 m-auto
              transition-all duration-500 ease-[cubic-bezier(.22,1,.36,1)]

              rotate-0 scale-0 opacity-0

              group-hover:rotate-0 group-hover:scale-100 group-hover:opacity-100

              dark:rotate-0 dark:scale-100 dark:opacity-100
              dark:group-hover:rotate-0 dark:group-hover:scale-0 dark:group-hover:opacity-0
              "
            />

            {/* ambient glow layer */}
            <span
              className="
              pointer-events-none absolute inset-0 rounded-xl opacity-0 transition-opacity duration-300

              /* glow when previewing dark */
              group-hover:opacity-100 group-hover:bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.15),transparent_70%)]

              /* glow when previewing light */
              dark:group-hover:bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.15),transparent_70%)]
              "
            />
          </button>
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">Agentium</h1>
        <p className="text-white">AI Agent Governance System</p>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { duration: 0.2, delay: 0.45, ease: "easeIn" } }}
          exit={{ opacity: 0, transition: { duration: 0.15, ease: "easeOut" } }}
          className="w-full max-w-md relative z-10"
        >
          {outlet}
        </motion.div>
      </AnimatePresence>

      <p className="text-center text-sm text-white mt-8 relative z-10">
        Secure AI Governance Platform v1.0.0
      </p>
    </div>
  );
}

export default function App() {
  const { user, isInitialized } = useAuthStore();
  const { startPolling, stopPolling } = useBackendStore();

  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, [startPolling, stopPolling]);

  // Block the entire app until checkAuth() has finished at least once.
  if (!isInitialized) {
    return <AppLoader />;
  }

  const isAuthenticated = user?.isAuthenticated === true;

  return (
    <Router>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          className: 'dark:bg-gray-800 dark:text-white',
          style: { background: '#1f2937', color: '#fff' },
        }}
      />
      
      {/* WRAP EVERYTHING WITH GLOBAL WEBSOCKET PROVIDER */}
      <GlobalWebSocketProvider>
        <Routes>
          {/* Auth Routes */}
          <Route element={<AuthLayout />}>
            <Route
              path="/login"
              element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
            />
            <Route
              path="/signup"
              element={isAuthenticated ? <Navigate to="/" replace /> : <SignupPage />}
            />
          </Route>

          {/* Protected Routes — MainLayout is never swapped out for a loader,
              so the sidebar stays mounted and pages never double-render */}
          <Route
            path="/"
            element={
              isAuthenticated ? <MainLayout /> : <Navigate to="/login" replace />
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="monitoring" element={<MonitoringPage />} />
            <Route path="constitution" element={<ConstitutionPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="channels" element={<ChannelsPage />} />
            <Route
              path="sovereign"
              element={
                <SovereignRoute>
                  <SovereignDashboard />
                </SovereignRoute>
              }
            />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </GlobalWebSocketProvider>
    </Router>
  );
}