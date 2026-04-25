import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { BrandMarkProps } from './BrandMark.types';

export function BrandMark({ sub = false, className }: BrandMarkProps): ReactElement {
    return (
        <div className={cx('flex flex-col items-center gap-[3px]', className)}>
            <span className="font-mono text-[9px] uppercase text-text-muted tracking-[6px]">
                J A R V I S
            </span>
            {sub && (
                <span className="font-mono text-[8px] uppercase text-text-muted tracking-[3px]">
                    MK XLII
                </span>
            )}
        </div>
    );
}

export default BrandMark;
