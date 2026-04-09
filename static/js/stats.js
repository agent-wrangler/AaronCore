function fmtN(n){
  if(n>=1e6) return (n/1e6).toFixed(1)+'M';
  if(n>=1e4) return (n/1e3).toFixed(1)+'K';
  return Number(n||0).toLocaleString();
}

var PRICE={deepseek:{i:1,o:2},minimax:{i:1,o:8},qwen:{i:2,o:6},glm:{i:1,o:1}};
function getPrice(model){
  var m=(model||'').toLowerCase();
  for(var k in PRICE){
    if(m.indexOf(k)!==-1) return PRICE[k];
  }
  return {i:2,o:4};
}

function sceneBucket(row){
  row=(row&&typeof row==='object')?row:{};
  return {
    requests: Math.max(Number(row.requests||0), 0),
    tokens: Math.max(Number(row.tokens||0), 0)
  };
}

function mergeSceneBuckets(){
  var merged={requests:0,tokens:0};
  for(var i=0;i<arguments.length;i++){
    var row=sceneBucket(arguments[i]);
    merged.requests+=row.requests;
    merged.tokens+=row.tokens;
  }
  return merged;
}

function normalizeSceneStats(raw){
  raw=(raw&&typeof raw==='object')?raw:{};
  return {
    // Runtime splitting now records part of user-facing traffic as tool_call / vision.
    // Fold them back into the legacy cockpit buckets so the dashboard does not "lose" data.
    chat: mergeSceneBuckets(raw.chat, raw.vision),
    route: sceneBucket(raw.route),
    skill: mergeSceneBuckets(raw.skill, raw.tool_call),
    learn: sceneBucket(raw.learn)
  };
}

function pctFromCount(count,saturation){
  var safeCount=Math.max(Number(count||0),0);
  var safeSaturation=Math.max(Number(saturation||1),1);
  return Math.min(100,Math.round(safeCount/safeSaturation*100));
}

function memoryReserveSignal(rate,count,saturation,weight,hasActivity){
  var liveRate=Math.max(Number(rate||0),0);
  var reservePct=pctFromCount(count,saturation);
  var reserveWeight=Math.max(0,Math.min(Number(weight||0),1));
  var reserveSignal=Math.round(reservePct*reserveWeight);
  return hasActivity?Math.max(liveRate,reserveSignal):reserveSignal;
}

function dashText(zh,en){
  try{
    if(typeof getLang==='function' && getLang()==='en') return en;
  }catch(_err){}
  return zh;
}

function buildSnapshotModule(s,bs){
  var mem=s.memory||{};
  var totalReq=s.total_requests||0;
  var totalTk=s.total_tokens||0;
  var realL3Count=Math.max(mem.real_l3_count||0, mem.l3_count||0);
  var realL5Count=Math.max(mem.real_l5_count||0, mem.l5_count||0);
  var l4SignalCount=
    (mem.real_l4_rule_count||0)+
    (mem.real_l4_profile_count||0)+
    (mem.real_l4_tone_count||0)+
    (mem.real_l4_particle_count||0)+
    (mem.real_l4_avoid_count||0)+
    ((mem.real_l4_style_prompt||0)?1:0);
  var scenes=[
    {k:'chat',n:t('dash.scene.chat')},
    {k:'skill',n:t('dash.scene.skill')},
    {k:'route',n:t('dash.scene.route')},
    {k:'learn',n:t('dash.scene.learn')}
  ];
  var topScene=scenes[0];
  var topSceneReq=0;
  var topSceneTk=0;
  scenes.forEach(function(sc){
    var req=(bs[sc.k]||{}).requests||0;
    var tk=(bs[sc.k]||{}).tokens||0;
    if(req>topSceneReq || (req===topSceneReq && tk>topSceneTk)){
      topScene=sc;
      topSceneReq=req;
      topSceneTk=tk;
    }
  });

  var h='<div class="stats-section"><div class="stats-section-title">'+dashText('数据快照','Snapshot')+'</div>';
  h+='<div class="stats-module"><div class="stats-cost-grid">';
  h+='<div class="stats-cost-main">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.requests')+'</span><span>'+totalReq.toLocaleString()+t('dash.cost.times')+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.scene.title')+'</span><span>'+topScene.n+' · '+topSceneReq+t('dash.cost.times')+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.totalTokens')+'</span><span>'+fmtN(totalTk)+' tokens</span></div>';
  h+='</div>';
  h+='<div class="stats-cost-sub">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.mem.L3')+'</span><span>'+fmtN(realL3Count)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.mem.L4')+'</span><span>'+fmtN(l4SignalCount)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.mem.L5')+'</span><span>'+fmtN(realL5Count)+'</span></div>';
  h+='</div>';
  h+='</div></div></div>';
  return h;
}

function buildSummaryCards(s,costYuan,cacheRate,compositeRate,topScene){
  var h='<div class="stats-summary">';
  var costHint=costYuan<1?t('dash.cost.low'):t('dash.cost.ok');
  var costCls='';
  var totalTk=s.total_tokens||0;
  var inpTk=s.input_tokens||0;
  var inPct=totalTk>0?Math.round(inpTk/totalTk*100):0;
  var totalReq=s.total_requests||0;
  var avgCost=totalReq>0?(costYuan/totalReq):0;
  var avgHint=totalReq>0?tf('dash.total.conv',totalReq):t('dash.no.conv');
  if(costYuan>10){ costHint=t('dash.cost.high'); costCls=' warn'; }

  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.cost')+'</div>';
  h+='<div class="stats-summary-value">\u00a5'+costYuan.toFixed(2)+'</div>';
  h+='<div class="stats-summary-hint'+costCls+'">'+costHint+'</div></div>';

  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.tokens')+'</div>';
  h+='<div class="stats-summary-value">'+fmtN(totalTk)+'</div>';
  h+='<div class="stats-summary-hint">'+t('dash.input.pct')+' '+inPct+'%</div></div>';

  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.mem.eff')+'</div>';
  h+='<div class="stats-summary-value">'+compositeRate+'%</div>';
  h+='<div class="stats-summary-hint'+(compositeRate<30?' warn':'')+'">'+(compositeRate>=50?t('dash.mem.good'):t('dash.mem.growing'))+'</div></div>';

  h+='<div class="stats-summary-card"><div class="stats-summary-label">'+t('dash.avg')+'</div>';
  h+='<div class="stats-summary-value">\u00a5'+avgCost.toFixed(4)+'</div>';
  h+='<div class="stats-summary-hint">'+avgHint+'</div></div>';
  h+='</div>';
  return h;
}

function buildCostModule(s,pr,costYuan){
  var inp=s.input_tokens||0, out=s.output_tokens||0, total=s.total_tokens||0;
  var totalReq=s.total_requests||0;
  var cw=s.cache_write_tokens||0, cr=s.cache_read_tokens||0;
  var costNew=cw*pr.i/1e6, costCache=cr*pr.i*0.1/1e6, costOut=out*pr.o/1e6;
  var saved=cr*pr.i*0.9/1e6;
  var avgCost=totalReq>0?(costYuan/totalReq):0;
  var avgInp=totalReq>0?Math.round(inp/totalReq):0;
  var avgOut=totalReq>0?Math.round(out/totalReq):0;
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.cost.title')+'</div>';

  h+='<div class="stats-module"><div class="stats-cost-grid">';
  h+='<div class="stats-cost-main">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.input')+'</span><span style="font-weight:600;">\u00a5'+costNew.toFixed(3)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.cache')+'</span><span style="font-weight:600;color:var(--tone-steel);">\u00a5'+costCache.toFixed(4)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.output')+'</span><span style="font-weight:600;">\u00a5'+costOut.toFixed(4)+'</span></div>';
  h+='<div class="stats-kv-mini" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--divider-panel);"><span class="stats-kv-label">'+t('dash.cost.total')+'</span><span style="font-weight:700;color:var(--tone-sage);">\u00a5'+costYuan.toFixed(2)+'</span></div>';
  if(saved>0){
    h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.saved')+'</span><span style="font-weight:600;color:var(--tone-sage);">\u00a5'+saved.toFixed(4)+'</span></div>';
  }
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.avg')+'</span><span style="font-weight:600;">\u00a5'+avgCost.toFixed(4)+'</span></div>';
  h+='</div>';

  h+='<div class="stats-cost-sub">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.requests')+'</span><span>'+totalReq.toLocaleString()+t('dash.cost.times')+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.totalTokens')+'</span><span>'+fmtN(total)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.inputTokens')+'</span><span>'+fmtN(inp)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.cacheTokens')+'</span><span>'+fmtN(cr)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.outputTokens')+'</span><span>'+fmtN(out)+' tokens</span></div>';
  h+='<div class="stats-kv-mini" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--divider-panel);"><span class="stats-kv-label">'+t('dash.cost.avgInput')+'</span><span>'+fmtN(avgInp)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">'+t('dash.cost.avgOutput')+'</span><span>'+fmtN(avgOut)+' tokens</span></div>';
  h+='</div>';
  h+='</div></div>';
  return h;
}

function renderStats(s){
  var bs=normalizeSceneStats(s.by_scene);
  var _pr=s.prices||getPrice(s.model);
  var pr={i:_pr.i||_pr.input||2,o:_pr.o||_pr.output||4};
  var cHit=s.cache_read_tokens||0;
  var cMiss=(s.input_tokens||0)-cHit;
  var costYuan=(Math.max(0,cMiss)*pr.i+cHit*pr.i*0.1+(s.output_tokens||0)*pr.o)/1e6;
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
  scenes.forEach(function(sc){
    var tokens=(bs[sc.k]||{}).tokens||0;
    if(tokens>topVal){ topVal=tokens; topScene=sc.n; }
  });

  var h='';
  h+=buildSummaryCards(s,costYuan,0,compositeRate,topScene);
  h+=buildCostModule(s,pr,costYuan);
  h+=buildModelModule(s);
  h+=buildMemoryModule(s);
  h+=buildSceneModule(s);
  h+=buildTrendModule(s);
  h+=buildDiagModule(s);
  return h;
}

function buildModelModule(s){
  var bm=s.by_model||{};
  var ap=s.all_prices||{};
  var keys=Object.keys(bm);
  var title=t('dash.model.title');
  if(title==='dash.model.title') title=(getLang&&getLang()==='zh')?'\u6a21\u578b\u6d88\u8017\u5206\u5e03':'Model Usage';
  if(keys.length===0) return '';
  var h='<div class="stats-section stats-section-model-usage"><div class="stats-section-title">'+title+'</div><div class="stats-module">';
  var totalT=0;
  keys.forEach(function(k){ totalT+=(bm[k].input||0)+(bm[k].output||0); });
  keys.sort(function(a,b){ return ((bm[b].input||0)+(bm[b].output||0))-((bm[a].input||0)+(bm[a].output||0)); });
  var colors=['var(--tone-sage)','var(--tone-steel)','var(--tone-amber)','var(--tone-mauve)','var(--tone-danger)'];

  keys.forEach(function(k,idx){
    var m=bm[k],inp=m.input||0,out=m.output||0,req=m.requests||0,tk=inp+out;
    var pct=totalT>0?Math.round(tk/totalT*100):0;
    var mp=null;
    for(var pk in ap){ if(k.indexOf(pk)!==-1){ mp=ap[pk]; break; } }
    if(!mp) mp={input:2,output:4};
    var cost=(inp*mp.input+out*mp.output)/1e6;
    var clr=colors[idx%colors.length];
    h+='<div class="stats-model-row">';
    h+='<div class="stats-model-name"><span style="width:8px;height:8px;border-radius:50%;background:'+clr+';flex-shrink:0;display:inline-block;"></span><span>'+k+'</span></div>';
    h+='<div class="stats-model-track"><div style="width:'+Math.max(pct,3)+'%;height:100%;border-radius:3px;background:'+clr+';"></div></div>';
    h+='<div class="stats-model-data">'+pct+'% · \u00a5'+cost.toFixed(2)+' · '+req+' '+t('dash.cost.times')+'</div>';
    h+='</div>';
  });

  h+='</div></div>';
  return h;
}

function buildMemoryModuleLegacy(s){
  var mem=s.memory||{};
  var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
  var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
  var tq=mem.total_queries||0;
  var realL3Count=Math.max(mem.real_l3_count||0, mem.l3_count||0);
  var realL5Count=Math.max(mem.real_l5_count||0, mem.l5_count||0);
  var realL8Count=Math.max(mem.real_l8_count||0, mem.l8_count||0);
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
  var l3pct=pctFromCount(realL3Count,20);
  var l4pct=mem.l4_available?Math.max(l4rate,Math.max(60,l4StyleSignal)):0;
  var l5pct=pctFromCount(realL5Count,12);
  var l8pct=pctFromCount(realL8Count,20);
  var depthL3Signal=memoryReserveSignal(l3rate,realL3Count,20,0.55,l3q>0);
  var depthL8Signal=memoryReserveSignal(l8rate,realL8Count,20,0.45,l8s>0);
  var kineticL5Signal=memoryReserveSignal(l5rate,realL5Count,12,0.55,l5q>0);

  var baseTone=mem.l4_available?Math.round(l1pct*0.35+l4StyleSignal*0.65):l1pct;
  var cogDepth=Math.round((l2rate+depthL3Signal+depthL8Signal)/3);
  var neuralKin=Math.round((kineticL5Signal+l6rate+l7rate)/3);
  var compositeRate=Math.round((baseTone+cogDepth+neuralKin)/3);
  var baseCls=baseTone<90?' warn':'';
  var depthCls=cogDepth<15?' amber':'';
  var kinCls=neuralKin===0?' amber':'';
  var baseState='',baseText='';
  var depthState='',depthText='';
  var kinState='',kinText='';
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.mem.title')+'</div><div class="stats-module">';

  if(!mem.l4_available){
    baseState=t('dash.brain.base.state.building');
    baseText=t('dash.brain.base.text.noL4');
  }else if(baseTone>=98){
    baseState=t('dash.brain.base.state.synced');
    baseText=tf('dash.brain.base.text.synced',baseTone);
  }else if(baseTone>=90){
    baseState=t('dash.brain.base.state.drifting');
    baseText=tf('dash.brain.base.text.drifting',l4Mode,l4RuleCount,l4RecentUpdates);
  }else{
    baseState=t('dash.brain.base.state.align');
    baseText=tf('dash.brain.base.text.align',l4Mode,l4StyleSignal);
  }

  if(cogDepth>45){
    depthState=t('dash.brain.depth.state.expand');
    depthText=t('dash.brain.depth.text.expand');
  }else if(cogDepth>=15){
    depthState=t('dash.brain.depth.state.resonate');
    depthText=t('dash.brain.depth.text.resonate');
  }else if(cogDepth>0){
    depthState=t('dash.brain.depth.state.shallow');
    depthText=t('dash.brain.depth.text.shallow');
  }else{
    depthState=t('dash.brain.depth.state.unexplored');
    depthText=t('dash.brain.depth.text.unexplored');
  }

  if(neuralKin>20){
    kinState=t('dash.brain.kinetic.state.active');
    kinText=t('dash.brain.kinetic.text.active');
  }else if(neuralKin>=5){
    kinState=t('dash.brain.kinetic.state.stable');
    kinText=t('dash.brain.kinetic.text.stable');
  }else if(neuralKin>0){
    kinState=t('dash.brain.kinetic.state.booting');
    kinText=t('dash.brain.kinetic.text.booting');
  }else{
    kinState=t('dash.brain.kinetic.state.idle');
    kinText=t('dash.brain.kinetic.text.idle');
  }

  h+='<div class="stats-brain-dims">';
  h+='<div class="stats-brain-dim'+baseCls+'">';
  h+='<div class="stats-brain-dim-header"><span class="stats-brain-dim-name">'+t('dash.brain.base.name')+'</span><span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+t('dash.brain.tip.base')+'</span></span></div>';
  h+='<div class="stats-brain-dim-en">'+t('dash.brain.base.en')+'</div>';
  h+='<div class="stats-brain-dim-val'+baseCls+'">'+baseTone+'%</div>';
  h+='<div class="stats-brain-dim-label'+baseCls+'">'+t('dash.brain.base.metric')+' · '+baseState+'</div>';
  h+='<div class="stats-brain-dim-status'+baseCls+'">'+baseText+'</div></div>';

  h+='<div class="stats-brain-dim'+depthCls+'">';
  h+='<div class="stats-brain-dim-header"><span class="stats-brain-dim-name">'+t('dash.brain.depth.name')+'</span><span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+t('dash.brain.tip.depth')+'</span></span></div>';
  h+='<div class="stats-brain-dim-en">'+t('dash.brain.depth.en')+'</div>';
  h+='<div class="stats-brain-dim-val'+depthCls+'">'+cogDepth+'%</div>';
  h+='<div class="stats-brain-dim-label'+depthCls+'">'+t('dash.brain.depth.metric')+' · '+depthState+'</div>';
  h+='<div class="stats-brain-dim-status'+depthCls+'">'+depthText+'</div></div>';

  h+='<div class="stats-brain-dim'+kinCls+'">';
  h+='<div class="stats-brain-dim-header"><span class="stats-brain-dim-name">'+t('dash.brain.kinetic.name')+'</span><span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+t('dash.brain.tip.kinetic')+'</span></span></div>';
  h+='<div class="stats-brain-dim-en">'+t('dash.brain.kinetic.en')+'</div>';
  h+='<div class="stats-brain-dim-val'+kinCls+'">'+neuralKin+'%</div>';
  h+='<div class="stats-brain-dim-label'+kinCls+'">'+t('dash.brain.kinetic.metric')+' · '+kinState+'</div>';
  h+='<div class="stats-brain-dim-status'+kinCls+'">'+kinText+'</div></div>';
  h+='</div>';

  var nodes=[
    {id:'L1',label:t('dash.mem.L1'),pct:l1pct},
    {id:'L2',label:t('dash.mem.L2'),pct:l2rate},
    {id:'L3',label:t('dash.mem.L3'),pct:l3pct},
    {id:'L4',label:t('dash.mem.L4'),pct:l4pct},
    {id:'L5',label:t('dash.mem.L5'),pct:l5pct},
    {id:'L6',label:t('dash.mem.L6'),pct:l6rate},
    {id:'L7',label:t('dash.mem.L7'),pct:l7rate},
    {id:'L8',label:t('dash.mem.L8'),pct:l8pct}
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

  h+='<div style="font-size:11px;color:var(--text-label);margin:14px 0 8px;">'+dashText('层级明细','Layer Detail')+'</div>';
  h+='<div class="stats-cost-grid">';
  h+='<div class="stats-cost-main">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L1 · '+t('dash.mem.L1')+'</span><span>'+fmtN(mem.l1_count||0)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L2 · '+t('dash.mem.L2')+'</span><span>'+fmtN(l2h)+' / '+fmtN(l2s)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L3 · '+t('dash.mem.L3')+'</span><span>'+fmtN(realL3Count)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L4 · '+t('dash.mem.L4')+'</span><span>'+fmtN(l4SignalCount)+' · '+l4Mode+'</span></div>';
  h+='</div>';
  h+='<div class="stats-cost-sub">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L5 · '+t('dash.mem.L5')+'</span><span>'+fmtN(realL5Count)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L6 · '+t('dash.mem.L6')+'</span><span>'+fmtN(mem.l6_hits||0)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L7 · '+t('dash.mem.L7')+'</span><span>'+fmtN(mem.l7_hits||0)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">L8 · '+t('dash.mem.L8')+'</span><span>'+fmtN(l8h)+' / '+fmtN(l8s)+'</span></div>';
  h+='</div>';
  h+='</div>';

  if(baseTone<90&&l4q>5){
    h+='<div class="stats-module-hint amber">'+t('dash.brain.warning.baseLow')+'</div>';
  }

  var flashC=mem.flash_count||0;
  var traceC=mem.trace_back_count||0;
  var totalC=flashC+traceC;
  h+='<div class="stats-cod-section">';
  h+='<div class="stats-cod-header"><span class="stats-cod-title">'+t('dash.cod.title')+'</span><span class="stats-cod-total">'+(totalC>0?tf('dash.cod.total',totalC):t('dash.cod.total.none'))+'</span></div>';
  if(totalC===0){
    h+='<div class="stats-cod-empty">'+t('dash.cod.empty')+'</div>';
  }else{
    var flashPct=Math.round(flashC/totalC*100);
    var tracePct=100-flashPct;
    var modeLabel=flashPct>=80?t('dash.cod.mode.flash'):flashPct>=60?t('dash.cod.mode.warm'):tracePct>=60?t('dash.cod.mode.trace'):t('dash.cod.mode.balanced');
    var modeLabelColor=flashPct>=60?'var(--tone-amber)':'var(--tone-steel)';
    var r=44,cx=60,cy=60,circ=2*Math.PI*r;
    var flashDash=circ*(flashPct/100);
    var traceDash=circ*(tracePct/100);
    var ringOpacity=Math.max(0.7,compositeRate/100);
    h+='<div class="stats-cod-ring-row">';
    h+='<div class="stats-cod-ring-wrap">';
    h+='<svg width="120" height="120" viewBox="0 0 120 120">';
    h+='<defs><filter id="codGlow"><feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" style="stroke:var(--divider-panel)" stroke-width="11"/>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" style="stroke:var(--tone-amber)" stroke-width="11" stroke-linecap="butt" stroke-dasharray="'+flashDash+' '+circ+'" transform="rotate(-90 '+cx+' '+cy+')" opacity="'+ringOpacity+'" filter="url(#codGlow)"/>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" style="stroke:var(--tone-steel)" stroke-width="11" stroke-linecap="butt" stroke-dasharray="'+traceDash+' '+circ+'" transform="rotate('+((-90)+flashPct*3.6)+' '+cx+' '+cy+')" opacity="'+ringOpacity+'" filter="url(#codGlow)"/>';
    h+='<text x="'+cx+'" y="'+(cy+5)+'" text-anchor="middle" fill="'+modeLabelColor+'" font-size="13" font-weight="600" font-family="inherit">'+modeLabel+'</text>';
    h+='<text x="'+cx+'" y="'+(cy+18)+'" text-anchor="middle" style="fill:var(--text-label)" font-size="8.5" font-family="inherit" letter-spacing="0.3">'+t('dash.cod.auto')+'</text>';
    h+='</svg></div>';
    h+='<div class="stats-cod-data">';
    h+='<div class="stats-cod-row"><span class="stats-cod-dot" style="background:var(--tone-amber);"></span><span class="stats-cod-row-label">'+t('dash.cod.flash')+'<span class="stats-cod-row-desc">'+t('dash.cod.flash.desc')+'</span></span><span class="stats-cod-row-val" style="color:var(--tone-amber);">'+flashPct+'%</span><span class="stats-cod-row-sub">'+flashC+'</span></div>';
    h+='<div class="stats-cod-row"><span class="stats-cod-dot" style="background:var(--tone-steel);"></span><span class="stats-cod-row-label">'+t('dash.cod.trace')+'<span class="stats-cod-row-desc">'+t('dash.cod.trace.desc')+'</span></span><span class="stats-cod-row-val" style="color:var(--tone-steel);">'+tracePct+'%</span><span class="stats-cod-row-sub">'+traceC+'</span></div>';
    h+='</div></div>';
    h+='<div class="stats-cod-footer">'+t('dash.cod.footer')+'</div>';
  }
  h+='</div>';
  h+='</div></div>';
  return h;
}

function buildMemoryModule(s){
  var mem=s.memory||{};
  var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
  var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
  var tq=mem.total_queries||0;
  var realL3Count=Math.max(mem.real_l3_count||0, mem.l3_count||0);
  var realL5Count=Math.max(mem.real_l5_count||0, mem.l5_count||0);
  var realL8Count=Math.max(mem.real_l8_count||0, mem.l8_count||0);
  var l2rate=l2s>0?Math.round(l2h/l2s*100):0;
  var l8rate=l8s>0?Math.round(l8h/l8s*100):0;
  var l1pct=Math.min(100,Math.round((mem.l1_count||0)/30*100));
  var l3q=mem.l3_queries||0, l3h=mem.l3_hits||0;
  var l4q=mem.l4_queries||0, l4h=mem.l4_hits||0;
  var l5q=mem.l5_queries||0, l5h=mem.l5_hits||0;
  var l3rate=l3q>0?Math.round(l3h/l3q*100):0;
  var l4rate=l4q>0?Math.round(l4h/l4q*100):0;
  var l5rate=l5q>0?Math.round(l5h/l5q*100):0;
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
  var l3pct=pctFromCount(realL3Count,20);
  var l4pct=mem.l4_available?Math.max(l4rate,Math.max(60,l4StyleSignal)):0;
  var l5pct=pctFromCount(realL5Count,12);
  var l8pct=pctFromCount(realL8Count,20);
  var depthL3Signal=memoryReserveSignal(l3rate,realL3Count,20,0.55,l3q>0);
  var depthL8Signal=memoryReserveSignal(l8rate,realL8Count,20,0.45,l8s>0);
  var kineticL5Signal=memoryReserveSignal(l5rate,realL5Count,12,0.55,l5q>0);

  var baseTone=mem.l4_available?Math.round(l1pct*0.35+l4StyleSignal*0.65):l1pct;
  var cogDepth=Math.round((l2rate+depthL3Signal+depthL8Signal)/3);
  var neuralKin=Math.round((kineticL5Signal+l6rate+l7rate)/3);
  var compositeRate=Math.round((baseTone+cogDepth+neuralKin)/3);
  var baseCls=baseTone<90?' warn':'';
  var depthCls=cogDepth<15?' amber':'';
  var kinCls=neuralKin===0?' amber':'';
  var baseState='',baseText='';
  var depthState='',depthText='';
  var kinState='',kinText='';
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.mem.title')+'</div><div class="stats-module">';

  if(!mem.l4_available){
    baseState=t('dash.brain.base.state.building');
    baseText=t('dash.brain.base.text.noL4');
  }else if(baseTone>=98){
    baseState=t('dash.brain.base.state.synced');
    baseText=tf('dash.brain.base.text.synced',baseTone);
  }else if(baseTone>=90){
    baseState=t('dash.brain.base.state.drifting');
    baseText=tf('dash.brain.base.text.drifting',l4Mode,l4RuleCount,l4RecentUpdates);
  }else{
    baseState=t('dash.brain.base.state.align');
    baseText=tf('dash.brain.base.text.align',l4Mode,l4StyleSignal);
  }

  if(cogDepth>45){
    depthState=t('dash.brain.depth.state.expand');
    depthText=t('dash.brain.depth.text.expand');
  }else if(cogDepth>=15){
    depthState=t('dash.brain.depth.state.resonate');
    depthText=t('dash.brain.depth.text.resonate');
  }else if(cogDepth>0){
    depthState=t('dash.brain.depth.state.shallow');
    depthText=t('dash.brain.depth.text.shallow');
  }else{
    depthState=t('dash.brain.depth.state.unexplored');
    depthText=t('dash.brain.depth.text.unexplored');
  }

  if(neuralKin>20){
    kinState=t('dash.brain.kinetic.state.active');
    kinText=t('dash.brain.kinetic.text.active');
  }else if(neuralKin>=5){
    kinState=t('dash.brain.kinetic.state.stable');
    kinText=t('dash.brain.kinetic.text.stable');
  }else if(neuralKin>0){
    kinState=t('dash.brain.kinetic.state.booting');
    kinText=t('dash.brain.kinetic.text.booting');
  }else{
    kinState=t('dash.brain.kinetic.state.idle');
    kinText=t('dash.brain.kinetic.text.idle');
  }

  h+='<div class="stats-brain-dims">';
  h+='<div class="stats-brain-dim'+baseCls+'">';
  h+='<div class="stats-brain-dim-header"><span class="stats-brain-dim-name">'+t('dash.brain.base.name')+'</span><span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+t('dash.brain.tip.base')+'</span></span></div>';
  h+='<div class="stats-brain-dim-en">'+t('dash.brain.base.en')+'</div>';
  h+='<div class="stats-brain-dim-val'+baseCls+'">'+baseTone+'%</div>';
  h+='<div class="stats-brain-dim-label'+baseCls+'">'+t('dash.brain.base.metric')+' · '+baseState+'</div>';
  h+='<div class="stats-brain-dim-status'+baseCls+'">'+baseText+'</div></div>';

  h+='<div class="stats-brain-dim'+depthCls+'">';
  h+='<div class="stats-brain-dim-header"><span class="stats-brain-dim-name">'+t('dash.brain.depth.name')+'</span><span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+t('dash.brain.tip.depth')+'</span></span></div>';
  h+='<div class="stats-brain-dim-en">'+t('dash.brain.depth.en')+'</div>';
  h+='<div class="stats-brain-dim-val'+depthCls+'">'+cogDepth+'%</div>';
  h+='<div class="stats-brain-dim-label'+depthCls+'">'+t('dash.brain.depth.metric')+' · '+depthState+'</div>';
  h+='<div class="stats-brain-dim-status'+depthCls+'">'+depthText+'</div></div>';

  h+='<div class="stats-brain-dim'+kinCls+'">';
  h+='<div class="stats-brain-dim-header"><span class="stats-brain-dim-name">'+t('dash.brain.kinetic.name')+'</span><span class="stats-brain-tip-wrap"><span class="stats-brain-tip-icon">?</span><span class="stats-brain-tip-text">'+t('dash.brain.tip.kinetic')+'</span></span></div>';
  h+='<div class="stats-brain-dim-en">'+t('dash.brain.kinetic.en')+'</div>';
  h+='<div class="stats-brain-dim-val'+kinCls+'">'+neuralKin+'%</div>';
  h+='<div class="stats-brain-dim-label'+kinCls+'">'+t('dash.brain.kinetic.metric')+' · '+kinState+'</div>';
  h+='<div class="stats-brain-dim-status'+kinCls+'">'+kinText+'</div></div>';
  h+='</div>';

  var nodes=[
    {id:'L1',label:t('dash.mem.L1'),pct:l1pct},
    {id:'L2',label:t('dash.mem.L2'),pct:l2rate},
    {id:'L3',label:t('dash.mem.L3'),pct:l3pct},
    {id:'L4',label:t('dash.mem.L4'),pct:l4pct},
    {id:'L5',label:t('dash.mem.L5'),pct:l5pct},
    {id:'L6',label:t('dash.mem.L6'),pct:l6rate},
    {id:'L7',label:t('dash.mem.L7'),pct:l7rate},
    {id:'L8',label:t('dash.mem.L8'),pct:l8pct}
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

  if(baseTone<90&&l4q>5){
    h+='<div class="stats-module-hint amber">'+t('dash.brain.warning.baseLow')+'</div>';
  }

  var flashC=mem.flash_count||0;
  var traceC=mem.trace_back_count||0;
  var totalC=flashC+traceC;
  h+='<div class="stats-cod-section">';
  h+='<div class="stats-cod-header"><span class="stats-cod-title">'+t('dash.cod.title')+'</span><span class="stats-cod-total">'+(totalC>0?tf('dash.cod.total',totalC):t('dash.cod.total.none'))+'</span></div>';
  if(totalC===0){
    h+='<div class="stats-cod-empty">'+t('dash.cod.empty')+'</div>';
  }else{
    var flashPct=Math.round(flashC/totalC*100);
    var tracePct=100-flashPct;
    var modeLabel=flashPct>=80?t('dash.cod.mode.flash'):flashPct>=60?t('dash.cod.mode.warm'):tracePct>=60?t('dash.cod.mode.trace'):t('dash.cod.mode.balanced');
    var modeLabelColor=flashPct>=60?'var(--tone-amber)':'var(--tone-steel)';
    var r=44,cx=60,cy=60,circ=2*Math.PI*r;
    var flashDash=circ*(flashPct/100);
    var traceDash=circ*(tracePct/100);
    var ringOpacity=Math.max(0.7,compositeRate/100);
    h+='<div class="stats-cod-ring-row">';
    h+='<div class="stats-cod-ring-wrap">';
    h+='<svg width="120" height="120" viewBox="0 0 120 120">';
    h+='<defs><filter id="codGlow"><feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" style="stroke:var(--divider-panel)" stroke-width="11"/>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" style="stroke:var(--tone-amber)" stroke-width="11" stroke-linecap="butt" stroke-dasharray="'+flashDash+' '+circ+'" transform="rotate(-90 '+cx+' '+cy+')" opacity="'+ringOpacity+'" filter="url(#codGlow)"/>';
    h+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" style="stroke:var(--tone-steel)" stroke-width="11" stroke-linecap="butt" stroke-dasharray="'+traceDash+' '+circ+'" transform="rotate('+((-90)+flashPct*3.6)+' '+cx+' '+cy+')" opacity="'+ringOpacity+'" filter="url(#codGlow)"/>';
    h+='<text x="'+cx+'" y="'+(cy+5)+'" text-anchor="middle" fill="'+modeLabelColor+'" font-size="13" font-weight="600" font-family="inherit">'+modeLabel+'</text>';
    h+='<text x="'+cx+'" y="'+(cy+18)+'" text-anchor="middle" style="fill:var(--text-label)" font-size="8.5" font-family="inherit" letter-spacing="0.3">'+t('dash.cod.auto')+'</text>';
    h+='</svg></div>';
    h+='<div class="stats-cod-data">';
    h+='<div class="stats-cod-row"><span class="stats-cod-dot" style="background:var(--tone-amber);"></span><span class="stats-cod-row-label">'+t('dash.cod.flash')+'<span class="stats-cod-row-desc">'+t('dash.cod.flash.desc')+'</span></span><span class="stats-cod-row-val" style="color:var(--tone-amber);">'+flashPct+'%</span><span class="stats-cod-row-sub">'+flashC+'</span></div>';
    h+='<div class="stats-cod-row"><span class="stats-cod-dot" style="background:var(--tone-steel);"></span><span class="stats-cod-row-label">'+t('dash.cod.trace')+'<span class="stats-cod-row-desc">'+t('dash.cod.trace.desc')+'</span></span><span class="stats-cod-row-val" style="color:var(--tone-steel);">'+tracePct+'%</span><span class="stats-cod-row-sub">'+traceC+'</span></div>';
    h+='</div></div>';
    h+='<div class="stats-cod-footer">'+t('dash.cod.footer')+'</div>';
  }
  h+='</div>';
  h+='</div></div>';
  return h;
}

function buildSceneModule(s){
  var bs=normalizeSceneStats(s.by_scene);
  var scenes=[{k:'chat',n:t('dash.scene.chat')},{k:'route',n:t('dash.scene.route')},{k:'skill',n:t('dash.scene.skill')},{k:'learn',n:t('dash.scene.learn')}];
  var totalSceneTokens=0;
  scenes.forEach(function(sc){ totalSceneTokens+=(bs[sc.k]||{}).tokens||0; });
  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.scene.title')+'</div>';
  if(totalSceneTokens>0){
    var sorted=scenes.slice().sort(function(a,b){ return ((bs[b.k]||{}).tokens||0)-((bs[a.k]||{}).tokens||0); });
    h+='<div class="stats-module"><div class="stats-bars">';
    sorted.forEach(function(sc){
      var tokens=(bs[sc.k]||{}).tokens||0,req=(bs[sc.k]||{}).requests||0;
      var pct=totalSceneTokens>0?Math.round(tokens/totalSceneTokens*100):0;
      var barW=pct>0?Math.max(pct,4):0;
      h+='<div class="stats-bar-row"><div class="stats-bar-label">'+sc.n+'</div>';
      h+='<div class="stats-bar-track"><div class="stats-bar-fill stats-scene-'+sc.k+'" style="width:'+barW+'%"></div></div>';
      h+='<div class="stats-bar-pct">'+pct+'% <span style="opacity:0.5;font-size:11px;">'+req+' · '+fmtN(tokens)+'t</span></div></div>';
    });
    h+='</div></div>';
  }else{
    h+='<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">'+t('dash.scene.empty')+'</div>';
  }
  h+='</div>';
  return h;
}

function buildTrendModule(s){
  var byDay=s.by_day||{};
  var dayKeys=[];
  var now=new Date();
  for(var di=6;di>=0;di--){
    var dd=new Date(now);
    dd.setDate(dd.getDate()-di);
    dayKeys.push(dd.toISOString().slice(0,10));
  }
  window._statsTrendData={byDay:byDay,dayKeys:dayKeys};
  var h='<div class="stats-section"><div class="stats-section-title" style="justify-content:space-between;">';
  h+='<span>'+t('dash.trend.title')+'</span><div style="display:flex;gap:4px;">';
  [{k:'tokens',n:t('dash.trend.tokens')},{k:'requests',n:t('dash.trend.requests')}].forEach(function(d,i){
    h+='<span class="stats-trend-tab'+(i===0?' stats-highlight':'')+'" data-dim="'+d.k+'" onclick="switchTrendDim(\''+d.k+'\')" style="cursor:pointer;font-size:11px;padding:2px 8px;border-radius:6px;'+(i===0?'background:var(--tone-sage-soft);':'')+'">'+d.n+'</span>';
  });
  h+='</div></div>';
  h+='<div id="statsTrendChart">'+renderTrendBars(byDay,dayKeys,'tokens')+'</div>';
  var first=(byDay[dayKeys[0]]||{}).tokens||0;
  var last=(byDay[dayKeys[6]]||{}).tokens||0;
  var activeDays=0;
  dayKeys.forEach(function(dk){ if((byDay[dk]||{}).tokens>0) activeDays++; });
  var hint='';
  if(activeDays<=2){
    hint=t('dash.trend.accumulating');
  }else if(first>0&&last>0){
    var change=Math.round((last-first)/Math.max(first,1)*100);
    if(change>30) hint=tf('dash.trend.up',change);
    else if(change<-30) hint=t('dash.trend.down');
    else hint=t('dash.trend.stable');
  }else{
    hint=t('dash.trend.building');
  }
  h+='<div class="stats-module-hint" style="margin-top:8px;">'+hint+'</div></div>';
  return h;
}

function renderTrendBars(byDay,dayKeys,dim){
  var dayMax=0;
  dayKeys.forEach(function(dk){
    var value=(byDay[dk]||{})[dim]||0;
    if(value>dayMax) dayMax=value;
  });
  if(dayMax===0) return '<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">'+t('dash.trend.nodata')+'</div>';
  var h='<div class="stats-trend"><div class="stats-trend-bars">';
  dayKeys.forEach(function(dk){
    var value=(byDay[dk]||{})[dim]||0;
    var pct=dayMax>0?Math.max(3,Math.round(value/dayMax*100)):3;
    h+='<div class="stats-trend-col"><div class="stats-trend-val">'+fmtN(value)+'</div><div class="stats-trend-bar" style="height:'+pct+'%"></div><div class="stats-trend-label">'+dk.slice(5)+'</div></div>';
  });
  h+='</div></div>';
  return h;
}

function switchTrendDim(dim){
  var d=window._statsTrendData;
  if(!d) return;
  document.getElementById('statsTrendChart').innerHTML=renderTrendBars(d.byDay,d.dayKeys,dim);
  var tabs=document.querySelectorAll('.stats-trend-tab');
  tabs.forEach(function(tab){
    if(tab.getAttribute('data-dim')===dim){
      tab.classList.add('stats-highlight');
      tab.style.background='var(--tone-sage-soft)';
    }else{
      tab.classList.remove('stats-highlight');
      tab.style.background='';
    }
  });
}

function buildDiagModule(s){
  var items=[];
  var pr=s.prices||getPrice(s.model);
  var cHit=s.cache_read_tokens||0;
  var cMiss=(s.input_tokens||0)-cHit;
  var costYuan=(Math.max(0,cMiss)*pr.i+cHit*pr.i*0.1+(s.output_tokens||0)*pr.o)/1e6;
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
  var bs=normalizeSceneStats(s.by_scene);
  var totalST=0;
  var chatPct=0;
  var avgCostD=totalReq>0?costYuan/totalReq:0;
  var skillReqs=(bs.skill||{}).requests||0;

  if(costYuan>10) items.push({t:'warn',m:tf('dash.diag.costHigh',costYuan.toFixed(2))});
  else if(costYuan>0) items.push({t:'ok',m:tf('dash.diag.costOk',costYuan.toFixed(2))});
  if(inp>0&&out>inp*2) items.push({t:'warn',m:tf('dash.diag.outputHigh',Math.round(out/inp))});
  if(cacheRate>=50) items.push({t:'ok',m:tf('dash.diag.cacheSaved',fmtN(cacheRead))});
  if(l2rate>=30&&l8rate>=20) items.push({t:'ok',m:t('dash.diag.memGood')});
  else if(l8rate<10&&l8s>5) items.push({t:'warn',c:'mem',m:tf('dash.diag.l8Low',l8rate)});
  if(l2rate<20&&l2s>5) items.push({t:'warn',c:'mem',m:tf('dash.diag.l2Low',l2rate)});
  [{k:'chat'},{k:'skill'}].forEach(function(sc){ totalST+=(bs[sc.k]||{}).tokens||0; });
  chatPct=totalST>0?Math.round(((bs.chat||{}).tokens||0)/totalST*100):0;
  if(chatPct>=85) items.push({t:'warn',m:tf('dash.diag.chatHigh',chatPct)});
  if(avgT>2000) items.push({t:'warn',m:tf('dash.diag.avgHigh',fmtN(avgT))});
  if(items.length===0) items.push({t:'ok',m:t('dash.diag.allOk')});
  if(l2rate>=80&&avgCostD<0.01&&totalReq>50) items.push({t:'ok',c:'mem',m:tf('dash.diag.memCost',avgCostD.toFixed(4))});
  if(skillReqs>20) items.push({t:'ok',c:'scene',m:tf('dash.diag.skillRoute',skillReqs)});

  var h='<div class="stats-section"><div class="stats-section-title">'+t('dash.diag.title')+'</div><div class="stats-diag">';
  items.forEach(function(it){
    var dotCls=it.t==='warn'?' warn':'';
    if(it.c==='cost') dotCls+=' cost';
    else if(it.c==='mem') dotCls+=' mem';
    else if(it.c==='scene') dotCls+=' scene';
    h+='<div class="stats-diag-item"><div class="stats-diag-dot'+dotCls+'"></div><div>'+it.m+'</div></div>';
  });
  h+='</div></div>';
  return h;
}
