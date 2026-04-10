from __future__ import annotations

SCRIPT = """
function createGame(api){
  const s = SPEC.settings;
  let raf = 0, paused = false, mx = canvas.width / 2, left = false, right = false;
  let paddleX = 0, ball = null, bricks = [], score = 0, lives = 3;
  function resetRound(){
    paddleX = canvas.width / 2 - s.paddle / 2;
    ball = {x: canvas.width / 2, y: canvas.height - 78, vx: s.speed * (Math.random() > 0.5 ? 1 : -1), vy: -s.speed, r: 10};
    bricks = [];
    const gap = 10, bw = (canvas.width - 120 - (s.cols - 1) * gap) / s.cols, bh = 24;
    for(let row = 0; row < s.rows; row += 1){
      for(let col = 0; col < s.cols; col += 1){
        bricks.push({x: 60 + col * (bw + gap), y: 70 + row * (bh + gap), w: bw, h: bh, hp: row >= s.rows - 2 ? 2 : 1});
      }
    }
  }
  function reset(){
    paused = false; score = 0; lives = 3;
    api.setScore(0); api.setStatus('进行中'); api.setExtra('生命 ' + lives); api.hide();
    resetRound();
  }
  function render(){
    api.backdrop();
    ctx.fillStyle = P.accent; ctx.shadowBlur = 20; ctx.shadowColor = P.accent;
    ctx.fillRect(paddleX, canvas.height - 40, s.paddle, 16); ctx.shadowBlur = 0;
    bricks.forEach((b) => { if(b.hp <= 0) return; ctx.fillStyle = b.hp > 1 ? P.accent2 : P.accent; ctx.fillRect(b.x, b.y, b.w, b.h); });
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2); ctx.fill();
  }
  function update(){
    if(paused) return;
    if(left) paddleX -= 9;
    else if(right) paddleX += 9;
    else paddleX += (mx - s.paddle / 2 - paddleX) * 0.14;
    paddleX = api.clamp(paddleX, 20, canvas.width - s.paddle - 20);
    ball.x += ball.vx; ball.y += ball.vy;
    if(ball.x <= ball.r || ball.x >= canvas.width - ball.r) ball.vx *= -1;
    if(ball.y <= ball.r) ball.vy *= -1;
    if(ball.y >= canvas.height - ball.r){
      lives -= 1; api.setExtra('生命 ' + lives);
      if(lives <= 0){ paused = true; api.setStatus('已结束'); api.show('这局结束了', '点重新开始再来一轮。'); return; }
      resetRound(); return;
    }
    if(ball.y + ball.r >= canvas.height - 40 && ball.x >= paddleX && ball.x <= paddleX + s.paddle && ball.vy > 0){
      ball.vy = -Math.abs(ball.vy);
      ball.vx = ((ball.x - paddleX) / s.paddle - 0.5) * s.speed * 1.8;
    }
    for(const b of bricks){
      if(b.hp <= 0) continue;
      const hitX = ball.x + ball.r > b.x && ball.x - ball.r < b.x + b.w;
      const hitY = ball.y + ball.r > b.y && ball.y - ball.r < b.y + b.h;
      if(hitX && hitY){ b.hp -= 1; score += b.hp <= 0 ? 15 : 8; api.setScore(score); ball.vy *= -1; break; }
    }
    if(bricks.every((b) => b.hp <= 0)){ paused = true; api.setStatus('胜利'); api.show('漂亮', '砖墙已经清空，点重新开始继续。'); }
  }
  function loop(){ update(); render(); raf = requestAnimationFrame(loop); }
  window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    mx = (e.clientX - rect.left) * (canvas.width / rect.width);
  });
  window.addEventListener('keydown', (e) => { if(e.key === 'ArrowLeft') left = true; if(e.key === 'ArrowRight') right = true; });
  window.addEventListener('keyup', (e) => { if(e.key === 'ArrowLeft') left = false; if(e.key === 'ArrowRight') right = false; });
  return {
    start(){ cancelAnimationFrame(raf); reset(); loop(); },
    restart(){ reset(); },
    pause(){ paused = !paused; api.setStatus(paused ? '暂停中' : '进行中'); paused ? api.show('暂停中', '空格或按钮继续。') : api.hide(); }
  };
}
"""
