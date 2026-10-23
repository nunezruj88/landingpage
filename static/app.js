'use strict';
const $=id=>document.getElementById(id);
const ICONS={basketball:'Baloncesto',globe:'Web',code:'Código',home:'Casa',chart:'Estadísticas',folder:'Carpeta',server:'Servidor',grid:'Panel'};
const COLORS={amber:'Ámbar',blue:'Azul',green:'Verde',rose:'Rosa',violet:'Violeta'};
let projects=[],category='Todos',favoritesOnly=false,editing=null,busy=false,undoId=null;
let favorites=new Set();
try{favorites=new Set(JSON.parse(localStorage.getItem('elsoci-favorites')||'[]'));}catch{}
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','icon');svg.setAttribute('aria-hidden','true');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-'+name);svg.append(use);return svg;}
function stored(key,value){try{localStorage.setItem(key,value);}catch{}}
function theme(value){document.documentElement.dataset.theme=value;const label=value==='dark'?'Activar tema claro':'Activar tema oscuro';$('theme-toggle').setAttribute('aria-label',label);$('theme-toggle').title=label;$('theme-toggle').replaceChildren(icon(value==='dark'?'sun':'moon'));}
let savedTheme=null;try{savedTheme=localStorage.getItem('elsoci-theme');}catch{}
theme(['light','dark'].includes(savedTheme)?savedTheme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
$('theme-toggle').addEventListener('click',()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';theme(value);stored('elsoci-theme',value);});
$('today').textContent=new Intl.DateTimeFormat('es-ES',{weekday:'long',day:'numeric',month:'long'}).format(new Date());
$('server-host').textContent=location.hostname||'Tu servidor';

function projectUrl(url){
 if(/^:\d{1,5}$/.test(url)){const dest=new URL('/',location.href);dest.port=url.slice(1);return dest.href;}
 const dest=new URL(url,location.origin);if(!['http:','https:'].includes(dest.protocol))throw Error('Dirección no válida.');return dest.href;
}
function address(url){try{const u=new URL(projectUrl(url));return u.host+(u.pathname==='/'?'':u.pathname);}catch{return url;}}
async function api(url,options={}){
 const response=await fetch(url,{...options,headers:{'Content-Type':'application/json','X-Landing-Request':'1',...options.headers}});
 let data;try{data=await response.json();}catch{throw Error('No se puede leer la respuesta del servidor.');}
 if(!response.ok){const error=Error(data.error||'No se ha podido completar la operación.');error.status=response.status;throw error;}
 return data;
}
function toast(message,restoreId=null){undoId=restoreId;$('toast-text').textContent=message;$('undo-delete').hidden=!restoreId;$('toast').hidden=false;}
$('close-toast').addEventListener('click',()=>{$('toast').hidden=true;});
$('undo-delete').addEventListener('click',async()=>{
 if(!undoId)return;const id=undoId;$('undo-delete').disabled=true;
 try{const result=await api('/api/projects/'+id+'/restore',{method:'POST',body:'{}'});projects.push(result.project);render();toast('Acceso restaurado.');}catch(e){toast(e.message);}finally{$('undo-delete').disabled=false;}
});

function toggleFavorite(project){
 if(favorites.has(project.id))favorites.delete(project.id);else favorites.add(project.id);
 stored('elsoci-favorites',JSON.stringify([...favorites]));render();
 const target=$('projects-grid').querySelector(`[data-favorite="${project.id}"]`);if(target)target.focus();
}
function toolButton(label,symbol,action){const button=node('button',undefined,'icon-button');button.type='button';button.title=label;button.setAttribute('aria-label',label);button.append(icon(symbol));button.addEventListener('click',action);return button;}
function projectCard(project){
 const card=node('article',undefined,'project-card accent-'+project.color),top=node('div',undefined,'card-top');card.dataset.project=project.id;
 const emblem=node('span',undefined,'project-icon');emblem.append(icon(project.icon));
 const tools=node('div',undefined,'card-tools'),favorite=toolButton('Favorito: '+project.name,'star',()=>toggleFavorite(project));
 favorite.classList.add('favorite');favorite.classList.toggle('active',favorites.has(project.id));favorite.setAttribute('aria-pressed',String(favorites.has(project.id)));favorite.dataset.favorite=project.id;
 tools.append(favorite,toolButton('Editar '+project.name,'edit',()=>openEditor(project)));
 top.append(emblem,node('span',project.category,'category-tag'),tools);
 const heading=node('h3'),link=node('a',project.name);link.href=projectUrl(project.url);link.target='_blank';link.rel='noopener noreferrer';heading.append(link);
 const description=node('p',project.description||'Un acceso directo a tu proyecto.','project-description');
 const open=node('a',undefined,'card-bottom');open.href=link.href;open.target='_blank';open.rel='noopener noreferrer';open.setAttribute('aria-label','Abrir '+project.name+' en otra pestaña');
 const text=node('span','Abrir proyecto'),arrow=node('span',undefined,'open-arrow');arrow.append(icon('arrow'));open.append(text,arrow);
 const url=node('div',undefined,'project-address');url.append(icon('globe'),node('span',address(project.url)));url.title=projectUrl(project.url);
 card.append(top,heading,description,open,url);return card;
}
function addCard(){const card=node('button',undefined,'add-card');card.type='button';const circle=node('span',undefined,'add-card-icon');circle.append(icon('plus'));const link=node('span','Añadir proyecto','add-card-link');link.append(icon('arrow'));card.append(circle,node('strong','El siguiente empieza aquí.'),node('p','Dale un lugar a esa web, herramienta o idea que tienes entre manos.'),link);card.addEventListener('click',()=>openEditor());return card;}
function normalize(text){return text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es');}
function render(){
 const total=projects.length,starred=projects.filter(p=>favorites.has(p.id)).length;
 $('nav-total').textContent=total;$('nav-favorites').textContent=starred;$('hero-total').textContent=String(total).padStart(2,'0');
 $('all-view').classList.toggle('active',!favoritesOnly);$('favorites-view').classList.toggle('active',favoritesOnly);$('all-view').setAttribute('aria-pressed',String(!favoritesOnly));$('favorites-view').setAttribute('aria-pressed',String(favoritesOnly));
 $('projects-title').firstChild.textContent=favoritesOnly?'Mis favoritos':'Mis proyectos';$('title-count').textContent=favoritesOnly?starred:total;
 const categories=[...new Set(projects.map(p=>p.category))].sort((a,b)=>a.localeCompare(b,'es'));
 if(category!=='Todos'&&!categories.includes(category))category='Todos';
 $('category-filters').replaceChildren(...['Todos',...categories].map(value=>{const button=node('button',value,'filter');button.type='button';button.classList.toggle('active',value===category);button.setAttribute('aria-pressed',String(value===category));button.addEventListener('click',()=>{category=value;render();[...$('category-filters').children].find(b=>b.textContent===value)?.focus();});return button;}));
 $('categories').replaceChildren(...categories.map(value=>{const option=node('option');option.value=value;return option;}));
 const query=normalize($('search').value.trim());
 const selected=projects.filter(p=>(!favoritesOnly||favorites.has(p.id))&&(category==='Todos'||p.category===category)&&normalize(p.name+' '+p.description+' '+p.category+' '+address(p.url)).includes(query)).sort((a,b)=>a.name.localeCompare(b.name,'es',{sensitivity:'base'}));
 $('projects-grid').replaceChildren(...selected.map(projectCard));
 if(!query&&category==='Todos'&&!favoritesOnly)$('projects-grid').append(addCard());
 $('empty-state').hidden=selected.length>0||(!total&&!favoritesOnly&&!query);
 if(!selected.length){$('empty-title').textContent=favoritesOnly&&!query?'Tus favoritos empiezan con una estrella.':'No hay proyectos con esos filtros.';$('empty-text').textContent=favoritesOnly&&!query?'Marca la estrella de un proyecto para tenerlo siempre a mano.':'Prueba otro nombre o vuelve a ver todos los proyectos.';}
 $('result-count').textContent=`${selected.length} ${selected.length===1?'proyecto':'proyectos'}${selected.length!==total?' de '+total:''} en esta vista`;
}
async function load(){
 $('loading').hidden=false;$('load-error').hidden=true;$('empty-state').hidden=true;
 try{const result=await api('/api/projects');projects=result.projects;render();}
 catch(e){$('projects-grid').replaceChildren();$('load-error').hidden=false;}
 finally{$('loading').hidden=true;}
}
$('retry').addEventListener('click',load);
$('search').addEventListener('input',render);
$('all-view').addEventListener('click',()=>{favoritesOnly=false;category='Todos';render();});
$('favorites-view').addEventListener('click',()=>{favoritesOnly=true;category='Todos';render();});
$('clear-filters').addEventListener('click',()=>{favoritesOnly=false;category='Todos';$('search').value='';render();});
document.addEventListener('keydown',event=>{if(event.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!document.querySelector('dialog[open]')){event.preventDefault();$('search').focus();}});

for(const [value,label] of Object.entries(ICONS)){
 const option=node('label',undefined,'radio-option');option.title=label;const input=node('input');input.type='radio';input.name='icon';input.value=value;input.setAttribute('aria-label',label);const display=node('span',undefined,'icon-choice');display.append(icon(value));option.append(input,display);$('icon-options').append(option);
}
for(const [value,label] of Object.entries(COLORS)){
 const option=node('label',undefined,'radio-option accent-'+value),input=node('input');input.type='radio';input.name='color';input.value=value;input.setAttribute('aria-label',label);const display=node('span',undefined,'color-choice');display.append(node('span',undefined,'color-dot'),node('span',label));option.append(input,display);$('color-options').append(option);
}
function openEditor(project=null){
 editing=project;const form=$('project-form');form.reset();$('dialog-title').textContent=project?'Editar proyecto':'Nuevo proyecto';$('save-project').textContent=project?'Guardar cambios':'Guardar proyecto';
 for(const name of ['name','url','description','category'])form.elements[name].value=project?.[name]||'';
 form.elements.icon.value=project?.icon||'globe';form.elements.color.value=project?.color||'green';
 $('form-error').hidden=true;$('delete-project').hidden=!project;$('project-dialog').showModal();$('project-name').focus();
}
function setBusy(value){busy=value;for(const control of $('project-form').elements)control.disabled=value;$('confirm-delete').disabled=value;}
$('add-project').addEventListener('click',()=>openEditor());
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>{if(!busy)$(button.dataset.close).close();}));
for(const id of ['project-dialog','delete-dialog'])$(id).addEventListener('cancel',event=>{if(busy)event.preventDefault();});
$('about-button').addEventListener('click',()=>$('about-dialog').showModal());
$('project-form').addEventListener('submit',async event=>{
 event.preventDefault();if(busy)return;
 const form=event.currentTarget,payload=Object.fromEntries(new FormData(form));if(editing)payload.version=editing.version;
 setBusy(true);$('form-error').hidden=true;
 try{
  const result=await api('/api/projects'+(editing?'/'+editing.id:''),{method:editing?'PATCH':'POST',body:JSON.stringify(payload)});
  const index=projects.findIndex(p=>p.id===result.project.id);if(index<0)projects.push(result.project);else projects[index]=result.project;
  favoritesOnly=false;category='Todos';$('search').value='';render();$('project-dialog').close();toast(editing?'Proyecto actualizado.':'Proyecto añadido. Ya tiene su lugar.');
 }catch(e){$('form-error').textContent=e.message;$('form-error').hidden=false;if(e.status===409)await load();}
 finally{setBusy(false);}
});
$('delete-project').addEventListener('click',()=>{if(!editing)return;$('delete-description').textContent=`Se quitará el acceso a «${editing.name}» de este panel.`;$('delete-error').hidden=true;$('delete-dialog').showModal();});
$('confirm-delete').addEventListener('click',async()=>{
 if(!editing||busy)return;setBusy(true);$('delete-error').hidden=true;
 try{const id=editing.id;await api('/api/projects/'+id,{method:'DELETE',body:JSON.stringify({version:editing.version})});projects=projects.filter(p=>p.id!==id);render();$('delete-dialog').close();$('project-dialog').close();toast('Acceso quitado del panel.',id);}
 catch(e){$('delete-error').textContent=e.message;$('delete-error').hidden=false;if(e.status===409)await load();}
 finally{setBusy(false);}
});
load();
