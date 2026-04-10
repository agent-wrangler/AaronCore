from __future__ import annotations

SCRIPT = """
function createGame(api){
  const s = SPEC.settings, cell = 24, cols = Math.floor(canvas.width / cell), rows = Math.floor(canvas.height / cell);
  let raf = 0, paused = false, last = 0, dir = {x: 1, y: 0}, next = {x: 1, y: 0}, score = 0, snake = [], food = {x: 8, y: 8};
  function spawnFood(){
    while(true){
      const f = {x: Math.floor(Math.random() * cols), y: Math.floor(Math.random() * rows)};
      if(!snake.some((p) => p.x === f.x && p.y === f.y)){ food = f; return; }
    }
  }
  function reset(){
    paused = false; last = 0; dir = {x: 1, y: 0}; next = {x: 1, y: 0}; score = 0;
    snake = [{x: 6, y: 11}, {x: 5, y: 11}, {x: 4, y: 11}];
    spawnFood(); api.setScore(0); api.setStatus('进行中'); api.setExtra('长度 3'); api.hide();
  }
  function step(){
    dir = next;
    const head = {x: snake[0].x + dir.x, y: snake[0].y + dir.y};
    if(head.x < 0 || head.y < 0 || head.x >= cols || head.y >= rows || snake.some((p) => p.x === head.x && p.y === head.y)){
      paused = true; api.setStatus('已结束'); api.show('撞到了', '点重新开始马上重来。'); return;
    }
    snake.unshift(head);
    if(head.x === food.x && head.y === food.y){ score += 10; api.setScore(score); api.setExtra('长度 ' + snake.length); spawnFood(); }
    else { snake.pop(); }
  }
  function render(){
    api.backdrop();
    ctx.fillStyle = 'rgba(255,255,255,0.04)';
    for(let x = 0; x < cols; x += 1){ for(let y = 0; y < rows; y += 1){ ctx.fillRect(x * cell + 1, y * cell + 1, cell - 2, cell - 2); } }
    ctx.fillStyle = P.accent2; ctx.beginPath(); ctx.arc(food.x * cell + cell / 2, food.y * cell + cell / 2, cell * 0.3, 0, Math.PI * 2); ctx.fill();
    snake.forEach((p, i) => { ctx.fillStyle = i === 0 ? P.accent2 : P.accent; ctx.fillRect(p.x * cell + 3, p.y * cell + 3, cell - 6, cell - 6); });
  }
  function loop(ts){ if(!paused && ts - last >= s.tick){ last = ts; step(); } render(); raf = requestAnimationFrame(loop); }
  return {
    start(){ cancelAnimationFrame(raf); reset(); loop(0); },
    restart(){ reset(); },
    pause(){ paused = !paused; api.setStatus(paused ? '暂停中' : '进行中'); paused ? api.show('暂停中', '空格或按钮继续。') : api.hide(); },
    onKey(key){
      if((key === 'arrowup' || key === 'w') && dir.y !== 1) next = {x: 0, y: -1};
      if((key === 'arrowdown' || key === 's') && dir.y !== -1) next = {x: 0, y: 1};
      if((key === 'arrowleft' || key === 'a') && dir.x !== 1) next = {x: -1, y: 0};
      if((key === 'arrowright' || key === 'd') && dir.x !== -1) next = {x: 1, y: 0};
    }
  };
}
"""
