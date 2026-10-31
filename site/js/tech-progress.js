(function(){
  var root=document.getElementById('tech-progress'); if(!root) return;
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function render(d){
    var ms=d.milestones||[], n=ms.length, done=ms.filter(function(m){return m.status==='done'}).length;
    var act=ms.findIndex(function(m){return m.status==='active'}), ap=Math.max(0,Math.min(100,d.active_progress||0));
    var pct=n?Math.round(((done+(act>=0?ap/100:0))/n)*100):0;
    var stepNo=act>=0?act+1:done;
    root.querySelector('[data-tp=now]').textContent=d.now||'';
    root.querySelector('[data-tp=detail]').textContent=d.now_detail||'';
    root.querySelector('[data-tp=phase]').textContent=d.phase||'';
    root.querySelector('[data-tp=pct]').textContent=pct+'%';
    root.querySelector('[data-tp=step]').textContent='Step '+stepNo+' of '+n+' · '+done+' shipped';
    root.querySelector('[data-tp=upd]').textContent=d.updated?('Updated '+new Date(d.updated).toLocaleString()):'';
    root.querySelector('.tp-fill').style.width=pct+'%';
    root.querySelector('.tp-steps').innerHTML=ms.map(function(m){
      var lbl={done:'Done',active:'Building now',next:'Next',blocked:'Blocked'}[m.status]||m.status;
      return '<li class="tp-step tp-'+esc(m.status)+'"><span class="tp-dot"></span><div><b>'+esc(m.title)+'</b><em>'+esc(lbl)+(m.status==='active'?' · '+ap+'%':'')+'</em><p>'+esc(m.detail)+'</p></div></li>';
    }).join('');
  }
  function load(){fetch('tech-progress.json?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.json()}).then(render).catch(function(){})}
  load(); setInterval(load,60000);
})();
