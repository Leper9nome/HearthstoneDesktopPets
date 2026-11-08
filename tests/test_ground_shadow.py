"""Fit tilted sole contacts and check the real GPU projection without game assets."""
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
import {fitContactPlane,contactPlane,groundShadowMaterial,shortShadowDirection} from './ground-shadow.js';
try{
 const check=(yes,message)=>{if(!yes)throw Error(message);};
 const turn=new THREE.Quaternion().setFromEuler(new THREE.Euler(.5,-.3,.25)),offset=new THREE.Vector3(.1,.2,-.1);
 const n=new THREE.Vector3(0,1,0).applyQuaternion(turn),points=[];
 for(const x of [-.6,-.4,.4,.6])for(const z of [-.2,0,.2])points.push(new THREE.Vector3(x,0,z).applyQuaternion(turn).add(offset));
 const plane=fitContactPlane(points,new THREE.Vector3(.1,1,.1).applyQuaternion(turn));
 check(plane.normal.dot(n)>.999999,'Fitted plane must follow the tilted feet');
 check(points.every(p=>Math.abs(plane.distanceToPoint(p))<1e-7),'Both soles must lie on the plane');
 const tentacleData={nodes:[{name:'root',parent:-1}],bones:[]},tentaclePositions=[],tentacleIndices=[],tentacleWeights=[];
 for(let i=0;i<6;i++){
  const parent=tentacleData.nodes.length;tentacleData.nodes.push({name:`arm${'ABC'[Math.floor(i/2)]}_1_${i%2?'R':'L'}_jnt`,parent:0},{name:'scale',parent});tentacleData.bones.push(parent+1);
  for(const y of [0,.5])for(const delta of [-.03,.03]){const angle=i*Math.PI/3;tentaclePositions.push(Math.cos(angle)+delta,y,Math.sin(angle));tentacleIndices.push(i,0,0,0);tentacleWeights.push(1,0,0,0);}
 }
 const tentacleGeometry=new THREE.BufferGeometry();tentacleGeometry.setAttribute('position',new THREE.Float32BufferAttribute(tentaclePositions,3));tentacleGeometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(tentacleIndices,4));tentacleGeometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(tentacleWeights,4));
 const tilted=new THREE.Matrix4().makeRotationZ(Math.PI/2),tentaclePet={geometry:tentacleGeometry,matrixWorld:new THREE.Matrix4(),skeleton:{bones:tentacleData.bones.map(()=>({matrixWorld:tilted})),boneInverses:tentacleData.bones.map(()=>new THREE.Matrix4())},getVertexPosition:(i,v)=>v.fromBufferAttribute(tentacleGeometry.attributes.position,i).applyMatrix4(tilted)};
 const support=contactPlane(tentaclePet,tentacleData,false);
 check(support.contacts.length===12&&support.plane.normal.dot(new THREE.Vector3(-1,0,0))>.9999,'Six tentacles with non-deforming parents must define the actual support plane');
 check(support.contacts.every(p=>Math.abs(support.plane.distanceToPoint(p))<1e-7),'Tentacle undersides must lie on their plane');
 const center=offset.clone().add(n),orientation=new THREE.Quaternion(),length=.1;
 const shortDirection=shortShadowDirection(plane,center,offset,orientation,length);
 const target=center.clone().addScaledVector(shortDirection,-plane.distanceToPoint(center)/plane.normal.dot(shortDirection)),shift=target.clone().sub(offset);
 check(Math.abs(plane.distanceToPoint(target))<1e-7,'Shifted shadow must remain on the sole plane');
 check(shift.x<0&&shift.y>0&&Math.abs(shift.x+shift.y)<1e-7,'Short shadow must point upper-left at 45 degrees');
 check(shift.length()<=length*3+1e-7,'Shadow offset must stay short');
 const edgePlane=new THREE.Plane(new THREE.Vector3(0,1,0),0),edgeDirection=shortShadowDirection(edgePlane,new THREE.Vector3(0,1,0),new THREE.Vector3(),orientation,length);
 check(edgeDirection.toArray().every(Number.isFinite)&&Math.abs(edgeDirection.y-1)<1e-7,'Edge-on ground must remain finite and preserve contact');
 const renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,preserveDrawingBuffer:true});renderer.setSize(128,128);renderer.setClearColor(0,0);document.body.append(renderer.domElement);
 const scene=new THREE.Scene(),direction=n.clone().add(new THREE.Vector3(.15,0,0).applyQuaternion(turn));
 const geometry=new THREE.BoxGeometry(.8,1,.6);geometry.translate(0,.5,0);
 const material=groundShadowMaterial(plane,direction),mesh=new THREE.Mesh(geometry,material);mesh.quaternion.copy(turn);mesh.position.copy(offset);scene.add(mesh);scene.updateMatrixWorld(true);
 const camera=new THREE.OrthographicCamera(-1.5,1.5,1.5,-1.5,.01,20),pixels=new Uint8Array(128*128*4);
 for(const position of [[2,3,4],[-3,2,3],[3,4,-2]]){
  camera.position.fromArray(position);camera.lookAt(offset);camera.updateMatrixWorld(true);renderer.render(scene,camera);
  renderer.getContext().readPixels(0,0,128,128,renderer.getContext().RGBA,renderer.getContext().UNSIGNED_BYTE,pixels);
  const actual={min:[128,128],max:[0,0]};let count=0;
  for(let y=0;y<128;y++)for(let x=0;x<128;x++)if(pixels[(y*128+x)*4+3]){count++;actual.min[0]=Math.min(actual.min[0],x);actual.min[1]=Math.min(actual.min[1],127-y);actual.max[0]=Math.max(actual.max[0],x);actual.max[1]=Math.max(actual.max[1],127-y);}
  const expected={min:[128,128],max:[0,0]};
  for(let i=0;i<geometry.attributes.position.count;i++){
   const p=new THREE.Vector3().fromBufferAttribute(geometry.attributes.position,i).applyMatrix4(mesh.matrixWorld);
   p.addScaledVector(direction,-plane.distanceToPoint(p)/plane.normal.dot(direction)).project(camera);
   const screen=[(p.x+1)*64,(1-p.y)*64];for(let j=0;j<2;j++){expected.min[j]=Math.min(expected.min[j],screen[j]);expected.max[j]=Math.max(expected.max[j],screen[j]);}
  }
  check(count>10,'Ground projection must render');
  // A diagonal tip can miss the last two pixel centers at this small resolution.
  for(const side of ['min','max'])for(let j=0;j<2;j++)check(Math.abs(actual[side][j]-expected[side][j])<3,'GPU footprint must stay on the contact plane as the camera rotates: '+JSON.stringify({actual,expected,position}));
 }
 window.result={ok:true};
}catch(error){window.result={error:String(error)};}
'''
view.setHtml('<script type="module">'+script+'</script>',QUrl.fromLocalFile(str(APP/'web/index.html')))
def poll():
 def received(raw):
  if not raw:QTimer.singleShot(100,poll);return
  try:
   result=json.loads(raw);assert result.get('ok'),result
   print('PASS: tilted soles share a plane; GPU shadow matches that plane from three camera angles',flush=True);app.quit()
  except Exception:traceback.print_exc();app.exit(1)
 view.page().runJavaScript('JSON.stringify(window.result)',received)
QTimer.singleShot(200,poll);QTimer.singleShot(15000,lambda:app.exit(2));sys.exit(app.exec())
