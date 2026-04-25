export interface ToggleProps {
    checked: boolean;
    onChange: (v: boolean) => void;
    label: string;
    description?: string;
}
