"""Windows hit routing with a real WebGL alpha buffer; no game assets required."""
import sys,ctypes,json,traceback
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QColor
from click_through import ClickThrough,user32,TRANSPARENT
from ctypes import wintypes as w
from paths import APP
app=QApplication(sys.argv);under=QWidget();under.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint);under.setGeometry(100,100,630,630);under.show()
v=QWebEngineView();v.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint);v.setAttribute(Qt.WA_TranslucentBackground);v.setGeometry(100,100,630,630);v.page().setBackgroundColor(QColor(0,0,0,0));v.show();v.raise_()
controller=ClickThrough(v);controller.timer.stop()
class Cursor:
 position=QPoint(0,0)
 @staticmethod
 def pos():return Cursor.position
cursor_patch=patch('click_through.QCursor',Cursor);cursor_patch.start()
buttons_patch=patch('click_through.mouse_down',return_value=False);buttons_patch.start()
user32.WindowFromPoint.argtypes=[w.POINT];user32.WindowFromPoint.restype=w.HWND
user32.GetAncestor.argtypes=[w.HWND,w.UINT];user32.GetAncestor.restype=w.HWND
user32.GetWindowRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
source=(APP/'web/viewer.js').read_text(encoding='utf-8');alpha=source[source.index('const hitPixel='):source.index('function hit(e)')]
shadow=source[source.index('const shadowCanvas='):source.index('const scene=')]
page=(APP/'web/index.html').read_text(encoding='utf-8')
style=page.split('<style>',1)[1].split('</style>',1)[0]
html='<style>'+style+'''</style><canvas></canvas><script>
const canvas=document.querySelector('canvas'),d=devicePixelRatio;canvas.width=innerWidth*d;canvas.height=innerHeight*d;canvas.style.width=innerWidth+'px';canvas.style.height=innerHeight+'px';
const gl=canvas.getContext('webgl2',{alpha:true,preserveDrawingBuffer:true});const renderer={getContext:()=>gl,domElement:canvas};
function clear(){gl.disable(gl.SCISSOR_TEST);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.enable(gl.SCISSOR_TEST);}
function body(){clear();gl.scissor(200*d,200*d,230*d,230*d);gl.clearColor(1,.3,.2,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.scissor(300*d,300*d,30*d,30*d);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);}
body();
'''+shadow+'''drawGroundShadow(436);
window.projectedFixture=()=>{clear();gl.scissor(300*d,180*d,150*d,40*d);gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT);drawGroundShadow();body();};
'''+alpha+'</script>'
cases=[(20,20,True),(240,250,False),(350,434,True),(435,250,True),(310,310,True),(240,250,False)]
projected=False
menu_checked=False
def fail():traceback.print_exc();app.exit(1)
def step(i=0):
 global projected,menu_checked,cases
 if i==len(cases):
  if not projected:
   projected=True;v.page().runJavaScript('projectedFixture()');QTimer.singleShot(200,step);return
  if not menu_checked:
   menu_checked=True
   v.page().runJavaScript("const bubble=document.createElement('button');bubble.style='position:absolute;left:50px;top:80px;width:110px;height:76px;background:white';document.body.append(bubble);window.petMenuHit=(x,y)=>{const r=bubble.getBoundingClientRect();return x>=r.left&&x<r.right&&y>=r.top&&y<r.bottom;};")
   cases=[(60,100,False),(20,20,True),(240,250,False)];QTimer.singleShot(200,step);return
  try:
   Cursor.position=v.mapToGlobal(QPoint(20,20))
   with patch('click_through.mouse_down',return_value=True):controller.poll();assert not user32.GetWindowLongW(int(v.winId()),-20)&TRANSPARENT
   controller.set_transparent(True);Cursor.position=v.mapToGlobal(QPoint(240,250))
   with patch('click_through.mouse_down',return_value=True):controller.poll();assert user32.GetWindowLongW(int(v.winId()),-20)&TRANSPARENT
   controller.loading();assert not controller.pending
   print('PASS: shadow/blank areas pass through; body and HTML bubbles receive Windows clicks; both drag origins retain capture',flush=True);app.quit()
  except Exception:fail()
  return
 x,y,transparent=cases[i];Cursor.position=v.mapToGlobal(QPoint(x,y));controller.poll()
 def verify():
  try:
   assert not controller.pending
   if (x,y)==(350,434):
    shot=v.grab().toImage();ratio=shot.devicePixelRatio()
    assert shot.pixelColor(round(x*ratio),round(y*ratio)).alpha()>0,'Shadow-only pixel must be visible'
    assert shot.pixelColor(round(435*ratio),round(250*ratio)).alpha()==0,'No halo around the body'
   assert bool(user32.GetWindowLongW(int(v.winId()),-20)&TRANSPARENT)==transparent,(i,x,y,transparent,menu_checked)
   rect=w.RECT();user32.GetWindowRect(int(v.winId()),ctypes.byref(rect));p=w.POINT(rect.left+int(x*(rect.right-rect.left)/v.width()),rect.top+int(y*(rect.bottom-rect.top)/v.height()))
   root=user32.GetAncestor(user32.WindowFromPoint(p),2)
   assert root==int(under.winId() if transparent else v.winId()),(i,root,transparent)
   step(i+1)
  except Exception:fail()
 QTimer.singleShot(100,verify)
v.setHtml(html);QTimer.singleShot(1500,step);QTimer.singleShot(15000,lambda:app.exit(2));code=app.exec();cursor_patch.stop();buttons_patch.stop();sys.exit(code)
