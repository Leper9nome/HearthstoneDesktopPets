import * as THREE from './three.module.js';

// Fit sole patches in their own basis so tilted feet need no world-up assumption.
export function fitContactPlane(points,up){
    const center=points.reduce((sum,p)=>sum.add(p),new THREE.Vector3()).multiplyScalar(1/points.length);
    const n=up.clone().normalize(),u=new THREE.Vector3(Math.abs(n.x)<.8?1:0,0,Math.abs(n.x)<.8?0:1);
    u.addScaledVector(n,-u.dot(n)).normalize();const v=new THREE.Vector3().crossVectors(n,u);
    let xx=0,xy=0,yy=0,xz=0,yz=0;
    for(const p of points){const d=p.clone().sub(center),x=d.dot(u),y=d.dot(v),z=d.dot(n);xx+=x*x;xy+=x*y;yy+=y*y;xz+=x*z;yz+=y*z;}
    const det=xx*yy-xy*xy;
    if(det>1e-12)n.addScaledVector(u,-(xz*yy-yz*xy)/det).addScaledVector(v,-(yz*xx-xz*xy)/det).normalize();
    return new THREE.Plane().setFromNormalAndCoplanarPoint(n,center);
}

export function contactPlane(pet,data,quadruped){
    const geometry=pet.geometry,positions=geometry.attributes.position,weights=geometry.attributes.skinWeight,indices=geometry.attributes.skinIndex;
    const candidates=data.nodes.map((node,i)=>({node,i}));
    let feet=candidates.filter(({node})=>/^legA_ankle_[LR]_jnt$/.test(node.name)||(quadruped&&/^armA_(wrist|hand)_[LR]_jnt$/.test(node.name)));
    // C'Thun rests on six tentacles; world Y points toward its face in this pose.
    if(!feet.length)feet=candidates.filter(({node})=>/^arm[ABC]_1_[LR]_jnt$/.test(node.name));
    const contacts=[],up=new THREE.Vector3();geometry.computeBoundingBox();
    const soleDepth=geometry.boundingBox.getSize(new THREE.Vector3()).y*.015;
    for(const {i} of feet){
        const descendants=new Set([i]);data.nodes.forEach((node,j)=>{if(descendants.has(node.parent))descendants.add(j);});
        const vertices=[];let lowest=Infinity;
        for(let j=0;j<positions.count;j++){
            let weight=0;for(let k=0;k<4;k++)if(descendants.has(data.bones[indices.getComponent(j,k)]))weight+=weights.getComponent(j,k);
            if(weight>.5){vertices.push(j);lowest=Math.min(lowest,positions.getY(j));}
        }
        for(const j of vertices)if(positions.getY(j)<=lowest+soleDepth)contacts.push(pet.getVertexPosition(j,new THREE.Vector3()).applyMatrix4(pet.matrixWorld));
        const bone=data.bones.includes(i)?data.bones.indexOf(i):data.bones.findIndex(node=>descendants.has(node));
        if(bone>=0)up.add(new THREE.Vector3(0,1,0).transformDirection(new THREE.Matrix4().multiplyMatrices(pet.skeleton.bones[bone].matrixWorld,pet.skeleton.boneInverses[bone])));
    }
    if(contacts.length>=3)return {plane:fitContactPlane(contacts,up),contacts};
    // Pets without feet rest on their lowest body surface.
    let lowest=Infinity;for(let j=0;j<positions.count;j++)lowest=Math.min(lowest,pet.getVertexPosition(j,new THREE.Vector3()).applyMatrix4(pet.matrixWorld).y);
    return {plane:new THREE.Plane(new THREE.Vector3(0,1,0),-lowest),contacts};
}

export function shortShadowDirection(plane,center,contact,orientation,length){
    const offset=new THREE.Vector3(-1,1,0).normalize().applyQuaternion(orientation).multiplyScalar(length);
    const outward=new THREE.Vector3(0,0,1).applyQuaternion(orientation),facing=plane.normal.dot(outward);
    // Move the target along the ground while keeping its screen direction upper-left.
    if(Math.abs(facing)>.05)offset.addScaledVector(outward,-plane.normal.dot(offset)/facing);
    else offset.projectOnPlane(plane.normal);
    offset.clampLength(0,length*3);
    return center.clone().sub(contact).sub(offset);
}

export function groundShadowMaterial(plane,direction=plane.normal){
    const material=new THREE.MeshBasicMaterial({color:0x000000,side:THREE.DoubleSide});
    material.onBeforeCompile=shader=>{
        shader.uniforms.groundPlane={value:new THREE.Vector4(...plane.normal.toArray(),plane.constant)};
        shader.uniforms.groundDirection={value:direction.clone().multiplyScalar(1/plane.normal.dot(direction))};
        shader.vertexShader='uniform vec4 groundPlane;\nuniform vec3 groundDirection;\n'+shader.vertexShader;
        shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>',`
            vec4 groundPosition=modelMatrix*vec4(transformed,1.0);
            groundPosition.xyz-=groundDirection*(dot(groundPlane.xyz,groundPosition.xyz)+groundPlane.w);
            vec4 mvPosition=viewMatrix*groundPosition;
            gl_Position=projectionMatrix*mvPosition;
        `);
    };
    return material;
}
