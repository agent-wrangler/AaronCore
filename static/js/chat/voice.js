var _voiceMode = false;

(function(){
 var voiceBtn=document.getElementById('voiceBtn');
 var inp=document.getElementById('inp');
 if(!voiceBtn) return;

 var SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
 var recognition=SpeechRecognition ? new SpeechRecognition() : null;
 var browserSpeechAvailable=!!recognition;
 var hasSpeechSynthesis=!!(window.speechSynthesis&&window.SpeechSynthesisUtterance);
 var nativeVoice={
  probed:false,
  available:false,
  sttAvailable:false,
  ttsAvailable:false,
  sttLangs:[],
  ttsLangs:[],
  request:null,
  probeTimer:0,
  probeAttempts:0
 };

 var isRecording=false;
 var isAwaitingReply=false;
 var isSpeaking=false;
 var silenceTimer=0;
 var listeningTimer=0;
 var pollTimer=0;
 var pollCount=0;
 var activeUtterance=null;
 var activeListenSource='';
 var activeSpeakSource='';
 var lastReplyIdForVoice='';
 var skipNextRecognitionEnd=false;
 var skipNextNativeSpeakStop=false;
 var suppressReplyPlayback=false;
 var bargeInTimer=0;
 var bargeInActive=false;

 if(recognition){
  recognition.lang=_voiceChatLang();
  recognition.continuous=true;
  recognition.interimResults=true;
 }

 function _defaultPlaceholder(){
  return typeof t==='function' ? t('input.placeholder') : 'Chat with AaronCore...';
 }

 function _listeningPlaceholder(){
  return typeof t==='function' ? t('input.listening') : 'Listening...';
 }

 function _waitingPlaceholder(){
  return typeof t==='function' ? t('input.waiting') : 'Waiting for reply...';
 }

 function _setPlaceholder(value){
  if(inp) inp.placeholder=String(value||'');
 }

 function _voiceChatLang(text){
  var lang='';
  try{
   if(typeof getLang==='function'){
    lang=String(getLang()||'').toLowerCase();
   }
  }catch(err){}
  if(!lang&&typeof _lang!=='undefined'){
   lang=String(_lang||'').toLowerCase();
  }
  if(!lang&&/[\u4e00-\u9fff]/.test(String(text||''))) return 'zh-CN';
  return lang==='en' ? 'en-US' : 'zh-CN';
 }

 function _normalizeLangValue(lang){
  return String(lang||'').trim();
 }

 function _normalizeLangList(values){
  var list=Array.isArray(values) ? values : (values ? [values] : []);
  var seen={};
  var normalized=[];
  for(var i=0;i<list.length;i++){
   var lang=_normalizeLangValue(list[i]);
   var key=lang.toLowerCase();
   if(!lang||seen[key]) continue;
   seen[key]=true;
   normalized.push(lang);
  }
  return normalized;
 }

 function _selectNativeLang(requestedLang, availableLangs){
  var langs=_normalizeLangList(availableLangs);
  var requested=_normalizeLangValue(requestedLang);
  if(!langs.length) return '';
  if(!requested) return langs[0];
  var lowered=requested.toLowerCase();
  for(var i=0;i<langs.length;i++){
   if(langs[i].toLowerCase()===lowered) return langs[i];
  }
  var prefix=lowered.split('-',1)[0];
  if(prefix){
   for(var j=0;j<langs.length;j++){
    var candidate=langs[j].toLowerCase();
    if(candidate===prefix||candidate.indexOf(prefix+'-')===0) return langs[j];
   }
  }
  return '';
 }

 function _getNativeVoiceApi(){
  if(window.pywebview&&window.pywebview.api) return window.pywebview.api;
  return null;
 }

 function _applyNativeVoiceStatus(status){
  var detail=status||{};
  nativeVoice.probed=true;
  nativeVoice.sttAvailable=!!detail.stt_available;
  nativeVoice.ttsAvailable=!!detail.tts_available;
  nativeVoice.sttLangs=_normalizeLangList(detail.stt_langs);
  nativeVoice.ttsLangs=_normalizeLangList(detail.tts_langs);
  nativeVoice.available=!!(nativeVoice.sttAvailable||nativeVoice.ttsAvailable);
  _syncVoiceAvailability();
  return nativeVoice;
 }

 function _syncVoiceAvailability(){
  if(nativeVoice.available||browserSpeechAvailable){
   voiceBtn.style.display='';
   return;
  }
  if(nativeVoice.probeAttempts>=12){
   voiceBtn.style.display='none';
  }
 }

 function _probeNativeVoiceBridge(force){
  var api=_getNativeVoiceApi();
  if(!api||typeof api.voice_bridge_status!=='function'){
   return Promise.resolve(nativeVoice);
  }
  if(nativeVoice.request&&!force) return nativeVoice.request;
  nativeVoice.request=Promise.resolve(api.voice_bridge_status()).then(function(status){
   return _applyNativeVoiceStatus(status||{});
  }).catch(function(){
   nativeVoice.probed=true;
   nativeVoice.available=false;
   _syncVoiceAvailability();
   return nativeVoice;
  }).finally(function(){
   nativeVoice.request=null;
  });
  return nativeVoice.request;
 }

 function _startNativeProbeLoop(){
  if(nativeVoice.probeTimer) return;
  function _tick(){
   nativeVoice.probeAttempts++;
   _probeNativeVoiceBridge(true).finally(function(){
    _syncVoiceAvailability();
    if(nativeVoice.available||nativeVoice.probeAttempts>=12){
     clearInterval(nativeVoice.probeTimer);
     nativeVoice.probeTimer=0;
    }
   });
  }
  _tick();
  nativeVoice.probeTimer=setInterval(_tick,500);
 }

 function _resolveNativeListenLang(lang){
  if(!nativeVoice.sttAvailable) return '';
  return _selectNativeLang(lang, nativeVoice.sttLangs);
 }

 function _resolveNativeSpeakLang(lang){
  if(!nativeVoice.ttsAvailable) return '';
  return _selectNativeLang(lang, nativeVoice.ttsLangs);
 }

 function _clearSilenceTimer(){
  if(silenceTimer){
   clearTimeout(silenceTimer);
   silenceTimer=0;
  }
 }

 function _clearListeningTimer(){
  if(listeningTimer){
   clearTimeout(listeningTimer);
   listeningTimer=0;
  }
 }

 function _clearBargeInTimer(){
  if(bargeInTimer){
   clearTimeout(bargeInTimer);
   bargeInTimer=0;
  }
 }

 function _stopReplyPolling(){
  if(pollTimer){
   clearInterval(pollTimer);
   pollTimer=0;
  }
  pollCount=0;
 }

 function _scheduleListening(delay){
  _clearListeningTimer();
  listeningTimer=setTimeout(function(){
   listeningTimer=0;
   startListening();
  },Math.max(0,Number(delay)||0));
 }

 function _supportsNativeBargeIn(){
  var api=_getNativeVoiceApi();
  return !!(
   api
   && typeof api.voice_listen_start==='function'
   && typeof api.voice_listen_stop==='function'
   && nativeVoice.sttAvailable
   && activeSpeakSource==='native'
  );
 }

 function _disarmBargeInListening(stopNative){
  _clearBargeInTimer();
  var wasBarge=(activeListenSource==='native-barge')||bargeInActive;
  bargeInActive=false;
  if(stopNative&&activeListenSource==='native-barge'){
   var api=_getNativeVoiceApi();
   if(api&&typeof api.voice_listen_stop==='function'){
    try{ api.voice_listen_stop(); }catch(err){}
   }
  }
  if(activeListenSource==='native-barge'){
   activeListenSource='';
   isRecording=false;
  }
  return wasBarge;
 }

 function _armBargeInListening(delay){
  var api=_getNativeVoiceApi();
  var lang=_resolveNativeListenLang(_voiceChatLang());
  if(!_voiceMode||!isSpeaking||!_supportsNativeBargeIn()||!lang) return false;
  if(activeListenSource==='native-barge'||bargeInActive) return true;
  _clearBargeInTimer();
  bargeInTimer=setTimeout(function(){
   bargeInTimer=0;
   if(!_voiceMode||!isSpeaking||!_supportsNativeBargeIn()||activeListenSource==='native-barge'||bargeInActive) return;
   bargeInActive=true;
   activeListenSource='native-barge';
   Promise.resolve(api.voice_listen_start(lang)).then(function(result){
    if(!_voiceMode) return;
    if(result&&result.ok){
     isRecording=true;
     _syncButtonState();
     return;
    }
    bargeInActive=false;
    if(activeListenSource==='native-barge'){
      activeListenSource='';
      isRecording=false;
    }
    if(_voiceMode&&isSpeaking&&activeSpeakSource==='native'){
     _armBargeInListening(700);
    }
   }).catch(function(){
    bargeInActive=false;
    if(activeListenSource==='native-barge'){
     activeListenSource='';
     isRecording=false;
    }
    if(_voiceMode&&isSpeaking&&activeSpeakSource==='native'){
     _armBargeInListening(900);
    }
   });
  },Math.max(0,Number(delay)||0));
  return true;
 }

 function _syncVoiceMode(enabled){
  fetch('/companion/voice_mode',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({enabled:!!enabled})
  }).catch(function(){});
 }

 function _syncTtsStatus(playing){
  fetch('/companion/tts_status',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({playing:!!playing})
  }).catch(function(){});
 }

 function _normalizeSpeechText(text){
  var clean=String(text||'').replace(/\r/g,'');
  if(typeof stripMarkdownForStreamingText==='function'){
   clean=stripMarkdownForStreamingText(clean);
  }
  clean=clean
   .replace(/```[\s\S]*?```/g,' ')
   .replace(/`([^`]+)`/g,'$1')
   .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'$1')
   .replace(/[*_~>#]+/g,' ')
   .replace(/\s+/g,' ')
   .trim();
  return clean;
 }

 function _pickSpeechVoice(lang){
  if(!hasSpeechSynthesis) return null;
  var voices=window.speechSynthesis.getVoices();
  if(!voices||!voices.length) return null;
  var exact=null;
  var broad=null;
  for(var i=0;i<voices.length;i++){
   var voice=voices[i];
   var voiceLang=String((voice&&voice.lang)||'').toLowerCase();
   if(!exact&&voiceLang===String(lang||'').toLowerCase()) exact=voice;
   if(!broad&&voiceLang.indexOf(String(lang||'').slice(0,2).toLowerCase())===0) broad=voice;
  }
  return exact||broad||voices[0]||null;
 }

 function _stopActiveListening(){
  if(activeListenSource==='browser'&&recognition){
   skipNextRecognitionEnd=true;
   try{ recognition.stop(); }catch(err){}
  }else if(activeListenSource==='native'||activeListenSource==='native-barge'){
   var api=_getNativeVoiceApi();
   if(api&&typeof api.voice_listen_stop==='function'){
    try{ api.voice_listen_stop(); }catch(err){}
   }
  }
  _clearBargeInTimer();
  bargeInActive=false;
  activeListenSource='';
  isRecording=false;
 }

 function _cancelSpeech(){
  _disarmBargeInListening(true);
  if(activeUtterance){
   activeUtterance.onstart=null;
   activeUtterance.onend=null;
   activeUtterance.onerror=null;
   activeUtterance=null;
  }
  if(activeSpeakSource==='native'){
   skipNextNativeSpeakStop=true;
   var api=_getNativeVoiceApi();
   if(api&&typeof api.voice_speak_stop==='function'){
    try{ api.voice_speak_stop(); }catch(err){}
   }
  }
  if(hasSpeechSynthesis){
   try{ window.speechSynthesis.cancel(); }catch(err){}
  }
  activeSpeakSource='';
  isSpeaking=false;
  _syncTtsStatus(false);
 }

 function _finishAwaitingReply(){
  isAwaitingReply=false;
  _stopReplyPolling();
 }

 function _syncButtonState(){
  voiceBtn.classList.toggle('recording',!!_voiceMode);
 }

 function _interruptVoiceCycleAndRelisten(){
  if(!_voiceMode) return false;
  if(isAwaitingReply&&typeof _stopGeneration==='function'){
   suppressReplyPlayback=true;
   _disarmBargeInListening(true);
   _stopGeneration();
   return true;
  }
  if(isSpeaking){
   suppressReplyPlayback=false;
   _cancelSpeech();
   _finishAwaitingReply();
   _setPlaceholder(_listeningPlaceholder());
   _scheduleListening(120);
   return true;
  }
  return false;
 }

 function _submitVoiceInput(){
  var text=String((inp&&inp.value)||'').trim();
  if(!text){
   if(_voiceMode) _scheduleListening(400);
   return;
  }
  _setPlaceholder(_waitingPlaceholder());
  isAwaitingReply=true;
  var replyIdBefore=lastReplyIdForVoice;
  _beginReplyPolling(replyIdBefore);
  try{
   send();
  }catch(err){
   _finishAwaitingReply();
   _scheduleListening(800);
  }
 }

 function enterVoiceMode(){
  _voiceMode=true;
  suppressReplyPlayback=false;
  _syncButtonState();
  _syncVoiceMode(true);
  _probeNativeVoiceBridge().finally(function(){
   startListening();
  });
 }

 function exitVoiceMode(){
  _voiceMode=false;
  suppressReplyPlayback=false;
  _finishAwaitingReply();
  _clearSilenceTimer();
  _clearListeningTimer();
  _clearBargeInTimer();
  _stopActiveListening();
  _cancelSpeech();
  _syncVoiceMode(false);
  _syncButtonState();
  _setPlaceholder(_defaultPlaceholder());
 }

 function _startBrowserListening(lang){
  if(!recognition){
   _scheduleListening(600);
   return;
  }
  _clearSilenceTimer();
  _clearListeningTimer();
  recognition.lang=lang||_voiceChatLang();
  if(inp) inp.value='';
  _setPlaceholder(_listeningPlaceholder());
  activeListenSource='browser';
  try{
   recognition.start();
   isRecording=true;
   _syncButtonState();
  }catch(err){
   activeListenSource='';
   isRecording=false;
   _scheduleListening(500);
  }
 }

 function _startNativeListening(lang){
  var api=_getNativeVoiceApi();
  if(!api||typeof api.voice_listen_start!=='function'){
   if(browserSpeechAvailable){
    _startBrowserListening(_voiceChatLang());
   }else{
    _scheduleListening(600);
   }
   return;
  }
  _clearSilenceTimer();
  _clearListeningTimer();
  if(inp) inp.value='';
  _setPlaceholder(_listeningPlaceholder());
  Promise.resolve(api.voice_listen_start(lang)).then(function(result){
   if(!_voiceMode) return;
   if(result&&result.ok){
    activeListenSource='native';
    isRecording=true;
    _syncButtonState();
    return;
   }
   if(browserSpeechAvailable){
    _startBrowserListening(_voiceChatLang());
    return;
   }
   _scheduleListening(700);
  }).catch(function(){
   if(browserSpeechAvailable){
    _startBrowserListening(_voiceChatLang());
    return;
   }
   _scheduleListening(700);
  });
 }

 function startListening(){
  if(!_voiceMode||isAwaitingReply||isSpeaking) return;
  if(!nativeVoice.probed){
   var api=_getNativeVoiceApi();
   if(api&&typeof api.voice_bridge_status==='function'){
    _probeNativeVoiceBridge(true).finally(function(){
     if(_voiceMode&&!isAwaitingReply&&!isSpeaking) startListening();
    });
    return;
   }
  }
  var lang=_voiceChatLang();
  var nativeListenLang=_resolveNativeListenLang(lang);
  if(nativeListenLang){
   _startNativeListening(nativeListenLang);
   return;
  }
  if(browserSpeechAvailable){
   _startBrowserListening(lang);
   return;
  }
  _scheduleListening(600);
 }

 function _speakReplyBrowser(text, lang){
  if(!hasSpeechSynthesis){
   _scheduleListening(350);
   return;
  }
  _cancelSpeech();
  var utterance=new SpeechSynthesisUtterance(text);
  utterance.lang=lang||_voiceChatLang(text);
  utterance.rate=/^zh/i.test(utterance.lang) ? 1.02 : 1;
  utterance.pitch=1;
  var voice=_pickSpeechVoice(utterance.lang);
  if(voice) utterance.voice=voice;
  utterance.onstart=function(){
   if(activeUtterance!==utterance) return;
   activeSpeakSource='browser';
   isSpeaking=true;
   _syncTtsStatus(true);
   _setPlaceholder(_waitingPlaceholder());
  };
  utterance.onend=function(){
   if(activeUtterance!==utterance) return;
   activeUtterance=null;
   activeSpeakSource='';
   isSpeaking=false;
   _syncTtsStatus(false);
   if(_voiceMode) _scheduleListening(300);
  };
  utterance.onerror=function(){
   if(activeUtterance!==utterance) return;
   activeUtterance=null;
   activeSpeakSource='';
   isSpeaking=false;
   _syncTtsStatus(false);
   if(_voiceMode) _scheduleListening(500);
  };
  activeUtterance=utterance;
  try{
   window.speechSynthesis.speak(utterance);
  }catch(err){
   activeUtterance=null;
   activeSpeakSource='';
   isSpeaking=false;
   _syncTtsStatus(false);
   _scheduleListening(500);
  }
 }

 function _speakReplyNative(text, lang){
  var api=_getNativeVoiceApi();
  if(!api||typeof api.voice_speak!=='function'){
   _speakReplyBrowser(text,lang||_voiceChatLang(text));
   return;
  }
  _cancelSpeech();
  activeSpeakSource='native';
  isSpeaking=true;
  _syncTtsStatus(true);
  _setPlaceholder(_waitingPlaceholder());
  Promise.resolve(api.voice_speak(text,lang)).then(function(result){
   if(result&&result.ok){
    activeSpeakSource='native';
    isSpeaking=true;
    return;
   }
   activeSpeakSource='';
   isSpeaking=false;
   _syncTtsStatus(false);
   if(hasSpeechSynthesis){
    _speakReplyBrowser(text,_voiceChatLang(text));
    return;
   }
   _scheduleListening(400);
  }).catch(function(){
   activeSpeakSource='';
   isSpeaking=false;
   _syncTtsStatus(false);
   if(hasSpeechSynthesis){
    _speakReplyBrowser(text,_voiceChatLang(text));
    return;
   }
   _scheduleListening(500);
  });
 }

 function _submitBargeInTranscript(text){
  var transcript=String(text||'').trim();
  bargeInActive=false;
  activeListenSource='';
  isRecording=false;
  if(!transcript){
   if(_voiceMode&&isSpeaking&&activeSpeakSource==='native'){
    _armBargeInListening(220);
   }
   return;
  }
  suppressReplyPlayback=false;
  _cancelSpeech();
  _finishAwaitingReply();
  if(inp) inp.value=transcript;
  _submitVoiceInput();
 }

 function _speakReply(text){
  var clean=_normalizeSpeechText(text);
  if(!_voiceMode) return;
  if(!clean){
   _scheduleListening(350);
   return;
  }
  var lang=_voiceChatLang(clean);
  var nativeSpeakLang=_resolveNativeSpeakLang(lang);
  if(nativeSpeakLang){
   _speakReplyNative(clean,nativeSpeakLang);
   return;
  }
  if(hasSpeechSynthesis){
   _speakReplyBrowser(clean,lang);
   return;
  }
  _scheduleListening(350);
 }

 function _handleAssistantReply(text, replyId){
  if(!_voiceMode) return;
  if(suppressReplyPlayback) return;
  var normalizedReplyId=String(replyId||'').trim();
  if(normalizedReplyId){
   if(normalizedReplyId===lastReplyIdForVoice&&!isAwaitingReply) return;
   lastReplyIdForVoice=normalizedReplyId;
  }
  _finishAwaitingReply();
  _speakReply(text);
 }

 function _beginReplyPolling(previousReplyId){
  var replyIdBefore=String(previousReplyId||'').trim();
  _stopReplyPolling();
  pollTimer=setInterval(function(){
   if(!_voiceMode||!isAwaitingReply){
    _stopReplyPolling();
    return;
   }
   pollCount++;
   if(pollCount>=45){
    _finishAwaitingReply();
    if(_voiceMode) _scheduleListening(500);
    return;
   }
   fetch('/companion/state')
    .then(function(r){ return r.json(); })
    .then(function(state){
     if(!_voiceMode||!isAwaitingReply||!state) return;
     var nextReplyId=String(state.last_reply_id||state.reply_id||'').trim();
     if(nextReplyId&&nextReplyId!==replyIdBefore){
      _handleAssistantReply(
       String(state.last_reply_full||state.last_reply_summary||state.last_reply||''),
       nextReplyId
      );
     }
    })
    .catch(function(){});
  },700);
 }

 voiceBtn.addEventListener('click',function(e){
  e.preventDefault();
  if(_voiceMode&&_interruptVoiceCycleAndRelisten()) return;
  if(_voiceMode) exitVoiceMode();
  else enterVoiceMode();
 });

 window.addEventListener('aaroncore:assistant-reply-final',function(evt){
  if(!_voiceMode||isSpeaking||suppressReplyPlayback) return;
  var detail=(evt&&evt.detail)||{};
  if(isRecording){
   _stopActiveListening();
  }
  _handleAssistantReply(String(detail.text||''),String(detail.reply_id||''));
 });

 window.addEventListener('aaroncore:chat-request-state',function(evt){
  var detail=(evt&&evt.detail)||{};
  var state=String(detail.state||'').toLowerCase();
  if(!_voiceMode) return;
  if(state==='started'){
   suppressReplyPlayback=false;
   _disarmBargeInListening(true);
   _stopActiveListening();
   _cancelSpeech();
   _finishAwaitingReply();
   isAwaitingReply=true;
   _setPlaceholder(_waitingPlaceholder());
   return;
  }
  if(state==='stopping'){
   suppressReplyPlayback=true;
   _disarmBargeInListening(true);
   _stopActiveListening();
   _cancelSpeech();
   _finishAwaitingReply();
   _setPlaceholder(_waitingPlaceholder());
   return;
  }
  if(state==='aborted'){
   _disarmBargeInListening(true);
   _finishAwaitingReply();
   _cancelSpeech();
   _setPlaceholder(_listeningPlaceholder());
   _scheduleListening(180);
   return;
  }
  if(state==='completed'){
   if(suppressReplyPlayback){
    _disarmBargeInListening(true);
    _finishAwaitingReply();
    _cancelSpeech();
    _scheduleListening(220);
    return;
   }
   var finalReplyText=String(detail.reply_text||'').trim();
   if(finalReplyText&&!isSpeaking&&isAwaitingReply){
    _handleAssistantReply(finalReplyText,String(detail.reply_id||''));
    return;
   }
   if(!finalReplyText&&!isSpeaking){
    _finishAwaitingReply();
    _scheduleListening(320);
   }
   return;
  }
  if(state==='error'){
   _disarmBargeInListening(true);
   _finishAwaitingReply();
   _cancelSpeech();
   _scheduleListening(500);
  }
 });

 window.addEventListener('aaroncore-native-voice-state',function(evt){
  var detail=(evt&&evt.detail)||{};
  _applyNativeVoiceStatus(detail);
  if(typeof detail.listening==='boolean'){
   if(detail.listening){
    if(activeListenSource!=='native-barge') activeListenSource='native';
    bargeInActive=(activeListenSource==='native-barge');
    isRecording=true;
    if(!(activeListenSource==='native-barge'&&isSpeaking)){
     _setPlaceholder(_listeningPlaceholder());
    }
   }else if(activeListenSource==='native'||activeListenSource==='native-barge'){
    var wasBarge=activeListenSource==='native-barge';
    activeListenSource='';
    bargeInActive=false;
    isRecording=false;
    if(wasBarge&&isSpeaking){
     _setPlaceholder(_waitingPlaceholder());
    }else if(!_voiceMode&&!isSpeaking){
     _setPlaceholder(_defaultPlaceholder());
    }
   }
  }
  if(typeof detail.speaking==='boolean'){
   if(detail.speaking){
     activeSpeakSource='native';
     isSpeaking=true;
     _syncTtsStatus(true);
     _setPlaceholder(_waitingPlaceholder());
     _armBargeInListening(650);
   }else if(activeSpeakSource==='native'){
     var hadSpeaking=isSpeaking;
     var suppressSchedule=skipNextNativeSpeakStop;
     skipNextNativeSpeakStop=false;
     _disarmBargeInListening(true);
     activeSpeakSource='';
     isSpeaking=false;
     _syncTtsStatus(false);
     if(_voiceMode&&hadSpeaking&&!suppressSchedule&&!isAwaitingReply&&!isRecording){
      _scheduleListening(300);
     }
   }
  }
  _syncButtonState();
 });

 window.addEventListener('aaroncore-native-voice-result',function(evt){
  if(!_voiceMode) return;
  var detail=(evt&&evt.detail)||{};
  if(activeListenSource==='native-barge'||(isSpeaking&&activeSpeakSource==='native')){
   _submitBargeInTranscript(String(detail.text||''));
   return;
  }
  bargeInActive=false;
  activeListenSource='';
  isRecording=false;
  if(inp) inp.value=String(detail.text||'');
  _submitVoiceInput();
 });

 window.addEventListener('aaroncore-native-voice-error',function(evt){
  var detail=(evt&&evt.detail)||{};
  var phase=String(detail.phase||'').toLowerCase();
  if(phase==='listen'){
   var wasBarge=(activeListenSource==='native-barge')||bargeInActive;
   activeListenSource='';
   bargeInActive=false;
   isRecording=false;
   if(!_voiceMode) return;
   if(wasBarge&&isSpeaking&&activeSpeakSource==='native'){
    var bargeDelay=String(detail.code||'').toLowerCase()==='no-speech' ? 220 : 900;
    _armBargeInListening(bargeDelay);
    return;
   }
   if(browserSpeechAvailable){
    var lang=_voiceChatLang();
    if(!_resolveNativeListenLang(lang)){
     _startBrowserListening(lang);
     return;
    }
   }
   var code=String(detail.code||'').toLowerCase();
   var delay=code==='no-speech' ? 500 : 900;
   _scheduleListening(delay);
   return;
  }
  if(phase==='speak'){
   var hadSpeaking=isSpeaking;
   _disarmBargeInListening(true);
   activeSpeakSource='';
   isSpeaking=false;
   skipNextNativeSpeakStop=false;
   _syncTtsStatus(false);
   if(_voiceMode&&hadSpeaking&&!isAwaitingReply){
    _scheduleListening(500);
   }
  }
 });

 if(recognition){
  recognition.onresult=function(e){
   var transcript='';
   var isFinal=false;
   activeListenSource='browser';
   for(var i=(e.resultIndex||0);i<e.results.length;i++){
    transcript+=e.results[i][0].transcript;
    if(e.results[i].isFinal) isFinal=true;
   }
   if(inp) inp.value=transcript;
   if(isFinal&&transcript.trim()){
    _clearSilenceTimer();
    silenceTimer=setTimeout(function(){
     if(!_voiceMode) return;
     _stopActiveListening();
    },1200);
   }
  };

  recognition.onend=function(){
   isRecording=false;
   _clearSilenceTimer();
   if(skipNextRecognitionEnd){
    skipNextRecognitionEnd=false;
    if(!_voiceMode) _setPlaceholder(_defaultPlaceholder());
    return;
   }
   if(!_voiceMode){
    _setPlaceholder(_defaultPlaceholder());
    return;
   }
   if(activeListenSource==='browser') activeListenSource='';
   if(isAwaitingReply||isSpeaking) return;
   _submitVoiceInput();
  };

  recognition.onerror=function(e){
   isRecording=false;
   _clearSilenceTimer();
   activeListenSource='';
   if(!_voiceMode) return;
   var code=String((e&&e.error)||'').trim().toLowerCase();
   if(code==='not-allowed'||code==='service-not-allowed'){
    exitVoiceMode();
    try{
     alert('Microphone access is required for voice chat.');
    }catch(err){}
    return;
   }
   if(isAwaitingReply||isSpeaking) return;
   var delay=code==='no-speech' ? 500 : (code==='aborted' ? 250 : 900);
   _scheduleListening(delay);
  };
 }

 _startNativeProbeLoop();
 _syncVoiceAvailability();
})();

function _setCodDot(mode){
 var dot=document.getElementById('codStatusDot');
 if(!dot) return;
 dot.className='cod-dot '+(mode==='trace'?'cod-trace':'cod-flash');
}
