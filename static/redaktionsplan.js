/* Redaktionsplan / Social-Media-Kalender für @edeka.berlin
   Daten: data/redaktionsplan.json (Einträge, Wochennotizen, Backlog).
   Rendert in #rp, im Look des Dashboards (Pills, Inter Tight, Blau #2A60FF). */
(function(){
  var CSS = ''
  + '.rp-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 16px}'
  + '.rp-seg{display:flex;gap:4px;background:#fff;border-radius:999px;padding:4px}'
  + '.rp-seg button,.rp-chip{font:600 13.5px "Inter Tight",Inter,sans-serif;border:0;background:none;color:#3E3B33;padding:9px 16px;border-radius:999px;cursor:pointer;min-height:38px}'
  + '.rp-seg button.on{background:#2A60FF;color:#fff}'
  + '.rp-chip{background:#fff;display:inline-flex;align-items:center;gap:7px}'
  + '.rp-chip.off{opacity:.4}'
  + '.rp-chip i,.rp-tag i,.rp-lg i{width:10px;height:10px;border-radius:3px;display:inline-block;background:var(--c)}'
  + '.rp-reel{--c:#2A60FF;--t:#fff}.rp-karussell{--c:#FFD43B;--t:#16150F}.rp-story{--c:#C9D6FF;--t:#16150F}'
  + '.rp-tiktok{--c:#16150F;--t:#fff}.rp-whatsapp{--c:#2E7D5B;--t:#fff}.rp-aktion{--c:#E0482B;--t:#fff}'
  + '.rp-grid{display:grid;grid-template-columns:84px repeat(7,minmax(0,1fr));gap:4px}'
  + '.rp-hd{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:#6E6A60;font-weight:600;padding:4px 6px}'
  + '.rp-kw{font-size:12.5px;color:#6E6A60;padding:8px 6px}.rp-kw b{display:block;color:#16150F;font-size:15px}'
  + '.rp-day{background:#fff;border-radius:10px;min-height:140px;padding:7px;display:flex;flex-direction:column;gap:4px;min-width:0}'
  + '.rp-day.out{background:rgba(255,255,255,.5)}.rp-day.out .rp-n{opacity:.45}'
  + '.rp-n{font-size:13px;font-weight:700;display:flex;justify-content:space-between;gap:4px}.rp-n small{color:#2A60FF;font-weight:600}'
  + '.rp-ev{display:block;width:100%;text-align:left;border:0;border-radius:7px;padding:4px 6px;font:600 12px/1.25 "Inter Tight",Inter,sans-serif;background:var(--c);color:var(--t);cursor:pointer}'
  + '.rp-ev span{opacity:.75;margin-right:4px}'
  + '.rp-ev.offen{background:repeating-linear-gradient(135deg,var(--c) 0 6px,color-mix(in srgb,var(--c) 68%,#fff) 6px 12px)}'
  + '.rp-ev:focus-visible,.rp-chip:focus-visible,.rp-seg button:focus-visible{outline:2px solid #2A60FF;outline-offset:2px}'
  + '.rp-det{background:#fff;border-radius:12px;padding:16px 18px;margin-top:12px;display:none}.rp-det.on{display:block}'
  + '.rp-det b.t{display:block;font-size:20px;letter-spacing:-.4px;margin:6px 0 4px}'
  + '.rp-tag{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;font-size:13px;font-weight:600}'
  + '.rp-st{font-size:12.5px;font-weight:600;padding:3px 10px;border-radius:999px;background:#E9EEFF;color:#2A60FF;white-space:nowrap}.rp-st.offen{background:#FDE4DE;color:#A3301B}'
  + '.rp-list td{vertical-align:top}.rp-list td:first-child{white-space:nowrap}'
  + '.rp-next{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0 0 16px}'
  + '.rp-nx{background:#fff;border-radius:12px;padding:12px 14px}.rp-nx small{color:#6E6A60;font-size:12.5px;display:block}.rp-nx b{display:block;font-size:15px;line-height:1.3;margin-top:4px}'
  + '.rp-back{list-style:none;margin:0;padding:0}.rp-back li{border-top:1px solid #E1DED6;padding:10px 0;font-size:14px;color:#3E3B33}.rp-back b{display:block;color:#16150F}'
  + '.rp-lg{display:grid;gap:9px;font-size:14px;color:#3E3B33}.rp-lg div{display:flex;gap:8px;align-items:center}'
  + '@media(max-width:860px){.rp-next{grid-template-columns:1fr}}'
  + '@media(max-width:760px){.rp-list thead{display:none}.rp-list tr{display:grid;padding:8px 0;border-bottom:1px solid #E1DED6}.rp-list td{border:0;padding:3px 0}}';

  var ORD = {aktion:0,reel:1,karussell:2,tiktok:3,story:4,whatsapp:5};
  var DN = ['Mo','Di','Mi','Do','Fr','Sa','So'];
  var MONTHS = [{k:'2026-12',n:'Dezember 2026',r:['2026-11-30','2026-12-31']},{k:'2027-01',n:'Januar 2027',r:['2027-01-01','2027-01-31']}];
  var D, S = {m:'2026-12', v:'monat', off:{}, sel:null};

  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function dt(d){return new Date(d+'T12:00:00Z')}
  function iso(x){return x.toISOString().slice(0,10)}
  function add(d,n){var x=dt(d);x.setUTCDate(x.getUTCDate()+n);return iso(x)}
  function wd(d){return (dt(d).getUTCDay()+6)%7}
  function kw(d){var x=dt(d);x.setUTCDate(x.getUTCDate()-wd(d)+3);var f=new Date(Date.UTC(x.getUTCFullYear(),0,4));return 1+Math.round(((x-f)/864e5-3+((f.getUTCDay()+6)%7))/7)}
  function fmt(d){return DN[wd(d)]+' '+d.slice(8)+'.'+d.slice(5,7)+'.'}
  function month(){for(var i=0;i<MONTHS.length;i++)if(MONTHS[i].k===S.m)return MONTHS[i]}
  function inM(e){var r=month().r;return e.date>=r[0]&&e.date<=r[1]}
  function vis(){return D.entries.filter(function(e){return !S.off[e.channel]}).sort(function(a,b){return a.date.localeCompare(b.date)||ORD[a.channel]-ORD[b.channel]})}
  function chip(e){var i=D.entries.indexOf(e);return '<button class="rp-ev rp-'+e.channel+(e.status==='offen'?' offen':'')+'" data-rpi="'+i+'" title="'+esc(e.title)+'">'+(e.time?'<span>'+esc(e.time)+'</span>':'')+esc(e.title)+'</button>'}

  function grid(){
    var first=S.m+'-01', d=add(first,-wd(first)), list=vis(), hol=D.holidays||[];
    var h='<div class="rp-grid"><div class="rp-hd">KW</div>'+DN.map(function(x){return '<div class="rp-hd">'+x+'</div>'}).join('');
    for(var w=0;w<6;w++){
      if(w>0&&d.slice(0,7)!==S.m)break;
      h+='<div class="rp-kw"><b>KW '+kw(d)+'</b>'+esc((D.weekNotes||{})[d]||'')+'</div>';
      for(var j=0;j<7;j++){
        var dd=d, evs=list.filter(function(e){return e.date===dd});
        h+='<div class="rp-day'+(d.slice(0,7)===S.m?'':' out')+'"><div class="rp-n">'+(+d.slice(8))+(hol.indexOf(d)>-1?'<small>Feiertag</small>':'')+'</div>'+evs.map(chip).join('')+'</div>';
        d=add(d,1);
      }
    }
    return h+'</div>';
  }
  function table(){
    var r=vis().filter(inM);
    return '<div style="overflow-x:auto"><table class="rp-list"><thead><tr><th>Datum</th><th>Kanal</th><th>Inhalt</th><th>Baustein</th><th>Status</th></tr></thead><tbody>'
      + r.map(function(e){return '<tr><td>'+fmt(e.date)+(e.time?' · '+esc(e.time):'')+'</td><td><span class="rp-tag rp-'+e.channel+'"><i></i>'+esc(D.channels[e.channel])+'</span></td><td><span class="strong">'+esc(e.title)+'</span><div class="sub2">'+esc(e.text)+'</div></td><td class="sub2">'+esc(e.source)+'</td><td><span class="rp-st '+e.status+'">'+(e.status==='offen'?'Zu klären':'Geplant')+'</span></td></tr>'}).join('')
      + '</tbody></table></div>';
  }
  function next(){
    var today=iso(new Date()), r=D.entries.filter(function(e){return e.date>=today&&(e.channel==='reel'||e.channel==='karussell'||e.channel==='aktion')}).sort(function(a,b){return a.date.localeCompare(b.date)||ORD[a.channel]-ORD[b.channel]}).slice(0,3);
    if(!r.length)return '';
    return '<div class="rp-next">'+r.map(function(e){return '<div class="rp-nx"><span class="rp-tag rp-'+e.channel+'"><i></i>'+esc(D.channels[e.channel])+'</span><small>'+fmt(e.date)+(e.time?' · '+esc(e.time)+' Uhr':'')+'</small><b>'+esc(e.title)+'</b></div>'}).join('')+'</div>';
  }
  function render(){
    var root=document.getElementById('rp'); if(!root||!D)return;
    var narrow=window.matchMedia('(max-width:760px)').matches;
    var cnt=function(c){return D.entries.filter(function(e){return e.channel===c&&inM(e)}).length};
    root.innerHTML = '<p class="sub2" style="margin:0 0 8px;font-weight:600;color:#16150F">Als Nächstes</p>'+next()
      + '<div class="rp-bar"><div class="rp-seg">'+MONTHS.map(function(m){return '<button data-rpm="'+m.k+'" class="'+(S.m===m.k?'on':'')+'">'+m.n+'</button>'}).join('')+'</div>'
      + '<div class="rp-seg"><button data-rpv="monat" class="'+(S.v==='monat'?'on':'')+'">Monat</button><button data-rpv="liste" class="'+(S.v==='liste'?'on':'')+'">Liste</button></div>'
      + Object.keys(D.channels).map(function(c){return '<button class="rp-chip rp-'+c+(S.off[c]?' off':'')+'" data-rpc="'+c+'"><i></i>'+esc(D.channels[c])+' '+cnt(c)+'</button>'}).join('')+'</div>'
      + ((S.v==='liste'||narrow)?table():grid())
      + '<div class="rp-det" id="rpdet"></div>';
    if(S.sel!=null)show(S.sel);
  }
  function show(i){
    var e=D.entries[i], el=document.getElementById('rpdet'); if(!e||!el)return; S.sel=i;
    el.innerHTML='<span class="rp-tag rp-'+e.channel+'"><i></i>'+esc(D.channels[e.channel])+'</span><b class="t">'+esc(e.title)+'</b>'
      +'<div class="sub2" style="margin-bottom:6px">'+fmt(e.date)+' '+e.date.slice(0,4)+(e.time?' · '+esc(e.time)+' Uhr':'')+' · KW '+kw(e.date)+' · '+esc(e.source)+'</div>'
      +'<div style="font-size:14.5px;color:#3E3B33;margin-bottom:8px">'+esc(e.text)+'</div><span class="rp-st '+e.status+'">'+(e.status==='offen'?'Zu klären':'Geplant')+'</span>';
    el.classList.add('on');
  }
  function side(){
    var b=document.getElementById('rpback'), l=document.getElementById('rplg');
    if(b)b.innerHTML=(D.backlog||[]).map(function(x){return '<li><b>'+esc(x.title)+'</b>'+esc(x.text)+'</li>'}).join('');
    if(l)l.innerHTML=Object.keys(D.channels).map(function(c){return '<div class="rp-'+c+'"><i></i><span><b>'+esc(D.channels[c])+'</b> · '+esc((D.channelHints||{})[c]||'')+'</span></div>'}).join('');
  }
  document.addEventListener('click',function(ev){
    var t=ev.target.closest&&ev.target.closest('[data-rpm],[data-rpv],[data-rpc],[data-rpi]'); if(!t)return;
    if(t.dataset.rpm){S.m=t.dataset.rpm;S.sel=null}
    else if(t.dataset.rpv){S.v=t.dataset.rpv}
    else if(t.dataset.rpc){var c=t.dataset.rpc;S.off[c]=!S.off[c]}
    else if(t.dataset.rpi){show(+t.dataset.rpi);return}
    render();
  });
  var mq=window.matchMedia('(max-width:760px)'); if(mq.addEventListener)mq.addEventListener('change',render);
  function init(){
    var st=document.createElement('style'); st.textContent=CSS; document.head.appendChild(st);
    fetch('data/redaktionsplan.json',{cache:'no-store'}).then(function(r){return r.json()}).then(function(j){
      D=j; var today=new Date().toISOString().slice(0,7); if(today==='2027-01')S.m='2027-01'; side(); render();
    }).catch(function(){var r=document.getElementById('rp'); if(r)r.innerHTML='<p class="sub2">Redaktionsplan konnte nicht geladen werden (data/redaktionsplan.json).</p>'});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
