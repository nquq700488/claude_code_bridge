"""Team UI embedded HTML/JS/CSS single-page application."""

TEAM_UI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CCB Team UI</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#090c10;--surface:#0d1117;--surface2:#111820;--border:#1c2333;--border-light:#253049;
  --text:#d2d8e0;--text-mid:#a0aab4;--text-dim:#9099a3;
  --claude:#d97706;--codex:#6366f1;--gemini:#059669;--kimi:#dc2626;--custom:#8b5cf6;--human:#58a6ff;
  --radius:6px;--font:system-ui,-apple-system,sans-serif;--mono:'SF Mono',JetBrains Mono,Menlo,monospace;
  --transition:150ms ease
}
html,body{height:100%;overflow:hidden}
body{font-family:var(--font);background:var(--bg);color:var(--text);display:flex;flex-direction:column;font-size:13px;line-height:1.5;-webkit-font-smoothing:antialiased}
header{flex-shrink:0;display:flex;align-items:center;gap:14px;padding:10px 18px;background:var(--surface);border-bottom:1px solid var(--border)}
header h1{font-size:14px;font-weight:600;letter-spacing:-.01em;color:var(--text);white-space:nowrap}
header .meta{font-size:11px;color:var(--text-mid);display:flex;gap:10px;align-items:center;font-variant-numeric:tabular-nums}
header .dot{width:7px;height:7px;border-radius:50%;display:inline-block}
header .dot.running{background:#3fb950;box-shadow:0 0 8px rgba(63,185,80,.4)}
header .dot.stopped{background:#f85149;box-shadow:0 0 8px rgba(248,81,73,.3)}
header button{font-size:11px;font-weight:500;padding:5px 12px;border:1px solid var(--border-light);border-radius:4px;background:transparent;color:var(--text-mid);cursor:pointer;transition:all var(--transition)}
header button:hover{border-color:var(--text-dim);color:var(--text)}
main{flex:1;display:flex;min-height:0}
aside.sidebar{width:188px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--border);overflow-y:auto;padding:6px 0}
aside.sidebar h2{font-size:10px;font-weight:600;text-transform:uppercase;color:var(--text-dim);padding:10px 14px 6px;letter-spacing:.08em}
.member-card{display:flex;align-items:center;gap:10px;padding:7px 14px;cursor:pointer;font-size:12px;transition:background var(--transition);margin:0 4px;border-radius:4px}
.member-card:hover{background:var(--surface2)}
.member-card .indicator{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.member-card .indicator.active{background:#3fb950;box-shadow:0 0 6px rgba(63,185,80,.5)}
.member-card .indicator.idle{background:#484f58}
.member-card .indicator.working{background:#d29922;box-shadow:0 0 6px rgba(210,153,34,.4);animation:pulse-dot 2s infinite}
.member-card .info{flex:1;min-width:0}
.member-card .name{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text);font-size:12px}
.member-card .meta{font-size:10px;color:var(--text-dim);margin-top:1px;font-variant-numeric:tabular-nums}
.timeline{flex:1;overflow-y:auto;overflow-x:hidden;padding:20px 24px;display:flex;flex-direction:column;gap:10px}
.msg{display:flex;flex-direction:column;max-width:76%;animation:msgIn .25s ease}
.msg.user{align-self:flex-end;align-items:flex-end}
.msg.system{align-self:center;align-items:center;max-width:100%}
.msg .sender{font-size:10.5px;color:var(--text-mid);margin-bottom:3px;display:flex;gap:5px;align-items:center;font-weight:500}
.msg .sender .badge{font-size:9.5px;padding:1px 6px;border-radius:3px;color:#fff;font-weight:600;letter-spacing:.03em}
.msg .bubble{padding:10px 14px;border-radius:var(--radius);font-size:13px;line-height:1.55;word-break:break-word;background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--border)}
.msg.user .bubble{background:rgba(88,166,255,.06);border-color:rgba(88,166,255,.12);border-left-color:var(--human)}
.msg.system .bubble{background:transparent;border:none;color:var(--text-dim);font-size:11px;text-align:center;padding:3px 8px}
.msg .time{font-size:9.5px;color:var(--text-dim);margin-top:3px;font-variant-numeric:tabular-nums}
.msg .reply-ctx{font-size:10.5px;color:var(--text-dim);border-left:2px solid var(--text-dim);padding-left:8px;margin-bottom:5px;max-height:3em;overflow:hidden;opacity:.7}
.msg .bubble code{font-family:var(--mono);font-size:11.5px;background:rgba(110,118,129,.15);padding:1.5px 5px;border-radius:3px}
.msg .bubble pre{background:rgba(0,0,0,.5);padding:12px 16px;border-radius:var(--radius);font-family:var(--mono);font-size:11.5px;overflow-x:auto;margin:8px 0;line-height:1.5;white-space:pre-wrap;border:1px solid rgba(255,255,255,.04)}
.msg .bubble pre code{background:none;padding:0;font-size:inherit}
.msg .bubble h1,.msg .bubble h2,.msg .bubble h3,.msg .bubble h4{font-size:13px;font-weight:600;margin:8px 0 3px;color:var(--text)}
.msg .bubble hr{border:none;border-top:1px solid var(--border);margin:10px 0}
.msg .bubble blockquote{border-left:2px solid var(--border-light);padding-left:10px;margin:6px 0;color:var(--text-mid);font-size:12px}
.msg .bubble ul,.msg .bubble ol{margin:5px 0;padding-left:20px}
.msg .bubble li{margin:2px 0}
.msg .bubble a{color:var(--human);text-decoration:none}
.msg .bubble a:hover{text-decoration:underline}
.msg .bubble strong{color:var(--text);font-weight:700}
.msg .bubble em{color:var(--text-mid)}
.msg.thinking .bubble{border-left-color:var(--text-dim);opacity:.6;font-style:italic}
.msg.thinking .dots{color:var(--text-mid);font-size:12px}
footer{flex-shrink:0;border-top:1px solid var(--border);padding:12px 18px;background:var(--surface)}
.input-row{display:flex;gap:8px;align-items:center}
.input-row select{background:var(--bg);color:var(--text-mid);border:1px solid var(--border);border-radius:var(--radius);padding:7px 10px;font-size:11.5px;min-width:130px;cursor:pointer;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath fill='%238b949e' d='M0 0h8L4 5z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;padding-right:26px}
.input-row input{flex:1;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:var(--radius);padding:7px 14px;font-size:13px;outline:none;transition:border-color var(--transition)}
.input-row input:focus{border-color:var(--human);box-shadow:0 0 0 2px rgba(88,166,255,.1)}
.input-row input::placeholder{color:var(--text-dim)}
.input-row button{padding:7px 20px;background:var(--codex);color:#fff;border:none;border-radius:var(--radius);font-size:12.5px;cursor:pointer;font-weight:600;transition:all var(--transition)}
.input-row button:hover{background:#7378f5;transform:translateY(-1px)}
.input-row button:disabled{opacity:.3;cursor:not-allowed;transform:none}
.mention-chips{display:flex;gap:4px;flex-wrap:wrap;padding:6px 0 0}
.mention-chips span{font-size:10.5px;padding:3px 10px;border-radius:12px;background:var(--surface2);border:1px solid var(--border);cursor:pointer;color:var(--text-mid);transition:all var(--transition)}
.mention-chips span:hover{background:var(--border-light);color:var(--text)}
.toast{position:fixed;top:16px;right:16px;padding:10px 18px;background:rgba(248,81,73,.95);color:#fff;border-radius:var(--radius);font-size:12px;z-index:100;animation:msgIn .2s;box-shadow:0 4px 12px rgba(0,0,0,.3)}
.error-bar{background:rgba(248,81,73,.08);color:#f85149;text-align:center;padding:5px;font-size:11px;display:none;border-bottom:1px solid rgba(248,81,73,.15)}
@keyframes msgIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse-dot{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes thinking-pulse{0%,100%{opacity:.4}50%{opacity:.8}}
.msg.thinking .dots{color:var(--text-mid);font-size:12px}
.msg.thinking .dot-pulse::after{content:'';animation:dots 1.4s steps(3) infinite}
.msg.thinking .dot-pulse{animation:pulse 1.4s infinite}
@keyframes pulse{0%,20%{opacity:0}50%{opacity:1}80%,100%{opacity:0}}
@keyframes dots{0%{content:'.'}33%{content:'..'}66%{content:'...'}100%{content:'.'}}
.msg.thinking{animation:thinking-pulse 1.8s infinite}
</style>
</head>
<body>
<header id="header">
  <h1 id="team-name">-</h1>
  <div class="meta">
    <span id="topology">-</span>
    <span class="dot" id="status-dot"></span>
    <span id="status-text">-</span>
  </div>
  <div style="flex:1"></div>
  <button id="btn-up">Start</button>
  <button id="btn-down">Stop</button>
</header>
<div class="error-bar" id="error-bar"></div>
<main>
<aside class="sidebar" id="sidebar"></aside>
<div class="timeline" id="timeline"></div>
</main>
<footer>
  <div class="input-row">
    <select id="send-target"></select>
    <input id="send-input" placeholder="Send a message... (@name / @all)" disabled>
    <button id="send-btn" disabled>Send</button>
  </div>
  <div class="mention-chips" id="mention-chips"></div>
</footer>
<div class="toast" id="toast" style="display:none"></div>
<script>
(function(){
var $=function(id){return document.getElementById(id);};
var PROVIDER_COLORS={claude:'#d97706',codex:'#6366f1',gemini:'#059669',kimi:'#dc2626',mmx:'#ec4899'};
var state={team:null,members:[],cursor:null,token:''};var seenKeys={};
var pollTimer=null;

function api(path,opts){
  opts=opts||{};
  var url=path+(path.indexOf('?')>=0?'&':'?')+'token='+state.token;
  return fetch(url,opts).then(function(r){return r.ok?r.json():Promise.reject(r.statusText);});
}

function loadState(){
  api('/api/state').then(function(s){
    state.team=s.team;state.members=s.members;
    renderHeader(s);renderSidebar(s);renderInput(s);
    // Don't override thinking-disabled state
    var hasThinking=$('timeline').querySelector('.msg.thinking');
    if(!hasThinking){
      $('send-input').disabled=(s.status!=='running');
      $('send-btn').disabled=(s.status!=='running');
    }
  }).catch(function(e){showError('Error: '+e);});
}

function loadTimeline(){
  var qs=state.cursor?'?since='+state.cursor:'';
  return api('/api/timeline'+qs).then(function(t){
    if(t.events&&t.events.length){
      // Only auto-scroll if user is already near bottom
      var tl=$('timeline'),wasAtBottom=(tl.scrollTop+tl.clientHeight>=tl.scrollHeight-40);
      appendEvents(t.events);state.cursor=t.cursor;
      if(wasAtBottom)scrollBottom();
    }
  }).catch(function(){});
}

function renderHeader(s){
  $('team-name').textContent=s.team;
  $('topology').textContent=s.topology;
  var dot=$('status-dot');
  dot.className='dot '+(s.status==='running'?'running':'stopped');
  $('status-text').textContent=s.status==='running'?'running':'stopped';
}

function renderSidebar(s){
  var html='<h2>Members ('+s.members.length+')</h2>';
  s.members.forEach(function(m){
    var color=PROVIDER_COLORS[m.provider]||defaultColor(m.provider);
    var cls=m.state==='visible'?'active':(m.state==='hidden'?'idle':'working');
    html+='<div class="member-card" data-member="'+esc(m.name)+'">'+
      '<span class="indicator '+cls+'" style="background:'+color+'"></span>'+
      '<div class="info"><div class="name">'+esc(m.name)+'</div>'+
      '<div class="meta">'+esc(m.provider)+(m.model?' '+esc(m.model):'')+'</div></div></div>';
  });
  $('sidebar').innerHTML=html;
}

function renderInput(s){
  var sel=$('send-target'),old=sel.value;
  sel.innerHTML='<option value="@all">@all (broadcast)</option>';
  s.members.forEach(function(m){
    sel.innerHTML+='<option value="'+esc(m.name)+'">@'+esc(m.name)+'</option>';
  });
  if(old)sel.value=old;  // preserve user's selection
  var chips='';
  s.members.forEach(function(m){
    chips+='<span class="mention-chip" data-member="'+esc(m.name)+'">@'+esc(m.name)+'</span>';
  });
  $('mention-chips').innerHTML=chips;
}

function appendEvents(events){
  var tl=$('timeline');
  events.forEach(function(ev){var key=(ev.job_id||'')+':'+ev.type;if(seenKeys[key])return;seenKeys[key]=true;
    // When a real reply arrives, clear thinking indicator for that specific agent
    if((ev.type==='reply'||ev.type==='system')&&ev.from&&ev.from!=='You'){
      removeThinking(ev.from);
    }
    var div=document.createElement('div');
    var isYou=ev.from==='human'||ev.from==='You';
    div.className='msg '+(isYou?'user':(ev.type==='system'?'system':''));
    if(ev.type==='system'){
      div.innerHTML='<div class="bubble">'+esc(ev.body)+'</div><div class="time">'+fmtTime(ev.time)+'</div>';
    }else{
      var color=PROVIDER_COLORS[ev.from_provider]||defaultColor(ev.from||'');
      var badge=isYou?
        '<span class="badge" style="background:var(--human)">You</span> ':
        '<span class="badge" style="background:'+color+'">'+esc(ev.from_provider||'')+'</span>'+esc(ev.from||'')+' ';
      var senderHtml=badge;
      if(ev.to){
        senderHtml+='<span style="font-size:10px;color:var(--text-dim)">→ '+esc(ev.to)+'</span>';
      }
      var body=ev.body_html||('<div>'+esc(ev.body||'').split(new RegExp(String.fromCharCode(10))).join('<br>')+'</div>');
      if(ev.reply_to){
        body='<div class="reply-ctx">↳ '+esc((ev.reply_to||'').substring(0,120))+'</div>'+body;
      }
      div.innerHTML='<div class="sender">'+senderHtml+'</div>'+
        '<div class="bubble" style="border-left-color:'+color+'">'+body+'</div><div class="time">'+fmtTime(ev.time)+'</div>';
    }
    tl.appendChild(div);
  });
}

function sendMessage(){
  var sel=$('send-target'),input=$('send-input'),body=input.value.trim();
  if(!body)return;
  var to=sel.value;
  api('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:to,body:body})})
    .then(function(r){
      input.value='';
      if(r.ask_event){appendEvents([r.ask_event]);}
      var targets=r.targets||(to==='@all'?[]:[to]);
      targets.forEach(function(t){showThinking(t);});
      setTimeout(scrollBottom,50);
    }).catch(function(e){showError('Send failed: '+e);});
}

function teamAction(action){
  api('/api/'+action,{method:'POST'}).then(function(r){
    appendEvents([{type:'system',body:action==='up'?'Team started':'Team stopped',time:new Date().toISOString()}]);
    setTimeout(loadState,1500);
  }).catch(function(e){showError(action+' failed: '+e);});
}

function fillMention(name){$('send-target').value=name;$('send-input').focus();}
function scrollBottom(){var tl=$('timeline');tl.scrollTop=tl.scrollHeight;}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function fmtTime(t){try{return new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});}catch(e){return'';}}
function defaultColor(name){var h=0;for(var i=0;i<name.length;i++)h=name.charCodeAt(i)+((h<<5)-h);return 'hsl('+(h%360)+',60%,55%)';}
function showError(msg){var t=$('toast');t.textContent=msg;t.style.display='block';setTimeout(function(){t.style.display='none';},4000);}
function showThinking(name){
  removeThinking(name);
  var div=document.createElement('div');div.className='msg thinking';div.setAttribute('data-target',name);
  var color='#6b7280',label=name;
  if(state.members)for(var i=0;i<state.members.length;i++){
    if(state.members[i].name===name){
      color=PROVIDER_COLORS[state.members[i].provider]||defaultColor(state.members[i].provider);
      label=state.members[i].provider;
      break;
    }
  }
  div.innerHTML='<div class="sender"><span class="badge" style="background:'+color+'">'+esc(label)+'</span>'+esc(name)+'</div>'+
    '<div class="bubble"><span class="dots">思考中</span>&nbsp;<span class="dot-pulse"></span></div>';
  $('timeline').appendChild(div);
  $('send-btn').disabled=true;$('send-input').disabled=true;
  setTimeout(scrollBottom,50);
}
function removeThinking(name){
  var prev=$('timeline').querySelector('.msg.thinking[data-target=\"'+name+'\"]');
  if(prev)prev.remove();
  if(!$('timeline').querySelector('.msg.thinking')){
    $('send-btn').disabled=false;$('send-input').disabled=false;
  }
}

$('send-btn').addEventListener('click',sendMessage);
$('send-input').addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}});
$('btn-up').addEventListener('click',function(){teamAction('up');});
$('btn-down').addEventListener('click',function(){teamAction('down');});
$('sidebar').addEventListener('click',function(e){
  var card=e.target.closest('.member-card');
  if(card&&card.dataset.member){fillMention(card.dataset.member);}
});
$('mention-chips').addEventListener('click',function(e){
  var chip=e.target.closest('.mention-chip');
  if(chip&&chip.dataset.member){fillMention(chip.dataset.member);}
});

state.token=new URLSearchParams(location.search).get('token')||'';
loadState();
loadTimeline().then(function(){setTimeout(scrollBottom,100);});
pollTimer=setInterval(loadTimeline,2000);
setInterval(loadState,5000);
})();
</script>
</body>
</html>"""

__all__ = ['TEAM_UI_HTML']
