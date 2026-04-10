from __future__ import annotations

SCRIPT = """
function createGame(api){
  const s = SPEC.settings;
  let raf = 0, paused = false, startedAt = 0, lastSpawn = 0, score = 0;
  let player = null, pointer = {x: canvas.width / 2, y: canvas.height * 0.82}, keys = {l:false, r:false, u:false, d:false}, obstacles = [], pickups = [];
  function hit(a, b){ const dx = a.x - b.x, dy = a.y - b.y; return Math.hypot(dx, dy) < a.r + b.r; }
  function reset(){
    paused = false; startedAt = 0; lastSpawn = 0; score = 0;
    player = {x: canvas.width / 2, y: canvas.height * 0.82, r: 16}; obstacles = []; pickups = [];
    api.setScore(0); api.setStatus('进行中'); api.setExtra('生存 0s'); api.hide();
  }
  function spawn(now){
    if(now - lastSpawn < s.spawn) return;
    lastSpawn = now;
    obstacles.push({x: api.rand(40, canvas.width - 40), y: -20, r: api.rand(12, 28), vy: api.rand(3.2, 4.6) + score * 0.005, vx: api.rand(-0.9, 0.9)});
    if(Math.random() > 0.72) pickups.push({x: api.rand(40, canvas.width - 40), y: -12, r: 10, vy: api.rand(2.6, 3.6)});
  }
  function update(now){
    if(paused) return;
    if(!startedAt) startedAt = now;
    spawn(now);
    if(keys.l) player.x -= s.speed; if(keys.r) player.x += s.speed; if(keys.u) player.y -= s.speed; if(keys.d) player.y += s.speed;
    player.x += (pointer.x - player.x) * 0.08; player.y += (pointer.y - player.y) * 0.08;
    player.x = api.clamp(player.x, 20, canvas.width - 20); player.y = api.clamp(player.y, 20, canvas.height - 20);
    for(const o of obstacles){ o.x += o.vx; o.y += o.vy; if(hit(player, o)){ paused = true; api.setStatus('已结束'); api.show('闪避失败', '重新开始再冲更高生存时间。'); } }
    for(const p of pickups){ p.y += p.vy; if(hit(player, p)){ p.y = canvas.height + 50; score += 35; } }
    obstacles = obstacles.filter((o) => o.y < canvas.height + 40); pickups = pickups.filter((p) => p.y < canvas.height + 40);
    score = Math.max(score, Math.floor((now - startedAt) / 120)); api.setScore(score); api.setExtra('生存 ' + Math.floor((now - startedAt) / 1000) + 's');
  }
  function render(){
    api.backdrop();
    ctx.strokeStyle = P.line; ctx.lineWidth = 2; ctx.strokeRect(24, 24, canvas.width - 48, canvas.height - 48);
    pickups.forEach((p) => { ctx.fillStyle = P.accent2; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill(); });
    obstacles.forEach((o) => { ctx.fillStyle = P.danger; ctx.beginPath(); ctx.arc(o.x, o.y, o.r, 0, Math.PI * 2); ctx.fill(); });
    ctx.fillStyle = P.accent; ctx.beginPath(); ctx.arc(player.x, player.y, player.r, 0, Math.PI * 2); ctx.fill();
  }
  function loop(now){ update(now); render(); raf = requestAnimationFrame(loop); }
  window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    pointer = {x: (e.clientX - rect.left) * (canvas.width / rect.width), y: (e.clientY - rect.top) * (canvas.height / rect.height)};
  });
  return {
    start(){ cancelAnimationFrame(raf); reset(); loop(0); },
    restart(){ reset(); },
    pause(){ paused = !paused; api.setStatus(paused ? '暂停中' : '进行中'); paused ? api.show('暂停中', '空格或按钮继续。') : api.hide(); },
    onKey(key){ if(key === 'arrowleft' || key === 'a') keys.l = true; if(key === 'arrowright' || key === 'd') keys.r = true; if(key === 'arrowup' || key === 'w') keys.u = true; if(key === 'arrowdown' || key === 's') keys.d = true; },
    onKeyUp(key){ if(key === 'arrowleft' || key === 'a') keys.l = false; if(key === 'arrowright' || key === 'd') keys.r = false; if(key === 'arrowup' || key === 'w') keys.u = false; if(key === 'arrowdown' || key === 's') keys.d = false; }
  };
}
"""
