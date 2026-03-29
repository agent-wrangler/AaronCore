// === 统计页驾驶舱 ===
function fmtN(n){if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e4)return(n/1e3).toFixed(1)+'K';return n.toLocaleString();}

var PRICE={'deepseek':{i:1,o:2},'minimax':{i:1,o:8},'qwen':{i:2,o:6},'glm':{i:1,o:1}};
function getPrice(model){var m=(model||'').toLowerCase();for(var k in PRICE){if(m.indexOf(k)!==-1)return PRICE[k];}return{i:2,o:4};}

// 顶部4个摘要卡
function buildSummaryCards(s,costYuan,cacheRate,compositeRate,topScene){
  var h='<div class="stats-summary">';
  // 1.成本概览
  var costHint=costYuan<1?t('dash.cost.low'):t('dash.cost.ok');
  var costCls='';
  if(costYuan>10){costHint=t('dash.cost.high');costCls=' warn';}
  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.cost')+'</div>';
  h+='<div class="stats-summary-value">\u00a5'+costYuan.toFixed(2)+'</div>';
  h+='<div class="stats-summary-hint'+costCls+'">'+costHint+'</div></div>';
  // 2.Tokens 吞吐
  var totalTk=s.total_tokens||0;
  var inpTk=s.input_tokens||0;
  var inPct=totalTk>0?Math.round(inpTk/totalTk*100):0;
  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.tokens')+'</div>';
  h+='<div class="stats-summary-value">'+fmtN(totalTk)+'</div>';
  h+='<div class="stats-summary-hint">'+t('dash.input.pct')+' '+inPct+'%</div></div>';
  // 3.记忆深度
  var memHint=compositeRate>=50?t('dash.mem.good'):t('dash.mem.growing');
  var memCls=compositeRate<30?' warn':'';
  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.mem.eff')+'</div>';
  h+='<div class="stats-summary-value">'+compositeRate+'%</div>';
  h+='<div class="stats-summary-hint'+memCls+'">'+memHint+'</div></div>';
  // 4.平均单次
  var totalReq=s.total_requests||0;
  var avgCost=totalReq>0?(costYuan/totalReq):0;
  var avgHint=totalReq>0?tf('dash.total.conv',totalReq):t('dash.no.conv');
  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.avg')+'</div>';
  h+='<div class="stats-summary-value">\u00a5'+avgCost.toFixed(4)+'</div>';
  h+='<div class="stats-summary-hint">'+avgHint+'</div></div>';
  h+='</div>';
  return h;
}

// 运行成本模块（三段式费用 + 平均维度）
function buildCostModule(s,pr,costYuan){
  var inp=s.input_tokens||0, out=s.output_tokens||0, total=s.total_tokens||0;
  var totalReq=s.total_requests||0;
  var cw=s.cache_write_tokens||0, cr=s.cache_read_tokens||0;
  var costNew=cw*pr.i/1e6, costCache=cr*pr.i*0.1/1e6, costOut=out*pr.o/1e6;
  var saved=cr*pr.i*0.9/1e6;
  var avgCost=totalReq>0?(costYuan/totalReq):0;
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.cost.title')+'</div>';
  h+='<div class="stats-module"><div class="stats-cost-grid">';
  // 左主区：三段式费用
  h+='<div class="stats-cost-main">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.input')+'</span><span style="font-weight:600;">¥'+costNew.toFixed(3)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.cache')+'</span><span style="font-weight:600;color:#6a9fd8;">¥'+costCache.toFixed(4)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.output')+'</span><span style="font-weight:600;">¥'+costOut.toFixed(4)+'</span></div>';
  h+='<div class="stats-kv-mini" style="margin-top:4px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.04);"><span class="stats-kv-label">'+t('dash.cost.total')+'</span><span style="font-weight:700;color:#6aaa88;">¥'+costYuan.toFixed(2)+'</span></div>';
  if(saved>0){h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.saved')+'</span><span style="font-weight:600;color:#6aaa88;">¥'+saved.toFixed(4)+'</span></div>';}
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.avg')+'</span><span style="font-weight:600;">¥'+avgCost.toFixed(4)+'</span></div>';
  h+='</div>';
  // 右辅区：平均维度
  var avgInp=totalReq>0?Math.round(inp/totalReq):0;
  var avgOut=totalReq>0?Math.round(out/totalReq):0;
  var inPct=total>0?Math.round(inp/total*100):0;
  h+='<div class="stats-cost-sub">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.requests')+'</span><span>'+totalReq.toLocaleString()+t('dash.cost.times')+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.totalTokens')+'</span><span>'+fmtN(total)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.inputTokens')+'</span><span>'+fmtN(cw)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.cacheTokens')+'</span><span>'+fmtN(cr)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.outputTokens')+'</span><span>'+fmtN(out)+' tokens</span></div>';
  h+='<div class="stats-kv-mini" style="margin-top:4px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.04);"><span class="stats-kv-label">'+t('dash.cost.avgInput')+'</span><span>'+fmtN(avgInp)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.avgOutput')+'</span><span>'+avgOut+' tokens</span></div>';
  h+='</div></div>';
  h+='</div></div>';
  return h;
}

// 主渲染入口
function renderStats(s){
  var bs=s.by_scene||{};
  var _pr=s.prices||getPrice(s.model);
  var pr={i:_pr.i||_pr.input||2,o:_pr.o||_pr.output||4};
  var cHit=s.cache_read_tokens||0;var cMiss=(s.input_tokens||0)-cHit;var costYuan=(Math.max(0,cMiss)*pr.i+cHit*pr.i*0.1+(s.output_tokens||0)*pr.o)/1e6;
  var cacheRead=s.cache_read_tokens||0;
  var cacheRate=(s.input_tokens||0)>0?Math.round(cacheRead/(s.input_tokens||1)*100):0;
  var mem=s.memory||{};
  var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
  var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
  var tq=mem.total_queries||0,fla=mem.full_layer_available||0;
  var fullPct=tq>0?Math.round(fla/(tq*4)*100):0;
  var searchHits=l2h+l8h,searchTotal=l2s+l8s;
  var searchPct=searchTotal>0?Math.round(searchHits/searchTotal*100):0;
  var compositeRate=tq>0?Math.min(100,Math.round((fullPct+searchPct)/2)):0;
  var scenes=[{k:'chat',n:t('dash.scene.chat')},{k:'route',n:t('dash.scene.route')},{k:'skill',n:t('dash.scene.skill')},{k:'learn',n:t('dash.scene.learn')}];
  var topScene=t('dash.scene.chat'),topVal=0;
  scenes.forEach(function(sc){var t=(bs[sc.k]||{}).tokens||0;if(t>topVal){topVal=t;topScene=sc.n;}});

  var h='';
  h+=buildSummaryCards(s,costYuan,cacheRate,compositeRate,topScene);
  h+=buildCostModule(s,pr,costYuan);
  h+=buildModelModule(s);
  h+=buildMemoryModule(s);
  h+=buildSceneModule(s);
  h+=buildTrendModule(s);
  h+=buildDiagModule(s);
  h+='<div class="stats-footer"><div class="stats-footer-info">'+t('dash.lastUsed')+'：'+(s.last_used||'-')+'</div></div>';
  return h;
}

// 模型消耗分布
function buildModelModule(s){
  var bm=s.by_model||{};var ap=s.all_prices||{};
  var keys=Object.keys(bm);
  if(keys.length===0) return '';
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.model.title','模型消耗分布')+'</div>';
  h+='<div class="stats-module">';
  var totalT=0;keys.forEach(function(k){totalT+=(bm[k].input||0)+(bm[k].output||0);});
  keys.sort(function(a,b){return((bm[b].input||0)+(bm[b].output||0))-((bm[a].input||0)+(bm[a].output||0));});
  var colors=['#6aaa88','#6a9fd8','#c4a35a','#b07cc6','#d4726a'];
  keys.forEach(function(k,idx){
    var m=bm[k],inp=m.input||0,out=m.output||0,req=m.requests||0,tk=inp+out;
    var pct=totalT>0?Math.round(tk/totalT*100):0;
    var mp=null;for(var pk in ap){if(k.indexOf(pk)!==-1){mp=ap[pk];break;}}
    if(!mp)mp={input:2,output:4};
    var cost=(inp*mp.input+out*mp.output)/1e6;
    var clr=colors[idx%colors.length];
    h+='<div class="stats-model-row">';
    h+='<div class="stats-model-name">';
    h+='<span style="width:8px;height:8px;border-radius:50%;background:'+clr+';flex-shrink:0;display:inline-block;"></span>';
    h+='<span>'+k+'</span></div>';
    h+='<div class="stats-model-track"><div style="width:'+Math.max(pct,3)+'%;height:100%;border-radius:3px;background:'+clr+';"></div></div>';
    h+='<div class="stats-model-data">'+pct+'% · ¥'+cost.toFixed(2)+' · '+req+t('dash.cost.times')+'</div>';
    h+='</div>';
  });
  h+='</div></div>';
  return h;
}

// 记忆引擎模块
function buildMemoryModule(s){
  var mem=s.memory||{};
  var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
  var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
  var tq=mem.total_queries||0;
  var l2rate=l2s>0?Math.round(l2h/l2s*100):0;
  var l8rate=l8s>0?Math.round(l8h/l8s*100):0;
  var l1pct=Math.min(100,Math.round((mem.l1_count||0)/30*100));
  var l3q=mem.l3_queries||0, l3h_=mem.l3_hits||0;
  var l4q=mem.l4_queries||0, l4h_=mem.l4_hits||0;
  var l5q=mem.l5_queries||0, l5h_=mem.l5_hits||0;
  var l3rate=l3q>0?Math.round(l3h_/l3q*100):0;
  var l4rate=l4q>0?Math.round(l4h_/l4q*100):0;
  var l5rate=l5q>0?Math.round(l5h_/l5q*100):0;
  var l6rate=tq>0?Math.round((mem.l6_hits||0)/tq*100):0;
  var l7rate=tq>0?Math.round((mem.l7_hits||0)/tq*100):0;
  var l4Mode=String(mem.real_l4_active_mode||'default');
  var l4RuleCount=mem.real_l4_rule_count||0;
  var l4ProfileCount=mem.real_l4_profile_count||0;
  var l4ToneCount=mem.real_l4_tone_count||0;
  var l4ParticleCount=mem.real_l4_particle_count||0;
  var l4AvoidCount=mem.real_l4_avoid_count||0;
  var l4StylePrompt=mem.real_l4_style_prompt||0;
  var l4RecentUpdates=mem.real_l4_recent_updates||0;
  var l4StyleSignal=Math.min(100,
    l4ToneCount*10+
    l4ParticleCount*6+
    l4AvoidCount*4+
    (l4StylePrompt?12:0)+
    Math.min(l4RuleCount,8)*4+
    Math.min(l4ProfileCount,10)*3+
    Math.min(l4RecentUpdates,5)*8+
    (mem.l4_available?8:0)
  );

  // ── 三维指标计算 ──────────────────────────────────────────
  var baseTone   = mem.l4_available ? Math.round(l1pct*0.35 + l4StyleSignal*0.65) : l1pct;
  var cogDepth   = Math.round((l2rate+l3rate+l8rate)/3);
  var neuralKin  = Math.round((l5rate+l6rate+l7rate)/3);
  var compositeRate = Math.round((baseTone+cogDepth+neuralKin)/3);

  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.mem.title')+'</div>';
  h+='<div class="stats-module">';

  // ── 三维指标卡片 ──────────────────────────────────────────
  var baseCls  = baseTone < 90 ? ' warn' : '';
  var depthCls = cogDepth < 15 ? ' amber' : '';
  var kinCls   = neuralKin === 0 ? ' amber' : '';

  // 认知基调：状态名 + 文案
  var baseState, baseTxt;
  if(!mem.l4_available){ baseState='积累中'; baseTxt='L4 还没真正接入当前轮状态'; }
  else if(baseTone>=98){ baseState='完美同步'; baseTxt='基底频率锁定中，核心人格共鸣率'+baseTone+'%'; }
  else if(baseTone>=90){ baseState='轻微相移'; baseTxt='当前模式：'+l4Mode+' · 规则 '+l4RuleCount+' 条 · 最近7天更新 '+l4RecentUpdates+' 次'; }
  else{ baseState='需要对齐'; baseTxt='L4 丰富度还在堆积：当前模式 '+l4Mode+'，语气信号 '+l4StyleSignal+'%'; }

  // 思维厚度：状态名 + 文案
  var depthState, depthTxt;
  if(cogDepth>45){ depthState='深度扩张'; depthTxt='深层记忆链路活跃，思维密度：扩张'; }
  else if(cogDepth>=15){ depthState='记忆共振'; depthTxt='记忆链路共振，多维经历涌现中'; }
  else if(cogDepth>0){ depthState='浅层触发'; depthTxt='记忆深度待积累，维持即时响应'; }
  else{ depthState='尚未探索'; depthTxt='思维留白，深海尚未探索'; }

  // 神经动能：状态名 + 文案
  var kinState, kinTxt;
  if(neuralKin>20){ kinState='高能演化'; kinTxt='方法经验已开始沉淀，L7 纠偏力矩稳定'; }
  else if(neuralKin>=5){ kinState='常规运行'; kinTxt='神经动能低速运行，状态稳定'; }
  else if(neuralKin>0){ kinState='初始化中'; kinTxt='执行轨迹开始累积，等待更多神经脉冲'; }
  else{ kinState='静息状态'; kinTxt='静态闭环，等待动作触发'; }

  // 视觉含义（tooltip）
  var baseTip  = '大脑的「背景辐射」。L1 对话或 L4 人格出现波动时，稳定性随之下降。';
  var depthTip = '系统正在进行「深海打捞」。数值越高，这次回复的知识负担与回溯深度越重。';
  var kinTip   = '系统的「应变储备」。L5/L6 是对外执行，L7 是对内自省与纠偏，三层共同决定面对复杂需求时的响应能力。';

  h+='<div class="stats-brain-dims">';

  // 认知基调
  h+='<div class="stats-brain-dim'+baseCls+'">';
  h+='<div class="stats-brain-dim-header">';
  h+='<span class="stats-brain-dim-name">认知基调</span>';
  h+='<span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+baseTip+'</span></span>';
  h+='</div>';
  h+='<div class="stats-brain-dim-en">Base Tone</div>';
  h+='<div class="stats-brain-dim-val'+baseCls+'">'+baseTone+'%</div>';
  h+='<div class="stats-brain-dim-label'+baseCls+'">稳定性 · '+baseState+'</div>';
  h+='<div class="stats-brain-dim-status'+baseCls+'">'+baseTxt+'</div>';
  h+='</div>';

  // 思维厚度
  h+='<div class="stats-brain-dim'+depthCls+'">';
  h+='<div class="stats-brain-dim-header">';
  h+='<span class="stats-brain-dim-name">思维厚度</span>';
  h+='<span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+depthTip+'</span></span>';
  h+='</div>';
  h+='<div class="stats-brain-dim-en">Cognitive Depth</div>';
  h+='<div class="stats-brain-dim-val'+depthCls+'">'+cogDepth+'%</div>';
  h+='<div class="stats-brain-dim-label'+depthCls+'">丰富度 · '+depthState+'</div>';
  h+='<div class="stats-brain-dim-status'+depthCls+'">'+depthTxt+'</div>';
  h+='</div>';

  // 神经动能
  h+='<div class="stats-brain-dim'+kinCls+'">';
  h+='<div class="stats-brain-dim-header">';
  h+='<span class="stats-brain-dim-name">神经动能</span>';
  h+='<span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+kinTip+'</span></span>';
  h+='</div>';
  h+='<div class="stats-brain-dim-en">Neural Kinetic</div>';
  h+='<div class="stats-brain-dim-val'+kinCls+'">'+neuralKin+'%</div>';
  h+='<div class="stats-brain-dim-label'+kinCls+'">应变能 · '+kinState+'</div>';
  h+='<div class="stats-brain-dim-status'+kinCls+'">'+kinTxt+'</div>';
  h+='</div>';

  h+='</div>'; // stats-brain-dims

  // ── 节点链路图 ──────────────────────────────────────────
  var nodes=[
    {id:'L1',label:t('dash.mem.L1'),pct:l1pct},
    {id:'L2',label:t('dash.mem.L2'),pct:l2rate},
    {id:'L3',label:t('dash.mem.L3'),pct:l3rate},
    {id:'L4',label:t('dash.mem.L4'),pct:l4rate},
    {id:'L5',label:t('dash.mem.L5'),pct:l5rate},
    {id:'L6',label:t('dash.mem.L6')||'执行',pct:l6rate},
    {id:'L7',label:t('dash.mem.L7')||'纠偏',pct:l7rate},
    {id:'L8',label:t('dash.mem.L8'),pct:l8rate}
  ];
  function nodeClass(n){
    if(n.pct>=50) return 'active';
    if(n.pct>0) return 'growing';
    return 'off';
  }
  h+='<div class="stats-mem-chain">';
  nodes.forEach(function(n){
    h+='<div class="stats-mem-node '+nodeClass(n)+'"><span style="font-weight:600;">'+n.id+'</span> '+n.label+' <span style="opacity:0.7;">'+n.pct+'%</span></div>';
  });
  h+='</div>';

  // 稳定性预警
  if(baseTone<90&&l4q>5){
    h+='<div class="stats-module-hint amber">认知基调低于 90%，检查人格或对话连续性</div>';
  }

  // ── CoD 路由复盘：单环，静态，纯数据 ───────────────────────────
  var flashC=mem.flash_count||0;
  var traceC=mem.trace_back_count||0;
  var totalC=flashC+traceC;
  h+='<div class="stats-cod-section">';
  h+='<div class="stats-cod-header"><span class="stats-cod-title">CoD：动态上下文分流系统</span><span class="stats-cod-total">'+(totalC>0?totalC+' 轮':'暂无数据')+'</span></div>';
  if(totalC===0){
    h+='<div class="stats-cod-empty">积累对话数据后显示</div>';
  }else{
    var flashPct=Math.round(flashC/totalC*100);
    var tracePct=100-flashPct;
    // 中心语义标签
    var modeLabel=flashPct>=80?'直觉主导':flashPct>=60?'热启为主':tracePct>=60?'记忆驱动':'均衡路由';
    var modeLabelColor=flashPct>=60?'#ffe066':'#7ec8e3';
    var r=44,cx=60,cy=60,circ=2*Math.PI*r;
    var flashDash=circ*(flashPct/100);
    var traceDash=circ*(tracePct/100);
    var ringOpacity=Math.max(0.7,compositeRate/100);
    h+='<div class="stats-cod-ring-row">';
    h+='<div class="stats-cod-ring-wrap">';
    h+='<svg width="120" height="120" viewBox="0 0 120 120">';
    h+='<defs><filter id="codGlow"><feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="11"/>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="#ffe066" stroke-width="11" stroke-linecap="butt" stroke-dasharray="'+flashDash+' '+circ+'" transform="rotate(-90 '+cx+' '+cy+')" opacity="'+ringOpacity+'" filter="url(#codGlow)"/>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="#7ec8e3" stroke-width="11" stroke-linecap="butt" stroke-dasharray="'+traceDash+' '+circ+'" transform="rotate('+((-90)+flashPct*3.6)+' '+cx+' '+cy+')" opacity="'+ringOpacity+'" filter="url(#codGlow)"/>';
    // 中心：语义标签 + 机制说明，垂直居中
    h+='<text x="'+cx+'" y="'+(cy+5)+'" text-anchor="middle" fill="'+modeLabelColor+'" font-size="13" font-weight="600" font-family="inherit">'+modeLabel+'</text>';
    h+='<text x="'+cx+'" y="'+(cy+18)+'" text-anchor="middle" fill="rgba(255,255,255,0.2)" font-size="8.5" font-family="inherit" letter-spacing="0.3">每轮自动决策</text>';
    h+='</svg>';
    h+='</div>';
    // 右侧数据列
    h+='<div class="stats-cod-data">';
    h+='<div class="stats-cod-row">';
    h+='<span class="stats-cod-dot" style="background:#ffe066;box-shadow:0 0 4px #ffe06688;"></span>';
    h+='<span class="stats-cod-row-label">闪念<span class="stats-cod-row-desc">瞬时直觉响应</span></span>';
    h+='<span class="stats-cod-row-val" style="color:#ffe066;">'+flashPct+'%</span>';
    h+='<span class="stats-cod-row-sub">'+flashC+' 轮</span>';
    h+='</div>';
    h+='<div class="stats-cod-row">';
    h+='<span class="stats-cod-dot" style="background:#7ec8e3;box-shadow:0 0 4px #7ec8e388;"></span>';
    h+='<span class="stats-cod-row-label">溯源<span class="stats-cod-row-desc">深度记忆对齐</span></span>';
    h+='<span class="stats-cod-row-val" style="color:#7ec8e3;">'+tracePct+'%</span>';
    h+='<span class="stats-cod-row-sub">'+traceC+' 轮</span>';
    h+='</div>';
    h+='</div>'; // stats-cod-data
    h+='</div>'; // stats-cod-ring-row
    h+='<div class="stats-cod-footer">以瞬时直觉维持共振，以深度溯源完成对齐</div>';
  }
  h+='</div>'; // stats-cod-section

  h+='</div></div>';
  return h;
}

// 场景分布增强版
function buildSceneModule(s){
  var bs=s.by_scene||{};
  var scenes=[{k:'chat',n:t('dash.scene.chat')},{k:'route',n:t('dash.scene.route')},{k:'skill',n:t('dash.scene.skill')},{k:'learn',n:t('dash.scene.learn')}];
  var totalSceneTokens=0;
  scenes.forEach(function(sc){totalSceneTokens+=(bs[sc.k]||{}).tokens||0;});
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.scene.title')+'</div>';
  if(totalSceneTokens>0){
    var sorted=scenes.slice().sort(function(a,b){return((bs[b.k]||{}).tokens||0)-((bs[a.k]||{}).tokens||0);});
    h+='<div class="stats-module"><div class="stats-bars">';
    sorted.forEach(function(sc){
      var t=(bs[sc.k]||{}).tokens||0,r=(bs[sc.k]||{}).requests||0;
      var pct=totalSceneTokens>0?Math.round(t/totalSceneTokens*100):0;
      var barW=pct>0?Math.max(pct,4):0;
      h+='<div class="stats-bar-row"><div class="stats-bar-label">'+sc.n+'</div>';
      h+='<div class="stats-bar-track"><div class="stats-bar-fill '+sc.k+'" style="width:'+barW+'%"></div></div>';
      h+='<div class="stats-bar-pct">'+pct+'% <span style="opacity:0.5;font-size:11px;">'+r+'次 '+fmtN(t)+'t</span></div></div>';
    });
    h+='</div></div>';
  }else{
    h+='<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">'+t('dash.scene.empty')+'</div>';
  }
  h+='</div>';
  return h;
}

// 7天趋势增强版
function buildTrendModule(s){
  var byDay=s.by_day||{};
  var dayKeys=[];var now=new Date();
  for(var di=6;di>=0;di--){var dd=new Date(now);dd.setDate(dd.getDate()-di);dayKeys.push(dd.toISOString().slice(0,10));}
  window._statsTrendData={byDay:byDay,dayKeys:dayKeys};
  var h='<div class="stats-section"><div class="stats-section-title" style="justify-content:space-between;">';
  h+='<span>'+t('dash.trend.title')+'</span>';
  h+='<div style="display:flex;gap:4px;">';
  var dims=[{k:'tokens',n:t('dash.trend.tokens')},{k:'requests',n:t('dash.trend.requests')}];
  dims.forEach(function(d,i){
    var active=i===0?' stats-highlight':'';
    h+='<span class="stats-trend-tab'+active+'" data-dim="'+d.k+'" onclick="switchTrendDim(\''+d.k+'\')" style="cursor:pointer;font-size:11px;padding:2px 8px;border-radius:6px;'+(i===0?'background:rgba(106,170,136,0.12);':'')+'">'+d.n+'</span>';
  });
  h+='</div></div>';
  h+='<div id="statsTrendChart">'+renderTrendBars(byDay,dayKeys,'tokens')+'</div>';
  var first=(byDay[dayKeys[0]]||{}).tokens||0,last=(byDay[dayKeys[6]]||{}).tokens||0;
  var activeDays=0;dayKeys.forEach(function(dk){if((byDay[dk]||{}).tokens>0)activeDays++;});
  var hint='';
  if(activeDays<=2){
    hint=t('dash.trend.accumulating');
  }else if(first>0&&last>0){
    var change=Math.round((last-first)/Math.max(first,1)*100);
    if(change>30) hint=tf('dash.trend.up',change);
    else if(change<-30) hint=t('dash.trend.down');
    else hint=t('dash.trend.stable');
  }else{hint=t('dash.trend.building');}
  h+='<div class="stats-module-hint" style="margin-top:8px;">'+hint+'</div></div>';
  return h;
}

function renderTrendBars(byDay,dayKeys,dim){
  var dayMax=0;
  dayKeys.forEach(function(dk){var v=(byDay[dk]||{})[dim]||0;if(v>dayMax)dayMax=v;});
  if(dayMax===0) return '<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">'+t('dash.trend.nodata')+'</div>';
  var h='<div class="stats-trend"><div class="stats-trend-bars">';
  dayKeys.forEach(function(dk){
    var v=(byDay[dk]||{})[dim]||0;
    var pct=dayMax>0?Math.max(3,Math.round(v/dayMax*100)):3;
    h+='<div class="stats-trend-col"><div class="stats-trend-val">'+fmtN(v)+'</div><div class="stats-trend-bar" style="height:'+pct+'%"></div><div class="stats-trend-label">'+dk.slice(5)+'</div></div>';
  });
  h+='</div></div>';
  return h;
}

function switchTrendDim(dim){
  var d=window._statsTrendData;if(!d)return;
  document.getElementById('statsTrendChart').innerHTML=renderTrendBars(d.byDay,d.dayKeys,dim);
  var tabs=document.querySelectorAll('.stats-trend-tab');
  tabs.forEach(function(t){
    if(t.getAttribute('data-dim')===dim){t.classList.add('stats-highlight');t.style.background='rgba(106,170,136,0.12)';}
    else{t.classList.remove('stats-highlight');t.style.background='';}
  });
}

// 系统诊断区
function buildDiagModule(s){
  var items=[];
  var pr=s.prices||getPrice(s.model);
  var cHit=s.cache_read_tokens||0;var cMiss=(s.input_tokens||0)-cHit;var costYuan=(Math.max(0,cMiss)*pr.i+cHit*pr.i*0.1+(s.output_tokens||0)*pr.o)/1e6;
  var totalReq=s.total_requests||0;
  var avgT=totalReq>0?Math.round((s.total_tokens||0)/totalReq):0;
  var inp=s.input_tokens||0,out=s.output_tokens||0;
  var cacheRead=s.cache_read_tokens||0;
  var cacheRate=inp>0?Math.round(cacheRead/inp*100):0;
  var mem=s.memory||{};
  var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
  var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
  var l2rate=l2s>0?Math.round(l2h/l2s*100):0;
  var l8rate=l8s>0?Math.round(l8h/l8s*100):0;
  var bs=s.by_scene||{};
  if(costYuan>10) items.push({t:'warn',m:tf('dash.diag.costHigh',costYuan.toFixed(2))});
  else if(costYuan>0) items.push({t:'ok',m:tf('dash.diag.costOk',costYuan.toFixed(2))});
  if(inp>0&&out>inp*2) items.push({t:'warn',m:tf('dash.diag.outputHigh',Math.round(out/inp))});
  if(cacheRate>=50) items.push({t:'ok',m:tf('dash.diag.cacheSaved',fmtN(cacheRead))});
  if(l2rate>=30&&l8rate>=20) items.push({t:'ok',m:t('dash.diag.memGood')});
  else if(l8rate<10&&l8s>5) items.push({t:'warn',c:'mem',m:tf('dash.diag.l8Low',l8rate)});
  if(l2rate<20&&l2s>5) items.push({t:'warn',c:'mem',m:tf('dash.diag.l2Low',l2rate)});
  var totalST=0;
  [{k:'chat'},{k:'skill'}].forEach(function(sc){totalST+=(bs[sc.k]||{}).tokens||0;});
  var chatPct=totalST>0?Math.round(((bs.chat||{}).tokens||0)/totalST*100):0;
  if(chatPct>=85) items.push({t:'warn',m:tf('dash.diag.chatHigh',chatPct)});
  if(avgT>2000) items.push({t:'warn',m:tf('dash.diag.avgHigh',fmtN(avgT))});
  if(items.length===0) items.push({t:'ok',m:t('dash.diag.allOk')});
  // 成本×记忆关联
  var avgCostD=totalReq>0?costYuan/totalReq:0;
  var skillReqs=(bs.skill||{}).requests||0;
  if(l2rate>=80&&avgCostD<0.01&&totalReq>50) items.push({t:'ok',c:'mem',m:tf('dash.diag.memCost',avgCostD.toFixed(4))});
  if(skillReqs>20) items.push({t:'ok',c:'scene',m:tf('dash.diag.skillRoute',skillReqs)});
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.diag.title')+'</div><div class="stats-diag">';
  items.forEach(function(it){
    var dotCls=it.t==='warn'?' warn':''; if(it.c==='cost')dotCls+=' cost'; else if(it.c==='mem')dotCls+=' mem'; else if(it.c==='scene')dotCls+=' scene';
    h+='<div class="stats-diag-item"><div class="stats-diag-dot'+dotCls+'"></div><div>'+it.m+'</div></div>';
  });
  h+='</div></div>';
  return h;
}
