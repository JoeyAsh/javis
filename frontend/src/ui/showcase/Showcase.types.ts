export type NavGroup = 'TOKENS' | 'PRIMITIVES' | 'COMPOSITIONS' | 'DEV' | null;

export interface NavItem {
    id: string;
    label: string;
    group: NavGroup;
}
