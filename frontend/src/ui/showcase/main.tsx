import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../../styles/tokens.css';
import '../../index.css';
import '../ui.css';
import { Showcase } from './Showcase';
import { ShowcaseSfxRoot } from './ShowcaseSfxRoot';

// The main app sets overflow:hidden on body/html to prevent scroll.
// Showcase is a long-form page — restore normal scroll here.
document.documentElement.style.overflow = 'auto';
document.body.style.overflow = 'auto';

const el = document.getElementById('showcase-root');
if (!el) throw new Error('Missing #showcase-root');

// The #root style in index.css sets h/w 100% which clips. Reset for showcase.
el.style.height = 'auto';
el.style.overflow = 'visible';

createRoot(el).render(
    <StrictMode>
        <ShowcaseSfxRoot>
            <Showcase />
        </ShowcaseSfxRoot>
    </StrictMode>,
);
