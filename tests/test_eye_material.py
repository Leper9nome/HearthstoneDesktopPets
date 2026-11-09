"""Check procedural pupils and packed reflection masks without game assets."""
import sys,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from paths import APP
app=QApplication(sys.argv);view=QWebEngineView();view.resize(200,200);view.show()
script='''
import * as THREE from './three.module.js';
import {eyeMaterial,screenMaterial} from './eye-material.js';
try{
 const check=(ok,message)=>{if(!ok)throw Error(message);};
 const renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,preserveDrawingBuffer:true});renderer.setSize(128,128);document.body.append(renderer.domElement);
 const errors=[];renderer.debug.onShaderError=()=>errors.push('Shader compilation failed');
 const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,.01,10);camera.position.z=2;
 const source={name:'Synthetic eye',shader:'Hero/Pet/Eye',textures:{},floats:{_IrisScale:.6,_PupilHorizontal:.25,_PupilVertical:.65},colors:{_ScleraColor:{r:1,g:1,b:1},_IrisMainColor:{r:0,g:0,b:1},_IrisSecondaryColor:{r:0,g:0,b:1},_IrisTertiaryColor:{r:1,g:1,b:1},_PupilColor:{r:0,g:0,b:0},_PupilSecondaryColor:{r:0,g:0,b:0},_PupilTertiaryColor:{r:0,g:0,b:1}}};
 const mat=await eyeMaterial(source,new THREE.TextureLoader(),new URL('.',location.href));
 const mesh=new THREE.Mesh(new THREE.PlaneGeometry(2,2),mat);scene.add(mesh);
 const gl=renderer.getContext(),pixel=new Uint8Array(4);
 const read=(x,y)=>{gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);return [...pixel];};
 const render=()=>renderer.render(scene,camera);
 render();check(read(64,64).slice(0,3).every(v=>v<8),'Pupil must be centered');
 check(read(8,8).slice(0,3).every(v=>v>245),'Sclera must remain outside the iris');
 check(read(64,80)[2]<8&&read(80,64)[2]>100,'Material dimensions must produce a vertical slit');
 mat.uniforms.Rotation.value=Math.PI/2;render();check(read(80,64)[2]<8&&read(64,80)[2]>100,'Eye rotation must rotate the pupil');
 mat.uniforms.Iris.value=0;render();check(read(64,64)[2]<8,'Disabling iris must preserve the pupil');
 const square=await eyeMaterial({...source,shader:'Hero/Pet/EyeSquare',floats:{_PupilHorizontal:.4,_PupilVertical:.08}},new THREE.TextureLoader(),new URL('.',location.href));mesh.material=square;render();
 check(read(82,64)[2]<8&&read(64,82)[2]>245,'Mechanical eyes must render rectangular pupils');
 const packed=new THREE.DataTexture(new Uint8Array([0,128,0,255]),1,1);packed.needsUpdate=true;square.uniforms.Matcap.value=packed;render();
 check(read(64,64).slice(0,3).every(v=>Math.abs(v-128)<2),'Matcap green channel must supply the highlight');
 square.uniforms.MatcapSpec.value=0;render();check(read(64,64).slice(0,3).every(v=>v<2),'Skin highlight intensity must be honored');
 const atlas=new Uint8Array(4*4*4);for(let i=0;i<16;i++)atlas[i*4+3]=255;atlas.set([255,255,255,255],12*4);
 const eyeAtlas=new THREE.DataTexture(atlas,4,4),mouthAtlas=new THREE.DataTexture(new Uint8Array([0,0,0,255]),1,1);eyeAtlas.needsUpdate=mouthAtlas.needsUpdate=true;
 const controls=[new THREE.Bone(),new THREE.Bone(),new THREE.Bone()];controls.forEach(n=>n.scale.set(0,0,1));
 const screen=await screenMaterial({name:'Synthetic CRT',screenControls:{EyeLeft:0,EyeRight:1,Mouth:2},textures:{_EyeTex:'eye',_MouthTex:'mouth'},floats:{_ScanLineOpacity:0},colors:{_ScreenColor:{r:0,g:0,b:1},_EyeColor:{r:1,g:1,b:1}}},{loadAsync:async url=>url.endsWith('mouth')?mouthAtlas:eyeAtlas},new URL('.',location.href),controls);
 const screenGeo=new THREE.PlaneGeometry(2,2),uv=screenGeo.attributes.uv;
 for(let i=0;i<uv.count;i++)uv.setXY(i,uv.getX(i)*.25,uv.getY(i)*.25+.75);
 screenGeo.setAttribute('color',new THREE.Float32BufferAttribute([1,0,0,1,0,0,1,0,0,1,0,0],3));mesh.geometry=screenGeo;mesh.material=screen;render();
 check(read(64,64).slice(0,3).every(v=>v>245),'CRT UV must sample the original atlas cell without scaling it twice');
 controls[0].scale.set(.25,-.25,1);screen.userData.updateExpression(true);render();
 check(read(64,64)[0]>245,'Animation transition must hold the previous expression');
 screen.userData.updateExpression(false);render();
 check(read(64,64)[0]<8&&screen.uniforms.EyeLeft.value.equals(new THREE.Vector2(.25,.25)),'Controller must use local scale X and negated Y to select the new cell');
 check(screen.uniforms.EyeRight.value.equals(new THREE.Vector2(0,0)),'Left eye must not change the right eye');
 controls[1].scale.set(.75,-.5,1);controls[2].scale.set(.5,-.25,1);screen.userData.updateExpression(false);
 check(screen.uniforms.EyeRight.value.equals(new THREE.Vector2(.75,.5))&&screen.uniforms.Mouth.value.equals(new THREE.Vector2(.5,.25)),'Right eye and mouth must have independent animation controls');
 const colors=screenGeo.attributes.color;for(let i=0;i<colors.count;i++)colors.setXYZ(i,0,1,0);colors.needsUpdate=true;render();
 const mouth=read(64,64);check(mouth[0]<8&&mouth[2]>245,'Green vertex mask must use the separate mouth atlas');
 check(!errors.length,errors.join(';'));window.result={ok:true};
}catch(error){window.result={error:String(error)};}
'''
view.setHtml('<script type="module">'+script+'</script>',QUrl.fromLocalFile(str(APP/'web/index.html')))
def poll():
 def received(raw):
  if not raw:QTimer.singleShot(100,poll);return
  try:
   result=json.loads(raw);assert result.get('ok'),result
   print('PASS: pupil center, slit size/rotation, iris toggle, mechanical eyes, reflection masks and animated CRT controls/transition hold',flush=True);app.quit()
  except Exception:traceback.print_exc();app.exit(1)
 view.page().runJavaScript('JSON.stringify(window.result)',received)
QTimer.singleShot(200,poll);QTimer.singleShot(15000,lambda:app.exit(2));sys.exit(app.exec())
