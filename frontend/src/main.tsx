import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { StoreProvider } from '@app';
import './styles/tokens.css';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
    throw new Error('Fatal: #root element not found in index.html');
}

ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
        <StoreProvider>
            <App />
        </StoreProvider>
    </React.StrictMode>,
);
