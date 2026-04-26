/**
 * Device feature types.
 *
 * DeviceInfoPayload mirrors the backend WS `device_info` message payload.
 * DeviceState is the Redux slice state shape.
 */

/**
 * Payload emitted by the backend on every WS connect inside the
 * per-connection initial-state push block.
 */
export interface DeviceInfoPayload {
    /** Sanitized device slug, e.g. "laptop-paps". */
    slug: string;
    /** OS platform string: "linux" | "darwin" | "win32". */
    platform: string;
    /** Raw value of socket.gethostname() before sanitization. */
    hostname: string;
}

/** Redux state for the device feature. */
export interface DeviceState {
    slug: string;
    platform: string;
    hostname: string;
    /** True once the first `device_info` WS message has been processed. */
    received: boolean;
}
