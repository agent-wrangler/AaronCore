// Skill catalog, modal, and skill action surfaces
// Source: app.js lines 1095-1769

// ── 技能商店 ──
var _skillIcons={
 '\u5929\u6c14':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M6.34 17.66l-1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/><circle cx="12" cy="12" r="4"/></svg>',
 '\u80a1\u7968':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
 '\u65b0\u95fb':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z"/><line x1="6" y1="8" x2="18" y2="8"/><line x1="6" y1="12" x2="14" y2="12"/><line x1="6" y1="16" x2="10" y2="16"/></svg>',
 '\u6587\u7ae0':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
 '\u6545\u4e8b':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>',
 '\u753b\u56fe':'<svg viewBox="0 0 24 24" width="22" height="22"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
 '\u4ee3\u7801':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
 '\u7f16\u7a0b':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>'
};
var _catIcons={
 '\u4fe1\u606f\u67e5\u8be2':'<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
 '\u5185\u5bb9\u521b\u4f5c':'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
 '\u5f00\u53d1\u5de5\u5177':'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>'
};
var _cachedSkillsData=null;
var _skillsViewScope='default';
var _skillsViewCounts={default:0,advanced:0};

function _skillsViewScopeQuery(){
 return _skillsViewScope==='advanced'?'default,advanced':'default';
}

function _renderSkillsToolbar(){
 var tabs=document.getElementById('skillsViewTabs');
 var note=document.getElementById('skillsViewNote');
 if(tabs){
  var items=[{scope:'default', label:t('skills.view.default')}];
  if((_skillsViewCounts.advanced||0)>0){
   items.push({scope:'advanced', label:t('skills.view.advanced')});
  }else if(_skillsViewScope==='advanced'){
   _skillsViewScope='default';
  }
  tabs.style.display=items.length>1?'flex':'none';
  tabs.innerHTML='';
  items.forEach(function(item){
   var active=item.scope===_skillsViewScope?' active':'';
   tabs.innerHTML+='<button class="skill-tab'+active+'" onclick="_setSkillsView(\''+item.scope+'\')">'+escapeHtml(item.label)+'</button>';
  });
 }
 if(note){
  note.textContent=_skillsViewScope==='advanced'
   ?t('skills.view.advanced.desc')
   :t('skills.view.default.desc');
 }
}

function _loadSkillsCatalogSummary(){
 fetch('/skills/catalog/summary').then(function(r){return r.json();}).then(function(d){
  var by=(d&&d.summary&&d.summary.by_user_view_scope)||{};
  var advancedCount=Number(by.advanced||0);
  var changed=_skillsViewScope==='advanced'&&advancedCount<=0;
  _skillsViewCounts={
   default:Number(by.default||0),
   advanced:advancedCount
  };
  if(changed){
   _skillsViewScope='default';
   if(window._currentTab===2){
    _loadSkillsList();
    return;
   }
  }
  _renderSkillsToolbar();
 }).catch(function(){
  _skillsViewCounts={default:0,advanced:0};
  if(_skillsViewScope==='advanced'){
   _skillsViewScope='default';
  }
  _renderSkillsToolbar();
 });
}

function _setSkillsView(scope){
 var next=scope==='advanced'?'advanced':'default';
 if(_skillsViewScope===next){
  _renderSkillsToolbar();
  return;
 }
 _skillsViewScope=next;
 _renderSkillsToolbar();
 _loadSkillsList();
}

function _loadSkillsList(){
 var list=document.getElementById('skillsList');
 if(!list) return;
 _renderSkillsToolbar();
 list.innerHTML=t('loading');
 fetch('/skills/views/user?scope='+encodeURIComponent(_skillsViewScopeQuery())).then(function(r){return r.json();}).then(function(d){
  _cachedSkillsData=d;
  if(!d||!d.skills){list.innerHTML='';return;}
  var filtered=d.skills.filter(function(s){return (s.source||'native')==='native';});
  _renderNativeSkills(filtered);
 }).catch(function(){
  list.innerHTML='<div style="color:#ef4444;">'+t('skills.load.fail')+'</div>';
 });
}

function _renderNativeSkills(skills){
 if(!Array.isArray(skills) || !skills.length){
  var emptyList=document.getElementById('skillsList');
  if(emptyList) emptyList.innerHTML='<div style="color:#94a3b8;padding:20px;">'+t('skills.empty')+'</div>';
  return;
 }
 var catOrder=[t('skills.cat.info'),t('skills.cat.content'),t('skills.cat.dev')];
 var groups={};
  catOrder.forEach(function(c){groups[c]=[];});
 skills.forEach(function(s){
  var cat=s.category||t('skills.cat.dev');
  if(!groups[cat])groups[cat]=[];
  groups[cat].push(s);
 });
 var html='';
 var renderedCount=0;
 function _appendSkillCard(skill){
  try{
   html+=_buildSkillCard(skill);
  }catch(_err){
   html+=_buildSkillFallbackCard(skill);
  }
  renderedCount++;
 }
 catOrder.forEach(function(catName){
  var items=groups[catName];
  if(!items||items.length===0)return;
  var ci=_catIcons[catName]||'';
  html+='<div class="skill-category">';
  html+='<div class="skill-category-header">'+ci+'<span class="skill-category-name">'+catName+'</span></div>';
  html+='<div class="skill-grid">';
  items.forEach(function(s){_appendSkillCard(s);});
  html+='</div></div>';
 });
 Object.keys(groups).forEach(function(cat){
  if(catOrder.indexOf(cat)===-1&&groups[cat].length>0){
   html+='<div class="skill-category"><div class="skill-category-header"><span class="skill-category-name">'+cat+'</span></div><div class="skill-grid">';
   groups[cat].forEach(function(s){_appendSkillCard(s);});
   html+='</div></div>';
  }
 });
 if(!renderedCount&&skills.length){
  html='<div class="skill-grid skill-grid-flat">';
  skills.forEach(function(s){_appendSkillCard(s);});
  html+='</div>';
 }
 if(!html) html='<div style="color:#94a3b8;padding:20px;">'+t('skills.empty')+'</div>';
 var list=document.getElementById('skillsList');
 if(list) list.innerHTML='<div class="skill-store-summary">'+tf('skills.visible.count', skills.length)+'</div>'+html;
}

function _buildSkillCard(s){
 var name=s.name||'';
 var id=s.id||'';
 var iconKey=Object.keys(_skillIcons).find(function(k){return name.indexOf(k)!==-1;});
 var icon=iconKey?_skillIcons[iconKey]:'<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
 var enabled=s.enabled!==false;
 var disabledCls=enabled?'':' disabled';
 var dotCls=enabled?'':'offline';
 var statusText=enabled?t('skills.status.ready'):t('skills.status.off');
 var html='<div class="skill-card'+disabledCls+'" id="skill-'+id+'">';
 html+='<div class="skill-card-icon">'+icon+'</div>';
 html+='<div class="skill-card-name">'+escapeHtml(name)+'</div>';
 html+='<div class="skill-card-desc">'+(s.description||t('skills.no.desc'))+'</div>';
 html+='<div class="skill-card-status"><span class="dot '+dotCls+'"></span>'+statusText+'</div>';
 html+='</div>';
 return html;
}

function _buildSkillFallbackCard(s){
 var name=escapeHtml(s&&s.name||s&&s.id||'Skill');
 var desc=escapeHtml(s&&s.description||t('skills.no.desc'));
 return '<div class="skill-card"><div class="skill-card-name">'+name+'</div><div class="skill-card-desc">'+desc+'</div></div>';
}

function _escHtml(s){
 if(!s) return '';
 return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ===== Codex-style skills surface override =====
var _skillIcons={
 weather:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 3v2"/><path d="M12 19v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M3 12h2"/><path d="M19 12h2"/><path d="M4.93 19.07l1.41-1.41"/><path d="M17.66 6.34l1.41-1.41"/><circle cx="12" cy="12" r="4"/></svg>',
 stock:'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
 news:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 5h13a3 3 0 013 3v11H7a3 3 0 01-3-3z"/><path d="M7 5v13a3 3 0 01-3-3V8a3 3 0 013-3z"/><line x1="9" y1="10" x2="17" y2="10"/><line x1="9" y1="14" x2="15" y2="14"/></svg>',
 article:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="14 3 14 9 20 9"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="14" y2="17"/></svg>',
 story:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>',
 draw:'<svg viewBox="0 0 24 24" width="22" height="22"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>',
 creator:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 5v14"/><path d="M5 12h14"/><path d="M4 4h16v16H4z" opacity="0.35"/></svg>',
 generic:'<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><circle cx="12" cy="16" r="1"/></svg>'
};
var _skillPinnedStorageKey='nova_skill_defaults_v2';
var _skillPinnedFallback=['weather'];
var _skillsCatalogCache=[];
var _skillsCatalogById={};
var _skillsSearchQuery='';
var _skillModalState=null;
var _skillToggleBusy={};
var _skillDetailCache={};
var _skillMeta={
 weather:{
  theme:'info',
  maturity:'core',
  summary:'查询城市当前天气和短期预报，适合出行前快速确认。',
  scenes:['今天和未来几天的天气概况','出门、通勤、周末安排前的快速判断'],
  boundary:'缺少城市时先确认；可以给出是否适合出门的结论，但不要把天气回复写成完整行程规划。',
  samplePrompt:'帮我看下上海今天和接下来三天的天气，顺便告诉我要不要带伞',
  promptPreview:'在用户需要当前天气或短期预报时使用。先确认城市；默认给今天和接下来几天，不先铺小时级数据。先讲温度、降雨、风和体感；如果用户在安排出行，最后补一句是否适合出门。',
  docLead:'在用户只是想先知道今天要不要带伞、周末能不能出门，或者某个城市接下来几天大概什么天气时，用这个 skill。它的目标是先把结论说清楚，再按需要展开，而不是把原始天气数据整页铺开。',
  docHighlights:['今天与未来几天的天气概况','出行、通勤、周末计划前的快速判断','需要一句明确结论再补数据的场景'],
  docQuickStart:['上海今天会下雨吗？顺手告诉我接下来三天大概怎么样','这周末杭州适合出门吗','北京今晚降温厉害吗，需要穿厚一点吗'].join('\n'),
  docNotes:['城市不明确时先追问，不硬猜。','默认先讲温度、降雨、风力和体感。','小时级细节只在用户明确需要时展开。','不要把天气回复写成旅游攻略或生活方式文章。']
 },
 news:{
  theme:'info',
  maturity:'beta',
  summary:'快速汇总最新动态，适合先建立今天发生了什么的全局感。',
  scenes:['今天最值得关注的几条动态','某个话题或行业的快速盘点'],
  boundary:'这是快速情报视图，不替代完整调研；不要把未证实信息写成定论。',
  samplePrompt:'帮我看下今天科技圈最值得关注的几条新闻，按重要性排一下',
  promptPreview:'在用户需要快速建立“今天发生了什么”的全局感时使用。先收窄话题或范围，再给 3 到 5 条最新重点；能给时间线索就给时间线索，变化快的话题要提醒用户继续核实。',
  docLead:'这个 skill 用来先建立一个清楚的新闻面，而不是一上来就写长篇研究。先给最新几条，再由用户决定要不要继续深挖其中一条。',
  docHighlights:['今天最值得关注的几条动态','某个行业、公司或话题的快速盘点','需要带时间线索和来源感的摘要'],
  docQuickStart:['今天 AI 圈最值得关注的几条新闻是什么','帮我看下最近和苹果有关的重点动态','用 5 条以内快速总结一下今天的国际新闻'].join('\n'),
  docNotes:['先给 3 到 5 条重点，不一上来写长评。','时效性强的话题尽量带时间线索。','敏感或不稳定消息要提醒继续核实。','只有当用户要继续时，再展开其中一条。']
 },
 stock:{
  theme:'info',
  maturity:'beta',
  summary:'查看股票最新价格、涨跌幅和交易时段，用于行情速查。',
  scenes:['单只股票的行情速查','需要一句数字结论再补充背景'],
  boundary:'给行情和必要背景，不做收益承诺，也不把速查结果写成投资建议。',
  samplePrompt:'帮我看下英伟达现在的股价、涨跌幅和今天的交易情况',
  promptPreview:'在用户需要快速看行情时使用。先确认股票代码或公司；先给最新价格、涨跌幅和交易时段，再补一句背景。这是行情速查，不是投资建议。',
  docLead:'这是一个行情速查 skill。重点不是替用户做决策，而是把最新数字、涨跌和交易阶段先说清楚，再补上一句最必要的背景信息。',
  docHighlights:['单只股票当前价格与涨跌幅','盘前、盘中、盘后的交易阶段判断','需要先看数字再决定要不要继续分析'],
  docQuickStart:['英伟达现在多少钱，今天涨了还是跌了','帮我看下特斯拉现在的股价和交易时段','AAPL 最新价格、涨跌幅、今天整体表现'].join('\n'),
  docNotes:['代码或公司名不明确时先澄清，不要猜错标的。','先给价格、涨跌幅和交易时段，再补一句背景。','行情结果要写成速查口吻，不写成投资建议。','用户想继续分析时，再往下展开。']
 },
 article:{
  theme:'content',
  maturity:'beta',
  summary:'按指定受众和语气把素材整理成可继续修改的成稿。',
  scenes:['把零散素材整理成完整草稿','按平台、受众和语气改写'],
  boundary:'它负责把素材写顺，不负责凭空补全事实，也不替代真实采访或查证。',
  samplePrompt:'帮我把这几条素材整理成一篇面向公众号读者的短文章，语气自然一点',
  promptPreview:'在用户已经有素材、观点或方向时使用。先锁定角度、受众和语气，再把零散信息整理成一篇能继续改的成稿；不要把原始要点直接堆成段落。',
  docLead:'这个 skill 的工作不是“多写一点”，而是先把主线、角度和结构找出来，再把素材组织成一篇可以继续修改的成稿。它适合从零散材料走到首版草稿。',
  docHighlights:['把素材、提纲或碎片笔记整理成成稿','按目标平台、受众和语气重写','给出一版可继续润色的首稿'],
  docQuickStart:['把这几条采访笔记整理成一篇 800 字公众号稿','按更口语一点的语气，把这段内容改成小红书风格','我给你一些要点，你先帮我起一版正式文章'].join('\n'),
  docNotes:['先定角度、受众和语气，再动笔。','原始素材要先整理，不直接硬拼成段落。','事实不稳的地方要留复核空间。','用户指明平台或语气时，要明显向那个口味靠。']
 },
 story:{
  theme:'content',
  maturity:'beta',
  summary:'根据题材、人物和情绪写完整片段或短篇开头。',
  scenes:['短篇开头与单场景片段','需要一个能继续扩写的故事骨架'],
  boundary:'这是虚构创作 skill；不要把真实问答误写成小说，也不要把事实内容包装成虚构。',
  samplePrompt:'写一个带一点悬疑感的短篇开头，主角是个总在凌晨接到陌生电话的人',
  promptPreview:'在用户需要一个顺的故事片段时使用。先定题材、人物和情绪，再写完整片段；就算篇幅短，也要有起势、转折和落点，而不是只堆设定。',
  docLead:'这个 skill 更像一个会先把叙事跑顺的写作者，而不是设定生成器。它的目标是先写出一个能读下去的片段，再看是否继续扩写。',
  docHighlights:['短篇开头、单场景片段、故事钩子','先给设定，再落成真正的叙事','需要一个能继续扩写的故事骨架'],
  docQuickStart:['写一个赛博朋克悬疑故事的开头，主角是失业调查员','帮我写一段温柔一点的校园重逢片段','给我一个黑色幽默风格的短故事开场'].join('\n'),
  docNotes:['用户没给方向时，先补一个明确的题材或情绪走向。','就算是短篇，也要有起势、转折和落点。','设定要服务故事推进，不要只堆概念。','如果用户只要脑洞，可以先给设定和开头。']
 },
 draw:{
  theme:'content',
  maturity:'beta',
  summary:'为插画、海报和概念图生成清晰可迭代的图像提示。',
  scenes:['海报、插画、概念图方向锁定','需要一段可继续迭代的生图提示'],
  boundary:'适合锁方向和生图提示，不替代严谨排版、品牌规范或后期精修。',
  samplePrompt:'帮我写一段海报级的生图提示：赛博朋克雨夜街头，电影感，竖版',
  promptPreview:'在用户需要为插画、海报或概念图快速锁定画面方向时使用。先确认主体、风格、用途和画幅，再生成可以继续迭代的图像提示；它更适合创意方向，不替代完整设计流程。',
  docLead:'这个 skill 用来把画面方向先锁清楚，再产出一段可以继续生成、继续细化的图像提示。它擅长海报、插画和概念图，不负责最后的品牌规范和精修交付。',
  docHighlights:['海报视觉：电影海报、活动海报、封面主视觉','插画方向：角色、场景、故事氛围图','概念图：产品概念、世界观氛围、风格探索','参考延展：在已有参考图上继续明确方向'],
  docQuickStart:['主体：一只在雨夜街头奔跑的银色机械狐','风格：电影感赛博朋克插画，冷蓝霓虹','用途：竖版海报主视觉，适合做封面','补充：高对比、湿润路面反光、画面中心构图'].join('\n'),
  docNotes:['先把主体、风格、用途和画幅说清楚。','有参考图时，先说明是延展、改造还是重做。','它给出的是可继续生成的提示，不是最终设计交付。','如果用户需要品牌规范、排版和成品修图，要明确那是后续流程。']
 }
};

function _defaultPinnedSkillIds(){
 var raw=null;
 try{ raw=localStorage.getItem(_skillPinnedStorageKey); }catch(_err){}
 if(!raw) return _skillPinnedFallback.slice();
 try{
  var parsed=JSON.parse(raw);
  if(Array.isArray(parsed)){
   var ids=[];
   parsed.forEach(function(id){
    id=String(id||'').trim();
    if(id && ids.indexOf(id)===-1) ids.push(id);
   });
   return ids.length?ids:_skillPinnedFallback.slice();
  }
 }catch(_err){}
 return _skillPinnedFallback.slice();
}

function _savePinnedSkillIds(ids){
 var unique=[];
 (ids||[]).forEach(function(id){
  id=String(id||'').trim();
  if(id && unique.indexOf(id)===-1) unique.push(id);
 });
 try{ localStorage.setItem(_skillPinnedStorageKey, JSON.stringify(unique)); }catch(_err){}
}

function _getSkillIcon(skill){
 if(skill&&skill.icon_url){
  return '<img class="skill-icon-img" src="'+escapeHtml(skill.icon_url)+'" alt="">';
 }
 if(skill&&skill.pseudo) return _skillIcons.creator;
 return _skillIcons[String(skill&&skill.id||'').trim()]||_skillIcons.generic;
}

function _getSkillMeta(skill){
 var base=_skillMeta[String(skill&&skill.id||'').trim()]||{};
 return {
  theme: base.theme||((skill&&skill.category)===t('skills.cat.content')?'content':'info'),
  maturity: base.maturity||'beta',
  summary: base.summary||'',
  scenes: base.scenes||[],
  boundary: base.boundary||t('skills.boundary.default'),
  samplePrompt: base.samplePrompt||t('skills.sample.default'),
  promptPreview: base.promptPreview||'',
  docLead: base.docLead||'',
  docHighlights: base.docHighlights||[],
  docQuickStart: base.docQuickStart||'',
  docNotes: base.docNotes||[],
  guideLead: base.guideLead||'',
  guideRules: base.guideRules||[],
  delivery: base.delivery||[]
  };
}

function _buildCreatorSkillCard(){
 return {
  id:'__skill_creator__',
  pseudo:true,
  name:t('skills.creator.name'),
  description:t('skills.creator.desc'),
  category:t('skills.cat.build'),
  tags:[t('skills.tag.user'),t('skills.tag.assistant')],
  theme:'builder',
  maturity:'core'
 };
}

function _openSkillCreatorEntry(){
 _showCreateSkillModal();
}

function _decorateSkill(skill){
 var item={};
 Object.keys(skill||{}).forEach(function(key){ item[key]=skill[key]; });
 var meta=_getSkillMeta(item);
 item.theme=meta.theme;
 item.maturity=meta.maturity;
 item.scenes=meta.scenes;
 item.description=item.description||meta.summary||'';
 item.boundary=meta.boundary;
 item.samplePrompt=meta.samplePrompt;
  item.tags=[item.category||'', meta.maturity==='core'?t('skills.badge.core'):t('skills.badge.beta')].filter(Boolean);
 return item;
}

function _renderSkillsToolbar(){
 var tabs=document.getElementById('skillsViewTabs');
 var note=document.getElementById('skillsViewNote');
 var toolbar=document.getElementById('skillsToolbar');
 if(toolbar){
  toolbar.innerHTML=
   '<button class="skill-toolbar-btn" onclick="_refreshSkillsCatalog()">'+
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15.5-6.36L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15.5 6.36L3 16"/></svg>'+
    '<span>'+escapeHtml(t('common.refresh'))+'</span>'+
   '</button>'+
   '<label class="skill-search-shell">'+
    '<span class="skill-search-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="20" y1="20" x2="16.65" y2="16.65"/></svg></span>'+
    '<input class="skill-search-input" type="text" value="'+escapeHtml(_skillsSearchQuery)+'" placeholder="'+escapeHtml(t('skills.search.placeholder'))+'" oninput="_onSkillSearch(this.value)">'+
   '</label>'+
   '<button class="skill-primary-btn" onclick="_openSkillCreatorEntry()">'+
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>'+
    '<span>'+escapeHtml(t('skills.new'))+'</span>'+
   '</button>';
 }
 if(tabs){
  tabs.style.display='none';
  tabs.innerHTML='';
 }
 if(note){
  note.textContent='';
  note.style.display='none';
 }
}

function _refreshSkillsCatalog(){
 _loadSkillsList();
}

function _onSkillSearch(value){
 _skillsSearchQuery=String(value||'').trim();
 _renderNativeSkills(_skillsCatalogCache);
}

function _loadSkillsList(){
 var list=document.getElementById('skillsList');
 if(!list) return;
 _renderSkillsToolbar();
 list.innerHTML=t('loading');
 fetch('/skills/views/user?scope=default').then(function(r){return r.json();}).then(function(d){
  _cachedSkillsData=d;
  if(!d||!d.skills){list.innerHTML='';return;}
  _skillsCatalogById={};
  _skillDetailCache={};
  _skillsCatalogCache=d.skills.filter(function(s){
   return (s.source||'native')==='native';
  }).map(function(s){
   var item=_decorateSkill(s);
   _skillsCatalogById[item.id]=item;
   return item;
  });
  _renderNativeSkills(_skillsCatalogCache);
 }).catch(function(){
  list.innerHTML='<div style="color:#ef4444;">'+t('skills.load.fail')+'</div>';
 });
}

function _skillMatchesQuery(skill, query){
 if(!query) return true;
 var haystack=[
  skill.name||'',
  skill.description||'',
  skill.category||'',
  (skill.tags||[]).join(' '),
  ((skill.keywords||[])||[]).join(' ')
 ].join(' ').toLowerCase();
 return haystack.indexOf(query.toLowerCase())!==-1;
}

function _buildSkillSection(title, desc, cards, sectionName){
 var html='<section class="skill-section">';
 html+='<div class="skill-section-head">';
 html+='<div><div class="skill-section-title">'+escapeHtml(title)+'</div>'+(desc?'<div class="skill-section-desc">'+escapeHtml(desc)+'</div>':'')+'</div>';
 html+='</div>';
 if(!cards.length){
  html+='<div class="skill-section-empty">'+escapeHtml(sectionName==='installed'?t('skills.empty.installed'):t('skills.empty.search'))+'</div>';
 }else{
  html+='<div class="skill-grid skill-grid-shelf">';
  cards.forEach(function(skill){ html+=_buildSkillCard(skill, sectionName); });
  html+='</div>';
 }
 html+='</section>';
 return html;
}

function _renderNativeSkills(skills){
 var list=document.getElementById('skillsList');
 if(!list) return;
 if(!Array.isArray(skills) || !skills.length){
  list.innerHTML='<div class="skill-section-empty">'+escapeHtml(t('skills.empty'))+'</div>';
  return;
 }
 var visible=skills.filter(function(skill){ return _skillMatchesQuery(skill, _skillsSearchQuery); });
 if(!visible.length){
  list.innerHTML='<div class="skill-section-empty">'+escapeHtml(t('skills.empty.search'))+'</div>';
  return;
 }
 var installed=visible.slice();
 var html=_buildSkillSection(t('skills.section.installed'), '', installed, 'installed');
 list.innerHTML=html;
}

function _skillBadgeHtml(label, cls){
 return '<span class="skill-pill '+cls+'">'+escapeHtml(label)+'</span>';
}

function _buildSkillCard(skill, sectionName){
 var icon=_getSkillIcon(skill);
 var enabled=skill.enabled!==false;
 var busy=!!_skillToggleBusy[skill.id];
 var actionHtml='<div class="skill-manage-wrap"><div class="skill-manage-label">'+escapeHtml(t('skills.action.manage'))+'</div><button class="skill-icon-btn skill-manage-btn" onclick="return _onSkillCardAction(event,\''+skill.id+'\',\'detail\')" title="'+escapeHtml(t('skills.action.manage'))+'"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6z"></path></svg></button></div>';
 actionHtml+='<button class="skill-switch '+(enabled?'is-on':'')+(busy?' is-busy':'')+'" onclick="return _onSkillCardAction(event,\''+skill.id+'\',\'toggle\')" title="'+escapeHtml(enabled?t('skills.action.disable'):t('skills.action.enable'))+'"'+(busy?' disabled':'')+'><span class="skill-switch-track"><span class="skill-switch-thumb"></span></span></button>';
 var html='<article class="skill-shelf-card theme-'+escapeHtml(skill.theme||'info')+(enabled?'':' is-disabled')+'" onclick="_openSkillModalById(\''+skill.id+'\')">';
 html+='<div class="skill-shelf-icon">'+icon+'</div>';
 html+='<div class="skill-shelf-main">';
 html+='<div class="skill-shelf-title-row"><div class="skill-shelf-title">'+escapeHtml(skill.name||skill.id||'Skill')+'</div></div>';
 html+='<div class="skill-shelf-desc">'+escapeHtml(skill.description||t('skills.no.desc'))+'</div>';
 html+='</div>';
 html+='<div class="skill-shelf-side">'+actionHtml+'</div>';
 html+='</article>';
 return html;
}

function _onSkillCardAction(evt, skillId, action){
 if(evt){
  evt.preventDefault();
  evt.stopPropagation();
 }
 if(action==='create'){
  _showCreateSkillModal();
  return false;
 }
 if(action==='detail'){
  _openSkillModalById(skillId);
  return false;
 }
 if(action==='toggle'){
  _toggleSkillEnabled(skillId);
  return false;
 }
 return false;
}

function _toggleSkillEnabled(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill || _skillToggleBusy[skillId]) return;
 _skillToggleBusy[skillId]=true;
 _renderNativeSkills(_skillsCatalogCache);
 fetch('/skills/'+encodeURIComponent(skillId)+'/toggle', {method:'POST'}).then(function(r){return r.json();}).then(function(d){
  if(d && d.ok){
   var enabled=d.enabled!==false;
   if(_skillsCatalogById[skillId]) _skillsCatalogById[skillId].enabled=enabled;
   _skillsCatalogCache=_skillsCatalogCache.map(function(item){
    if(item.id===skillId){
     item.enabled=enabled;
    }
    return item;
   });
  }
 }).catch(function(){}).finally(function(){
  delete _skillToggleBusy[skillId];
  _renderNativeSkills(_skillsCatalogCache);
  if(_skillModalState && _skillModalState.id===skillId) _openSkillModalById(skillId);
 });
}

function _copyText(text){
 text=String(text||'');
 if(!text) return;
 if(navigator.clipboard && navigator.clipboard.writeText){
  navigator.clipboard.writeText(text).catch(function(){});
  return;
 }
 try{
  var input=document.createElement('textarea');
  input.value=text;
  input.setAttribute('readonly','readonly');
  input.style.position='fixed';
  input.style.opacity='0';
  document.body.appendChild(input);
  input.select();
  document.execCommand('copy');
  if(input.parentNode) input.parentNode.removeChild(input);
 }catch(_err){}
}

function _copySkillPrompt(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill) return false;
 _copyText(_buildSkillPromptPreview(skill));
 return false;
}

function _openSkillFolder(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill) return false;
 fetch('/skills/'+encodeURIComponent(skillId)+'/open-folder', {method:'POST'}).catch(function(){});
 return false;
}

function _buildSkillPromptPreview(skill){
 return String((skill&&skill.default_prompt)||'').trim();
}

function _renderSkillModal(content){
 _closeSkillModal(true);
 var host=document.createElement('div');
 host.id='skillModalHost';
 host.innerHTML='<div class="skill-modal-backdrop" onclick="_closeSkillModal()"><div class="skill-modal" onclick="event.stopPropagation()">'+content+'</div></div>';
 document.body.appendChild(host);
 document.body.classList.add('skill-modal-open');
}

function _closeSkillModal(silent){
 var host=document.getElementById('skillModalHost');
 if(host && host.parentNode) host.parentNode.removeChild(host);
 document.body.classList.remove('skill-modal-open');
 if(!silent) _skillModalState=null;
}

function _buildSkillDetailSections(skill){
 return '<div class="skill-modal-doc">'+String((skill&&skill.body_html)||'')+'</div>';
}

function _renderInstalledSkillModal(skill){
 if(!skill) return;
 var enabled=skill.enabled!==false;
 var disableLabel=enabled?t('skills.action.disable'):t('skills.action.enable');
 var promptPreview=_buildSkillPromptPreview(skill);
 var content='';
 content+='<button class="skill-modal-close" onclick="_closeSkillModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>';
 content+='<div class="skill-modal-header"><div class="skill-modal-icon theme-'+escapeHtml(skill.theme||'info')+'">'+_getSkillIcon(skill)+'</div><div class="skill-modal-head-main"><div class="skill-modal-title">'+escapeHtml(skill.name||skill.id)+'</div><div class="skill-modal-subtitle">'+escapeHtml(skill.description||t('skills.no.desc'))+'</div></div><div class="skill-modal-head-actions"><button class="skill-modal-link" onclick="return _openSkillFolder(\''+skill.id+'\')">'+escapeHtml(t('skills.action.openFolder'))+' <span>&#8599;</span></button></div></div>';
 if(promptPreview){
  content+='<div class="skill-modal-prompt-panel"><div class="skill-modal-prompt-head"><div class="skill-modal-section-title">'+escapeHtml(t('skills.detail.example'))+'</div><button class="skill-modal-copy" onclick="return _copySkillPrompt(\''+skill.id+'\')" title="'+escapeHtml(t('skills.action.copyPrompt'))+'"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="10" height="10" rx="2"></rect><path d="M5 15V7a2 2 0 0 1 2-2h8"></path></svg></button></div><div class="skill-modal-prompt-text">'+escapeHtml(promptPreview)+'</div></div>';
 }
 content+='<div class="skill-modal-scroll"><div class="skill-modal-body">'+_buildSkillDetailSections(skill)+'</div></div>';
 content+='<div class="skill-modal-actions"><div class="skill-modal-actions-left"><button class="skill-modal-btn ghost" onclick="_toggleSkillEnabled(\''+skill.id+'\')">'+escapeHtml(disableLabel)+'</button></div><div class="skill-modal-actions-right"><button class="skill-modal-btn primary" onclick="_trySkill(\''+skill.id+'\')">'+escapeHtml(t('skills.action.try'))+'</button></div></div>';
 _renderSkillModal(content);
}

function _openSkillModalById(skillId){
 if(skillId==='__skill_creator__'){
  _showCreateSkillModal();
  return;
 }
 var skill=_skillsCatalogById[skillId];
 if(!skill) return;
 _skillModalState={id:skillId};
 if(_skillDetailCache[skillId]){
  var merged=Object.assign({}, skill, _skillDetailCache[skillId]);
  _skillsCatalogById[skillId]=merged;
  _renderInstalledSkillModal(merged);
  return;
 }
 _renderSkillModal(
  '<button class="skill-modal-close" onclick="_closeSkillModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>'+
  '<div class="skill-modal-header"><div class="skill-modal-icon theme-'+escapeHtml(skill.theme||'info')+'">'+_getSkillIcon(skill)+'</div><div class="skill-modal-head-main"><div class="skill-modal-title">'+escapeHtml(skill.name||skill.id)+'</div><div class="skill-modal-subtitle">'+escapeHtml(skill.description||t('skills.no.desc'))+'</div></div></div>'+
  '<div class="skill-modal-scroll"><div class="skill-modal-loading">'+escapeHtml(t('loading'))+'</div></div>'
 );
 fetch('/skills/'+encodeURIComponent(skillId)+'/detail').then(function(r){return r.json();}).then(function(d){
  if(!d || !d.ready || !d.skill) return;
  _skillDetailCache[skillId]=d.skill;
  var merged=Object.assign({}, _skillsCatalogById[skillId]||{}, d.skill);
  _skillsCatalogById[skillId]=merged;
  if(_skillModalState && _skillModalState.id===skillId){
   _renderInstalledSkillModal(merged);
  }
 }).catch(function(){});
}

function _showCreateSkillModal(){
 _skillModalState={id:'__skill_creator__'};
 var content='';
 content+='<button class="skill-modal-close" onclick="_closeSkillModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>';
 content+='<div class="skill-modal-header"><div class="skill-modal-icon theme-builder">'+_skillIcons.creator+'</div><div class="skill-modal-head-main"><div class="skill-modal-title-row"><div class="skill-modal-title">'+escapeHtml(t('skills.creator.name'))+'</div></div><div class="skill-modal-subtitle">'+escapeHtml(t('skills.creator.summary'))+'</div></div></div>';
 content+='<div class="skill-modal-scroll"><div class="skill-modal-body">';
 content+='<div class="skill-modal-section"><div class="skill-modal-section-title">'+escapeHtml(t('skills.creator.user.title'))+'</div><div class="skill-modal-paragraph">'+escapeHtml(t('skills.creator.user.desc'))+'</div></div>';
 content+='<div class="skill-modal-section"><div class="skill-modal-section-title">'+escapeHtml(t('skills.modal.boundary.title'))+'</div><div class="skill-modal-paragraph">'+escapeHtml(t('skills.modal.createBoundary'))+'</div></div>';
 content+='</div></div>';
 content+='<div class="skill-modal-actions"><div class="skill-modal-actions-right"><button class="skill-modal-btn primary" onclick="_startCreateSkillFlow(\'user\')">'+escapeHtml(t('skills.action.userCreate'))+'</button></div></div>';
 _renderSkillModal(content);
}

function _startCreateSkillFlow(mode){
 _closeSkillModal(true);
 if(mode==='user'){
  if(typeof window._setForgeComposerMode==='function'){
   window._setForgeComposerMode('skill', {});
  }
  show(6);
  return;
 }
 show(1);
 setTimeout(function(){ quickSend(t('skills.creator.assistant.prompt')); },0);
}

function _trySkill(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill) return;
 _closeSkillModal(true);
 show(1);
 var prompt=String(skill.default_prompt||'').trim();
 if(!prompt) prompt=String(skill.description||'').trim();
 if(!prompt) prompt='请用'+String(skill.name||skill.id||'这个技能')+'来处理这个任务。';
 setTimeout(function(){ quickSend(prompt); },0);
}

