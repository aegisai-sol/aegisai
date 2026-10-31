(function(){const el=document.getElementById('how-lottie');if(!el)return;
const steps=[...document.querySelectorAll('.how-step')],ex=[...document.querySelectorAll('.how-ex')];
const B=[0,55,115,190,260];function set(s){steps.forEach((e,i)=>e.classList.toggle('on',i===s));ex.forEach((e,i)=>e.classList.toggle('on',i<=s));}
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function go(){if(!window.lottie){set(4);return;}
const a=lottie.loadAnimation({container:el,renderer:'svg',loop:!reduce,autoplay:!reduce,path:'assets/how-pov.json'});
const fin=()=>{if(reduce){a.goToAndStop(359,true);set(4);return;}};a.addEventListener('DOMLoaded',fin);a.addEventListener('data_ready',fin);
a.addEventListener('enterFrame',()=>{const f=a.currentFrame;let s=0;B.forEach((b,i)=>{if(f>=b)s=i});set(s);});
steps.forEach((e,i)=>e.style.cursor='pointer',0);steps.forEach((e,i)=>e.onclick=()=>{a.goToAndPlay(B[i],true)});}
document.readyState==='complete'?go():addEventListener('load',go);})();
