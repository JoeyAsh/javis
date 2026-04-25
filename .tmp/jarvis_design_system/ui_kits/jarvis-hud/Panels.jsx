// Panels: System, NowPlaying, Transcript, Lights, Notifications
function Sparkline({ values, color='var(--accent-bright)' }) {
  const w=100, h=24; const max = Math.max(...values,1); const step = w/Math.max(values.length-1,1);
  const pts = values.map((v,i)=>`${(i*step).toFixed(1)},${(h-(v/max)*h).toFixed(1)}`).join(' L ');
  const path = `M ${pts}`; const fill = `${path} L ${w},${h} L 0,${h} Z`;
  return <svg viewBox="0 0 100 24" preserveAspectRatio="none" style={{width:'100%',height:24,display:'block'}}>
    <path d={fill} fill={color} opacity={.15}/><path d={path} stroke={color} strokeWidth={1.2} fill="none"/>
  </svg>;
}

function useDrift(base, range=8) {
  const [v, setV] = React.useState(base);
  React.useEffect(()=>{ const id=setInterval(()=>{ setV(x => Math.max(0, Math.min(100, x + (Math.random()-.5)*range))); }, 1500); return ()=>clearInterval(id); },[]);
  return v;
}

function SystemPanel() {
  const cpu = useDrift(42), ram = useDrift(61), gpu = useDrift(18), temp = useDrift(62, 4), dn = useDrift(14,3), disk=useDrift(58, 1);
  const [hist, setHist] = React.useState({ cpu:[30,35,42,40,45,42,48,50,42,42], ram:[58,60,62,61,60,62,63,61,60,61], gpu:[10,15,12,20,18,22,18,20,18,18], temp:[58,60,62,61,63,64,62,60,62,62], net:[8,12,14,11,13,14,15,13,14,14], disk:[57,58,58,57,58,58,59,58,58,58] });
  React.useEffect(()=>{ const id=setInterval(()=>{ setHist(h => ({ cpu:[...h.cpu.slice(1),cpu], ram:[...h.ram.slice(1),ram], gpu:[...h.gpu.slice(1),gpu], temp:[...h.temp.slice(1),temp], net:[...h.net.slice(1),dn], disk:[...h.disk.slice(1),disk]})); }, 1500); return ()=>clearInterval(id); },[cpu,ram,gpu,temp,dn,disk]);
  const tiles = [
    {id:'cpu', label:'CPU', unit:'%', val:cpu, hist:hist.cpu},
    {id:'ram', label:'RAM', unit:'%', val:ram, hist:hist.ram},
    {id:'gpu', label:'GPU', unit:'%', val:gpu, hist:hist.gpu},
    {id:'temp', label:'CPU TEMP', unit:'°C', val:temp, hist:hist.temp, warn: temp>70},
    {id:'net', label:'NET', unit:'Mb/s', val:dn, hist:hist.net},
    {id:'disk', label:'DISK', unit:'%', val:disk, hist:hist.disk},
  ];
  return <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:10}}>
    {tiles.map(t=><div key={t.id} className={"tile "+(t.warn?'warn':'')}>
      <div className="hd"><span className="lb">{t.label}</span><span className="vl">{t.val.toFixed(t.unit==='Mb/s'?1:0)}<small>{t.unit}</small></span></div>
      <Sparkline values={t.hist} color={t.warn?'var(--warning)':'var(--accent-bright)'}/>
    </div>)}
  </div>;
}

function TranscriptPanel({ turns }) {
  const ref = React.useRef(null);
  React.useEffect(()=>{ if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [turns]);
  return <div ref={ref} style={{height:'100%', overflowY:'auto'}}>{turns.map(t=>(
    <div key={t.id} className={"turn "+t.role} style={{display:'flex',flexDirection:'column',alignItems:t.role==='user'?'flex-end':'flex-start'}}>
      <div className="meta">{t.role==='user'?'YOU':'JARVIS'} · {t.time}</div>
      <div className="body">{t.text}</div>
    </div>
  ))}</div>;
}

function NowPlayingPanel() {
  const [playing, setPlaying] = React.useState(true);
  const [prog, setProg] = React.useState(102);
  const dur = 238;
  React.useEffect(()=>{ if (!playing) return; const id=setInterval(()=>setProg(p=>(p+1)%dur),1000); return ()=>clearInterval(id); },[playing]);
  const fmt = s => `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
  return <>
    <div style={{display:'flex',gap:10,marginBottom:8}}>
      <div className="art">AC/DC</div>
      <div style={{minWidth:0,flex:1}}>
        <div style={{fontSize:12,color:'var(--text)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>Thunderstruck</div>
        <div style={{fontSize:10,color:'var(--text-secondary)'}}>AC/DC</div>
        <div style={{fontSize:9,color:'var(--text-muted)',letterSpacing:1,textTransform:'uppercase',marginTop:2}}>The Razors Edge</div>
      </div>
    </div>
    <div className="bar"><div className="fill" style={{width:(prog/dur*100)+'%'}}/></div>
    <div style={{display:'flex',justifyContent:'space-between',fontSize:9,color:'var(--text-muted)',letterSpacing:1}}><span>{fmt(prog)}</span><span>{fmt(dur)}</span></div>
    <div style={{display:'flex',justifyContent:'center',gap:8,marginTop:10}}>
      <button className="tbtn"><svg viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4"/><rect x="5" y="5" width="2" height="14"/></svg></button>
      <button className="tbtn primary" onClick={()=>setPlaying(p=>!p)}>{playing ? <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> : <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21"/></svg>}</button>
      <button className="tbtn"><svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20"/><rect x="17" y="5" width="2" height="14"/></svg></button>
    </div>
  </>;
}

function LightsPanel() {
  const [lights, setLights] = React.useState([
    {id:'lab',name:'Workshop',on:true},
    {id:'kit',name:'Kitchen',on:false},
    {id:'liv',name:'Living',on:true},
    {id:'bed',name:'Bedroom',on:false},
    {id:'ext',name:'Exterior',on:true},
    {id:'drw',name:'Driveway',on:false},
  ]);
  const toggle = (id) => setLights(L => L.map(l => l.id===id?{...l,on:!l.on}:l));
  return <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6}}>
    {lights.map(l=>(
      <div key={l.id} className={"light "+(l.on?'on':'')} onClick={()=>toggle(l.id)}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><span className="nm">{l.name}</span><span className="bulb"/></div>
        <div style={{fontSize:8,letterSpacing:1,color:'var(--text-muted)'}}>{l.on?'ON · 72%':'OFF'}</div>
      </div>
    ))}
  </div>;
}

function NotificationsPanel() {
  const items = [
    {nm:'GitLab', ti:'09:02', tx:'MR #428 merged to main — jarvis-frontend', t:'info'},
    {nm:'Mail',   ti:'08:47', tx:'3 new messages · 1 flagged priority', t:'info'},
    {nm:'System', ti:'08:33', tx:'CPU temp crossed 85°C — fan curve adjusted', t:'warn'},
    {nm:'Spotify', ti:'08:21', tx:'Queue refreshed from morning mix', t:'info'},
    {nm:'Calendar', ti:'07:58', tx:'Board meeting in 3 hours · conf room 4', t:'info'},
  ];
  return <div>{items.map((n,i)=>(
    <div key={i} className={"notif "+(n.t==='warn'?'warn':'')}>
      <div style={{flex:1}}>
        <div style={{display:'flex',alignItems:'baseline'}}><span className="nm">{n.nm}</span><span className="ti">{n.ti}</span></div>
        <div className="tx">{n.tx}</div>
      </div>
    </div>
  ))}</div>;
}

function AgendaPanel() {
  const ev = [
    {t:'11:00', s:'Board Meeting', d:'Conf · R4 · 1h'},
    {t:'14:00', s:'Design Review', d:'Mark XLII HUD · 45min'},
    {t:'16:30', s:'Suit Test — Maria', d:'Workshop · 2h'},
    {t:'19:00', s:'Dinner w/ Pepper', d:'The Lighthouse · 19th'},
  ];
  return <>{ev.map((e,i)=>(
    <div key={i} style={{display:'flex',gap:10,padding:'5px 0',borderBottom:'1px dashed var(--border)'}}>
      <div style={{width:36,flexShrink:0}}><div style={{fontSize:11,color:'var(--accent-bright)',fontVariantNumeric:'tabular-nums'}}>{e.t}</div></div>
      <div style={{flex:1}}>
        <div style={{fontSize:11,color:'var(--text)'}}>{e.s}</div>
        <div style={{fontSize:9,color:'var(--text-muted)',letterSpacing:1,textTransform:'uppercase',marginTop:1}}>{e.d}</div>
      </div>
    </div>
  ))}</>;
}

Object.assign(window, { SystemPanel, TranscriptPanel, NowPlayingPanel, LightsPanel, NotificationsPanel, AgendaPanel, Sparkline });
