// Output page post-load helpers extracted from output.html.
_applyI18n();
function checkQQMonitor(){
 fetch('/qq/monitor').then(r=>r.json()).then(d=>{
  var dot=document.getElementById('qqMonitorDot');
  var label=document.getElementById('qqMonitorLabel');
  if(d.active){
   dot.style.display='flex';
   var groups=d.groups||[];
   dot.title=groups.join(', ')||'';
   label.textContent=t('qq.label')+(groups.length>1?' · '+groups.length+t('qq.groups'):'' );
  }else{
   dot.style.display='none';
  }
 }).catch(()=>{});
}
checkQQMonitor();
setInterval(checkQQMonitor,5000);