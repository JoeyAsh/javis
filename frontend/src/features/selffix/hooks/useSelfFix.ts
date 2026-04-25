import { selfFixMock } from '../mock';
import type { UseSelfFixReturn } from './useSelfFix.types';

export function useSelfFix(): UseSelfFixReturn {
    return { entries: selfFixMock, loading: false };
}
