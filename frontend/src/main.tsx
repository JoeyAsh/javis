import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
// @app/providers avoids bare-alias Vite dev-cache failure; do not revert to '@app'.
import { AppProviders } from '@app/providers';
import './styles/tokens.css';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
    throw new Error('Fatal: #root element not found in index.html');
}

ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
        <AppProviders>
            <App />
        </AppProviders>
    </React.StrictMode>,
);
