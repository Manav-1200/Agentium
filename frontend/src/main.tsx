import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { authService } from './services/auth';
import './index.css';

// Initialize authentication from stored token
authService.initAuth();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);