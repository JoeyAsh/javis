// Re-export from new canonical location.
// vite.config.ts still references this file; Sub-Call 5 will update
// test.setupFiles to point directly to src/test/setup.ts.
import './test/setup';
