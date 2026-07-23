"""Team UI embedded HTML/JS/CSS single-page application."""

TEAM_UI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CCB Team UI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--surface:#1a1d27;--border:#2a2d38;--text:#e1e4eb;--text-dim:#6b7280;
  --claude:#d97706;--codex:#6366f1;--gemini:#059669;--kimi:#dc2626;--custom:#8b5cf6;--human:#3b82f6;
  --radius:8px;--font:system-ui,-apple-system,sans-serif;--mono:'SF Mono',Menlo,monospace
}
body{font-family:var(--font);background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:12px;padding:12px 16px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
header h1{font-size:15px;font-weight:600}
header .meta{font-size:12px;color:var(--text-dim);display:flex;gap:8px;align-items:center}
header .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
header .dot.running{background:#22c55e}
header .dot.stopped{background:#ef4444}
header button{font-size:12px;padding:4px 10px;border:1px solid var(--border);border-radius:4px;background:transparent;color:var(--text);cursor:pointer}
header button:hover{background:var(--border)}
main{display:flex;flex:1;overflow:hidden}
aside.sidebar{width:200px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--border);overflow-y:auto;padding:8px 0}
aside.sidebar h2{font-size:11px;text-transform:uppercase;color:var(--text-dim);padding:8px 16px 4px;letter-spacing:.5px}
.member-card{display:flex;align-items:center;gap:8px;padding:8px 16px;cursor:pointer;font-size:13px;transition:background .15s}
.member-card:hover{background:var(--border)}
.member-card .indicator{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.member-card .indicator.active{background:#22c55e}
.member-card .indicator.idle{background:#6b7280}
.member-card .indicator.working{background:#f59e0b}
.member-card .info{flex:1;min-width:0}
.member-card .name{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.member-card .meta{font-size:11px;color:var(--text-dim)}
.timeline{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{display:flex;flex-direction:column;max-width:80%;animation:fadeIn .2s}
.msg.user{align-self:flex-end;align-items:flex-end}
.msg.system{align-self:center;align-items:center;max-width:100%}
.msg .sender{font-size:11px;color:var(--text-dim);margin-bottom:2px;display:flex;gap:6px;align-items:center}
.msg .sender .badge{font-size:10px;padding:1px 5px;border-radius:3px;color:#fff;font-weight:600}
.msg .bubble{padding:10px 14px;border-radius:var(--radius);font-size:13px;line-height:1.55;word-break:break-word;background:var(--surface);border:1px solid var(--border)}
.msg.user .bubble{background:rgba(59,130,246,.12);border-color:rgba(59,130,246,.3)}
.msg.system .bubble{background:transparent;border:none;color:var(--text-dim);font-size:12px;text-align:center;padding:4px 8px}
.msg .time{font-size:10px;color:var(--text-dim);margin-top:2px}
.msg .reply-ctx{font-size:11px;color:var(--text-dim);border-left:2px solid var(--border);padding-left:8px;margin-bottom:4px;max-height:3em;overflow:hidden}
.msg .bubble code{font-family:var(--mono);font-size:12px;background:rgba(0,0,0,.2);padding:1px 4px;border-radius:3px}
.msg .bubble pre{background:rgba(0,0,0,.35);padding:10px 14px;border-radius:6px;font-family:var(--mono);font-size:12px;overflow-x:auto;margin:6px 0;line-height:1.45;white-space:pre-wrap}
.msg .bubble pre code{background:none;padding:0;font-size:inherit}
.msg .bubble .expand{color:var(--text-dim);font-size:11px;cursor:pointer}
.msg .bubble h1,.msg .bubble h2,.msg .bubble h3,.msg .bubble h4{font-size:14px;font-weight:600;margin:6px 0 2px;color:var(--text)}
.msg .bubble hr{border:none;border-top:1px solid var(--border);margin:8px 0}
.msg .bubble blockquote{border-left:3px solid var(--claude);padding-left:10px;margin:6px 0;color:var(--text-dim);font-style:italic}
.msg .bubble ul,.msg .bubble ol{margin:4px 0;padding-left:18px}
.msg .bubble li{margin:2px 0}
.msg .bubble a{color:var(--codex);text-decoration:underline}
.msg .bubble strong{color:var(--text);font-weight:700}
.msg .bubble em{color:var(--text-dim)}
footer{border-top:1px solid var(--border);padding:10px 16px;background:var(--surface);flex-shrink:0}
.input-row{display:flex;gap:8px;align-items:center}
.input-row select{background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:6px 8px;font-size:13px;min-width:140px}
.input-row input{flex:1;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:6px 12px;font-size:13px;outline:none}
.input-row input:focus{border-color:var(--codex)}
.input-row button{padding:6px 16px;background:var(--codex);color:#fff;border:none;border-radius:4px;font-size:13px;cursor:pointer;font-weight:600}
.input-row button:disabled{opacity:.4;cursor:not-allowed}
.mention-chips{display:flex;gap:4px;flex-wrap:wrap;padding:4px 0 0}
.mention-chips span{font-size:11px;padding:2px 8px;border-radius:10px;background:var(--border);cursor:pointer}
.mention-chips span:hover{background:var(--codex);color:#fff}
.toast{position:fixed;top:12px;right:12px;padding:8px 16px;background:#ef4444;color:#fff;border-radius:6px;font-size:13px;z-index:100;animation:fadeIn .2s}
@keyframes fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.error-bar{background:rgba(239,68,68,.1);color:#fca5a5;text-align:center;padding:6px;font-size:12px;display:none}
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
  <button id="btn-up">Up</button>
  <button id="btn-down">Down</button>
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
var state={team:null,members:[],cursor:null,token:''};var seenJids={};
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
    $('send-input').disabled=(s.status!=='running');
    $('send-btn').disabled=(s.status!=='running');
  }).catch(function(e){showError('Error: '+e);});
}

function loadTimeline(){
  var qs=state.cursor?'?since='+state.cursor:'';
  api('/api/timeline'+qs).then(function(t){
    if(t.events&&t.events.length){appendEvents(t.events);state.cursor=t.cursor;scrollBottom();}
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
  events.forEach(function(ev){if(ev.job_id&&seenJids[ev.job_id])return;if(ev.job_id)seenJids[ev.job_id]=true;
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
        '<div class="bubble">'+body+'</div><div class="time">'+fmtTime(ev.time)+'</div>';
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
      // Use server-rendered ask event for immediate display
      if(r.ask_event){appendEvents([r.ask_event]);}
      scrollBottom();
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
loadTimeline();
pollTimer=setInterval(loadTimeline,2000);
setInterval(loadState,5000);
})();
</script>
</body>
</html>"""

__all__ = ['TEAM_UI_HTML']
