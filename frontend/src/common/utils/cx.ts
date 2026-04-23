export type ClassValue =
    | string
    | number
    | false
    | null
    | undefined
    | Record<string, boolean>
    | ClassValue[];

/**
 * Lightweight classnames helper. Accepts strings, numbers, objects, arrays,
 * and falsy values. No external dependencies.
 *
 * @example
 * cx('foo', condition && 'bar', { baz: true, qux: false })
 * // => "foo bar baz"
 */
export function cx(...args: ClassValue[]): string {
    const classes: string[] = [];

    for (const arg of args) {
        if (!arg && arg !== 0) continue;

        if (typeof arg === 'string' || typeof arg === 'number') {
            classes.push(String(arg));
        } else if (Array.isArray(arg)) {
            const inner = cx(...arg);
            if (inner) classes.push(inner);
        } else if (typeof arg === 'object') {
            for (const key of Object.keys(arg)) {
                if (arg[key]) classes.push(key);
            }
        }
    }

    return classes.join(' ');
}
