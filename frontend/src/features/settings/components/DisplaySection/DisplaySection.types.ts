import type { OrbStyle } from '../../types';

export interface DisplaySectionProps {
    panelOpacity: number;
    onPanelOpacityChange: (v: number) => void;
    orbStyle: OrbStyle;
    onOrbStyleChange: (v: OrbStyle) => void;
}
