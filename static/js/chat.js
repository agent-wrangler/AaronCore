// ── textarea 自动撑高 ──
var _pendingImages = []; // base64 图片暂存（支持多张）
var MAX_IMAGES = 4;
var _abortController = null; // 用于中断 SSE 请求

var _sendSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M22 2L11 13" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var _stopSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>';

(function(){
 var inp=document.getElementById('inp');
 if(!inp)return;
 function autoResize(){
  var maxH=Math.floor(window.innerHeight*0.4);
  // 先临时设 auto 让浏览器算出真实 scrollHeight，但用 overflow:hidden 防止闪烁
  var prevOverflow=inp.style.overflow;
  inp.style.overflow='hidden';
  inp.style.height='auto';
  var sh=inp.scrollHeight;
  inp.style.height=Math.min(sh,maxH)+'px';
  inp.style.overflow=prevOverflow||'';
 }
 inp.addEventListener('input',function(){ autoResize(); updateSendButton(); });

 // 动态 Placeholder 轮换
 var _placeholders=['与 Nova 对话...','向 Nova 提问...','粘贴代码进行分析...','聊聊你的想法...','描述你需要的帮助...'];
 var _phIdx=0;
 setInterval(function(){
  if(inp===document.activeElement||inp.value.trim()) return;
  _phIdx=(_phIdx+1)%_placeholders.length;
  inp.setAttribute('placeholder',_placeholders[_phIdx]);
 },8000);

 // 粘贴图片拦截
 inp.addEventListener('paste',function(e){
  var items=e.clipboardData&&e.clipboardData.items;
  if(!items)return;
  for(var i=0;i<items.length;i++){
   if(items[i].type.indexOf('image')!==-1){
    e.preventDefault();
    var file=items[i].getAsFile();
    if(file) readImageFile(file);
    return;
   }
  }
 });
})();

function readImageFile(file){
 if(!file||file.size>10*1024*1024)return;
 if(_pendingImages.length>=MAX_IMAGES) return;
 var reader=new FileReader();
 reader.onload=function(e){
  _pendingImages.push(e.target.result);
  renderImagePreviews();
  updateSendButton();
 };
 reader.readAsDataURL(file);
}

function handleImageFile(input){
 if(input.files){
  for(var i=0;i<input.files.length&&_pendingImages.length<MAX_IMAGES;i++){
   readImageFile(input.files[i]);
  }
 }
 input.value='';
}

function renderImagePreviews(){
 var bar=document.getElementById('imagePreviewBar');
 if(!bar)return;
 bar.innerHTML='';
 if(_pendingImages.length===0){ bar.style.display='none'; return; }
 bar.style.display='flex';
 _pendingImages.forEach(function(dataUrl,idx){
  var item=document.createElement('div');
  item.className='image-preview-item';
  var img=document.createElement('img');
  img.src=dataUrl; img.alt='preview';
  var btn=document.createElement('button');
  btn.className='image-preview-remove';
  btn.title=t('chat.remove.image');
  btn.innerHTML='&times;';
  btn.onclick=function(){ removeImageAt(idx); };
  item.appendChild(img);
  item.appendChild(btn);
  bar.appendChild(item);
 });
}

function removeImageAt(idx){
 _pendingImages.splice(idx,1);
 renderImagePreviews();
 updateSendButton();
}

function removeImagePreview(){
 _pendingImages=[];
 renderImagePreviews();
 updateSendButton();
}

function _enterStopMode(){
 var btn=document.getElementById('sendBtn');
 btn.disabled=false;
 btn.classList.add('stop-mode');
 btn.innerHTML=_stopSvg;
}

function _exitStopMode(){
 var btn=document.getElementById('sendBtn');
 btn.classList.remove('stop-mode');
 btn.innerHTML=_sendSvg;
 updateSendButton();
}

function _stopGeneration(){
 if(_abortController){
  _abortController.abort();
  _abortController=null;
 }
}

function addMessage(sender,text,type,imageUrl){
 var chat=document.getElementById('chat');
 var msgDiv=document.createElement('div');
 msgDiv.className='msg '+(type==='user'?'user':'assistant');
 
 // 创建头像（确保正确显示）
 var avatar=document.createElement('div');
 avatar.className='avatar';
 if(type==='user'){
  avatar.textContent=t('chat.you');
  avatar.title=t('chat.you');
  avatar.style.background='linear-gradient(135deg, #10b981 0%, #059669 100%)';
 }else{
  avatar.textContent='N';
  avatar.title='Nova AI';
  avatar.style.background='linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
 }
 
 // 创建消息内容区域
 var msgContent=document.createElement('div');
 msgContent.className='msg-content';
 
 // 创建气泡
 var bubble=document.createElement('div');
 bubble.className='bubble';
 if(imageUrl){
  var img=document.createElement('img');
  img.className='bubble-image';
  img.src=imageUrl;
  img.alt='图片';
  bubble.appendChild(img);
 }
 if(text){
  var textNode=document.createElement('div');
  textNode.className='bubble-body';
  // 用户消息不做 markdown 渲染，直接显示纯文本
  if(type==='user'){
   textNode.textContent=text;
  }else{
   textNode.innerHTML=formatBubbleText(text);
  }
  bubble.appendChild(textNode);
 }
 
 // 创建元信息（昵称+时间）
 var msgMeta=document.createElement('div');
 msgMeta.className='msg-meta';
 var nameSpan=document.createElement('span');
 nameSpan.className='msg-name';
 nameSpan.textContent=type==='user'?t('chat.you'):'Nova';
 var timeSpan=document.createElement('span');
 timeSpan.className='msg-time';
 timeSpan.textContent=T();
 var copyBtn=document.createElement('button');
 copyBtn.className='msg-copy';
 copyBtn.textContent=t('chat.copy');
 copyBtn.onclick=function(){navigator.clipboard.writeText(text).then(function(){copyBtn.textContent=t('chat.copied');setTimeout(function(){copyBtn.textContent=t('chat.copy');},1200);});};
 if(type==='user'){
  msgMeta.appendChild(copyBtn);
  msgMeta.appendChild(nameSpan);
  msgMeta.appendChild(timeSpan);
 } else {
  msgMeta.appendChild(nameSpan);
  msgMeta.appendChild(timeSpan);
  msgMeta.appendChild(copyBtn);
 }
 
  // 组装消息：meta（昵称+时间）在上，bubble 在下
  msgContent.appendChild(msgMeta);
  msgContent.appendChild(bubble);
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(msgContent);
  
  chat.appendChild(msgDiv);
 chat.scrollTop=chat.scrollHeight;
 
 // 保存到历史
 if(type==='user'||type==='assistant'){
  chatHistory+=msgDiv.outerHTML;
  trimChatHistory();
  localStorage.setItem('nova_chat_history',chatHistory);
 }
}

var _thinkingLabels=null; // removed: no more fake rotating labels

function buildPendingAssistantMessage(){
 var msgDiv=document.createElement('div');
 msgDiv.className='msg assistant thinking-msg';

 var avatar=document.createElement('div');
 avatar.className='avatar';
 avatar.textContent='N';
 avatar.title='Nova AI';
 avatar.style.background='linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

 var wrap=document.createElement('div');
 wrap.className='msg-content-wrap';

 var planStrip=document.createElement('div');
 planStrip.className='plan-strip';
 planStrip.style.display='none';

 var tracker=document.createElement('div');
 tracker.className='step-tracker';

 var status=document.createElement('div');
 status.className='step-tracker-status';
 status.innerHTML='<span class="thinking-status-text">'+t('chat.thinking')+'</span>';
 status.style.display='none';

 var contentArea=document.createElement('div');
 contentArea.className='msg-content';
 contentArea.style.display='none';

 wrap.appendChild(planStrip);
 wrap.appendChild(tracker);
 wrap.appendChild(status);
 wrap.appendChild(contentArea);
 msgDiv.appendChild(avatar);
 msgDiv.appendChild(wrap);

 return {
  root: msgDiv,
  wrap: wrap,
  planStrip: planStrip,
  tracker: tracker,
  status: status,
  contentArea: contentArea,
  plan: null,
  steps: [],
  labelTimer: null,
  persisted: false
 };
}

function finalizePendingAssistantMessage(pendingState, replyText){
 if(!pendingState || !pendingState.root) return;
 if(typeof window._clearAskUserSlot==='function') window._clearAskUserSlot();
 if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
 if(pendingState.steps && pendingState.steps.length){
  _collapseSteps();
 }
 if(pendingState.status) pendingState.status.style.display='none';
 pendingState.root.className='msg assistant';
 var contentArea=pendingState.contentArea;
 if(!contentArea){
  contentArea=document.createElement('div');
  contentArea.className='msg-content';
  pendingState.wrap.appendChild(contentArea);
 }
 contentArea.style.display='';
 contentArea.innerHTML='';
 var bubble=document.createElement('div');
 bubble.className='bubble';
 bubble.innerHTML=formatBubbleText(replyText);
 var meta=document.createElement('div');
 meta.className='msg-meta';
 var nameSpan=document.createElement('span');
 nameSpan.className='msg-name';
 nameSpan.textContent='Nova';
 var timeSpan=document.createElement('span');
 timeSpan.className='msg-time';
 timeSpan.textContent=T();
 meta.appendChild(nameSpan);
 meta.appendChild(timeSpan);
 contentArea.appendChild(meta);
 contentArea.appendChild(bubble);
 if(!pendingState.persisted){
  chatHistory+=pendingState.root.outerHTML;
  trimChatHistory();
  localStorage.setItem('nova_chat_history',chatHistory);
  pendingState.persisted=true;
 }
 if(_sessionTaskPlan){
  var _reply=String(replyText||'');
  if(_isTaskPlanTerminal(_sessionTaskPlan) || /执行失败|当前聊天失败|后端连接失败|已停止|没接稳/.test(_reply)){
   _scheduleTaskPlanClear(1800);
  }
 }
}

function showRepairBar(repair){
 if(!repair || !repair.show) return;
 var bar=document.getElementById('repairBar');
 var headline=document.getElementById('repairHeadline');
 var detail=document.getElementById('repairDetail');
 var progress=document.getElementById('repairProgress');
 if(!bar||!headline||!detail||!progress) return;

 if(bar._repairTimer){ clearInterval(bar._repairTimer); bar._repairTimer=null; }
 headline.textContent=repair.headline||t('repair.recorded');
 detail.textContent=repair.detail||'';
 progress.style.width=(repair.progress||20)+'%';
 bar.style.display='';

 if(repair.watch && repair.poll_ms && repair.max_polls){
  var polls=0;
  var maxPolls=repair.max_polls||10;
  var interval=repair.poll_ms||1600;
  bar._repairTimer=setInterval(function(){
   polls++;
   var pct=Math.min(22+Math.round((polls/maxPolls)*68), 90);
   progress.style.width=pct+'%';
   if(polls>=maxPolls){
    clearInterval(bar._repairTimer); bar._repairTimer=null;
    progress.style.width='100%';
    detail.textContent=t('repair.done');
    setTimeout(function(){ hideRepairBar(); }, 3000);
   }
  }, interval);
 }else{
  setTimeout(function(){ hideRepairBar(); }, 6000);
 }
}

function hideRepairBar(){
 var bar=document.getElementById('repairBar');
 if(!bar) return;
 if(bar._repairTimer){ clearInterval(bar._repairTimer); bar._repairTimer=null; }
 bar.style.display='none';
}

// cleanInlineText is in utils.js

function createProcessBubble(card){
 var bubble=document.createElement('div');
 bubble.className='thinking-bubble done';

 var body=document.createElement('div');
 body.className='thinking-bubble-body';

 var label=document.createElement('div');
 label.className='thinking-bubble-label';
 label.textContent=card.label||t('chat.process');

 var detail=document.createElement('div');
 detail.className='thinking-bubble-text';
 detail.textContent=card.detail||'';

 body.appendChild(label);
 body.appendChild(detail);
 bubble.appendChild(body);
 return bubble;
}

async function send(){
 AwarenessManager.stopPolling();
 if(typeof hideWelcome==='function') hideWelcome();
 if(typeof window._clearSessionTaskPlan==='function') window._clearSessionTaskPlan();
 if(typeof window._clearAskUserSlot==='function') window._clearAskUserSlot();
 var inp=document.getElementById('inp');
 var text=inp.value.trim();
 var images=_pendingImages.slice();
 var image=images.length>0?images[0]:null;
 if(text===''&&!image)return;

 addMessage(t('chat.you'),text,'user',image);
 inp.value='';
 inp.style.height='auto';
 _pendingImages=[];
 renderImagePreviews();
 updateSendButton();

 var btn=document.getElementById('sendBtn');
 btn.classList.add('sending');
 setTimeout(function(){btn.classList.remove('sending');},500);
 _enterStopMode();
 var pendingState=buildPendingAssistantMessage();
 var chat=document.getElementById('chat');
 chat.appendChild(pendingState.root);
 chat.scrollTop=chat.scrollHeight;

 var replyText='';
 var replyImage='';
 var _thinkingContent='';
 var _showRawThinkingPanel=false;
  var repairData=null;
  var hasTrace=false;
  var _streamBubble=null; // 流式输出的气泡
  var _streamText=''; // 流式累积的文本
  var _streamStarted=false;

 function _setStepStatus(stepObj, newStatus){
  if(!stepObj) return;
  stepObj.status=newStatus;
  stepObj.el.className='step-item '+newStatus;
  var icon=stepObj.el.querySelector('.step-icon');
  if(icon) icon.className='step-icon '+newStatus;
 }

function _applyStepDetail(stepObj, detail, fullDetail){
  if(!stepObj || !stepObj.detailEl) return;
  stepObj.summaryDetail=String(detail||'');
  stepObj.fullDetail=String(fullDetail||'').trim();
  stepObj.expandable=false;
  stepObj.expanded=true;
  stepObj.el.classList.remove('expandable');
  stepObj.el.classList.add('expanded');
  stepObj.detailEl.textContent=stepObj.fullDetail||stepObj.summaryDetail;
  stepObj.el.removeAttribute('role');
  stepObj.el.removeAttribute('tabindex');
  stepObj.el.removeAttribute('title');
 }

 function _planCssStatus(status){
  status=String(status||'pending');
  if(status==='done') return 'done';
  if(status==='running') return 'running';
  if(status==='waiting_user') return 'waiting-user';
  if(status==='blocked' || status==='error' || status==='failed') return 'error';
  return '';
 }

 function _renderPendingPlan(plan){
  pendingState.plan=null;
  var host=pendingState.planStrip;
  if(host){
   host.style.display='none';
   host.innerHTML='';
  }
  if(!plan || !plan.items || !plan.items.length){
   if(typeof window._clearSessionTaskPlan==='function'){
    window._clearSessionTaskPlan();
   }
   return;
  }
  pendingState.plan=plan;
  if(host){
   host.style.display='';
   var goal=document.createElement('div');
   goal.className='plan-goal';
   goal.textContent=String(plan.goal||'当前任务');
   host.appendChild(goal);
   var summaryText=String(plan.summary||'').trim();
   if(summaryText){
    var summary=document.createElement('div');
    summary.className='plan-summary';
    summary.textContent=summaryText;
    host.appendChild(summary);
   }
   var items=document.createElement('div');
   items.className='plan-items';
   (plan.items||[]).forEach(function(item){
    var chip=document.createElement('div');
    chip.className='plan-item';
    var cssStatus=_planCssStatus(item&&item.status);
    if(cssStatus) chip.classList.add(cssStatus);
    chip.textContent=String((item&&item.title)||'');
    items.appendChild(chip);
   });
   host.appendChild(items);
  }
  if(typeof window._setSessionTaskPlan==='function'){
   window._setSessionTaskPlan(plan);
  }
 }

 function addStep(card){
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  hasTrace=true;
  var label=card.label||'';
  var detail=card.detail||'';
  var status=card.status||'running';

  // 更新 spinner 状态文字，隐藏三个点动画
  var statusText=pendingState.status.querySelector('.thinking-status-text');
  if(statusText){
   statusText.textContent=detail||label;
   statusText.style.animation='none';
   statusText.offsetHeight;
   statusText.style.animation='statusFade 0.5s ease';
  }
  var dotsEl=pendingState.status.querySelector('.thinking');
  if(dotsEl) dotsEl.style.display='none';

  // 如果上一个 step 是 running 且 label 不同 → 自动标记为 done
  var steps=pendingState.steps;
  if(steps.length>0){
   var last=steps[steps.length-1];
   if(last.status==='running' && last.label!==label){
    _setStepStatus(last,'done');
   }
  }

  // 如果 label 和上一个相同 → 原地更新
  if(steps.length>0 && steps[steps.length-1].label===label){
   var existing=steps[steps.length-1];
   _applyStepDetail(existing, detail, card.full_detail||'');
   _setStepStatus(existing, status);
   chat.scrollTop=chat.scrollHeight;
   return;
  }

  // 创建新 step-item
 var el=document.createElement('div');
 el.className='step-item '+status;
  var icon=document.createElement('div');
  icon.className='step-icon '+status;
  var mainEl=document.createElement('div');
  mainEl.className='step-main';
  var labelEl=document.createElement('div');
  labelEl.className='step-label';
  labelEl.textContent=label;
  var detailEl=document.createElement('div');
  detailEl.className='step-detail';
  el.appendChild(icon);
  mainEl.appendChild(labelEl);
  mainEl.appendChild(detailEl);
  el.appendChild(mainEl);
  var stepObj={el:el, label:label, status:status, labelEl:labelEl, detailEl:detailEl, summaryDetail:'', fullDetail:'', expandable:false, expanded:true};
  _applyStepDetail(stepObj, detail, card.full_detail||'');
  pendingState.tracker.appendChild(el);
  steps.push(stepObj);
  chat.scrollTop=chat.scrollHeight;
 }

 function _collapseSteps(){
  var tracker=pendingState.tracker;
  var steps=pendingState.steps;
  if(!tracker || steps.length===0) return;
  // 确保所有 running 变 done
  for(var i=0;i<steps.length;i++){
   if(steps[i].status==='running') _setStepStatus(steps[i],'done');
  }
  tracker.style.display='flex';
  tracker.classList.remove('collapsed');
  var existingToggle=tracker.querySelector('.step-tracker-toggle');
  if(existingToggle) existingToggle.remove();
 }

 function _initStreamBubble(){
  // 把所有 running 步骤标记为 done
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i].status==='running') _setStepStatus(pendingState.steps[i],'done');
  }
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  _collapseSteps();
  // 隐藏 spinner，显示内容区
  pendingState.status.style.display='none';
  pendingState.root.className='msg assistant';
  var contentArea=pendingState.contentArea;
  contentArea.style.display='';
  contentArea.innerHTML='';
  var bubble=document.createElement('div');
  bubble.className='bubble';
  var cursor=document.createElement('span');
  cursor.className='typing-cursor';
  bubble.appendChild(cursor);
  var meta=document.createElement('div');
  meta.className='msg-meta';
  var nameSpan=document.createElement('span');
  nameSpan.className='msg-name';
  nameSpan.textContent='Nova';
  var timeSpan=document.createElement('span');
  timeSpan.className='msg-time';
  timeSpan.textContent=T();
  meta.appendChild(nameSpan);
  meta.appendChild(timeSpan);
  contentArea.appendChild(meta);
  contentArea.appendChild(bubble);
  _streamBubble=bubble;
  _streamStarted=true;
  _streamTokenCount=0;
  _lastRenderedBlockCount=0;
  // 思考步骤结束、回复开始 → 强制滚到底部，确保用户能看到新内容
  chat.scrollTop=chat.scrollHeight;
 }

 var _scrollRAF=0; // scroll 节流
 var _renderTimer=0; // 渐进渲染节流
 var _streamTokenCount=0; // 流式 token 计数，前 N 个无条件滚动
 var _lastRenderedBlockCount=0; // 上次渲染的块数，用于 fade-in 新块

 // 判断是否在底部附近（阈值 120px），避免强制跳视图打断用户回翻
 function _nearBottom(){
  return chat.scrollHeight - chat.scrollTop - chat.clientHeight < 120;
 }

 // ── 渐进式 Markdown 渲染引擎 ──
 // 不再逐字符塞裸文本，而是把累积的 _streamText 整体跑 formatBubbleText，
 // 新出现的块自动带 fade-in 动画，光标始终在末尾。
 function _progressiveRender(){
  _renderTimer=0;
  if(!_streamBubble || !_streamText) return;
  // 用 formatBubbleText 把当前累积文本渲染成结构化 HTML
  var html=formatBubbleText(_streamText);
  // 创建临时容器解析出块元素
  var temp=document.createElement('div');
  temp.innerHTML=html;
  var newBlocks=temp.children;
  var totalBlocks=newBlocks.length;
  // 清空气泡内容（保留光标）
  var cursor=_streamBubble.querySelector('.typing-cursor');
  _streamBubble.innerHTML='';
  // 逐块插入，新块带 fade-in
  for(var bi=0;bi<totalBlocks;bi++){
   var block=newBlocks[0]; // 始终取第一个（因为 appendChild 会从 temp 中移走）
   if(bi>=_lastRenderedBlockCount){
    block.classList.add('block-fade-in');
   }
   _streamBubble.appendChild(block);
  }
  // 光标放末尾
  if(!cursor){cursor=document.createElement('span');cursor.className='typing-cursor';}
  _streamBubble.appendChild(cursor);
  _lastRenderedBlockCount=totalBlocks;
  _streamTokenCount++;
  // 滚动控制
  if(_streamTokenCount<=5 || _nearBottom()){
   if(!_scrollRAF){
    _scrollRAF=requestAnimationFrame(function(){
     chat.scrollTop=chat.scrollHeight;
     _scrollRAF=0;
    });
   }
  }
 }

 function _appendStreamToken(token){
  if(!_streamStarted) _initStreamBubble();
  _streamText+=token;
  // 节流渐进渲染：每 80ms 最多渲染一次，避免高频 DOM 操作
  if(!_renderTimer){
   _renderTimer=setTimeout(_progressiveRender, 80);
  }
 }

 function _finalizeStream(fullText){
  if(!_streamBubble) return;
  // 清除未执行的渐进渲染定时器
  if(_renderTimer){clearTimeout(_renderTimer);_renderTimer=0;}
  // 最终渲染：用完整文本做一次格式化（确保和 reply 事件的文本一致）
  _streamBubble.innerHTML=formatBubbleText(fullText);
  // 移除所有 fade-in 动画类（已经渲染完毕）
  var fadingBlocks=_streamBubble.querySelectorAll('.block-fade-in');
  for(var fi=0;fi<fadingBlocks.length;fi++){fadingBlocks[fi].classList.remove('block-fade-in');}
  // 如果有附带图片，追加到气泡末尾
  if(replyImage){
   var img=document.createElement('img');
   img.className='bubble-image';
   img.src=replyImage;
   img.alt='截图';
   img.style.maxWidth='100%';
   img.style.maxHeight='400px';
   img.style.borderRadius='8px';
   img.style.marginTop='8px';
   img.style.cursor='pointer';
   img.onclick=function(){window.open(replyImage,'_blank');};
   _streamBubble.appendChild(img);
  }
  var meta=_streamBubble.parentNode.querySelector('.msg-meta');
  if(meta&&!meta.querySelector('.msg-copy')){
   var cpBtn=document.createElement('button');
   cpBtn.className='msg-copy';
   cpBtn.textContent=t('chat.copy');
   cpBtn.onclick=function(){navigator.clipboard.writeText(fullText).then(function(){cpBtn.textContent=t('chat.copied');setTimeout(function(){cpBtn.textContent=t('chat.copy');},1200);});};
   meta.appendChild(cpBtn);
  }
  // ── 思考折叠面板（流式路径）──
  if(_showRawThinkingPanel && _thinkingContent && _streamBubble.parentNode){
   var existPanel=_streamBubble.parentNode.querySelector('.thinking-panel');
   if(!existPanel){
    var thinkPanel=document.createElement('details');
    thinkPanel.className='thinking-panel';
    var thinkSummary=document.createElement('summary');
    thinkSummary.textContent='💭 模型思考过程';
    thinkSummary.style.cssText='cursor:pointer;font-size:12px;color:#888;padding:6px 0;user-select:none;';
    var thinkBody=document.createElement('div');
    thinkBody.style.cssText='font-size:12px;color:#999;padding:8px 12px;background:rgba(128,128,128,0.08);border-radius:8px;margin:4px 0 8px;white-space:pre-wrap;line-height:1.5;max-height:300px;overflow-y:auto;';
    thinkBody.textContent=_thinkingContent;
    thinkPanel.appendChild(thinkSummary);
    thinkPanel.appendChild(thinkBody);
    _streamBubble.parentNode.insertBefore(thinkPanel,_streamBubble);
   }
  }
  _collapseSteps();
  chat.scrollTop=chat.scrollHeight;
  if(!pendingState.persisted){
   chatHistory+=pendingState.root.outerHTML;
   trimChatHistory();
   localStorage.setItem('nova_chat_history',chatHistory);
   // 持久化 steps 摘要
   if(pendingState.steps&&pendingState.steps.length>0){
    var stepsMap=JSON.parse(localStorage.getItem('nova_steps_map')||'{}');
    var tsKey=String(Date.now());
    stepsMap[tsKey]=pendingState.steps.map(function(s){
     return {
      label:s.label||'',
      detail:(s.detailEl&&s.detailEl.textContent)||'',
      status:s.status||'done'
     };
    });
    // 只保留最近 200 条
    var keys=Object.keys(stepsMap);
    if(keys.length>200){keys.sort();keys.slice(0,keys.length-200).forEach(function(k){delete stepsMap[k];});}
    localStorage.setItem('nova_steps_map',JSON.stringify(stepsMap));
    pendingState.root.setAttribute('data-steps-key',tsKey);
   }
   pendingState.persisted=true;
  }
 }

 function showFinalReply(text){
  // 把所有 running 步骤标记为 done
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i].status==='running') _setStepStatus(pendingState.steps[i],'done');
  }
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  _collapseSteps();
  // 隐藏 spinner，显示内容区
  pendingState.status.style.display='none';
  pendingState.root.className='msg assistant';
  var contentArea=pendingState.contentArea;
  contentArea.style.display='';
  contentArea.innerHTML='';
  var bubble=document.createElement('div');
  bubble.className='bubble';
  var meta=document.createElement('div');
  meta.className='msg-meta';
  var nameSpan=document.createElement('span');
  nameSpan.className='msg-name';
  nameSpan.textContent='Nova';
  var timeSpan=document.createElement('span');
  timeSpan.className='msg-time';
  timeSpan.textContent=T();
  meta.appendChild(nameSpan);
  meta.appendChild(timeSpan);
  var cpBtn=document.createElement('button');
  cpBtn.className='msg-copy';
  cpBtn.textContent=t('chat.copy');
  cpBtn.onclick=function(){navigator.clipboard.writeText(text).then(function(){cpBtn.textContent=t('chat.copied');setTimeout(function(){cpBtn.textContent=t('chat.copy');},1200);});};
  meta.appendChild(cpBtn);
  contentArea.appendChild(meta);

  // ── 思考折叠面板 ──
  if(_showRawThinkingPanel && _thinkingContent){
   var thinkPanel=document.createElement('details');
   thinkPanel.className='thinking-panel';
   var thinkSummary=document.createElement('summary');
   thinkSummary.textContent='💭 模型思考过程';
   thinkSummary.style.cssText='cursor:pointer;font-size:12px;color:#888;padding:6px 0;user-select:none;';
   var thinkBody=document.createElement('div');
   thinkBody.style.cssText='font-size:12px;color:#999;padding:8px 12px;background:rgba(128,128,128,0.08);border-radius:8px;margin:4px 0 8px;white-space:pre-wrap;line-height:1.5;max-height:300px;overflow-y:auto;';
   thinkBody.textContent=_thinkingContent;
   thinkPanel.appendChild(thinkSummary);
   thinkPanel.appendChild(thinkBody);
   contentArea.appendChild(thinkPanel);
  }

  contentArea.appendChild(bubble);

  // ── 如果有附带图片（如截图），在气泡内渲染 ──
  if(replyImage){
   var img=document.createElement('img');
   img.className='bubble-image';
   img.src=replyImage;
   img.alt='截图';
   img.style.maxWidth='100%';
   img.style.maxHeight='400px';
   img.style.borderRadius='8px';
   img.style.marginTop='8px';
   img.style.cursor='pointer';
   img.onclick=function(){window.open(replyImage,'_blank');};
   bubble.appendChild(img);
  }

  // ── 渐进块动画：解析 markdown 后逐块 fade-in ──
  var formattedHtml=formatBubbleText(text);
  var temp=document.createElement('div');
  temp.innerHTML=formattedHtml;
  var allBlocks=[];
  while(temp.firstChild){allBlocks.push(temp.firstChild);temp.removeChild(temp.firstChild);}

  var blockIdx=0;
  var blockDelay=60; // 每块间隔 ms
  function revealNextBlock(){
   if(blockIdx>=allBlocks.length){
    // 所有块显示完毕 → 持久化
    _collapseSteps();
    chat.scrollTop=chat.scrollHeight;
    if(!pendingState.persisted){
     chatHistory+=pendingState.root.outerHTML;
     trimChatHistory();
     localStorage.setItem('nova_chat_history',chatHistory);
     pendingState.persisted=true;
    }
    return;
   }
   var block=allBlocks[blockIdx];
   block.classList.add('block-fade-in');
   bubble.appendChild(block);
   blockIdx++;
   if(chat.scrollHeight-chat.scrollTop-chat.clientHeight<120){
    chat.scrollTop=chat.scrollHeight;
   }
   setTimeout(revealNextBlock, blockDelay);
  }
  revealNextBlock();
 }

 try{
  _abortController=new AbortController();
  var imagesBase64=null;
  if(images&&images.length>0){
   imagesBase64=images.map(function(img){
    var commaIdx=img.indexOf(',');
    return commaIdx>=0?img.substring(commaIdx+1):img;
   });
  }
  var resp=await fetch('/chat',{
   method:'POST',
   headers:{'Content-Type':'application/json; charset=utf-8','Accept':'text/event-stream'},
   body:JSON.stringify({message:String(text||t('chat.describe.image')),image:imagesBase64?imagesBase64[0]:null,images:imagesBase64}),
   signal:_abortController.signal
  });

  var reader=resp.body.getReader();
  var decoder=new TextDecoder();
  var buffer='';

  while(true){
   var result=await reader.read();
   if(result.done) break;
   buffer+=decoder.decode(result.value, {stream:true});

   var lines=buffer.split('\n');
   buffer=lines.pop();

   var currentEvent='';
   var currentData='';
   for(var i=0;i<lines.length;i++){
    var line=lines[i].trim();
    if(line.startsWith('event:')){
     currentEvent=line.slice(6).trim();
    }else if(line.startsWith('data:')){
     currentData=line.slice(5).trim();
    }else if(line===''){
     if(currentEvent && currentData){
      try{
       var parsed=JSON.parse(currentData);
       if(currentEvent==='trace'){
        addStep(parsed);
        // ── CoD 状态点：轻量级，只更新 5px 指示灯颜色 ──
        try{
         var _det=String(parsed.detail||'');
         if(_det.indexOf('recall_memory')!==-1||_det.indexOf('query_knowledge')!==-1){
          _setCodDot('trace');
         }
        }catch(e){}
       }else if(currentEvent==='plan'){
        _renderPendingPlan(parsed);
       }else if(currentEvent==='reply'){
        replyText=parsed.reply||t('chat.error.retry');
        if(parsed.image) replyImage=parsed.image;
        // 本轮回复完成 → 复位状态点为金色
        try{ setTimeout(function(){_setCodDot('flash');},600); }catch(e){}
       }else if(currentEvent==='agent_step'){
        if(parsed.phase==='complete'){
         for(var si=0;si<pendingState.steps.length;si++){
          if(pendingState.steps[si].status==='running') _setStepStatus(pendingState.steps[si],'done');
         }
        }
       }else if(currentEvent==='thinking'){
        var _thinkingText=String(parsed.content||'').replace(/<\/?think>/ig,' ').trim();
        if(_thinkingText){
         addStep({label:'模型思考',detail:_thinkingText,status:(parsed.status||'done'),full_detail:_thinkingText});
         if(_showRawThinkingPanel) _thinkingContent=_thinkingText;
        }
       }else if(currentEvent==='ask_user'){
        // agent 暂停等用户选择 → 渲染选项卡片
        _renderAskUser(parsed, pendingState);
       }else if(currentEvent==='stream'){
        _appendStreamToken(parsed.token||'');
       }else if(currentEvent==='reply'){
        replyText=parsed.reply||t('chat.error.retry');
        if(parsed.image) replyImage=parsed.image;
       }else if(currentEvent==='repair'){
        repairData=parsed;
       }else if(currentEvent==='awareness'){
        AwarenessManager.handleEvent(parsed);
       }else if(currentEvent==='model_changed'){
        var newModel=parsed.model||'';
        var newName=parsed.model_name||newModel;
        if(newModel){
         window._novaCurrentModel=newModel;
         var el=document.getElementById('modelName');
         if(el) el.textContent=newName||newModel;
         if(typeof _settingsCurrentModel!=='undefined') _settingsCurrentModel=newModel;
         if(typeof loadSettingsModels==='function') loadSettingsModels();
         if(typeof updateImageBtnState==='function') updateImageBtnState();
        }
       }
      }catch(e){}
     }
     currentEvent='';
     currentData='';
    }
   }
  }

  if(_streamStarted){
   // 流式已经显示了内容，用 reply 事件的完整文本做最终格式化
   var finalText=replyText||_streamText||t('chat.error.retry');
   _finalizeStream(finalText);
  }else if(replyText){
   showFinalReply(replyText);
  }else{
   finalizePendingAssistantMessage(pendingState, t('chat.error.retry'));
  }
  if(repairData && repairData.show){ showRepairBar(repairData); }
  _completeTaskProgress();
  AwarenessManager.startPolling();
 }catch(e){
  if(e.name==='AbortError'){
   // 用户点了停止，显示已有的部分回复或提示
   if(_streamStarted&&_streamText){
    _finalizeStream(_streamText);
   }else if(replyText){
    showFinalReply(replyText);
   }else{
    finalizePendingAssistantMessage(pendingState, t('chat.stopped')||'已停止');
   }
  }else{
   finalizePendingAssistantMessage(pendingState, t('chat.error.noconnect'));
  }
 }
 _abortController=null;
 _exitStopMode();
 chat.scrollTop=chat.scrollHeight;
}

// ── 当前任务板（输入框上方） ──
var _sessionTaskPlan=null;
var _taskPlanClearTimer=null;

function _isTaskPlanTerminal(plan){
 if(!plan || !plan.items || !plan.items.length) return true;
 var phase=String(plan.phase||'').trim();
 if(phase==='done' || phase==='failed' || phase==='blocked' || phase==='cancelled') return true;
 var hasRunning=false;
 var hasPending=false;
 var hasWaitingUser=false;
 for(var i=0;i<plan.items.length;i++){
  var status=String((plan.items[i]&&plan.items[i].status)||'pending');
  if(status==='running') hasRunning=true;
  if(status==='pending') hasPending=true;
  if(status==='waiting_user') hasWaitingUser=true;
 }
 return !hasRunning && !hasPending && !hasWaitingUser;
}

function _taskPlanStateLabel(status){
 status=String(status||'pending');
 if(status==='running') return '进行中';
 if(status==='done') return '已完成';
 if(status==='waiting_user') return '待选择';
 if(status==='blocked' || status==='error' || status==='failed') return '卡住';
 return '待执行';
}

function _taskPlanStateIcon(status){
 status=String(status||'pending');
 if(status==='running') return '◉';
 if(status==='done') return '✓';
 if(status==='blocked' || status==='error' || status==='failed') return '!';
 return '○';
}

function _scheduleTaskPlanClear(delayMs){
 if(_taskPlanClearTimer){ clearTimeout(_taskPlanClearTimer); _taskPlanClearTimer=null; }
 _taskPlanClearTimer=setTimeout(function(){
  window._clearSessionTaskPlan();
 }, delayMs||2600);
}

function _renderSessionTaskPlan(){
 var board=document.getElementById('taskPlanBoard');
 if(!board) return;
 if(!_sessionTaskPlan || !_sessionTaskPlan.items || !_sessionTaskPlan.items.length){
  board.style.display='none';
  board.innerHTML='';
  return;
 }
 var plan=_sessionTaskPlan;
 var terminal=_isTaskPlanTerminal(plan);
 board.style.display='';
 board.innerHTML='';
 board.className='task-plan-board'+(terminal?' is-terminal':'');

 var head=document.createElement('div');
 head.className='task-plan-head';
 var goal=document.createElement('div');
 goal.className='task-plan-goal';
 goal.textContent=String(plan.goal||'当前任务');
 var phase=document.createElement('div');
 phase.className='task-plan-phase';
 phase.textContent=String(plan.summary||'正在推进任务');
 head.appendChild(goal);
 head.appendChild(phase);
 board.appendChild(head);

 var list=document.createElement('div');
 list.className='task-plan-list';
 (plan.items||[]).forEach(function(item,idx){
 var row=document.createElement('div');
  var status=String((item&&item.status)||'pending');
  row.className='task-plan-item '+status;

  var index=document.createElement('div');
  index.className='task-plan-index';
  index.textContent=_taskPlanStateIcon(status);
  index.title=_taskPlanStateLabel(status);

  var body=document.createElement('div');
  body.className='task-plan-body';

  var titleRow=document.createElement('div');
  titleRow.className='task-plan-title-row';

  var title=document.createElement('div');
  title.className='task-plan-title';
  title.textContent=String((item&&item.title)||'');

  var state=document.createElement('div');
  state.className='task-plan-state '+status;
  state.textContent=_taskPlanStateLabel(status);

  titleRow.appendChild(title);
  titleRow.appendChild(state);
  body.appendChild(titleRow);

  var detailText=String((item&&item.detail)||'').trim();
  if(detailText){
   var detail=document.createElement('div');
   detail.className='task-plan-detail';
   detail.textContent=detailText;
   body.appendChild(detail);
  }

  row.appendChild(index);
  row.appendChild(body);
  list.appendChild(row);
 });
 board.appendChild(list);
}

window._setSessionTaskPlan=function(plan){
 if(_taskPlanClearTimer){ clearTimeout(_taskPlanClearTimer); _taskPlanClearTimer=null; }
 _sessionTaskPlan=plan&&plan.items&&plan.items.length?plan:null;
 _renderSessionTaskPlan();
 if(_sessionTaskPlan && _isTaskPlanTerminal(_sessionTaskPlan)){
  _scheduleTaskPlanClear(2800);
 }
};

window._clearSessionTaskPlan=function(){
 if(_taskPlanClearTimer){ clearTimeout(_taskPlanClearTimer); _taskPlanClearTimer=null; }
 _sessionTaskPlan=null;
 _renderSessionTaskPlan();
};

function _getAskUserSlot(){
 var slot=document.getElementById('askUserSlot');
 if(slot) return slot;
 var inputArea=document.querySelector('.input');
 var planBoard=document.getElementById('taskPlanBoard');
 if(!inputArea || !planBoard) return null;
 slot=document.createElement('div');
 slot.id='askUserSlot';
 slot.className='ask-user-slot';
 slot.style.display='none';
 inputArea.insertBefore(slot, planBoard);
 return slot;
}

function _clearAskUserSlot(){
 var slot=document.getElementById('askUserSlot');
 if(!slot) return;
 slot.innerHTML='';
 slot.style.display='none';
}

function _dismissAskUserCard(slot, card){
 if(slot){
  _clearAskUserSlot();
  return;
 }
 if(card) card.style.display='none';
}

window._clearAskUserSlot=_clearAskUserSlot;

// ── 任务进度条（输入框上方） ──
function _addTaskProgress(label, value){
 var bar=document.getElementById('taskProgressBar');
 if(!bar)return;
 bar.style.display='';
 var item=document.createElement('div');
 item.className='task-progress-item';
 item.innerHTML='<span class="task-progress-icon">■</span><span class="task-progress-label">'+escapeHtml(label)+'</span><span class="task-progress-value">'+escapeHtml(value)+'</span>';
 item.dataset.status='working';
 bar.appendChild(item);
}

function _completeTaskProgress(){
 var bar=document.getElementById('taskProgressBar');
 if(!bar)return;
 var items=bar.querySelectorAll('.task-progress-item');
 for(var i=0;i<items.length;i++){
  if(items[i].dataset.status==='working'){
   items[i].dataset.status='done';
   var icon=items[i].querySelector('.task-progress-icon');
   if(icon){icon.textContent='✓';icon.classList.add('done');}
  }
 }
 // 5秒后淡出隐藏
 setTimeout(function(){
  bar.style.opacity='0';
  setTimeout(function(){bar.style.display='none';bar.style.opacity='';bar.innerHTML='';},500);
 },5000);
}

// ── ask_user 选项卡片渲染 ──
function _renderAskUser(data, pendingState){
 var qid=data.id||'';
 var question=data.question||'';
 var options=data.options||[];
 var slot=_getAskUserSlot();
 if(!question || !options.length){
  _clearAskUserSlot();
  return;
 }

 // 在输入框上方插入选项卡片
 var card=document.createElement('div');
 card.className='ask-user-card';
 card.innerHTML='<div class="ask-user-question">'+escapeHtml(question)+'</div>';
 var optionsDiv=document.createElement('div');
 optionsDiv.className='ask-user-options';
 // LLM 给的选项
 options.forEach(function(opt){
  var btn=document.createElement('button');
  btn.className='ask-user-option';
  btn.textContent=opt;
  btn.onclick=function(){
   var btns=optionsDiv.querySelectorAll('button');
   for(var i=0;i<btns.length;i++){btns[i].disabled=true;btns[i].classList.remove('selected');}
   btn.classList.add('selected');
   // 在输入框上方挂进度条
   _addTaskProgress(question, opt);
   // 收起选项卡片
   setTimeout(function(){ _dismissAskUserCard(slot, card); },400);
   fetch('/chat/answer',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({question_id:qid,answer:opt})
   });
  };
  optionsDiv.appendChild(btn);
 });
 // 系统兜底：都不满意
 var noneBtn=document.createElement('button');
 noneBtn.className='ask-user-option ask-user-none';
 noneBtn.textContent='都不满意';
 noneBtn.onclick=function(){
  var btns=optionsDiv.querySelectorAll('button');
  for(var i=0;i<btns.length;i++){btns[i].disabled=true;btns[i].classList.remove('selected');}
  noneBtn.classList.add('selected');
  _addTaskProgress(question, '都不满意，重新推荐');
  setTimeout(function(){ _dismissAskUserCard(slot, card); },400);
  fetch('/chat/answer',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({question_id:qid,answer:'都不满意，请换其他方案'})
  });
 };
 optionsDiv.appendChild(noneBtn);
 card.appendChild(optionsDiv);
 if(slot){
  slot.innerHTML='';
  slot.style.display='';
  slot.appendChild(card);
 }else{
  // fallback：插到聊天区底部
  var chat=document.getElementById('chat');
  chat.appendChild(card);
  chat.scrollTop=chat.scrollHeight;
 }
}

// ── 语音对话模式（点一次进入，自动循环，再点退出） ──
var _voiceMode = false;

(function(){
 var voiceBtn=document.getElementById('voiceBtn');
 if(!voiceBtn) return;

 var SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SpeechRecognition){
  voiceBtn.style.display='none';
  return;
 }

 var recognition=new SpeechRecognition();
 recognition.lang='zh-CN';
 recognition.continuous=true;
 recognition.interimResults=true;

 var isRecording=false;
 var inp=document.getElementById('inp');
 var _silenceTimer=null; // 静默检测：无新结果后自动发送
 var _lastResultTime=0;

 voiceBtn.addEventListener('click',function(e){
  e.preventDefault();
  if(_voiceMode){ exitVoiceMode(); }
  else{ enterVoiceMode(); }
 });

 function enterVoiceMode(){
  _voiceMode=true;
  voiceBtn.classList.add('recording');
  _syncVoiceMode(true);
  startListening();
 }

 function exitVoiceMode(){
  _voiceMode=false;
  voiceBtn.classList.remove('recording');
  _syncVoiceMode(false);
  if(_silenceTimer){ clearTimeout(_silenceTimer); _silenceTimer=null; }
  if(isRecording){ try{ recognition.stop(); }catch(err){} }
  isRecording=false;
  if(inp) inp.placeholder=t('input.placeholder');
 }

 function _syncVoiceMode(enabled){
  fetch('/companion/voice_mode',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({enabled:enabled})
  }).catch(function(){});
 }

 function startListening(){
  if(!_voiceMode) return;
  if(_silenceTimer){ clearTimeout(_silenceTimer); _silenceTimer=null; }
  isRecording=true;
  _lastResultTime=0;
  if(inp){ inp.value=''; inp.placeholder=t('input.listening'); }
  try{ recognition.start(); }catch(err){}
 }

 recognition.onresult=function(e){
  var transcript='';
  var isFinal=false;
  for(var i=0;i<e.results.length;i++){
   transcript+=e.results[i][0].transcript;
   if(e.results[i].isFinal) isFinal=true;
  }
  if(inp) inp.value=transcript;
  _lastResultTime=Date.now();
  // 有最终结果后启动静默计时，1.8秒无新内容自动发送
  if(isFinal && transcript.trim()){
   if(_silenceTimer) clearTimeout(_silenceTimer);
   _silenceTimer=setTimeout(function(){
    if(!_voiceMode) return;
    try{ recognition.stop(); }catch(err){}
   },1800);
  }
 };

 recognition.onend=function(){
  isRecording=false;
  if(_silenceTimer){ clearTimeout(_silenceTimer); _silenceTimer=null; }
  if(!_voiceMode){ if(inp) inp.placeholder='\u4e0e Nova \u5bf9\u8bdd...'; return; }
  var text=(inp&&inp.value||'').trim();
  if(!text){ setTimeout(startListening,500); return; }
  if(inp) inp.placeholder=t('input.waiting');
  var replyIdBefore=_lastReplyIdForVoice||'';
  send();
  waitForReplyThenListen(replyIdBefore);
 };

 recognition.onerror=function(e){
  isRecording=false;
  if(!_voiceMode) return;
  // no-speech / aborted 是正常情况，不要太快重启
  var delay=e.error==='no-speech'?500:e.error==='aborted'?300:1000;
  setTimeout(startListening, delay);
 };

 // 等 Nova 回复完 + TTS 播完再开始听
 function waitForReplyThenListen(replyIdBefore){
  if(!_voiceMode) return;
  var polls=0;
  var gotReply=false;
  var seenTtsStart=false;
  var replyTime=0;
  var timer=setInterval(function(){
   polls++;
   if(!_voiceMode||polls>=100){ clearInterval(timer); if(_voiceMode) startListening(); return; }
   fetch('/companion/state').then(function(r){return r.json();}).then(function(s){
    if(!gotReply){
     // 阶段1：等新回复出现
     if(s.last_reply_id && s.last_reply_id!==replyIdBefore){
      gotReply=true;
      replyTime=Date.now();
      _lastReplyIdForVoice=s.last_reply_id;
      // 用文本长度估算最大等待时间（兜底）
      var text=s.last_reply_full||s.last_reply_summary||'';
      var maxWait=Math.max((text.length/3)*1000+5000, 8000);
      setTimeout(function(){
       clearInterval(timer);
       if(_voiceMode) startListening();
      }, maxWait);
     }
    }else{
     // 阶段2：等 TTS 播完
     if(s.tts_playing){
      seenTtsStart=true;
     }
     if(seenTtsStart && !s.tts_playing){
      // 确认播完了
      clearInterval(timer);
      if(_voiceMode) setTimeout(startListening,300);
     }
     // 如果等了 6 秒还没看到 tts_playing=true，伴侣窗口可能没开
     if(!seenTtsStart && Date.now()-replyTime>6000){
      clearInterval(timer);
      if(_voiceMode) startListening();
     }
    }
   }).catch(function(){});
  },600);
 }
 var _lastReplyIdForVoice='';
})();


// ── CoD 状态点：5px 指示灯，金=闪念 蓝=溯源 ──────────────────────
function _setCodDot(mode){
  var dot=document.getElementById('codStatusDot');
  if(!dot) return;
  dot.className='cod-dot '+(mode==='trace'?'cod-trace':'cod-flash');
}
