// Voice mode loop and CoD indicator state
// Source: chat.js lines 2341-2496

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
