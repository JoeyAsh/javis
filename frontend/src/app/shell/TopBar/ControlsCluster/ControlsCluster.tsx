import type { ReactElement } from 'react';
import { Crosshair, Mic, MicOff, RotateCcw, Settings, Volume2, VolumeX } from 'lucide-react';
import { Button, Icon } from '@ui';
import styles from '../TopBar.module.css';
import type { ControlsClusterProps } from './ControlsCluster.types';

export function ControlsCluster({
    idle,
    onToggleIdle,
    onResetLayout,
    onOpenSettings,
    micMuted,
    onToggleMicMute,
    sfxMuted,
    onToggleSfxMute,
}: ControlsClusterProps): ReactElement {
    return (
        <div className={styles.right}>
            <Button
                variant="ghost"
                size="sm"
                aria-label={idle ? 'Exit idle mode (Ctrl+.)' : 'Enter idle mode (Ctrl+.)'}
                onClick={onToggleIdle}
                className={`${styles.iconBtn}${idle ? ` ${styles.iconBtnActive}` : ''}`}
            >
                <Icon icon={Crosshair} size="sm" aria-hidden="true" />
            </Button>
            <Button
                variant="ghost"
                size="sm"
                aria-label="Reset layout"
                onClick={onResetLayout}
                className={styles.iconBtn}
            >
                <Icon icon={RotateCcw} size="sm" aria-hidden="true" />
            </Button>
            <Button
                variant="ghost"
                size="sm"
                aria-label={micMuted ? 'Unmute microphone' : 'Mute microphone'}
                onClick={onToggleMicMute}
                className={`${styles.iconBtn}${micMuted ? ` ${styles.iconBtnActive}` : ''}`}
            >
                <Icon icon={micMuted ? MicOff : Mic} size="sm" aria-hidden="true" />
            </Button>
            <Button
                variant="ghost"
                size="sm"
                aria-label={sfxMuted ? 'Unmute sound effects' : 'Mute sound effects'}
                onClick={onToggleSfxMute}
                className={`${styles.iconBtn}${sfxMuted ? ` ${styles.iconBtnActive}` : ''}`}
            >
                <Icon icon={sfxMuted ? VolumeX : Volume2} size="sm" aria-hidden="true" />
            </Button>
            <Button
                variant="ghost"
                size="sm"
                aria-label="Open settings"
                onClick={onOpenSettings}
                className={styles.iconBtn}
            >
                <Icon icon={Settings} size="sm" aria-hidden="true" />
            </Button>
        </div>
    );
}

export default ControlsCluster;
