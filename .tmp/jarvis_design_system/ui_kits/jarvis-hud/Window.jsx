// Floating window wrapper + drag state
function Window({ id, title, x, y, w, h, focused, onFocus, children }) {
  const [pos, setPos] = React.useState({x, y});
  const drag = React.useRef(null);
  const onDown = (e) => {
    if (e.target.closest('.btn-x')) return;
    onFocus(id);
    const startX = e.clientX, startY = e.clientY, sx = pos.x, sy = pos.y;
    drag.current = { startX, startY, sx, sy };
    const move = (ev) => { const d = drag.current; setPos({ x: sx + ev.clientX - startX, y: sy + ev.clientY - startY }); };
    const up = () => { drag.current = null; window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  };
  return (
    <div className={"window " + (focused?'focused':'')} style={{ left:pos.x, top:pos.y, width:w, height:h }} onPointerDown={()=>onFocus(id)}>
      <span className="wc-bl" /><span className="wc-br" />
      <span className="wfx" />
      <span className="wtick t" /><span className="wtick b" />
      <span className="wrail l" /><span className="wrail r" />
      <div className="win-header" onPointerDown={onDown}>
        <span className="dot" />
        <span className="t">{title}</span>
        <span className="btns"><button className="btn-x">_</button><button className="btn-x">☐</button></span>
      </div>
      <div className="win-body">{children}</div>
    </div>
  );
}

Object.assign(window, { Window });
