// === 统计页驾驶舱 ===
function fmtN(n){if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e4)return(n/1e3).toFixed(1)+'K';return n.toLocaleString();}

var PRICE={'deepseek':{i:1,o:2},'minimax':{i:1,o:2},'qwen':{i:2,o:6},'glm':{i:1,o:1}};
function getPrice(model){var m=(model||'').toLowerCase();for(var k in PRICE){if(m.indexOf(k)!==-1)return PRICE[k];}return{i:2,o:4};}

// 顶部4个摘要卡
function buildSummaryCards(s,costYuan,cacheRate,compositeRate,topScene){
  var h='<div class="stats-summary">';
  // 1.成本概览
  var costHint=costYuan<1?'运行成本很低，轻松运行中':'运行成本平稳，保持得不错';
  var costCls='';
  if(costYuan>10){costHint='成本稍高，可以留意输出占比';costCls=' warn';}
  h+='<div class="stats-summary-card"><div class="stats-summary-label">运行成本</div>';
  h+='<div class="stats-summary-value">\u00a5'+costYuan.toFixed(2)+'</div>';
  h+='<div class="stats-summary-hint'+costCls+'">'+costHint+'</div></div>';
  // 2.Tokens 吞吐
  var totalTk=s.total_tokens||0;
  var inpTk=s.input_tokens||0;
  var inPct=totalTk>0?Math.round(inpTk/totalTk*100):0;
  h+='<div class="stats-summary-card"><div class="stats-summary-label">Tokens \u541e\u5410</div>';
  h+='<div class="stats-summary-value">'+fmtN(totalTk)+'</div>';
  h+='<div class="stats-summary-hint">\u8f93\u5165\u5360 '+inPct+'%</div></div>';
  // 3.记忆深度
  var memHint=compositeRate>=50?'\u547d\u4e2d\u826f\u597d\uff0c\u6301\u7eed\u6210\u957f':'\u79ef\u7d2f\u4e2d\uff0c\u8d8a\u7528\u8d8a\u51c6';
  var memCls=compositeRate<30?' warn':'';
  h+='<div class="stats-summary-card"><div class="stats-summary-label">\u8bb0\u5fc6\u6548\u7387</div>';
  h+='<div class="stats-summary-value">'+compositeRate+'%</div>';
  h+='<div class="stats-summary-hint'+memCls+'">'+memHint+'</div></div>';
  // 4.平均单次
  var totalReq=s.total_requests||0;
  var avgCost=totalReq>0?(costYuan/totalReq):0;
  var avgHint=totalReq>0?('\u5171 '+totalReq+' \u6b21\u5bf9\u8bdd'):'\u6682\u65e0\u5bf9\u8bdd\u6570\u636e';
  h+='<div class="stats-summary-card"><div class="stats-summary-label">\u5e73\u5747\u5355\u6b21</div>';
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
  var h='<div class="stats-section"><div class="stats-section-title">运行成本</div>';
  h+='<div class="stats-module"><div class="stats-cost-grid">';
  // 左主区：三段式费用
  h+='<div class="stats-cost-main">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">输入成本</span><span style="font-weight:600;">¥'+costNew.toFixed(3)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">缓存复用</span><span style="font-weight:600;color:#6a9fd8;">¥'+costCache.toFixed(4)+'</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">输出成本</span><span style="font-weight:600;">¥'+costOut.toFixed(4)+'</span></div>';
  h+='<div class="stats-kv-mini" style="margin-top:4px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.04);"><span class="stats-kv-label">实际总费用</span><span style="font-weight:700;color:#6aaa88;">¥'+costYuan.toFixed(2)+'</span></div>';
  if(saved>0){h+='<div class="stats-kv-mini"><span class="stats-kv-label">记忆系统节省</span><span style="font-weight:600;color:#6aaa88;">¥'+saved.toFixed(4)+'</span></div>';}
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">平均/次</span><span style="font-weight:600;">¥'+avgCost.toFixed(4)+'</span></div>';
  h+='</div>';
  // 右辅区：平均维度
  var avgInp=totalReq>0?Math.round(inp/totalReq):0;
  var avgOut=totalReq>0?Math.round(out/totalReq):0;
  var inPct=total>0?Math.round(inp/total*100):0;
  h+='<div class="stats-cost-sub">';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">总请求</span><span>'+totalReq.toLocaleString()+'次</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">总 Tokens</span><span>'+fmtN(total)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">输入</span><span>'+fmtN(cw)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">缓存复用</span><span>'+fmtN(cr)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">输出</span><span>'+fmtN(out)+' tokens</span></div>';
  h+='<div class="stats-kv-mini" style="margin-top:4px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.04);"><span class="stats-kv-label">平均输入/次</span><span>'+fmtN(avgInp)+' tokens</span></div>';
  h+='<div class="stats-kv-mini"><span class="stats-kv-label">平均输出/次</span><span>'+avgOut+' tokens</span></div>';
  h+='</div></div>';
  h+='</div></div>';
  return h;
}

// 主渲染入口
function renderStats(s){
  var bs=s.by_scene||{};
  var pr=getPrice(s.model);
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
  var scenes=[{k:'chat',n:'\u804a\u5929'},{k:'route',n:'\u8def\u7531'},{k:'skill',n:'\u6280\u80fd'},{k:'learn',n:'\u5b66\u4e60'}];
  var topScene='\u804a\u5929',topVal=0;
  scenes.forEach(function(sc){var t=(bs[sc.k]||{}).tokens||0;if(t>topVal){topVal=t;topScene=sc.n;}});

  var h='';
  h+=buildSummaryCards(s,costYuan,cacheRate,compositeRate,topScene);
  h+=buildCostModule(s,pr,costYuan);
  h+=buildMemoryModule(s);
  h+=buildSceneModule(s);
  h+=buildTrendModule(s);
  h+=buildDiagModule(s);
  h+='<div class="stats-footer"><div class="stats-footer-info">\u6700\u540e\u4f7f\u7528\uff1a'+(s.last_used||'-')+'</div></div>';
  return h;
}

// 记忆引擎模块（结构化链路图）
function buildMemoryModule(s){
  var mem=s.memory||{};
  var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
  var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
  var tq=mem.total_queries||0,fla=mem.full_layer_available||0;
  var fullPct=tq>0?Math.round(fla/(tq*4)*100):0;
  var searchHits=l2h+l8h,searchTotal=l2s+l8s;
  var searchPct=searchTotal>0?Math.round(searchHits/searchTotal*100):0;
  var compositeRate=tq>0?Math.min(100,Math.round((fullPct+searchPct)/2)):0;
  var l2rate=l2s>0?Math.round(l2h/l2s*100):0;
  var l8rate=l8s>0?Math.round(l8h/l8s*100):0;
  var h='<div class="stats-section"><div class="stats-section-title">\u8bb0\u5fc6\u5f15\u64ce</div>';
  h+='<div class="stats-module">';
  // 主值：综合有效率
  h+='<div class="stats-mem-hero"><span class="stats-mem-hero-val">'+compositeRate+'%</span><span class="stats-mem-hero-label">综合有效率</span></div>';
  // 次值：L2/L8
  h+='<div class="stats-mem-sub">';
  h+='<div class="stats-kv"><span class="stats-kv-label">L2 命中</span><span class="stats-kv-val accent">'+l2rate+'%</span></div>';
  h+='<div class="stats-kv"><span class="stats-kv-label">L8 命中</span><span class="stats-kv-val accent">'+l8rate+'%</span></div>';
  h+='<div class="stats-kv"><span class="stats-kv-label">全量命中</span><span class="stats-kv-val">'+fullPct+'%</span></div>';
  h+='<div class="stats-kv"><span class="stats-kv-label">检索命中</span><span class="stats-kv-val">'+searchPct+'%</span></div>';
  h+='<div class="stats-kv"><span class="stats-kv-label">检索次数</span><span class="stats-kv-val">'+searchTotal+'</span></div>';
  h+='<div class="stats-kv"><span class="stats-kv-label">命中次数</span><span class="stats-kv-val">'+searchHits+'</span></div>';
  h+='</div>';
  var l1pct=Math.min(100,Math.round((mem.l1_count||0)/30*100));
  var l3pct=Math.min(100,Math.round((mem.l3_count||0)/20*100));
  var l4pct=mem.l4_available?100:0;
  var l5pct=Math.min(100,Math.round((mem.l5_count||0)/10*100));
  var nodes=[
    {id:'L1',label:'\u5bf9\u8bdd',pct:l1pct},
    {id:'L2',label:'\u8bb0\u5fc6',pct:l2rate},
    {id:'L3',label:'\u7ecf\u5386',pct:l3pct},
    {id:'L4',label:'\u4eba\u683c',pct:l4pct},
    {id:'L5',label:'\u6280\u80fd',pct:l5pct},
    {id:'L8',label:'\u77e5\u8bc6',pct:l8rate}
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
  var hint='';
  var hint='';
  if(compositeRate>=50) hint='本地记忆系统通过高价值层稳定命中，有效控制长上下文场景下的输入成本';
  else hint='记忆系统仍在早期积累，高价值层命中率有提升空间，持续使用将逐步降低输入成本';
  var cls=compositeRate<50?' amber':'';
  h+='<div class="stats-module-hint'+cls+'">'+hint+'</div>';
  h+='</div></div>';
  return h;
}

// 场景分布增强版
function buildSceneModule(s){
  var bs=s.by_scene||{};
  var scenes=[{k:'chat',n:'\u804a\u5929'},{k:'route',n:'\u8def\u7531'},{k:'skill',n:'\u6280\u80fd'},{k:'learn',n:'\u5b66\u4e60'}];
  var totalSceneTokens=0;
  scenes.forEach(function(sc){totalSceneTokens+=(bs[sc.k]||{}).tokens||0;});
  var h='<div class="stats-section"><div class="stats-section-title">\u573a\u666f\u6d3b\u8dc3\u5ea6</div>';
  if(totalSceneTokens>0){
    var sorted=scenes.slice().sort(function(a,b){return((bs[b.k]||{}).tokens||0)-((bs[a.k]||{}).tokens||0);});
    h+='<div class="stats-module"><div class="stats-bars">';
    sorted.forEach(function(sc){
      var t=(bs[sc.k]||{}).tokens||0,r=(bs[sc.k]||{}).requests||0;
      var pct=totalSceneTokens>0?Math.round(t/totalSceneTokens*100):0;
      var barW=pct>0?Math.max(pct,4):0;
      h+='<div class="stats-bar-row"><div class="stats-bar-label">'+sc.n+'</div>';
      h+='<div class="stats-bar-track"><div class="stats-bar-fill '+sc.k+'" style="width:'+barW+'%"></div></div>';
      h+='<div class="stats-bar-pct">'+pct+'% <span style="opacity:0.5;font-size:11px;">'+r+'\u6b21 '+fmtN(t)+'t</span></div></div>';
    });
    h+='</div></div>';
  }else{
    h+='<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">\u804a\u51e0\u53e5\u5c31\u6709\u6570\u636e\u4e86</div>';
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
  h+='<span>\u6210\u957f\u8d8b\u52bf</span>';
  h+='<div style="display:flex;gap:4px;">';
  var dims=[{k:'tokens',n:'Tokens'},{k:'requests',n:'\u8bf7\u6c42'}];
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
    hint='趋势数据仍在积累，当前更适合观察短期活跃变化';
  }else if(first>0&&last>0){
    var change=Math.round((last-first)/Math.max(first,1)*100);
    if(change>30) hint='近 7 天使用频率提升 '+change+'%，活跃度明显上升';
    else if(change<-30) hint='近 7 天使用频率有所回落，可以留意变化';
    else hint='近 7 天使用频率保持平稳';
  }else{hint='数据正在积累，继续使用将展示完整趋势';}
  h+='<div class="stats-module-hint" style="margin-top:8px;">'+hint+'</div></div>';
  return h;
}

function renderTrendBars(byDay,dayKeys,dim){
  var dayMax=0;
  dayKeys.forEach(function(dk){var v=(byDay[dk]||{})[dim]||0;if(v>dayMax)dayMax=v;});
  if(dayMax===0) return '<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">\u6682\u65e0\u6309\u5929\u6570\u636e</div>';
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
  var pr=getPrice(s.model);
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
  if(costYuan>10) items.push({t:'warn',m:'\u8d39\u7528\u5df2\u8fbe \u00a5'+costYuan.toFixed(2)+'\uff0c\u5173\u6ce8\u9ad8\u9891\u8f7b\u4efb\u52a1\u662f\u5426\u9002\u5408\u964d\u7ea7\u6a21\u578b'});
  else if(costYuan>0) items.push({t:'ok',m:'\u8fd0\u884c\u6210\u672c \u00a5'+costYuan.toFixed(2)+'\uff0c\u6574\u4f53\u53ef\u63a7'});
  if(inp>0&&out>inp*2) items.push({t:'warn',m:'\u8f93\u51fa Tokens \u662f\u8f93\u5165\u7684 '+Math.round(out/inp)+' \u500d\uff0c\u56de\u590d\u504f\u5197\u957f'});
  if(cacheRate>=50) items.push({t:'ok',m:'\u6a21\u578b\u7f13\u5b58\u8282\u7701\u4e86 '+fmtN(cacheRead)+' token \u7684\u91cd\u590d\u8ba1\u7b97'});
  if(l2rate>=30&&l8rate>=20) items.push({t:'ok',m:'\u8bb0\u5fc6\u7cfb\u7edf L2/L8 \u547d\u4e2d\u826f\u597d\uff0c\u77e5\u8bc6\u79ef\u7d2f\u5728\u53d1\u6325\u4f5c\u7528'});
  else if(l8rate<10&&l8s>5) items.push({t:'warn',c:'mem',m:'L8 \u77e5\u8bc6\u547d\u4e2d\u7387\u504f\u4f4e ('+l8rate+'%)\uff0c\u957f\u671f\u6210\u957f\u8bb0\u5fc6\u6c89\u6dc0\u4e0d\u8db3'});
  if(l2rate<20&&l2s>5) items.push({t:'warn',c:'mem',m:'L2 \u8bb0\u5fc6\u547d\u4e2d\u7387\u504f\u4f4e ('+l2rate+'%)'});
  var totalST=0;
  [{k:'chat'},{k:'skill'}].forEach(function(sc){totalST+=(bs[sc.k]||{}).tokens||0;});
  var chatPct=totalST>0?Math.round(((bs.chat||{}).tokens||0)/totalST*100):0;
  if(chatPct>=85) items.push({t:'warn',m:'\u804a\u5929\u573a\u666f\u5360\u6bd4 '+chatPct+'%\uff0c\u53ef\u5c1d\u8bd5\u66f4\u591a\u6280\u80fd\u4ea4\u4e92'});
  if(avgT>2000) items.push({t:'warn',m:'\u5e73\u5747\u5355\u6b21\u6d88\u8017 '+fmtN(avgT)+' token\uff0c\u5173\u6ce8\u4e0a\u4e0b\u6587\u957f\u5ea6'});
  if(items.length===0) items.push({t:'ok',m:'\u7cfb\u7edf\u8fd0\u884c\u6b63\u5e38\uff0c\u6682\u65e0\u9700\u8981\u5173\u6ce8\u7684\u95ee\u9898'});
  // 成本×记忆关联
  var avgCostD=totalReq>0?costYuan/totalReq:0;
  var skillReqs=(bs.skill||{}).requests||0;
  if(l2rate>=80&&avgCostD<0.01&&totalReq>50) items.push({t:'ok',c:'mem',m:'记忆系统稳定命中，单次平均仅 ¥'+avgCostD.toFixed(4)+'，长上下文场景下成本保持可控'});
  if(skillReqs>20) items.push({t:'ok',c:'scene',m:'技能路由已承担 '+skillReqs+' 次请求，减少了对 LLM 的直接依赖'});
  var h='<div class="stats-section"><div class="stats-section-title">\u7cfb\u7edf\u6d1e\u5bdf</div><div class="stats-diag">';
  items.forEach(function(it){
    var dotCls=it.t==='warn'?' warn':''; if(it.c==='cost')dotCls+=' cost'; else if(it.c==='mem')dotCls+=' mem'; else if(it.c==='scene')dotCls+=' scene';
    h+='<div class="stats-diag-item"><div class="stats-diag-dot'+dotCls+'"></div><div>'+it.m+'</div></div>';
  });
  h+='</div></div>';
  return h;
}
