/* Redaktionsplan / Social-Media-Kalender für @edeka.berlin
   Daten: data/redaktionsplan.json. Karten lassen sich verschieben (Maus, Touch mit langem Drücken),
   Texte bearbeiten, neu anlegen und löschen. Änderungen speichert diese statische Seite im Browser
   (localStorage); „Änderungen kopieren“ gibt den Stand als JSON für data/redaktionsplan.json aus.
   Der Kalender erscheint in „Übersicht“ und im Tab „Redaktionsplan“ (ein Exemplar, wird verschoben). */
(function(){
  var CSS = ''
  + '#rpwrap{margin-top:14px}'
  + '.rp-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 10px}'
  + '.rp-seg{display:flex;gap:4px;background:#fff;border-radius:999px;padding:4px}'
  + '.rp-seg button,.rp-chip,.rp-btn{font:600 13.5px "Inter Tight",Inter,sans-serif;border:0;background:none;color:#3E3B33;padding:9px 16px;border-radius:999px;cursor:pointer;min-height:38px}'
  + '.rp-seg button.on{background:#2A60FF;color:#fff}'
  + '.rp-chip,.rp-btn{background:#fff;display:inline-flex;align-items:center;gap:7px}'
  + '.rp-chip.off{opacity:.4}.rp-btn:disabled{opacity:.4;cursor:default}'
  + '.rp-btn.pri{background:#2A60FF;color:#fff}.rp-btn.del{color:#A3301B}'
  + '.rp-status{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13.5px;color:#6E6A60;margin:0 0 14px}.rp-status b{color:#2A60FF}'
  + '.rp-chip i,.rp-tag i,.rp-lg i{width:10px;height:10px;border-radius:3px;display:inline-block;background:var(--c)}'
  + '.rp-reel{--c:#2A60FF;--t:#fff}.rp-karussell{--c:#FFD43B;--t:#16150F}.rp-story{--c:#C9D6FF;--t:#16150F}'
  + '.rp-tiktok{--c:#16150F;--t:#fff}.rp-whatsapp{--c:#2E7D5B;--t:#fff}.rp-aktion{--c:#E0482B;--t:#fff}'
  + '.rp-grid{display:grid;grid-template-columns:84px repeat(7,minmax(0,1fr));gap:4px}'
  + '.rp-hd{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:#6E6A60;font-weight:600;padding:4px 6px}'
  + '.rp-kw{font-size:12.5px;color:#6E6A60;padding:8px 6px}.rp-kw b{display:block;color:#16150F;font-size:15px}'
  + '.rp-day{background:#fff;border-radius:10px;min-height:140px;padding:7px;display:flex;flex-direction:column;gap:4px;min-width:0;transition:background .15s}'
  + '.rp-day.out{background:rgba(255,255,255,.5)}.rp-day.out .rp-n{opacity:.45}'
  + '.rp-day.over,.rp-agd.over,.rp-back.over{background:#E9EEFF;box-shadow:inset 0 0 0 2px #2A60FF}'
  + '.rp-n{font-size:13px;font-weight:700;display:flex;justify-content:space-between;gap:4px}.rp-n small{color:#2A60FF;font-weight:600}'
  + '.rp-ev{display:block;width:100%;text-align:left;border:0;border-radius:7px;padding:4px 6px;font:600 12px/1.25 "Inter Tight",Inter,sans-serif;background:var(--c);color:var(--t);cursor:grab;user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}'
  + '.rp-grid .rp-ev{touch-action:none}.rp-ag .rp-ev,.rp-back .rp-ev{touch-action:pan-y}'
  + '.rp-ev span{opacity:.75;margin-right:4px}'
  + '.rp-ev.offen{background:repeating-linear-gradient(135deg,var(--c) 0 6px,color-mix(in srgb,var(--c) 68%,#fff) 6px 12px)}'
  + '.rp-ev.moved{box-shadow:0 0 0 2px #F2F0EB,0 0 0 3.5px #2A60FF}'
  + '.rp-ev.lift{opacity:.3}'
  + '.rp-ghost{position:fixed;z-index:50;pointer-events:none;width:180px;transform:rotate(-2deg);box-shadow:0 12px 30px rgba(0,0,0,.25)}'
  + '.rp-ev:focus-visible,.rp-chip:focus-visible,.rp-seg button:focus-visible,.rp-btn:focus-visible{outline:2px solid #2A60FF;outline-offset:2px}'
  + '.rp-ag{display:grid;gap:4px}.rp-agkw{font-size:13px;color:#6E6A60;padding:12px 2px 4px}.rp-agkw b{color:#16150F}'
  + '.rp-agd{display:grid;grid-template-columns:64px minmax(0,1fr);gap:10px;background:#fff;border-radius:10px;padding:8px;min-height:44px;transition:background .15s}'
  + '.rp-agh{font-size:14px;line-height:1.25}.rp-agh small{display:block;color:#2A60FF;font-size:12px}.rp-agd.we .rp-agh b{color:#6E6A60}'
  + '.rp-agc{display:flex;flex-direction:column;gap:5px}.rp-ag .rp-ev{font-size:14px;padding:8px 10px}'
  + '.rp-back{display:grid;gap:8px;min-height:110px;border:1.5px dashed #D3CFC5;border-radius:12px;padding:10px;transition:background .15s}'
  + '.rp-back .rp-ev{padding:8px 10px;font-size:14px}.rp-back .rp-ev small{display:block;font-weight:500;opacity:.85;font-size:12.5px;margin-top:2px}'
  + '.rp-list td{vertical-align:top}.rp-list td:first-child{white-space:nowrap}'
  + '.rp-tag{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;font-size:13px;font-weight:600}'
  + '.rp-st{font-size:12.5px;font-weight:600;padding:3px 10px;border-radius:999px;background:#E9EEFF;color:#2A60FF;white-space:nowrap}.rp-st.offen{background:#FDE4DE;color:#A3301B}'
  + '.rp-lg{display:grid;gap:9px;font-size:14px;color:#3E3B33}.rp-lg div{display:flex;gap:8px;align-items:center}'
  + '.rp-next{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0 0 14px}'
  + '.rp-nx{background:#fff;border-radius:12px;padding:12px 14px}.rp-nx small{color:#6E6A60;font-size:12.5px;display:block}.rp-nx b{display:block;font-size:15px;line-height:1.3;margin-top:4px}'
  + '.rp-panel{position:fixed;right:16px;bottom:16px;width:min(400px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;background:#fff;border-radius:16px;padding:20px;box-shadow:0 18px 50px rgba(0,0,0,.2);display:none;z-index:40;font-family:"Inter Tight",Inter,sans-serif}'
  + '.rp-panel.on{display:block}.rp-panel h4{font-size:22px;letter-spacing:-.5px;line-height:1.15;margin:8px 30px 6px 0}'
  + '.rp-panel .x{position:absolute;right:8px;top:8px;width:40px;height:40px;border:0;background:none;font-size:20px;cursor:pointer;color:#16150F}'
  + '.rp-panel label{display:block;font-size:12.5px;color:#6E6A60;margin:12px 0 4px;font-weight:600}'
  + '.rp-panel input,.rp-panel select,.rp-panel textarea{width:100%;font:16px "Inter Tight",Inter,sans-serif;min-height:40px;border:0;border-radius:10px;padding:0 12px;background:#F2F0EB;color:#16150F}'
  + '.rp-panel textarea{padding:9px 12px;min-height:76px;resize:vertical;line-height:1.4}.rp-panel input[type=date]{width:auto}'
  + '.rp-panel .rp-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:6px}.rp-panel .rp-row>div{flex:1 1 140px}'
  + '.rp-panel .rp-btn{background:#F2F0EB}.rp-panel .rp-btn.pri{background:#2A60FF;color:#fff}'
  + '@media(max-width:860px){.rp-next{grid-template-columns:1fr}}'
  + '@media(max-width:760px){.rp-list thead{display:none}.rp-list tr{display:grid;padding:8px 0;border-bottom:1px solid #E1DED6}.rp-list td{border:0;padding:3px 0}.rp-chips{display:flex;gap:6px;overflow-x:auto;width:100%;padding-bottom:4px}.rp-chip{flex:none}}'
  + '@media(max-width:600px){.rp-panel{left:0;right:0;bottom:0;width:100%;border-radius:18px 18px 0 0;max-height:86vh}}'
  + '@media(prefers-reduced-motion:reduce){.rp-day,.rp-agd,.rp-back{transition:none}.rp-ghost{transform:none}}';

  var CH = {reel:'Instagram Reel',karussell:'Instagram Karussell',story:'Instagram Story',tiktok:'TikTok',whatsapp:'WhatsApp',aktion:'Gewinnspiel / Aktion'};
  var CHD = {reel:'Hofbesuch, Team, Humor, POV · 21 Uhr',karussell:'Preis mit Gesicht, Rezepte, Top 5 · 21 Uhr',story:'Handzettel, Umfragen, Super-Samstag',tiktok:'2 pro Woche, nativ geschnitten',whatsapp:'1 pro Woche, Angebot der Woche',aktion:'Start, Fristen, App & PAYBACK'};
  var ORD = {aktion:0,reel:1,karussell:2,tiktok:3,story:4,whatsapp:5};
  var DN = ['Mo','Di','Mi','Do','Fr','Sa','So'];
  var MONTHS = [{k:'2026-12',n:'Dezember 2026',r:['2026-11-30','2026-12-31']},{k:'2027-01',n:'Januar 2027',r:['2027-01-01','2027-01-31']}];
  var KEY = 'edeka-redaktionsplan-v1';
  var D = null, BASE = null;
  var V = {m:'2026-12', v:'monat', off:{}, sel:null, del:null, reset:false, undo:[], msg:''};

  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function dt(d){return new Date(d+'T12:00:00Z')}
  function iso(x){return x.toISOString().slice(0,10)}
  function add(d,n){var x=dt(d);x.setUTCDate(x.getUTCDate()+n);return iso(x)}
  function wd(d){return (dt(d).getUTCDay()+6)%7}
  function kw(d){var x=dt(d);x.setUTCDate(x.getUTCDate()-wd(d)+3);var f=new Date(Date.UTC(x.getUTCFullYear(),0,4));return 1+Math.round(((x-f)/864e5-3+((f.getUTCDay()+6)%7))/7)}
  function fmt(d){return d?DN[wd(d)]+' '+d.slice(8)+'.'+d.slice(5,7)+'.':'ohne Termin'}
  function month(){for(var i=0;i<MONTHS.length;i++)if(MONTHS[i].k===V.m)return MONTHS[i]}
  function inM(e){var r=month().r;return e.d&&e.d>=r[0]&&e.d<=r[1]}
  function byId(id){for(var i=0;i<D.entries.length;i++)if(D.entries[i].id===id)return D.entries[i]}
  function moved(e){return e.o!=null&&e.d!==e.o}
  function vis(){return D.entries.filter(function(e){return !V.off[e.ch]}).sort(function(a,b){return (a.d||'').localeCompare(b.d||'')||ORD[a.ch]-ORD[b.ch]})}
  function $(id){return document.getElementById(id)}
  function narrow(){return window.matchMedia('(max-width:760px)').matches}

  function store(){try{localStorage.setItem(KEY,JSON.stringify({base:BASE,entries:D.entries,updated:D.updated}))}catch(e){}}
  function changed(){D.updated=new Date().toISOString();store();render();}

  function chip(e,big){
    return '<button class="rp-ev rp-'+e.ch+(e.st==='z'?' offen':'')+(moved(e)?' moved':'')+'" data-rpi="'+esc(e.id)+'" title="'+esc(e.ti)+'">'
      +(e.t&&!big?'<span>'+esc(e.t)+'</span>':'')+esc(e.ti)+(big?'<small>'+esc(e.de)+'</small>':'')+'</button>';
  }
  function grid(){
    var first=V.m+'-01', d=add(first,-wd(first)), list=vis(), hol=D.holidays||[];
    var h='<div class="rp-grid"><div class="rp-hd">KW</div>'+DN.map(function(x){return '<div class="rp-hd">'+x+'</div>'}).join('');
    for(var w=0;w<6;w++){
      if(w>0&&d.slice(0,7)!==V.m)break;
      h+='<div class="rp-kw"><b>KW '+kw(d)+'</b>'+esc((D.weekNotes||{})[d]||'')+'</div>';
      for(var j=0;j<7;j++){
        var dd=d, evs=list.filter(function(e){return e.d===dd});
        h+='<div class="rp-day'+(d.slice(0,7)===V.m?'':' out')+'" data-rpdrop="'+d+'"><div class="rp-n">'+(+d.slice(8))+(hol.indexOf(d)>-1?'<small>Feiertag</small>':'')+'</div>'+evs.map(function(e){return chip(e)}).join('')+'</div>';
        d=add(d,1);
      }
    }
    return h+'</div>';
  }
  function agenda(){
    var r=month().r, list=vis(), d=r[0], h='<div class="rp-ag">', hol=D.holidays||[];
    while(d<=r[1]){
      var dd=d, evs=list.filter(function(e){return e.d===dd});
      if(d===r[0]||wd(d)===0){var n=(D.weekNotes||{})[d];h+='<div class="rp-agkw"><b>KW '+kw(d)+'</b>'+(n?' · '+esc(n):'')+'</div>'}
      h+='<div class="rp-agd'+(wd(d)>4?' we':'')+'" data-rpdrop="'+d+'"><div class="rp-agh"><b>'+DN[wd(d)]+' '+d.slice(8)+'.'+d.slice(5,7)+'.</b>'+(hol.indexOf(d)>-1?'<small>Feiertag</small>':'')+'</div><div class="rp-agc">'+evs.map(function(e){return chip(e)}).join('')+'</div></div>';
      d=add(d,1);
    }
    return h+'</div>';
  }
  function table(){
    var r=vis().filter(inM);
    return '<div style="overflow-x:auto"><table class="rp-list"><thead><tr><th>Datum</th><th>Kanal</th><th>Inhalt</th><th>Baustein</th><th>Status</th></tr></thead><tbody>'
      + r.map(function(e){return '<tr><td>'+fmt(e.d)+(e.t?' · '+esc(e.t):'')+'</td><td><span class="rp-tag rp-'+e.ch+'"><i></i>'+esc(CH[e.ch])+'</span></td><td><button class="rp-btn" style="padding:0;min-height:0;background:none;font-weight:700;text-align:left" data-rpi="'+esc(e.id)+'">'+esc(e.ti)+'</button><div class="sub2">'+esc(e.de)+'</div></td><td class="sub2">'+esc(e.src)+'</td><td><span class="rp-st'+(e.st==='z'?' offen':'')+'">'+(e.st==='z'?'Zu klären':'Geplant')+'</span></td></tr>'}).join('')
      + '</tbody></table></div>';
  }
  function next(){
    var today=iso(new Date());
    var r=D.entries.filter(function(e){return e.d&&e.d>=today&&(e.ch==='reel'||e.ch==='karussell'||e.ch==='aktion')}).sort(function(a,b){return a.d.localeCompare(b.d)||ORD[a.ch]-ORD[b.ch]}).slice(0,3);
    if(!r.length)return '';
    return '<p class="sub2" style="margin:0 0 8px;font-weight:600;color:#16150F">Als Nächstes</p><div class="rp-next">'+r.map(function(e){return '<button class="rp-nx" style="border:0;text-align:left;cursor:pointer;font:inherit" data-rpi="'+esc(e.id)+'"><span class="rp-tag rp-'+e.ch+'"><i></i>'+esc(CH[e.ch])+'</span><small>'+fmt(e.d)+(e.t?' · '+esc(e.t)+' Uhr':'')+'</small><b>'+esc(e.ti)+'</b></button>'}).join('')+'</div>';
  }
  function status(){
    var n=D.entries.filter(moved).length;
    return '<div class="rp-status"><span>'+(V.msg?esc(V.msg):'Änderungen werden in diesem Browser gespeichert.')+'</span>'
      +(n?'<span><b>'+n+'</b> Karte'+(n>1?'n':'')+' verschoben</span>':'')
      +'<button class="rp-btn" data-rpa="new">+ Neue Karte</button>'
      +'<button class="rp-btn" data-rpa="undo"'+(V.undo.length?'':' disabled')+'>Rückgängig</button>'
      +'<button class="rp-btn" data-rpa="copy">Änderungen kopieren</button>'
      +(V.reset?'<button class="rp-btn del" data-rpa="resetok">Ja, auf Stand der Datei zurücksetzen</button><button class="rp-btn" data-rpa="resetno">Abbrechen</button>':'<button class="rp-btn" data-rpa="reset">Zurücksetzen</button>')
      +'</div>';
  }
  function render(){
    var root=$('rp'); if(!root||!D)return;
    var cnt=function(c){return D.entries.filter(function(e){return e.ch===c&&inM(e)}).length};
    root.innerHTML = next()
      + '<div class="rp-bar"><div class="rp-seg">'+MONTHS.map(function(m){return '<button data-rpm="'+m.k+'" class="'+(V.m===m.k?'on':'')+'">'+m.n+'</button>'}).join('')+'</div>'
      + '<div class="rp-seg"><button data-rpv="monat" class="'+(V.v==='monat'?'on':'')+'">Monat</button><button data-rpv="liste" class="'+(V.v==='liste'?'on':'')+'">Liste</button></div>'
      + '<div class="rp-chips" style="display:flex;gap:6px;flex-wrap:wrap">'+Object.keys(CH).map(function(c){return '<button class="rp-chip rp-'+c+(V.off[c]?' off':'')+'" data-rpc="'+c+'"><i></i>'+esc(CH[c])+' '+cnt(c)+'</button>'}).join('')+'</div></div>'
      + status()
      + (V.v==='liste'?table():narrow()?agenda():grid());
    var b=$('rpback');
    if(b){var bl=D.entries.filter(function(e){return !e.d});b.innerHTML=bl.length?bl.map(function(e){return chip(e,true)}).join(''):'<p class="sub2" style="margin:0">Alles eingeplant.</p>'}
    if(V.sel)show(V.sel);
  }
  function show(id,msg){
    var e=byId(id); if(!e)return; V.sel=id;
    var opts=Object.keys(CH).map(function(c){return '<option value="'+c+'"'+(c===e.ch?' selected':'')+'>'+CH[c]+'</option>'}).join('');
    $('rppc').innerHTML='<span class="rp-tag rp-'+e.ch+'"><i></i>'+esc(CH[e.ch])+'</span><h4>'+esc(e.ti)+'</h4>'
      +'<div class="sub2"><b style="color:#16150F">'+fmt(e.d)+(e.d?' '+e.d.slice(0,4):'')+(e.t?' · '+esc(e.t)+' Uhr':'')+'</b>'+(e.d?' · KW '+kw(e.d):'')+(moved(e)?' · ursprünglich '+esc(fmt(e.o)):'')+'</div>'
      +'<label for="rpfti">Titel</label><input id="rpfti" value="'+esc(e.ti)+'">'
      +'<label for="rpfde">Beschreibung</label><textarea id="rpfde" rows="3">'+esc(e.de)+'</textarea>'
      +'<div class="rp-row"><div><label for="rpfch">Kanal</label><select id="rpfch">'+opts+'</select></div><div><label for="rpft">Uhrzeit</label><input id="rpft" type="time" value="'+esc(e.t)+'"></div></div>'
      +'<label for="rpfsrc">Baustein</label><input id="rpfsrc" value="'+esc(e.src)+'">'
      +'<div class="rp-row" style="margin-top:12px"><button class="rp-btn pri" data-rpa="sv">Text speichern</button><span class="sub2" aria-live="polite">'+esc(msg||'')+'</span></div>'
      +'<label for="rpnd">Verschieben auf</label><div class="rp-row"><input type="date" id="rpnd" min="2026-11-30" max="2027-01-31" value="'+(e.d||'')+'"><button class="rp-btn" data-rpa="go">Übernehmen</button><button class="rp-btn" data-rpa="unplan">Ohne Termin</button></div>'
      +(e.d?'<div class="rp-row"><button class="rp-btn" data-rpa="dm">← Vortag</button><button class="rp-btn" data-rpa="dp">Folgetag →</button></div>':'')
      +'<label>Status</label><div class="rp-row"><button class="rp-btn" data-rpa="stt">'+(e.st==='z'?'Als geplant markieren':'Als „zu klären“ markieren')+'</button>'+(moved(e)?'<button class="rp-btn" data-rpa="orig">Zurück auf ursprünglich</button>':'')+'</div>'
      +'<div class="rp-row" style="margin-top:16px">'+(V.del===id?'<button class="rp-btn del" data-rpa="delok">Ja, Karte löschen</button><button class="rp-btn" data-rpa="delno">Abbrechen</button>':'<button class="rp-btn del" data-rpa="del">Karte löschen</button>')+'</div>';
    $('rppanel').classList.add('on');
  }
  function closePanel(){V.sel=null;V.del=null;var p=$('rppanel');if(p)p.classList.remove('on')}
  function change(id,patch,msg){
    var e=byId(id); if(!e)return;
    if(Object.keys(patch).every(function(k){return e[k]===patch[k]})){if(msg)show(id,'Keine Änderung.');return}
    V.undo.push(Object.assign({},e)); Object.assign(e,patch); V.msg=''; changed(); if(msg&&V.sel===id)show(id,msg);
  }
  function saveText(){
    var g=function(x){return $(x).value};
    change(V.sel,{ti:g('rpfti').trim()||'Ohne Titel',de:g('rpfde').trim(),ch:g('rpfch'),t:g('rpft'),src:g('rpfsrc').trim()},'Übernommen.');
  }
  function action(a){
    var e=V.sel&&byId(V.sel);
    if(a==='sv')saveText();
    else if(a==='go'){var v=$('rpnd').value;if(v)change(V.sel,{d:v})}
    else if(a==='unplan')change(V.sel,{d:null});
    else if(a==='dm'||a==='dp'){if(e&&e.d)change(V.sel,{d:add(e.d,a==='dp'?1:-1)})}
    else if(a==='stt'){if(e)change(V.sel,{st:e.st==='z'?'g':'z'})}
    else if(a==='orig'){if(e)change(V.sel,{d:e.o})}
    else if(a==='del'){V.del=V.sel;show(V.sel)}
    else if(a==='delno'){V.del=null;show(V.sel)}
    else if(a==='delok'){var i=D.entries.findIndex(function(x){return x.id===V.sel});if(i>-1){var r=Object.assign({},D.entries[i]);r._del=true;r._i=i;V.undo.push(r);D.entries.splice(i,1);closePanel();changed()}}
    else if(a==='new'){var id='n'+Date.now().toString(36);D.entries.push({id:id,d:null,t:'',ch:'reel',ti:'Neue Karte',de:'',src:'',st:'z',o:null});V.undo.push({id:id,_new:true});changed();show(id,'Text eintragen, speichern und die Karte aus „Noch ohne Termin“ auf einen Tag ziehen.');var f=$('rpfti');if(f){f.focus();f.select()}}
    else if(a==='undo'){var p=V.undo.pop();if(p){if(p._new){D.entries=D.entries.filter(function(x){return x.id!==p.id});if(V.sel===p.id)closePanel()}else if(p._del){var i2=p._i;delete p._del;delete p._i;D.entries.splice(Math.min(i2,D.entries.length),0,p)}else{var t=byId(p.id);if(t)Object.assign(t,p)}changed()}}
    else if(a==='copy'){var txt=JSON.stringify({entries:D.entries,weekNotes:D.weekNotes,holidays:D.holidays,updated:D.updated},null,1);
      try{navigator.clipboard.writeText(txt).then(function(){V.msg='Stand kopiert: an make happen schicken, dann wird er für alle übernommen.';render()},function(){V.msg='Kopieren wurde vom Browser blockiert.';render()})}catch(err){V.msg='Kopieren wurde vom Browser blockiert.';render()}}
    else if(a==='reset'){V.reset=true;render()}
    else if(a==='resetno'){V.reset=false;render()}
    else if(a==='resetok'){V.reset=false;try{localStorage.removeItem(KEY)}catch(e2){}closePanel();V.undo=[];load(true)}
  }

  /* Ziehen: Maus und Stift sofort, Touch nach langem Drücken */
  var drag=null, justDragged=false, lp=null;
  function place(x,y){
    drag.g.style.left=(x-20)+'px';drag.g.style.top=(y-14)+'px';
    var t=document.elementFromPoint(x,y), z=t&&t.closest('[data-rpdrop]');
    if(z!==drag.over){if(drag.over)drag.over.classList.remove('over');if(z)z.classList.add('over');drag.over=z}
  }
  function startGhost(c){drag.g=c.cloneNode(true);drag.g.classList.add('rp-ghost');document.body.appendChild(drag.g);c.classList.add('lift')}
  function endDrag(ok){
    if(!drag)return; var d=drag; drag=null;
    if(!d.on)return; justDragged=true; setTimeout(function(){justDragged=false},0);
    if(d.iv)clearInterval(d.iv); d.g.remove(); d.el.classList.remove('lift'); if(d.over)d.over.classList.remove('over');
    if(ok&&d.over){var v=d.over.getAttribute('data-rpdrop');change(d.id,{d:v==='none'?null:v})}
  }
  var SEL='.rp-grid .rp-ev,.rp-back .rp-ev,.rp-ag .rp-ev';
  document.addEventListener('pointerdown',function(ev){
    if(ev.pointerType==='touch')return;
    var c=ev.target.closest&&ev.target.closest(SEL); if(!c||ev.button>0)return;
    drag={id:c.getAttribute('data-rpi'),el:c,x:ev.clientX,y:ev.clientY,on:false,over:null};
  });
  document.addEventListener('pointermove',function(ev){
    if(!drag||ev.pointerType==='touch')return;
    if(!drag.on){if(Math.hypot(ev.clientX-drag.x,ev.clientY-drag.y)<6)return;drag.on=true;startGhost(drag.el)}
    ev.preventDefault(); place(ev.clientX,ev.clientY);
    if(ev.clientY<60)window.scrollBy(0,-12);else if(ev.clientY>window.innerHeight-60)window.scrollBy(0,12);
  },{passive:false});
  document.addEventListener('pointerup',function(ev){if(ev.pointerType!=='touch')endDrag(true)});
  document.addEventListener('pointercancel',function(ev){if(ev.pointerType!=='touch')endDrag(false)});
  document.addEventListener('touchstart',function(ev){
    var c=ev.target.closest&&ev.target.closest(SEL); if(!c||ev.touches.length>1)return;
    var t=ev.touches[0];
    lp={x:t.clientX,y:t.clientY,tm:setTimeout(function(){if(!lp)return;
      drag={id:c.getAttribute('data-rpi'),el:c,on:true,over:null};startGhost(c);place(lp.x,lp.y);
      try{if(navigator.vibrate)navigator.vibrate(12)}catch(e){}
      drag.iv=setInterval(function(){if(!drag||!lp)return;var m=80;if(lp.y<m)window.scrollBy(0,-14);else if(lp.y>window.innerHeight-m)window.scrollBy(0,14);else return;place(lp.x,lp.y)},30);
    },380)};
  },{passive:true});
  document.addEventListener('touchmove',function(ev){
    if(!lp)return; var t=ev.touches[0];
    if(drag&&drag.on){ev.preventDefault();lp.x=t.clientX;lp.y=t.clientY;place(lp.x,lp.y);return}
    if(Math.hypot(t.clientX-lp.x,t.clientY-lp.y)>8){clearTimeout(lp.tm);lp=null}
  },{passive:false});
  document.addEventListener('touchend',function(ev){if(lp){clearTimeout(lp.tm);lp=null}if(drag&&drag.on){ev.preventDefault();endDrag(true)}},{passive:false});
  document.addEventListener('touchcancel',function(){if(lp){clearTimeout(lp.tm);lp=null}if(drag)endDrag(false)});
  document.addEventListener('contextmenu',function(ev){if(ev.target.closest&&ev.target.closest('.rp-ev'))ev.preventDefault()});

  document.addEventListener('click',function(ev){
    if(justDragged)return;
    var t=ev.target.closest&&ev.target.closest('[data-rpm],[data-rpv],[data-rpc],[data-rpi],[data-rpa],#rpx'); if(!t)return;
    if(t.id==='rpx'){closePanel();return}
    if(t.dataset.rpm){V.m=t.dataset.rpm;render()}
    else if(t.dataset.rpv){V.v=t.dataset.rpv;render()}
    else if(t.dataset.rpc){var c=t.dataset.rpc;V.off[c]=!V.off[c];render()}
    else if(t.dataset.rpi){V.del=null;show(t.dataset.rpi)}
    else if(t.dataset.rpa){action(t.dataset.rpa)}
  });
  document.addEventListener('keydown',function(ev){
    if(ev.key==='Enter'&&ev.target.matches&&ev.target.matches('#rpfti,#rpfsrc,#rpft')){ev.preventDefault();saveText();return}
    if(ev.key==='Escape'){if(drag)endDrag(false);else closePanel()}
  });
  var mq=window.matchMedia('(max-width:760px)'); if(mq.addEventListener)mq.addEventListener('change',render);

  /* Ein Kalender für „Übersicht“ und „Redaktionsplan“: der Block wandert in den sichtbaren Bereich */
  function dock(id){var w=$('rpwrap'),s=document.querySelector('.rp-slot[data-for="'+id+'"]');if(w&&s&&w.parentNode!==s)s.appendChild(w)}
  if(typeof window.sec==='function'){var _sec=window.sec;window.sec=function(id,el){_sec(id,el);dock(id)}}

  function side(){
    var l=$('rplg'); if(l)l.innerHTML=Object.keys(CH).map(function(c){return '<div class="rp-'+c+'"><i></i><span><b>'+esc(CH[c])+'</b> · '+esc(CHD[c])+'</span></div>'}).join('');
  }
  function load(forceFile){
    fetch('data/redaktionsplan.json',{cache:'no-store'}).then(function(r){return r.json()}).then(function(j){
      D=j; BASE=j.updated||null; D.entries.forEach(function(e){if(e.o===undefined)e.o=e.d});
      if(!forceFile){try{var s=JSON.parse(localStorage.getItem(KEY)||'null');
        if(s&&s.entries){if(s.base===BASE){D.entries=s.entries;D.updated=s.updated}else{V.msg='Der Plan wurde zentral aktualisiert, lokale Änderungen wurden ersetzt.';localStorage.removeItem(KEY)}}}catch(e){}}
      if(new Date().toISOString().slice(0,7)==='2027-01')V.m='2027-01';
      side(); render();
    }).catch(function(){var r=$('rp');if(r)r.innerHTML='<p class="sub2">Redaktionsplan konnte nicht geladen werden (data/redaktionsplan.json).</p>'});
  }
  function init(){
    var st=document.createElement('style'); st.textContent=CSS; document.head.appendChild(st);
    var p=document.createElement('aside');p.id='rppanel';p.className='rp-panel';p.setAttribute('aria-live','polite');
    p.innerHTML='<button class="x" id="rpx" aria-label="Schließen">×</button><div id="rppc"></div>';document.body.appendChild(p);
    var on=document.querySelector('.tab2.on'); dock(on?on.getAttribute('data-s'):'s0');
    load(false);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
