import type { MailMessage } from '../../types';

export interface MailItemRowProps {
    message: MailMessage;
    onClick?: (message: MailMessage) => void;
}
