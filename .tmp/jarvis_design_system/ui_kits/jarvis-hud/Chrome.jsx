// TopBar + status tray + PTT
function TopBar({ idle, onIdle, onSettings, onTweaks }) {
  const [now, setNow] = React.useState(new Date());
  React.useEffect(()=>{ const id=setInterval(()=>setNow(new Date()),1000); return ()=>clearInterval(id); },[]);
  const time = now.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  const date = now.toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  return (
    <div className="topbar">
      <div className="infobar">
        <span className="brand-tag" style={{marginRight:8}}>J&nbsp;A&nbsp;R&nbsp;V&nbsp;I&nbsp;S</span>
        <b>{time}</b><span className="sep">·</span>
        <span>{date}</span><span className="sep">·</span>
        <span className="wx"><span className="glyph">☀</span>14°C Wien</span>
        <span className="sep">·</span>
        <span style={{color:'var(--success)'}}>● LINK</span>
        <span className="sep">·</span>
        <span>LAT 12ms</span>
      </div>
      <div className="tb-icons">
        <button className="icon-btn" onClick={onTweaks} title="Tweaks"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><line x1="8" y1="12" x2="16" y2="6"/><line x1="8" y1="12" x2="16" y2="18"/></svg></button>
        <button className="icon-btn" title="Reset"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg></button>
        <button className="icon-btn" onClick={onSettings} title="Settings"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></button>
        <button className={"icon-btn pill " + (idle?'':'on')} onClick={onIdle}>{idle?'IDLE':'LIVE'}</button>
      </div>
    </div>
  );
}

function StatusTray({ state }) {
  const labels = { idle:'', listening:'listening...', thinking:'thinking...', speaking:'speaking...' };
  const label = labels[state] ?? '';
  return (
    <div className="status-tray">
      <span className={"state " + (label?'on':'')}>{label}</span>
      <span className="brand">JARVIS  ·  MARK XLII</span>
    </div>
  );
}

function PTT({ state, onClick }) {
  const active = state === 'listening' || state === 'thinking';
  return (
    <button className={"ptt " + (active?'active':'')} onClick={onClick} aria-label="Push to talk">
      {active ? (
        <span className="wave"><i style={{height:10}}/><i style={{height:6}}/><i style={{height:14}}/><i style={{height:4}}/><i style={{height:12}}/><i style={{height:7}}/><i style={{height:9}}/></span>
      ) : (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
      )}
    </button>
  );
}

Object.assign(window, { TopBar, StatusTray, PTT });
