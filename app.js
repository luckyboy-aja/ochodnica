const routeMap={
  domov:'',
  obec:'obec/',
  samosprava:'samosprava/',
  aktuality:'aktuality/',
  uradna:'uradna-tabula/',
  vybavit:'ako-vybavit/',
  kontakt:'kontakt/'
};
const base='/ochodnica/';
const nav=document.getElementById('nav');
const menu=document.getElementById('menu');
const contrast=document.getElementById('contrast');
const govToggle=document.getElementById('govToggle');
const govInfo=document.getElementById('govInfo');

document.querySelectorAll('[data-route]').forEach(link=>{
  const route=link.dataset.route;
  if(routeMap[route]!==undefined){
    link.setAttribute('href',base+routeMap[route]);
    link.addEventListener('click',e=>{
      e.preventDefault();
      window.location.href=base+routeMap[route];
    });
  }
});

menu?.addEventListener('click',()=>{
  const open=nav?.classList.toggle('open');
  menu.setAttribute('aria-expanded',String(Boolean(open)));
});
contrast?.addEventListener('click',()=>document.body.classList.toggle('high-contrast'));
govToggle?.addEventListener('click',()=>{
  const hidden=govInfo?.hasAttribute('hidden');
  if(!govInfo)return;
  if(hidden)govInfo.removeAttribute('hidden');else govInfo.setAttribute('hidden','');
});
