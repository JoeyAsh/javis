// Orb + scene backdrop
function Orb({ state }) {
  const className = 'orb-core' + (state === 'speaking' ? ' speaking' : '') + (state === 'thinking' ? ' thinking' : '');
  return (
    <div className="orb-wrap">
      <div className="ring r4" />
      <div className="ring r3" />
      <div className="ring r2"><i /><i /></div>
      <div className="ring r1" />
      {state === 'listening' && <>
        <div className="pulse listening" />
        <div className="pulse listening delay" />
      </>}
      <div className={className} />
      {Array.from({length:6}).map((_,i)=>(
        <Particle key={i} i={i} />
      ))}
    </div>
  );
}

function Particle({ i }) {
  const [t, setT] = React.useState(0);
  React.useEffect(()=>{ const id = setInterval(()=>setT(x=>x+1), 16); return ()=>clearInterval(id); }, []);
  const baseR = 180 + (i%3)*40;
  const speed = 0.008 + i*0.0014;
  const angle = t*speed + i*1.04;
  const x = Math.cos(angle)*baseR;
  const y = Math.sin(angle)*baseR*0.5;
  return <div className="particle" style={{ transform:`translate(${x}px, ${y}px)`, opacity: 0.5 + 0.5*Math.sin(angle*2)}} />;
}

function Scene() {
  return <>
    <div className="scene" />
    <div className="reactor-base" />
    <div className="vignette" />
    <div className="hud-fr tl" /><div className="hud-fr tr" /><div className="hud-fr bl" /><div className="hud-fr br" />
  </>;
}

Object.assign(window, { Orb, Scene, Particle });
