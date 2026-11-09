"""Camera preference validation and optional real-model editor integration."""
import sys,json,math,tempfile,argparse,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camera_settings import validated
assert validated({'rotation':[0,0,0,2],'zoom':1.2})=={'rotation':[0,0,0,1],'zoom':1.2}
for value in [None,{}, {'rotation':[0]*4,'zoom':1}, {'rotation':[0,0,0,float('nan')],'zoom':1}, {'rotation':[0,0,0,1],'zoom':2}]:
    try:validated(value)
    except ValueError:pass
    else:raise AssertionError(value)
parser=argparse.ArgumentParser();parser.add_argument('--data-dir');args=parser.parse_args()
if not args.data_dir:
    print('PASS: camera preference validation');sys.exit()
from desktop_pet import Desktop,Page
from manager import PetManager
from PySide6.QtCore import QSettings,QEventLoop,QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript
app=QApplication(sys.argv);view=QWebEngineView();view.resize(630,630);view.setPage(Page(view))
bridge=Desktop(view);channel=QWebChannel(view.page());channel.registerObject('desktop',bridge);view.page().setWebChannel(channel)
m=PetManager(view,bridge,Path(args.data_dir));temp=tempfile.TemporaryDirectory();m.settings=QSettings(str(Path(temp.name)/'preferences.ini'),QSettings.IniFormat)
def wait(predicate):
    end=time.monotonic()+20
    while not predicate():
        app.processEvents();time.sleep(.01)
        assert time.monotonic()<end,'Timed out'
def js(code):
    result=[];view.page().runJavaScript(code,lambda value:result.append(value));wait(lambda:len(result)>0);return result[0]
def obj(code):return json.loads(js('JSON.stringify('+code+')'))
def click(action):js("document.querySelector('[data-action="+action+"]').click()")
entries=[c for c in m.catalog if 'model' in c];first=entries[0];second=next(c for c in entries if c['petId']==first['petId'] and c['id']!=first['id'])
m.select(first['id']);wait(lambda:m.loaded==first['id'])
assert m.view_settings.height()==28 and not m.view_settings.icon().isNull()
assert m.panel.layout().minimumSize().height()<=m.panel.height()
m.panel.grab().save(str(Path(args.data_dir)/'camera-panel.png'))
bridge.set_view_locked(True);m.view_settings.click();assert m.camera.editing
assert obj('petCheck().view')['locked']==False
assert obj("[...document.querySelectorAll('#pet-menu button')].map(b=>[b.textContent,b.classList.contains('left')])")==[['复原',True],['保存',False]]
js("window.dispatchEvent(new Event('blur'));document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));petZoom(.2)")
assert js("document.querySelector('#pet-menu').hidden")==False
click('view-restore');assert abs(obj('petCheck().view')['zoom']-1)<1e-8;assert m.camera.editing
assert not m.settings.contains('camera/'+str(first['petId']))
# Rotation is stored as a normalized offset from each skin's built-in calibration.
js("petApplyDefault({rotation:[0,.2588190451,0,.9659258263],zoom:1.25})")
expected=obj('petViewPreset()');click('view-save');wait(lambda:not m.camera.editing)
assert obj('petCheck().view')['locked'];saved=json.loads(m.settings.value('camera/'+str(first['petId'])));assert abs(saved['zoom']-1.25)<1e-8
assert QSettings(m.settings.fileName(),QSettings.IniFormat).value('camera/'+str(first['petId']))
observer=QWebEngineScript();observer.setName('test-first-frame');observer.setInjectionPoint(QWebEngineScript.DocumentCreation);observer.setWorldId(QWebEngineScript.MainWorld)
observer.setSourceCode("window.cameraFrames=[];const raf=window.requestAnimationFrame;window.requestAnimationFrame=callback=>raf.call(window,time=>{if(window.petViewPreset&&cameraFrames.length<8)cameraFrames.push(petViewPreset());callback(time);});")
view.page().scripts().insert(observer)
m.select(second['id']);wait(lambda:m.loaded==second['id']);actual=obj('petViewPreset()')
frames=obj('cameraFrames');assert frames
for frame in frames:
    assert abs(frame['zoom']-expected['zoom'])<1e-8
    assert sum((a-b)**2 for a,b in zip(frame['rotation'],expected['rotation']))<1e-10
assert abs(actual['zoom']-expected['zoom'])<1e-8
assert sum((a-b)**2 for a,b in zip(actual['rotation'],expected['rotation']))<1e-10
m.camera.begin();js('petZoom(-.2)');click('view-restore');assert abs(obj('petCheck().view')['zoom']-1.25)<1e-8
js('petZoom(-.1)');js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))");wait(lambda:not m.camera.editing)
assert abs(obj('petCheck().view')['zoom']-1.25)<1e-8
m.camera.begin();old=m.selected['id'];m.select(first['id']);assert m.selected['id']==old
m.camera.action(json.dumps(dict(variant='stale',rotation=[0,0,0,1],zoom=.7)));assert m.camera.editing
m.camera.action(json.dumps(dict(variant=old,cancel=True)));wait(lambda:not m.camera.editing)
assert json.loads(m.settings.value('camera/'+str(first['petId'])))==saved
m.camera.begin();js('petZoom(.1)');view.grab().save(str(Path(args.data_dir)/'camera-bubbles.png'))
print('PASS: editor bubbles, blur/drag persistence, restore/cancel, lock restoration, per-pet cross-skin defaults, disk persistence and stale save guard',flush=True)
view.close();m.panel.close();temp.cleanup()
