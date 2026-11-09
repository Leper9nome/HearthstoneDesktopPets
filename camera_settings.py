"""Per-pet camera preferences and the panel's editing session."""
import json, math
from PySide6.QtCore import QSettings
from PySide6.QtWebEngineCore import QWebEngineScript

def validated(value):
    if not isinstance(value,dict):raise ValueError('Invalid camera')
    rotation=value.get('rotation');zoom=value.get('zoom')
    if not isinstance(rotation,list) or len(rotation)!=4:raise ValueError('Invalid rotation')
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in rotation):raise ValueError('Invalid rotation')
    norm=math.sqrt(sum(x*x for x in rotation))
    if not math.isfinite(norm) or norm<1e-8:raise ValueError('Invalid rotation')
    if type(zoom) not in (int,float) or not math.isfinite(zoom) or not .65<=zoom<=1.5:raise ValueError('Invalid zoom')
    return dict(rotation=[x/norm for x in rotation],zoom=zoom)

class CameraSettings:
    def __init__(self,manager):
        self.manager=manager;self.editing=False;self.key=None
        manager.desktop.camera_settings=self

    def js(self,script):self.manager.view.page().runJavaScript(script)

    def prepare(self):
        self.editing=False
        key='camera/'+str(self.manager.desktop.variant['petId'])
        try:preset=validated(json.loads(self.manager.settings.value(key,'null')))
        except (ValueError,TypeError):preset=None
        scripts=self.manager.view.page().scripts()
        for old in scripts.find('pet-camera-default'):scripts.remove(old)
        script=QWebEngineScript();script.setName('pet-camera-default')
        script.setInjectionPoint(QWebEngineScript.DocumentCreation);script.setWorldId(QWebEngineScript.MainWorld);script.setRunsOnSubFrames(False)
        script.setSourceCode('window.PET_CAMERA_DEFAULT='+json.dumps(preset)+';');scripts.insert(script)

    def begin(self):
        m=self.manager
        if not m.selected or m.loaded!=m.selected['id'] or m.view.windowOpacity()==0:return
        self.editing=True;self.key=m.selected['id']
        m.pets.setEnabled(False);m.skins.setEnabled(False)
        self.js('petBeginViewSettings()')
        m.panel.hide();m.view.activateWindow();m.view.setFocus()
        m.status.setText('右键拖动旋转 · Shift＋右键调整倾斜 · 滚轮缩放')

    def action(self,raw):
        m=self.manager
        if not self.editing or m.selected['id']!=self.key:return
        try:
            value=json.loads(raw)
            if value.get('variant')!=self.key:return
            if value.get('cancel'):
                self.js('petFinishViewSettings(false)');self.editing=False;m.refresh_panel();m.status.setText('已放弃本次视角更改。');return
            preset=validated(value)
        except (ValueError,TypeError,AttributeError):return
        key='camera/'+str(m.selected['petId']);previous=m.settings.value(key)
        m.settings.setValue(key,json.dumps(preset));m.settings.sync()
        if m.settings.status()!=QSettings.NoError:
            if previous is None:m.settings.remove(key)
            else:m.settings.setValue(key,previous)
            m.status.setText('保存失败，请检查设置文件是否可写。');m.open_panel();return
        self.js('petFinishViewSettings(true)');self.editing=False;m.refresh_panel()
        m.status.setText('默认视角已保存，同一宠物的所有皮肤共用。')
