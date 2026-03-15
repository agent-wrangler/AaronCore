// ============================================
// 轻感知状态层 — AwarenessManager
// ============================================
var AwarenessManager=(function(){
 var STORAGE_KEY='awareness_balls';
 var POLL_INTERVAL=5000;
 var POLL_MAX=6;
 var STAGGER_DELAY=300;
 var MAX_BALLS=50;
 var pollTimer=null;
 var pollCount=0;
 var lastPollTs=null;

 var TYPE_CLASS={'l7_feedback':'l7','l8_learn':'l8-learn','l8_relearn':'l8-relearn'};
 var TYPE_LABEL={'l7_feedback':'\u53cd\u9988\u8c03\u6574','l8_learn':'\u5b66\u4e60','l8_relearn':'\u91cd\u5b66'};

 function todayKey(){return new Date().toISOString().slice(0,10);}

 function loadBalls(){
  try{
   var raw=localStorage.getItem(STORAGE_KEY);
   if(!raw) return [];
   var data=JSON.parse(raw);
   if(data.date!==todayKey()){localStorage.removeItem(STORAGE_KEY);return [];}
   return data.balls||[];
  }catch(e){return [];}
 }

 function saveBalls(balls){
  localStorage.setItem(STORAGE_KEY,JSON.stringify({date:todayKey(),balls:balls}));
 }

 function addBallToStorage(ballData){
  var balls=loadBalls();
  if(balls.length>=MAX_BALLS) return false;
  for(var i=0;i<balls.length;i++){
   if(balls[i].ts===ballData.ts && balls[i].type===ballData.type) return false;
  }
  balls.push(ballData);
  saveBalls(balls);
  return true;
 }

 function getBar(){return document.getElementById('awarenessBar');}

 function updateBarClass(){
  var bar=getBar();
  if(!bar) return;
  if(bar.querySelectorAll('.awareness-ball').length>0){
   bar.classList.add('has-balls');
  }else{
   bar.classList.remove('has-balls');
  }
 }

 function createBallEl(ballData,animate){
  var el=document.createElement('div');
  var cls=TYPE_CLASS[ballData.type]||'l8-learn';
  el.className='awareness-ball '+cls;
  var label=TYPE_LABEL[ballData.type]||'\u8c03\u6574';
  var time='';
  if(ballData.ts){
   try{var d=new Date(ballData.ts);time=d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}catch(e){}
  }
  // 从 summary 中去掉和 label 重复的前缀
  var desc=(ballData.summary||'').replace(/^.*[:：]\s*/,'').slice(0,30);
  var tip=label+(desc?' · '+desc:'')+(time?' · '+time:'');
  el.setAttribute('data-tooltip',tip.trim());
  el.setAttribute('data-type',ballData.type);
  el.setAttribute('data-ts',ballData.ts||'');

  if(animate){
   el.classList.add('rolling-in');
   el.addEventListener('animationend',function(){
    el.classList.remove('rolling-in');
    el.classList.add('settled');
   },{once:true});
  }else{
   el.classList.add('settled');
   el.style.opacity='1';
  }
  return el;
 }

 function renderBall(ballData,animate){
  var bar=getBar();
  if(!bar) return;
  var el=createBallEl(ballData,animate);
  bar.prepend(el);
  updateBarClass();
 }

 function init(){
  var bar=getBar();
  if(!bar) return;
  var saved=loadBalls();
  for(var i=0;i<saved.length;i++) renderBall(saved[i],false);
  scheduleMidnightClear();
  console.log('[awareness] init, restored '+saved.length+' balls');
 }

 function handleEvent(evtData){
  var ballData={
   type:evtData.type,
   summary:evtData.summary||'',
   ts:evtData.ts||new Date().toISOString(),
   detail:evtData.detail||{}
  };
  var isNew=addBallToStorage(ballData);
  if(!isNew) return;
  renderBall(ballData,true);
 }

 function handleEvents(arr){
  if(!Array.isArray(arr)||arr.length===0) return;
  for(var i=0;i<arr.length;i++){
   (function(idx){
    setTimeout(function(){handleEvent(arr[idx]);},idx*STAGGER_DELAY);
   })(i);
  }
 }

 function startPolling(){
  stopPolling();
  pollCount=0;
  lastPollTs=new Date().toISOString();
  pollTimer=setInterval(function(){
   pollCount++;
   if(pollCount>POLL_MAX){stopPolling();return;}
   var url='/awareness/pending'+(lastPollTs?'?since='+encodeURIComponent(lastPollTs):'');
   fetch(url).then(function(r){return r.json();}).then(function(data){
    if(data.server_ts) lastPollTs=data.server_ts;
    if(data.events && data.events.length>0){
     handleEvents(data.events);
     pollCount=Math.max(0,pollCount-2);
    }
   }).catch(function(){});
  },POLL_INTERVAL);
 }

 function stopPolling(){
  if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
  pollCount=0;
 }

 function scheduleMidnightClear(){
  var now=new Date();
  var midnight=new Date(now);
  midnight.setHours(24,0,0,0);
  var ms=midnight-now;
  setTimeout(function(){
   clearAllBalls();
   scheduleMidnightClear();
  },ms);
 }

 function clearAllBalls(){
  var bar=getBar();
  if(!bar) return;
  var balls=bar.querySelectorAll('.awareness-ball');
  for(var i=0;i<balls.length;i++){
   (function(el,idx){
    setTimeout(function(){
     el.classList.remove('settled');
     el.classList.add('clearing');
     el.addEventListener('animationend',function(){
      el.remove();
      updateBarClass();
     },{once:true});
    },idx*80);
   })(balls[i],i);
  }
  localStorage.removeItem(STORAGE_KEY);
 }

 return {
  init:init,
  handleEvent:handleEvent,
  handleEvents:handleEvents,
  startPolling:startPolling,
  stopPolling:stopPolling,
  clearAllBalls:clearAllBalls
 };
})();
