// Settings overlay + Tweaks panel
function Settings({ open, onClose, voice, setVoice, orbHue, setOrbHue, density, setDensity, scanlines, setScanlines }) {
  if (!open) return null;
  return <div className="overlay" onClick={onClose}>
    <div className="modal" onClick={e=>e.stopPropagation()}>
      <h2>System Settings</h2>
      <div className="sub">Mark XLII · Core Parameters</div>
      <div className="field">
        <label>Voice Profile</label>
        <div className="seg">
          {['Standard','Formal','Casual'].map(v=>(
            <button key={v} className={voice===v?'active':''} onClick={()=>setVoice(v)}>{v}</button>
          ))}
        </div>
      </div>
      <div className="field">
        <label>Orb Hue <span className="val">{orbHue}°</span></label>
        <input type="range" min="180" max="260" value={orbHue} onChange={e=>setOrbHue(+e.target.value)}/>
      </div>
      <div className="field">
        <label>HUD Density <span className="val">{density}</span></label>
        <div className="seg">
          {['Minimal','Standard','Dense'].map(v=>(
            <button key={v} className={density===v?'active':''} onClick={()=>setDensity(v)}>{v}</button>
          ))}
        </div>
      </div>
      <div className="field">
        <label>Scanlines</label>
        <div className="seg">
          <button className={scanlines?'active':''} onClick={()=>setScanlines(true)}>On</button>
          <button className={!scanlines?'active':''} onClick={()=>setScanlines(false)}>Off</button>
        </div>
      </div>
      <div style={{display:'flex',justifyContent:'flex-end',gap:8,marginTop:10}}>
        <button className="icon-btn pill" onClick={onClose}>CLOSE</button>
      </div>
    </div>
  </div>;
}

function Tweaks({ open, tweaks, setTweaks }) {
  const set = (k,v) => setTweaks(t => ({...t, [k]:v}));
  return <div className={"tweaks "+(open?'open':'')}>
    <h3>Tweaks</h3>
    <div className="f">
      <label>Accent Hue <span className="val">{tweaks.hue}°</span></label>
      <input type="range" min="180" max="280" value={tweaks.hue} onChange={e=>set('hue',+e.target.value)}/>
      <div className="swatches">
        {[200,215,260,300,20].map(h=>(
          <div key={h} className={"sw "+(tweaks.hue===h?'active':'')} style={{background:`oklch(0.72 0.18 ${h})`}} onClick={()=>set('hue',h)}/>
        ))}
      </div>
    </div>
    <div className="f">
      <label>Grid Density <span className="val">{tweaks.grid}px</span></label>
      <input type="range" min="24" max="96" step="12" value={tweaks.grid} onChange={e=>set('grid',+e.target.value)}/>
    </div>
    <div className="f">
      <label>Orb Glow <span className="val">{tweaks.glow}</span></label>
      <input type="range" min="0" max="100" value={tweaks.glow} onChange={e=>set('glow',+e.target.value)}/>
    </div>
    <div className="f">
      <label>Scanlines</label>
      <div className="seg" style={{marginTop:4}}>
        <button className={tweaks.scan?'active':''} onClick={()=>set('scan',true)}>On</button>
        <button className={!tweaks.scan?'active':''} onClick={()=>set('scan',false)}>Off</button>
      </div>
    </div>
    <div className="f">
      <label>Idle Dim</label>
      <div className="seg" style={{marginTop:4}}>
        <button className={tweaks.idleDim?'active':''} onClick={()=>set('idleDim',true)}>On</button>
        <button className={!tweaks.idleDim?'active':''} onClick={()=>set('idleDim',false)}>Off</button>
      </div>
    </div>
  </div>;
}

Object.assign(window, { Settings, Tweaks });
