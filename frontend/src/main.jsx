import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.jsx';
import AppErrorBoundary from './AppErrorBoundary.jsx';
import './index.css';
import './datasources.css';
createRoot(document.getElementById('root')).render(<React.StrictMode><AppErrorBoundary><App/></AppErrorBoundary></React.StrictMode>);
