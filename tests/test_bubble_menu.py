"""Asset-free menu navigation, layout, native dispatch and click-region tests."""
import sys,json,traceback
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bubble_menu import menu_items,perform_menu_action,random_variant
from unittest.mock import patch
from paths import APP
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

scripts=[];events=[]
desktop=SimpleNamespace(variant={'pet':'ysera','clips':['Emote_Greetings','Reaction_Happy_Big','Emote_Wow','Emote_Threaten','Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out','Sequence_Flying_Idle'],'sounds':'local'},view=SimpleNamespace(page=lambda:SimpleNamespace(runJavaScript=scripts.append)),view_locked=False,muted=True,open_panel=lambda:events.append('panel'),quit=lambda:events.append('quit'),toggle_sound=lambda:events.append('sound'),set_view_locked=lambda value:events.append(('locked',value)),random_pet=lambda:events.append('random'))
items=menu_items(desktop);assert len(items['emotions'])==len(items['controls'])==6
assert all(item['id']!='idle' for item in items['emotions'])
perform_menu_action(desktop,'flight');assert 'Sequence_Flying_Idle' in scripts[-1] and 'Idle_Neutral' in scripts[-1]
perform_menu_action(desktop,'lock');assert events[-1]==('locked',True)
perform_menu_action(desktop,'random');assert events[-1]=='random'
catalog=[{'id':'a','petId':1},{'id':'b','petId':1},{'id':'c','petId':2},{'id':'d','petId':3},{'id':'e','petId':3}]
with patch('bubble_menu.random.choice',side_effect=lambda choices:choices[-1]):assert random_variant(catalog,catalog[0])==catalog[-1]
assert random_variant(catalog[:2],catalog[0])==catalog[1]
assert random_variant(catalog[:1],catalog[0]) is None and random_variant([],None) is None
desktop.view_locked=True;before=len(scripts);perform_menu_action(desktop,'reset');perform_menu_action(desktop,'arbitrary-script');assert len(scripts)==before
desktop.variant['clips'].remove('Sequence_Flying_Idle');desktop.variant['clips'].append('Idle_Happy');assert menu_items(desktop)['emotions'][-1]['label']=='挂机'
desktop.variant['clips'].remove('Sequence_Pet_Out');assert not menu_items(desktop)['emotions'][1]['enabled']
app=QApplication(sys.argv);v=QWebEngineView();v.resize(630,630);v.show()
script='''
import {createBubbleMenu} from './bubble-menu.js';
import {createIdleActions} from './idle-actions.js';
try{
 const check=(ok,message)=>{if(!ok)throw Error(message);},calls=[];
 const automatic=[],choices=['Emote_Greetings','pet','Reaction_Happy_Big','Emote_Wow','Emote_Threaten'];
 const available=Object.fromEntries([...choices,'Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out'].map(name=>[name,true]));
 const tick=createIdleActions(available,name=>automatic.push(name)),originalRandom=Math.random;
 for(let i=0;i<5;i++){Math.random=()=>(i+.5)/5;tick(59,'Idle_Neutral');check(automatic.length===i,'Automatic action must wait a full minute');tick(1,'Idle_Neutral');check(automatic.at(-1)===choices[i],'All five reactions must be selectable');}
 Math.random=originalRandom;
 for(const hold of ['Sequence_Flying_Idle','Idle_Happy']){const count=automatic.length;tick(59,'Idle_Neutral');tick(120,hold);tick(1,'Idle_Neutral');check(automatic.length===count,'Flight and AFK must reset the timer');tick(59,'Idle_Neutral');check(automatic.length===count+1,'Normal idle resumes with a full-minute wait');}
 const count=automatic.length;tick(60,'Emote_Greetings');check(automatic.length===count,'Never interrupt a playing reaction');tick(.01,'Idle_Neutral');check(automatic.length===count+1,'Elapsed minute triggers after the current reaction');
 let state='Idle_Neutral';const items=ITEMS;
 const menu=await createBubbleMenu({bounds:()=>{throw Error('Menu must not inspect animated body bounds');},state:()=>state,onAction:id=>calls.push(id)});
 const buttons=()=>[...document.querySelectorAll('#pet-menu button')],hidden=()=>document.querySelector('#pet-menu').hidden;
 const root=document.querySelector('#pet-menu'),positions=()=>buttons().map(b=>[b.style.left,b.style.top]);
 const finished=async()=>{await Promise.all(root.getAnimations({subtree:true}).map(a=>a.finished.catch(()=>{})));await Promise.resolve();};
 menu.show(items);check(buttons().length===7,'Six emotions plus options');
 const fixed=JSON.stringify(positions());
 const face=buttons()[0].querySelector('.bubble-face'),pop=face.getAnimations()[0];pop.pause();
 let largest=0;for(let time=0;time<=360;time+=12){pop.currentTime=time;largest=Math.max(largest,new DOMMatrix(getComputedStyle(face).transform).a);check(JSON.stringify(positions())===fixed,'Pop animation must not move the button hit regions');}
 check(largest>1.08&&largest<1.16,'Bubble must slightly overshoot its resting size');
 check(Math.abs(new DOMMatrix(getComputedStyle(face).transform).a-1)<.001,'Bubble must settle back to its resting size');
 root.getAnimations({subtree:true}).forEach(a=>a.finish());
 check(buttons().filter(b=>b.classList.contains('left')).length===3,'Three emotions on the left');
 const [top,middle,bottom]=buttons().slice(0,3).map(b=>b.getBoundingClientRect());
 check(top.left>middle.left&&bottom.left>middle.left,'Bubbles must follow an arc');
 check(menu.contains(top.left+top.width/2,top.top+top.height/2)&&!menu.contains(5,5),'Only bubble regions catch clicks');
 check(buttons().every(b=>{const r=b.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;}),'All bubbles must fit inside the viewport');
 document.querySelector('[data-action=options]').click();check(buttons().length===7&&buttons().at(-1).textContent==='返回','Options opens six controls plus return');
 check(JSON.stringify(positions())===fixed,'Control page must keep exactly the same center and arc');
 check(buttons().some(b=>b.dataset.action==='random'&&b.textContent==='换一个'),'Random pet and skin control is available');
 document.querySelector('[data-action=options]').click();check(buttons().at(-1).textContent==='选项','Return restores emotions');
 const flight=document.querySelector('[data-action=flight]');flight.click();flight.click();
 check(!hidden()&&root.inert&&calls.filter(id=>id==='flight').length===1,'Action must dispatch once while close animation plays');
 check(!menu.contains(top.left+top.width/2,top.top+top.height/2),'Closing bubbles must stop intercepting clicks immediately');
 await finished();check(hidden(),'Close animation must remove its bubbles');
 state='Sequence_Flying_Idle';menu.show(items);check(document.querySelector('[data-action=flight]').textContent==='降落','Flight becomes landing');
 check(JSON.stringify(positions())===fixed,'Changing pose and reopening must not move menu');
 let escaped=false;window.addEventListener('keydown',()=>escaped=true);document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check(root.inert&&!escaped,'Escape closes menu without quitting');await finished();check(hidden(),'Escape close completes');
 menu.show(items);document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));await finished();check(hidden(),'Outside pointer closes menu');
 menu.show(items);window.dispatchEvent(new Event('blur'));check(!menu.contains(top.left+20,top.top+20),'Losing focus clears all click regions');await finished();check(hidden(),'Blur close completes');
 menu.show(items);menu.show(items);check(root.inert,'Second right click starts closing');
 menu.show(items);await finished();check(!hidden()&&!root.inert&&JSON.stringify(positions())===fixed,'Reopening during close must cancel stale cleanup and retain fixed placement');
 menu.hide();await finished();check(hidden(),'Final close completes');
 window.result={ok:true};
}catch(error){window.result={error:String(error)};}
'''.replace('ITEMS',json.dumps(items,ensure_ascii=False))
v.setHtml('<link rel="stylesheet" href="bubble-menu.css"><script type="module">'+script+'</script>',QUrl.fromLocalFile(str(APP/'web/index.html')))
def poll():
 def received(raw):
  if not raw:QTimer.singleShot(100,poll);return
  try:
   result=json.loads(raw);assert result.get('ok'),result
   print('PASS: fixed center, spring overshoot/settling, interrupted close/reopen, immediate click release, six actions/controls and flight toggle',flush=True);app.quit()
  except Exception:traceback.print_exc();app.exit(1)
 v.page().runJavaScript('JSON.stringify(window.result)',received)
QTimer.singleShot(200,poll);QTimer.singleShot(15000,lambda:app.exit(2));sys.exit(app.exec())
