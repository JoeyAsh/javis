import { type ReactElement } from 'react';
import { AppProviders } from '@app';
import { AppShell } from '@app/shell/AppShell';
import { useAudioPlayback } from '@core/audio';

function AppInner(): ReactElement {
    useAudioPlayback(); // side-effect: drains the TTS queue
    return <AppShell />;
}

export function App(): ReactElement {
    return (
        <AppProviders>
            <AppInner />
        </AppProviders>
    );
}

export default App;
