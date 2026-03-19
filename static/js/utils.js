var chatHistory='';
var CHAT_HISTORY_MAX=60;
var voiceEnabled=false;
function T(){var d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}

function trimChatHistory(){
 var tmp=document.createElement('div');
 tmp.innerHTML=chatHistory;
 var msgs=tmp.querySelectorAll('.msg');
 if(msgs.length>CHAT_HISTORY_MAX){
  var remove=msgs.length-CHAT_HISTORY_MAX;
  for(var i=0;i<remove;i++) msgs[i].parentNode.removeChild(msgs[i]);
  chatHistory=tmp.innerHTML;
 }
}

function updateSendButton(){
 var inp=document.getElementById('inp');
 var btn=document.getElementById('sendBtn');
 var hasText=inp.value.trim().length>0;
 var hasImage=typeof _pendingImage!=='undefined'&&!!_pendingImage;

 btn.disabled=!(hasText||hasImage);
}

function formatBubbleText(text){
 var div=document.createElement('div');
 div.textContent=String(text||'');
 var escaped=div.innerHTML;
 escaped=escaped.replace(/\n\n+/g,'<br><br>');
 escaped=escaped.replace(/\n/g,'<br>');
 return escaped;
}

function escapeHtml(text){
 return String(text||'')
  .replace(/&/g,'&amp;')
  .replace(/</g,'&lt;')
  .replace(/>/g,'&gt;')
  .replace(/"/g,'&quot;')
  .replace(/'/g,'&#39;');
}

function cleanInlineText(text, limit){
 var cleaned=String(text||'').replace(/\s+/g,' ').trim();
 if(!cleaned) return '';
 if(limit && cleaned.length>limit) return cleaned.slice(0, Math.max(limit-1, 1))+'\u2026';
 return cleaned;
}

function setInputVisible(visible){
 var inputArea=document.querySelector('.input');
 if(!inputArea) return;
 inputArea.style.display=visible?'block':'none';
}

