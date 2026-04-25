import type {
    CSSProperties,
    ReactNode,
    MouseEvent,
    Ref,
    PointerEventHandler,
} from 'react';

export interface PanelProps {
    ix?: ReactNode;
    title?: ReactNode;
    badge?: ReactNode;
    actions?: ReactNode;
    focused?: boolean;
    onFocus?: () => void;
    className?: string;
    style?: CSSProperties;
    children?: ReactNode;
    headerRef?: Ref<HTMLDivElement>;
    onHeaderPointerDown?: PointerEventHandler<HTMLDivElement>;
    onHeaderClick?: (e: MouseEvent<HTMLDivElement>) => void;
}
