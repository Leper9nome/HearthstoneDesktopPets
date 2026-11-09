"""Render out-of-range diffuse UVs with the production material loader."""
import sys,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from paths import APP
app=QApplication(sys.argv);view=QWebEngineView();view.resize(200,200);view.show()
source=(APP/'web/viewer.js').read_text(encoding='utf-8')
material_function=source[source.index('async function materialFor(source){'):source.index('\nconst materials=')]
script='''
import * as THREE from './three.module.js';
try{
 const check=(ok,message)=>{if(!ok)throw Error(message);};
 const texture=new THREE.DataTexture(new Uint8Array([255,0,0,255,0,255,0,255,0,0,255,255,255,255,255,255]),2,2);texture.needsUpdate=true;
 const loader={loadAsync:async()=>texture},assetBase=new URL('.',location.href),data={};
 MATERIAL_FUNCTION
 const material=await materialFor({shader:'Hero/Pet/Diffuse',textures:{_MainTex:'synthetic'},floats:{}});
 const renderer=new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true});renderer.setSize(64,64);document.body.append(renderer.domElement);
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,.01,10);camera.position.z=2;
 const geo=new THREE.PlaneGeometry(2,2),uv=geo.attributes.uv;
 for(let i=0;i<uv.count;i++)uv.setXY(i,-.25,-.25);
 scene.add(new THREE.Mesh(geo,material));renderer.render(scene,camera);
 const gl=renderer.getContext(),pixel=new Uint8Array(4);gl.readPixels(32,32,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
 check(pixel[0]>245&&pixel[1]>245&&pixel[2]>245,'Negative UV must repeat to the white texel, not stretch the red border');
 for(let i=0;i<uv.count;i++)uv.setXY(i,1.25,.25);uv.needsUpdate=true;renderer.render(scene,camera);gl.readPixels(32,32,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
 check(pixel[0]>245&&pixel[1]<8&&pixel[2]<8,'UV above one must repeat back to the red texel');
 window.result={ok:true};
}catch(error){window.result={error:String(error)};}
'''.replace('MATERIAL_FUNCTION',material_function)
view.setHtml('<script type="module">'+script+'</script>',QUrl.fromLocalFile(str(APP/'web/index.html')))
def poll():
 def received(raw):
  if not raw:QTimer.singleShot(100,poll);return
  try:
   result=json.loads(raw);assert result.get('ok'),result
   print('PASS: negative and above-one UVs repeat correctly in the production diffuse material',flush=True);app.quit()
  except Exception:traceback.print_exc();app.exit(1)
 view.page().runJavaScript('JSON.stringify(window.result)',received)
QTimer.singleShot(200,poll);QTimer.singleShot(15000,lambda:app.exit(2));sys.exit(app.exec())
