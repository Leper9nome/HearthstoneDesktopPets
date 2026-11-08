export async function createBubbleMenu({assets={},state,onAction}){
    const root=document.createElement('div');root.id='pet-menu';root.hidden=true;root.setAttribute('role','menu');root.setAttribute('aria-label','宠物菜单');document.body.append(root);
    if(assets.font){try{const face=await new FontFace('PetCardName',`url(${JSON.stringify(assets.font)})`).load();document.fonts.add(face);}catch(error){console.warn('本地卡名字体未加载，使用系统隶书',error);}}
    await Promise.all(['top','middle','bottom','top-hover','middle-hover','bottom-hover'].map(async key=>{if(assets[key]){const im=new Image();im.src=assets[key];try{await im.decode();}catch{delete assets[key];}}}));
    const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
    let items=null,controls=false,closing=false,transition=0;
    function clear(){root.getAnimations({subtree:true}).forEach(animation=>animation.cancel());root.replaceChildren();}
    function hide(){
        if(root.hidden||closing)return;
        closing=true;root.inert=true;const generation=++transition;
        const animations=[...root.querySelectorAll('.bubble-face')].map(face=>{
            const style=getComputedStyle(face),start={transform:style.transform,opacity:style.opacity};
            face.getAnimations().forEach(animation=>animation.cancel());
            return face.animate([start,{transform:'scale(.12)',opacity:0}],{duration:reducedMotion.matches?0:160,easing:'ease-in',fill:'forwards'});
        });
        Promise.all(animations.map(animation=>animation.finished.catch(()=>{}))).then(()=>{
            if(generation!==transition||!closing)return;
            root.hidden=true;clear();closing=false;root.inert=false;
        });
    }
    function render(){
        clear();const rows=controls?items.controls:items.emotions;
        const cx=innerWidth/2,cy=innerHeight/2,radius=140,w=112,h=76;
        const top=Math.max(8,Math.min(innerHeight-4*h-8,cy-1.8*h));
        function button(item,side,row){
            const b=document.createElement('button');b.type='button';b.className='pet-bubble '+side+' row-'+row;b.dataset.action=item.id;b.setAttribute('role','menuitem');b.disabled=item.enabled===false;
            const face=document.createElement('div');face.className='bubble-face';b.append(face);
            const bend=[.82,1,.88,.62][row],x=cx+(side==='left'?-1:1)*radius*bend-w/2;
            b.style.left=Math.max(6,Math.min(innerWidth-w-6,x))+'px';b.style.top=(top+row*h)+'px';
            const shape=row===0?'top':row===1?'middle':'bottom';
            if(assets[shape]){
                for(const [key,cls] of [[shape,'normal'],[shape+'-hover','highlight']]){const im=document.createElement('img');im.src=assets[key]||assets[shape];im.alt='';im.className=cls;im.draggable=false;face.append(im);}
            }else b.classList.add('fallback');
            const label=document.createElement('span');label.textContent=item.id==='flight'&&state()==='Sequence_Flying_Idle'?'降落':item.label;face.append(label);b.setAttribute('aria-label',label.textContent);
            b.addEventListener('pointerdown',event=>event.stopPropagation());
            b.addEventListener('click',event=>{event.stopPropagation();if(closing)return;if(item.id==='options'){controls=!controls;render();root.querySelector('[data-action="options"]').focus();}else{hide();onAction(item.id);}});
            root.append(b);
            face.animate([{transform:'scale(.12)',opacity:0},{transform:'scale(1.13)',opacity:1,offset:.55},{transform:'scale(.96)',offset:.78},{transform:'scale(1.025)',offset:.9},{transform:'scale(1)',opacity:1}],{duration:reducedMotion.matches?0:360,easing:'ease-out'});
        }
        rows.forEach((item,i)=>button(item,i<3?'left':'right',i%3));
        button({id:'options',label:controls?'返回':'选项'},'right',3);
    }
    function show(value){if(!root.hidden&&!closing){hide();return;}transition++;closing=false;root.inert=false;items=value;controls=false;root.hidden=false;render();root.querySelector('button:not(:disabled)')?.focus();}
    function contains(x,y){return !root.hidden&&!closing&&[...root.querySelectorAll('button')].some(b=>{const r=b.getBoundingClientRect();return x>=r.left&&x<r.right&&y>=r.top&&y<r.bottom;});}
    window.addEventListener('blur',hide);window.addEventListener('resize',hide);
    document.addEventListener('pointerdown',event=>{if(!root.hidden&&!root.contains(event.target))hide();},true);
    document.addEventListener('keydown',event=>{if(!root.hidden&&event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();hide();}},true);
    return {show,hide,contains};
}
