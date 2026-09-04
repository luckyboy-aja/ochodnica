const pages=[...document.querySelectorAll('.page')];
const routeLinks=[...document.querySelectorAll('.route')];
const nav=document.getElementById('nav');
const menu=document.getElementById('menu');
const contrast=document.getElementById('contrast');
const govToggle=document.getElementById('govToggle');
const govInfo=document.getElementById('govInfo');

function showPage(name){
  const target=pages.find(p=>p.dataset.page===name)||pages[0];
  pages.forEach(p=>p.classList.toggle('active',p===target));
  routeLinks.forEach(a=>a.classList.toggle('active',a.dataset.route===name));
  nav.classList.remove('open');
  window.scrollTo({top:0,behavior:'smooth'});
}

routeLinks.forEach(a=>a.addEventListener('click',e=>{
  e.preventDefault();
  const route=a.dataset.route;
  history.replaceState(null,'',`#${route}`);
  showPage(route);
}));

menu?.addEventListener('click',()=>nav.classList.toggle('open'));
contrast?.addEventListener('click',()=>document.body.classList.toggle('high-contrast'));
govToggle?.addEventListener('click',()=>{
  const isHidden=govInfo.hasAttribute('hidden');
  if(isHidden) govInfo.removeAttribute('hidden'); else govInfo.setAttribute('hidden','');
});

const initial=location.hash.replace('#','')||'domov';
showPage(initial);
