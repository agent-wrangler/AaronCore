var docsPanelState={
 index:null,
 currentPath:'',
 currentDoc:null,
 error:'',
 loading:false
};

// escapeHtml is in utils.js

function formatDocInline(text, isLight){
 var html=escapeHtml(text||'');
 html=html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<span style="font-weight:600;color:'+(isLight?'#374151':'#c7d2fe')+';">$1</span>');
 html=html.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
 html=html.replace(/`([^`]+)`/g,'<code style="padding:2px 6px;border-radius:6px;background:'+(isLight?'rgba(100,100,110,0.08)':'rgba(120,120,130,0.14)')+';color:'+(isLight?'#374151':'#c7d2fe')+';font-family:Consolas,monospace;font-size:12px;">$1</code>');
 return html;
}

function renderDocMarkdown(text, isLight){
 var lines=String(text||'').replace(/\r/g,'').split('\n');
 var html=[];
 var paragraph=[];
 var listType='';
 var inCode=false;
 var codeLines=[];
 var codeBg=isLight?'#f8fafc':'#1c1c1e';
 var codeBorder=isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.08)';
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';

 function flushParagraph(){
  if(!paragraph.length) return;
  html.push('<p style="margin:0 0 14px 0;color:'+textColor+';font-size:14px;line-height:1.95;">'+paragraph.join('<br>')+'</p>');
  paragraph=[];
 }

 function closeList(){
  if(!listType) return;
  html.push(listType==='ol' ? '</ol>' : '</ul>');
  listType='';
 }

 function flushCode(){
  if(!inCode) return;
  html.push('<pre style="margin:0 0 16px 0;padding:14px 16px;border-radius:14px;background:'+codeBg+';border:1px solid '+codeBorder+';overflow:auto;"><code style="font-family:Consolas,monospace;font-size:12px;line-height:1.8;color:'+textColor+';">'+escapeHtml(codeLines.join('\n'))+'</code></pre>');
  codeLines=[];
  inCode=false;
 }

 lines.forEach(function(line){
  if(line.trim().startsWith('```')){
   flushParagraph();
   closeList();
   if(inCode){
    flushCode();
   }else{
    inCode=true;
    codeLines=[];
   }
   return;
  }

  if(inCode){
   codeLines.push(line);
   return;
  }

  var trimmed=line.trim();
  if(!trimmed){
   flushParagraph();
   closeList();
   return;
  }

  var heading=trimmed.match(/^(#{1,3})\s+(.*)$/);
  if(heading){
   flushParagraph();
   closeList();
   var level=heading[1].length;
   var size=level===1?24:(level===2?18:15);
   html.push('<div style="margin:'+(level===1?'0 0 14px 0':'20px 0 10px 0')+';font-size:'+size+'px;font-weight:800;color:'+textColor+';">'+formatDocInline(heading[2], isLight)+'</div>');
   return;
  }

  var bullet=trimmed.match(/^-\s+(.*)$/);
  if(bullet){
   flushParagraph();
   if(listType!=='ul'){
    closeList();
    html.push('<ul style="margin:0 0 14px 18px;padding:0;color:'+textColor+';">');
    listType='ul';
   }
   html.push('<li style="margin:0 0 8px 0;line-height:1.85;color:'+textColor+';">'+formatDocInline(bullet[1], isLight)+'</li>');
   return;
  }

  var ordered=trimmed.match(/^\d+\.\s+(.*)$/);
  if(ordered){
   flushParagraph();
   if(listType!=='ol'){
    closeList();
    html.push('<ol style="margin:0 0 14px 20px;padding:0;color:'+textColor+';">');
    listType='ol';
   }
   html.push('<li style="margin:0 0 8px 0;line-height:1.85;color:'+textColor+';">'+formatDocInline(ordered[1], isLight)+'</li>');
   return;
  }

  closeList();
  paragraph.push(formatDocInline(trimmed, isLight));
 });

 flushParagraph();
 closeList();
 flushCode();

 if(!html.length){
  return '<div style="color:'+subColor+';">这份文档暂时还是空的。</div>';
 }
 return html.join('');
}

function renderDocsPage(isLight){
 var box=document.getElementById('docsBox');
 if(!box) return;

 // 保存左侧列表和右侧内容区滚动位置
 var leftPanel=box.querySelector('[data-role="doc-left"]');
 var leftScroll=leftPanel?leftPanel.scrollTop:0;
 var rightPanel=box.querySelector('[data-role="doc-right"]');
 var rightScroll=rightPanel?rightPanel.scrollTop:0;

 var cardBg=isLight?'#ffffff':'rgba(36,36,40,0.95)';
 var softBg=isLight?'#f8fafc':'rgba(28,28,30,0.5)';
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var borderColor=isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)';
 var sections=(docsPanelState.index&&docsPanelState.index.sections)||[];
 var doc=docsPanelState.currentDoc||{};
 var html='';

 html+='<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px;flex-wrap:wrap;">';
 html+='<div><div style="font-size:26px;font-weight:800;color:'+textColor+';margin-bottom:6px;">文档中枢</div><div style="font-size:13px;line-height:1.8;color:'+subColor+';max-width:760px;">把当前主链、架构说明、前端现状和路线图都收进这里，省得每次再去文件夹里翻。</div></div>';
 html+='<div style="padding-top:6px;font-size:12px;color:'+subColor+';">当前 L3：2 条事实、8 条规则、2 条学习、1 条里程碑、1 条一般记录</div>';
 html+='</div>';

 html+='<div style="display:grid;grid-template-columns:minmax(240px,280px) minmax(0,1fr);gap:16px;align-items:start;">';
 html+='<div data-role="doc-left" style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:18px;padding:16px;position:sticky;top:0;max-height:calc(100vh - 180px);overflow:auto;">';
 html+='<div style="font-size:15px;font-weight:800;color:'+textColor+';margin-bottom:6px;">当前文档</div><div style="font-size:12px;line-height:1.7;color:'+subColor+';margin-bottom:14px;">先看总览和架构就能快速回到当前口径。</div>';
 if(!sections.length){
  html+='<div style="color:'+subColor+';">文档目录加载中...</div>';
 }else{
  sections.forEach(function(section){
   html+='<div style="margin-bottom:14px;">';
   html+='<div style="font-size:11px;font-weight:800;letter-spacing:0.08em;color:'+(isLight?'#374151':'#c7d2fe')+';margin-bottom:8px;">'+escapeHtml(section.section||'文档')+'</div>';
   (section.docs||[]).forEach(function(item){
    var active=item.path===docsPanelState.currentPath;
    html+='<button onclick="openDoc(\''+String(item.path||'').replace(/'/g,"\\'")+'\')" style="width:100%;text-align:left;padding:12px 12px 11px;border-radius:14px;border:1px solid '+(active?(isLight?'rgba(100,100,110,0.26)':'rgba(150,150,160,0.24)'):borderColor)+';background:'+(active?(isLight?'rgba(100,100,110,0.1)':'rgba(120,120,130,0.14)'):softBg)+';margin-bottom:8px;cursor:pointer;">';
    html+='<div style="font-size:13px;font-weight:700;color:'+textColor+';margin-bottom:4px;">'+escapeHtml(item.title||item.path||'未命名文档')+'</div>';
    html+='<div style="font-size:11px;line-height:1.7;color:'+subColor+';">'+escapeHtml(item.summary||item.path||'')+'</div>';
    html+='</button>';
   });
   html+='</div>';
  });
 }
 html+='</div>';

 html+='<div data-role="doc-right" style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:18px;padding:18px;min-width:0;min-height:520px;overflow:auto;max-height:calc(100vh - 140px);">';
 if(docsPanelState.error){
  html+='<div style="color:#ef4444;font-size:13px;">'+escapeHtml(docsPanelState.error)+'</div>';
 }else if(docsPanelState.loading && !doc.content){
  html+='<div style="color:'+subColor+';">文档加载中...</div>';
 }else if(!doc.content){
  html+='<div style="color:'+subColor+';">选一份文档看看吧。</div>';
 }else{
  html+='<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:18px;">';
  html+='<div><div style="font-size:24px;font-weight:800;color:'+textColor+';margin-bottom:4px;">'+escapeHtml(doc.title||'文档')+'</div><div style="font-size:12px;color:'+subColor+';">'+escapeHtml(doc.path||'')+'</div></div>';
  html+='<button onclick="openDoc(\''+String(docsPanelState.currentPath||'').replace(/'/g,"\\'")+'\')" style="padding:9px 12px;border:none;border-radius:12px;background:'+(isLight?'rgba(100,100,110,0.1)':'rgba(120,120,130,0.16)')+';color:'+(isLight?'#374151':'#c7d2fe')+';font-size:12px;font-weight:700;cursor:pointer;">刷新文档</button>';
  html+='</div>';
  html+='<div style="font-size:14px;line-height:1.9;color:'+textColor+';">'+renderDocMarkdown(doc.content, isLight)+'</div>';
 }
 html+='</div></div>';

 box.innerHTML=html;
 // 恢复左侧列表和右侧内容区滚动位置
 requestAnimationFrame(function(){
  var newLeftPanel=box.querySelector('[data-role="doc-left"]');
  if(newLeftPanel && leftScroll) newLeftPanel.scrollTop=leftScroll;
  var newRightPanel=box.querySelector('[data-role="doc-right"]');
  if(newRightPanel && rightScroll) newRightPanel.scrollTop=rightScroll;
 });
}

function openDoc(path){
 var isLight=document.body.classList.contains('light');
 if(!path) return;
 docsPanelState.currentPath=path;
 docsPanelState.error='';
 docsPanelState.loading=true;
 renderDocsPage(isLight);
 fetch('/docs/content?path='+encodeURIComponent(path)).then(function(r){ return r.json(); }).then(function(data){
  if(!data || !data.ok){
   docsPanelState.error='文档内容加载失败';
   docsPanelState.loading=false;
   renderDocsPage(isLight);
   return;
  }
  docsPanelState.currentDoc=data;
  docsPanelState.currentPath=data.path||path;
  docsPanelState.loading=false;
  renderDocsPage(isLight);
 }).catch(function(){
  docsPanelState.error='文档内容加载失败';
  docsPanelState.loading=false;
  renderDocsPage(isLight);
 });
}

function loadDocsPage(isLight, preferredPath){
 var chat=document.getElementById('chat');
 setInputVisible(false);
 chat.innerHTML='<div style="padding:20px;"><div id="docsBox">文档加载中...</div></div>';
 docsPanelState.error='';
 docsPanelState.loading=true;
 fetch('/docs/index').then(function(r){ return r.json(); }).then(function(data){
  docsPanelState.index=data||{};
  docsPanelState.loading=false;
  renderDocsPage(isLight);
  var target=preferredPath||docsPanelState.currentPath||(data&&data.default_path)||'';
  if(target){
   openDoc(target);
  }
 }).catch(function(){
  docsPanelState.error='文档目录加载失败';
  docsPanelState.loading=false;
  renderDocsPage(isLight);
 });
}
