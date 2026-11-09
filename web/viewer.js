import {eyeMaterial,screenMaterial} from './eye-material.js';
import * as THREE from './three.module.js';
import {createIdleActions} from './idle-actions.js';
import {createBubbleMenu} from './bubble-menu.js';
import {contactPlane,groundShadowMaterial,shortShadowDirection} from './ground-shadow.js';
window.petErrors=[];
function fail(e){window.petErrors.push(String(e));const el=document.querySelector('#error');el.style.display='block';el.textContent='加载失败：'+e;}
window.addEventListener('error',e=>fail(e.message));
window.addEventListener('unhandledrejection',e=>fail(e.reason));
const catalogURL=new URLSearchParams(location.search).get('catalog');
if(!catalogURL||new URL(catalogURL).protocol!=='file:')throw Error('缺少本地素材目录');
await loadScript(catalogURL);
const config=window.PET_CATALOG.find(c=>c.id===new URLSearchParams(location.search).get('pet'))||window.PET_CATALOG[0];
async function loadScript(path){await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=path;script.onload=resolve;script.onerror=()=>reject(Error('无法读取素材：'+path));document.head.append(script);});}
await loadScript(config.model);if(config.sounds)await loadScript(config.sounds);
const data=window.PET_DATA,assetBase=new URL('.',new URL(config.model,location.href));
const boneIndex=name=>{const i=data.nodes.findIndex(n=>n.name===name);if(i<0)throw Error('Missing bone: '+name);return i;};
const firstBone=names=>{const name=names.find(name=>data.nodes.some(n=>n.name===name));return boneIndex(name);};
const faceBones=[boneIndex('eyeA_L_jnt'),boneIndex('eyeA_R_jnt'),firstBone(['browA_1_L_jnt','eyeA_M_jnt','eyeB_M_jnt']),firstBone(['browA_1_R_jnt','eyeA_M_jnt','eyeB_M_jnt']),firstBone(['noseA_wing_L_jnt','noseA_wingIn_L_jnt','noseA_M_jnt','jawA_top_M_jnt','eyeA_pupil_M_jnt','eyeB_pupil_M_jnt']),firstBone(['noseA_wing_R_jnt','noseA_wingIn_R_jnt','noseA_M_jnt','jawA_top_M_jnt','eyeA_pupil_M_jnt','eyeB_pupil_M_jnt'])];
const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0,0);
renderer.outputColorSpace=THREE.SRGBColorSpace;document.body.prepend(renderer.domElement);
// Keep the ground shadow outside WebGL so hit testing sees only the pet.
const shadowCanvas=document.createElement('canvas');shadowCanvas.id='ground-shadow';
shadowCanvas.setAttribute('aria-hidden','true');document.body.prepend(shadowCanvas);
const shadowContext=shadowCanvas.getContext('2d');
function drawGroundShadow(groundY){
    const w=innerWidth,h=innerHeight;
    if(shadowCanvas.width!==w||shadowCanvas.height!==h){shadowCanvas.width=w;shadowCanvas.height=h;}
    shadowContext.clearRect(0,0,w,h);
    if(groundY===undefined){
        shadowContext.globalAlpha=.25;shadowContext.drawImage(renderer.domElement,0,0,w,h);shadowContext.globalAlpha=1;return;
    }
    // Floating pets retain their soft, detached footprint.
    shadowContext.setTransform(.75,0,-.12,.18,w*.125+.12*groundY,.82*groundY);
    shadowContext.drawImage(renderer.domElement,0,0,w,h);
    shadowContext.setTransform(1,0,0,1,0,0);
    shadowContext.globalCompositeOperation='source-in';
    shadowContext.fillStyle='rgba(0,0,0,.25)';shadowContext.fillRect(0,0,w,h);
    shadowContext.globalCompositeOperation='source-over';
}
const scene=new THREE.Scene(),stage=new THREE.Group();scene.add(stage);stage.scale.z=-1;
const nodes=data.nodes.map((n,i)=>{const b=new THREE.Bone();b.name='bone_'+i;b.position.fromArray(n.position);b.quaternion.fromArray(n.quaternion);b.scale.fromArray(n.scale);return b;});
data.nodes.forEach((n,i)=>{(n.parent<0?stage:nodes[n.parent]).add(nodes[i]);});
// The outer prefab transform places the pet on the Hearthstone board.
nodes[0].position.set(0,0,0);nodes[0].scale.set(1,1,1);
const geo=new THREE.BufferGeometry();
for(const [name,values,size] of [['position',data.positions,3],['normal',data.normals.map(v=>v.slice(0,3)),3],['uv',data.uv,2],['skinWeight',data.skinWeights,4]])geo.setAttribute(name,new THREE.Float32BufferAttribute(values.flat(),size));
geo.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(data.skinIndices.flat(),4));
if(data.vertexColors)geo.setAttribute('color',new THREE.Float32BufferAttribute(data.vertexColors.flat(),3));
geo.setIndex(data.indices);data.groups.forEach(g=>geo.addGroup(g.start,g.count,g.material));
const loader=new THREE.TextureLoader();
// Body materials retain their baked color textures.
async function materialFor(source){
    if(/^Hero\/Pet\/Eye(?:Square|FX)?$/.test(source.shader))return eyeMaterial(source,loader,assetBase);
    if(source.shader==='Hero/Pet/PetFlipBook'&&data.vertexColors)return screenMaterial(source,loader,assetBase,nodes);
    const file=source.textures._MainTex||source.textures._BaseMap||source.textures._EyeTex;
    if(file){
        const map=await loader.loadAsync(new URL(file,assetBase).href);map.colorSpace=THREE.SRGBColorSpace;
        // Unity diffuse UVs can cross tile boundaries, including negative coordinates.
        if(source.textures._MainTex||source.textures._BaseMap)map.wrapS=map.wrapT=THREE.RepeatWrapping;
        if(source.textures._EyeTex){const tiles=source.floats._Tiles||4,tile=source.floats._CurrentTile||0;map.repeat.set(1/tiles,1/tiles);map.offset.set((tile%tiles)/tiles,1-(Math.floor(tile/tiles)+1)/tiles);}
        const transparent=source.shader?.includes('Transparent')||false;
        // shortcut: use fixed translucency until the game's view-dependent jelly shader is ported.
        const opacity=transparent?(source.floats._FresnelTransparency? .55:source.floats._Opacity??1):1;
        return new THREE.MeshBasicMaterial({map,side:THREE.DoubleSide,transparent,opacity,depthWrite:!transparent,forceSinglePass:true});
    }
    const color=source.colors?._Color;
    return new THREE.MeshBasicMaterial({color:color?new THREE.Color(color.r,color.g,color.b):0xffffff,side:THREE.DoubleSide});
}
const materials=await Promise.all(data.materials.map(materialFor));
const pet=new THREE.SkinnedMesh(geo,materials);pet.frustumCulled=false;stage.add(pet);
stage.updateMatrixWorld(true);
const skeleton=new THREE.Skeleton(data.bones.map(i=>nodes[i]),data.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m)));
pet.bind(skeleton,new THREE.Matrix4());
scene.add(new THREE.AmbientLight(0xffffff,1.5));const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(-3,5,4);scene.add(light);
const camera=new THREE.OrthographicCamera(-1.25,1.25,1.2,-1.2,.01,100);
const mixer=new THREE.AnimationMixer(stage),actions={};
for(const c of data.clips){const tracks=c.tracks.map(t=>new (t.property==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)('bone_'+t.node+'.'+t.property,c.times,t.values));actions[c.name]=mixer.clipAction(new THREE.AnimationClip(c.name,c.duration,tracks));}
const savedZoom=Number(sessionStorage.getItem('petZoom'));
let current=null,queue=[],muted=true,voice=null,zoom=Number.isFinite(savedZoom)&&savedZoom>=.65&&savedZoom<=1.5?savedZoom:1,drag=null,native=null,viewLocked=false,transitionUntil=0,viewEditing=false,previousLock=false,defaultZoom=1;
const defaultView=new THREE.Quaternion(),viewOrientation=new THREE.Quaternion();
const flightCorrection=new THREE.Quaternion();
const idleTarget=new THREE.Vector3(0,.5,0),flightTarget=new THREE.Vector3(-.4,.9,-.18);
function updateView(){const flying=window.petState==='Sequence_Flying_Idle',target=flying?flightTarget:idleTarget;camera.quaternion.copy(viewOrientation);if(flying)camera.quaternion.premultiply(flightCorrection);camera.position.set(0,0,4).applyQuaternion(camera.quaternion).add(target);camera.updateMatrixWorld(true);}
function play(name,loop=false){if(!actions[name])throw Error('Unknown animation: '+name);const next=actions[name],crossfade=current&&current!==next;transitionUntil=mixer.time+(crossfade ? .18 : 0);if(crossfade)current.fadeOut(.18);next.reset().setEffectiveWeight(1).setEffectiveTimeScale(1);next.setLoop(loop?THREE.LoopRepeat:THREE.LoopOnce,loop===true?Infinity:loop||1);next.clampWhenFinished=loop!==true;if(crossfade)next.fadeIn(.18);next.play();current=next;window.petState=name;updateView();}
function sound(name){if(muted||!window.PET_SOUNDS?.[name])return;if(voice)voice.pause();voice=new Audio(window.PET_SOUNDS[name]);voice.volume=.4;voice.play().catch(fail);}
function command(name){queue=[];if(name==='pet'){queue=[['Sequence_Pet_Loop',2],['Sequence_Pet_Out',false]];play('Sequence_Pet_In');sound('pet');}else{play(name,['Idle_Neutral','Idle_Happy','Sequence_Flying_Idle'].includes(name));sound(name);}}
mixer.addEventListener('finished',event=>{if(event.action!==current)return;if(queue.length){const [n,l]=queue.shift();play(n,l);}else play('Idle_Neutral',true);});
const point=i=>nodes[i].getWorldPosition(new THREE.Vector3());
// Each pose has its own head orientation in the source animation.
function calibrateView(name){
mixer.stopAllAction();current=null;play(name,true);current.stopFading().setEffectiveWeight(1);mixer.update(0);
const [leftEye,rightEye,leftBrow,rightBrow,leftNose,rightNose]=faceBones;
const eyeMid=point(leftEye).add(point(rightEye)).multiplyScalar(.5);
const across=point(rightEye).sub(point(leftEye)).normalize();
const forehead=point(leftBrow).add(point(rightBrow)).multiplyScalar(.5).sub(eyeMid);
const outward=new THREE.Vector3().crossVectors(across,forehead).normalize();
const noseDirection=point(leftNose).add(point(rightNose)).multiplyScalar(.5).sub(eyeMid);
if(config.pet==='deathling')outward.copy(noseDirection).addScaledVector(across,-noseDirection.dot(across)).normalize();
if(config.faceMode==='pupils'){
    const pupil=(name,eye)=>{const i=data.nodes.findIndex(n=>n.name===name);return i>=0?point(i):new THREE.Vector3(0,.05,0).applyMatrix4(nodes[eye].matrixWorld);};
    const pupilLeft=pupil('eyeA_pupil_L_jnt',leftEye),pupilRight=pupil('eyeA_pupil_R_jnt',rightEye);
    outward.copy(pupilLeft.add(pupilRight).multiplyScalar(.5).sub(eyeMid)).addScaledVector(across,-outward.dot(across)).normalize();
}else if(outward.dot(noseDirection)<0)outward.negate();
const right=across.clone();
if(new THREE.Vector3().crossVectors(forehead,outward).dot(right)<0)right.negate();
const up=new THREE.Vector3().crossVectors(outward,right).normalize();
if(config.pet!=='ysera'){stage.updateMatrixWorld(true);skeleton.update();pet.computeBoundingBox();pet.boundingBox.getCenter(name==='Sequence_Flying_Idle'?flightTarget:idleTarget).applyMatrix4(pet.matrixWorld);}
const [yaw,pitch,roll]=config.viewAngles||[-.32,0,0];
return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(right,up,outward))
    .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),yaw))
    .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),pitch))
    .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),roll));
}
const flightView=actions.Sequence_Flying_Idle?calibrateView('Sequence_Flying_Idle'):null;
defaultView.copy(calibrateView('Idle_Neutral'));
if(flightView)flightCorrection.copy(flightView).multiply(defaultView.clone().invert());
const baseView=defaultView.clone();
viewOrientation.copy(defaultView);updateView();
function updateProjection(){const w=innerWidth,h=innerHeight,height=(config.viewHeight||2.1)*h/420/zoom;camera.left=-height*w/h/2;camera.right=-camera.left;camera.top=height/2;camera.bottom=-height/2;camera.updateProjectionMatrix();}
function resize(){renderer.setSize(innerWidth,innerHeight);updateProjection();}
window.addEventListener('resize',resize);resize();
stage.updateMatrixWorld(true);skeleton.update();
let groundLevel=Infinity;const groundVertex=new THREE.Vector3();
for(let i=0;i<geo.attributes.position.count;i++)groundLevel=Math.min(groundLevel,pet.getVertexPosition(i,groundVertex).applyMatrix4(pet.matrixWorld).project(camera).y/zoom);
const ground=[9,16].includes(config.petId)?null:contactPlane(pet,data,[7,15,6].includes(config.petId));
let groundMaterial=null;
if(ground){
    pet.computeBoundingBox();const center=pet.boundingBox.getCenter(new THREE.Vector3()).applyMatrix4(pet.matrixWorld);
    const contact=ground.contacts.length?ground.contacts.reduce((sum,p)=>sum.add(p),new THREE.Vector3()).multiplyScalar(1/ground.contacts.length):ground.plane.projectPoint(center,new THREE.Vector3());
    // Keep the footprint short and behind the feet in the default view.
    const length=pet.boundingBox.getSize(new THREE.Vector3()).length()*.075;
    const direction=shortShadowDirection(ground.plane,center,contact,camera.quaternion,length);
    groundMaterial=groundShadowMaterial(ground.plane,ground.plane.normal.dot(direction)>.001?direction:ground.plane.normal);
}
if(ground)shadowCanvas.style.filter='blur(6px)';
let renderFrames=0;
function renderFrame(){
    for(const material of materials)material.userData.updateExpression?.(mixer.time<transitionUntil);
    if(groundMaterial){
        scene.overrideMaterial=groundMaterial;
        try{renderer.render(scene,camera);drawGroundShadow();}finally{scene.overrideMaterial=null;}
    }
    renderer.render(scene,camera);
    if(!groundMaterial)drawGroundShadow((1-groundLevel*zoom)*innerHeight/2+6*zoom);
    renderFrames++;
}

window.petCommand=command;window.petMute=value=>{muted=value;if(muted&&voice)voice.pause();};
window.petZoom=delta=>{if(viewLocked)return;zoom=THREE.MathUtils.clamp(zoom+delta,.65,1.5);sessionStorage.setItem('petZoom',String(zoom));updateProjection();};
window.petSetViewLocked=value=>{viewLocked=Boolean(value);};
window.petResetView=()=>{if(viewLocked)return;viewOrientation.copy(defaultView);zoom=defaultZoom;sessionStorage.setItem('petZoom',String(zoom));updateView();updateProjection();};
window.petCheck=()=>{stage.updateMatrixWorld(true);skeleton.update();pet.computeBoundingBox();const box=pet.boundingBox,screenBox=new THREE.Box3(),v=new THREE.Vector3();for(let i=0;i<geo.attributes.position.count;i++)screenBox.expandByPoint(pet.getVertexPosition(i,v).applyMatrix4(pet.matrixWorld).project(camera));return {ready:true,variant:config.id,state:window.petState,bones:skeleton.bones.length,clips:Object.keys(actions),view:{orientation:viewOrientation.toArray(),zoom,locked:viewLocked},viewport:[innerWidth,innerHeight],screenBounds:{min:screenBox.min.toArray(),max:screenBox.max.toArray()},face:{left:point(faceBones[0]).project(camera).toArray(),right:point(faceBones[1]).project(camera).toArray(),forehead:point(faceBones[2]).add(point(faceBones[3])).multiplyScalar(.5).project(camera).toArray(),nose:point(faceBones[4]).add(point(faceBones[5])).multiplyScalar(.5).project(camera).toArray()},renderFrames,screenExpressions:materials.filter(m=>m.userData.updateExpression).map(m=>Object.fromEntries(['EyeLeft','EyeRight','Mouth'].map(key=>[key,m.uniforms[key].value.toArray()]))),ground:ground?{normal:ground.plane.normal.toArray(),constant:ground.plane.constant,contactSamples:ground.contacts.length}:null,bounds:{min:box.min.toArray(),max:box.max.toArray()},errors:window.petErrors};};
window.petSample=(name,time)=>{mixer.stopAllAction();current=null;play(name,true);current.stopFading().setEffectiveWeight(1);current.time=time;mixer.update(0);renderFrame();return window.petCheck();};
window.petInspect=()=>{renderFrame();return renderer.domElement.toDataURL();};
window.petStep=dt=>{renderer.setAnimationLoop(null);mixer.update(dt);return {state:window.petState,root:nodes[boneIndex('rootA_M_jnt')].quaternion.toArray(),weights:Object.fromEntries(Object.entries(actions).map(([name,action])=>[name,action.getEffectiveWeight()]))};};
const bubbleMenu=await createBubbleMenu({assets:window.PET_MENU_ASSETS||{},state:()=>window.petState,onAction:id=>{if(id==='view-restore')window.petResetView();else if(id==='view-save')native?.cameraAction(JSON.stringify({...window.petViewPreset(),variant:config.id}));else if(id==='view-cancel')native?.cameraAction(JSON.stringify({cancel:true,variant:config.id}));else native?.menuAction(id);}});
window.petViewPreset=()=>({rotation:baseView.clone().invert().multiply(viewOrientation).normalize().toArray(),zoom});
window.petApplyDefault=preset=>{if(!preset)return;defaultView.copy(baseView).multiply(new THREE.Quaternion().fromArray(preset.rotation)).normalize();defaultZoom=preset.zoom;window.petResetView();};
// Apply the local preference before any frame can be painted or declared ready.
window.petApplyDefault(window.PET_CAMERA_DEFAULT);
window.petBeginViewSettings=()=>{if(viewEditing)return;viewEditing=true;previousLock=viewLocked;viewLocked=false;command('Idle_Neutral');bubbleMenu.edit();};
window.petFinishViewSettings=save=>{if(!viewEditing)return;if(save){defaultView.copy(viewOrientation);defaultZoom=zoom;}else window.petResetView();viewEditing=false;viewLocked=previousLock;bubbleMenu.finish();};
window.petShowMenu=bubbleMenu.show;window.petHideMenu=bubbleMenu.hide;window.petMenuHit=bubbleMenu.contains;
// Wait for the first painted frame before the native window becomes visible.
if(window.qt&&window.QWebChannel)new QWebChannel(qt.webChannelTransport,c=>{native=c.objects.desktop;requestAnimationFrame(()=>{renderFrame();requestAnimationFrame(()=>native.ready());});});
document.addEventListener('contextmenu',e=>e.preventDefault());
const ray=new THREE.Raycaster();
const hitPixel=new Uint8Array(4);
window.petHitTest=(x,y,width,height)=>{
    if(x<0||y<0||x>=width||y>=height)return false;
    if(window.petMenuHit?.(x/width*innerWidth,y/height*innerHeight))return true;
    const gl=renderer.getContext(),canvas=renderer.domElement;
    if(gl.isContextLost())return false;
    gl.readPixels(Math.floor(x/width*canvas.width),canvas.height-1-Math.floor(y/height*canvas.height),1,1,gl.RGBA,gl.UNSIGNED_BYTE,hitPixel);
    return hitPixel[3]>8;
};
function hit(e){pet.computeBoundingSphere();ray.setFromCamera(new THREE.Vector2(e.clientX/innerWidth*2-1,1-e.clientY/innerHeight*2),camera);return ray.intersectObject(pet).length>0;}
renderer.domElement.addEventListener('pointerdown',e=>{
    if(e.button!==2&&(e.button!==0||!hit(e)))return;
    drag={button:e.button,x:e.screenX,y:e.screenY,lastX:e.screenX,lastY:e.screenY,moved:false};
    renderer.domElement.setPointerCapture(e.pointerId);
});
renderer.domElement.addEventListener('pointermove',e=>{
    if(!drag)return;
    if(!drag.moved&&Math.hypot(e.screenX-drag.x,e.screenY-drag.y)>5){
        drag.moved=true;
        if(drag.button===0)native?.dragWindow();
    }
    if(drag.moved&&drag.button===2&&!viewLocked){
        const dx=e.screenX-drag.lastX,dy=e.screenY-drag.lastY;
        // Camera-local rotations remain continuous through poles; Shift adds roll.
        const axis=e.shiftKey?new THREE.Vector3(0,0,1):new THREE.Vector3(-dy,-dx,0).normalize();
        const angle=e.shiftKey?-dx*.008:Math.hypot(dx,dy)*.008;
        viewOrientation.multiply(new THREE.Quaternion().setFromAxisAngle(axis,angle)).normalize();
        updateView();
    }
    drag.lastX=e.screenX;drag.lastY=e.screenY;
});
renderer.domElement.addEventListener('pointerup',()=>{
    const gesture=drag;drag=null;
    if(!gesture||gesture.moved||viewEditing)return;
    if(gesture.button===2)native?.menu();else command('pet');
});
renderer.domElement.addEventListener('pointercancel',()=>{drag=null;});
renderer.domElement.addEventListener('lostpointercapture',()=>{drag=null;});
window.addEventListener('wheel',e=>{e.preventDefault();window.petZoom(e.deltaY>0?-.05:.05);},{passive:false});
window.addEventListener('keydown',e=>{if(viewEditing)return;if(e.key==='Escape')native?.quit();if(e.key===' ')command('Emote_Greetings');});
const idleActions=createIdleActions(actions,command);
let last=performance.now(),nextFrame=last;
renderer.setAnimationLoop(now=>{if(now+.5<nextFrame)return;const dt=Math.min((now-last)/1000,.1);last=now;nextFrame+=1000/60;if(nextFrame<now)nextFrame=now+1000/60;mixer.update(dt);if(!viewEditing)idleActions(dt,window.petState);renderFrame();});
window.petReady=true;
