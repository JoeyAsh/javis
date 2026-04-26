import { useState, useEffect, useRef, useCallback } from 'react';
import type { ReactElement, ChangeEvent, KeyboardEvent } from 'react';
import { SEARCH_DEBOUNCE_MS } from '../../constants';
import type { SearchInputProps } from './SearchInput.types';

export function SearchInput({ value, onChange, onSearch }: SearchInputProps): ReactElement {
    // Local state drives the visible input — avoids a Redux round-trip on every keystroke.
    const [inputValue, setInputValue] = useState(value);
    const inputRef = useRef<HTMLInputElement>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Sync local state when the external value is cleared (e.g. Escape from parent).
    useEffect(() => {
        if (value === '') {
            setInputValue('');
        }
    }, [value]);

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    useEffect(() => {
        return () => {
            if (debounceRef.current !== null) {
                clearTimeout(debounceRef.current);
            }
        };
    }, []);

    const handleChange = useCallback(
        (e: ChangeEvent<HTMLInputElement>): void => {
            const next = e.target.value;
            setInputValue(next);
            // Notify parent of every keystroke (for controlled-value tracking).
            onChange(next);

            // Debounce: only onSearch (which updates Redux) fires after delay.
            if (debounceRef.current !== null) {
                clearTimeout(debounceRef.current);
            }
            debounceRef.current = setTimeout(() => {
                onSearch(next);
                debounceRef.current = null;
            }, SEARCH_DEBOUNCE_MS);
        },
        [onChange, onSearch],
    );

    const handleKeyDown = useCallback(
        (e: KeyboardEvent<HTMLInputElement>): void => {
            if (e.key === 'Escape') {
                if (debounceRef.current !== null) {
                    clearTimeout(debounceRef.current);
                    debounceRef.current = null;
                }
                setInputValue('');
                onChange('');
                onSearch('');
            }
            if (e.key === 'Enter') {
                if (debounceRef.current !== null) {
                    clearTimeout(debounceRef.current);
                    debounceRef.current = null;
                }
                onSearch(inputValue);
            }
        },
        [onChange, onSearch, inputValue],
    );

    return (
        <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="SEARCH SPOTIFY"
            aria-label="Search Spotify"
            className="w-full px-3 py-2 bg-transparent border border-[var(--border)] text-[var(--text)] placeholder-[var(--text-muted)] font-[var(--font)] text-[11px] tracking-widest outline-none focus:border-[var(--accent)] focus:shadow-[var(--glow)] transition-all duration-[var(--dur-fast)] mb-3 flex-shrink-0"
        />
    );
}

export default SearchInput;
