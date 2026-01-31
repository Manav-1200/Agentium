import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from '@/store/authStore';
import { MainLayout } from '@/components/layout/MainLayout';
import { LoginPage } from '@/pages/LoginPage';
import { Dashboard } from '@/pages/Dashboard';
import { SettingsPage } from '@/pages/SettingsPage';
import { ChatPage } from '@/pages/ChatPage';

// Placeholder pages for routes
function AgentsPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">Agents</h1>
      <p className="text-gray-600 dark:text-gray-400">Agent management interface coming soon...</p>
    </div>
  );
}

function TasksPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">Tasks</h1>
      <p className="text-gray-600 dark:text-gray-400">Task management interface coming soon...</p>
    </div>
  );
}

function ConstitutionPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">Constitution</h1>
      <p className="text-gray-600 dark:text-gray-400">Constitution viewer coming soon...</p>
    </div>
  );
}

function ModelsPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">AI Models</h1>
      <p className="text-gray-600 dark:text-gray-400">Model configuration interface coming soon...</p>
    </div>
  );
}

export default function App() {
  const { user } = useAuthStore();

  return (
    <Router>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          className: 'dark:bg-gray-800 dark:text-white'
        }}
      />

      <Routes>
        <Route
          path="/login"
          element={!user?.isAuthenticated ? <LoginPage /> : <Navigate to="/" replace />}
        />

        <Route
          path="/"
          element={user?.isAuthenticated ? <MainLayout /> : <Navigate to="/login" replace />}
        >
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="constitution" element={<ConstitutionPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}