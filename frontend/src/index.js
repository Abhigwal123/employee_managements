import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

console.log('[TRACE] Initializing React application...');

// Verify root element exists
const rootElement = document.getElementById('root');
if (!rootElement) {
  console.error('[ERROR] Root element not found!');
  document.body.innerHTML = '<div style="padding: 20px; color: red;">Error: Root element not found!</div>';
} else {
  console.log('[TRACE] Root element found, rendering App...');
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
