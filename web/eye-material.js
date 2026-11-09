import * as THREE from './three.module.js';

export async function screenMaterial(source,loader,assetBase,nodes=[]){
    const f=source.floats||{},c=source.colors||{},uniforms={Time:{value:0}};
    for(const key of ['EyeTex','MouthTex']){
        const map=await loader.loadAsync(new URL(source.textures['_'+key],assetBase).href);
        map.wrapS=map.wrapT=THREE.RepeatWrapping;map.colorSpace=THREE.NoColorSpace;
        uniforms[key]={value:map};
    }
    for(const [key,fallback] of Object.entries({Tiles:4,ScanLineAmount:75,ScanLineDensity:.55,ScanLineSpeed:.2,ScanLineOpacity:.15}))uniforms[key]={value:f['_'+key]??fallback};
    for(const [key,fallback] of Object.entries({ScreenColor:[.1,.16,.26],EyeColor:[.76,.89,1],ScanLinesColor:[.37,.39,.69]})){
        const v=c['_'+key];uniforms[key]={value:new THREE.Vector3(...(v?[v.r,v.g,v.b]:fallback))};
    }
    for(const key of ['EyeLeft','EyeRight','Mouth']){
        const v=c['_'+key];uniforms[key]={value:new THREE.Vector2(v?.r||0,v?.g||0)};
    }
    const material=new THREE.ShaderMaterial({name:source.name,uniforms,vertexColors:true,side:THREE.DoubleSide,
        vertexShader:`
            #include <common>
            #include <skinning_pars_vertex>
            varying vec2 screenUV;
            varying vec3 screenPart;
            void main(){
                screenUV=uv;screenPart=color;
                #include <skinbase_vertex>
                #include <begin_vertex>
                #include <skinning_vertex>
                #include <project_vertex>
            }`,
        fragmentShader:`
            uniform sampler2D EyeTex,MouthTex;
            uniform vec2 EyeLeft,EyeRight,Mouth;
            uniform vec3 ScreenColor,EyeColor,ScanLinesColor;
            uniform float Time,Tiles,ScanLineAmount,ScanLineDensity,ScanLineSpeed,ScanLineOpacity;
            varying vec2 screenUV;
            varying vec3 screenPart;
            vec2 atlasUV(vec2 selection){
                vec2 tile=floor(clamp(selection,0.,.99)*Tiles)/Tiles;
                // The mesh UVs already occupy one atlas cell.
                return screenUV+vec2(tile.x,-tile.y);
            }
            void main(){
                vec2 eye=mix(EyeRight,EyeLeft,step(.5,screenPart.r));
                vec3 mask=mix(texture2D(EyeTex,atlasUV(eye)).rgb,texture2D(MouthTex,atlasUV(Mouth)).rgb,step(.5,screenPart.g));
                vec3 color=mix(ScreenColor,EyeColor,mask);
                float scan=step(1.-ScanLineDensity,fract((screenUV.y+Time*ScanLineSpeed*.05)*ScanLineAmount));
                gl_FragColor=vec4(mix(color,ScanLinesColor,scan*ScanLineOpacity),1.);
            }`
    });
    if(source.screenControls){
        const controls=['EyeLeft','EyeRight','Mouth'].map(key=>{
            const index=source.screenControls[key];
            if(!Number.isInteger(index)||!nodes[index])throw Error('Invalid screen controller: '+key);
            return {value:uniforms[key].value,node:nodes[index]};
        });
        // The game copies animated localScale to atlas coordinates after animation transitions.
        material.userData.updateExpression=transitioning=>{
            if(transitioning)return;
            for(const {value,node} of controls)value.set(node.scale.x,-node.scale.y);
        };
    }
    material.onBeforeRender=()=>{uniforms.Time.value=performance.now()/1000;};
    return material;
}

// Eye colors and shape parameters come from the user's local material cache.
export async function eyeMaterial(source,loader,assetBase){
    const f=source.floats||{},c=source.colors||{},uniforms={};
    for(const [name,fallback] of Object.entries({Iris:1,IrisScale:1,IrisBlend:0,IrisShadow:.8,PupilHorizontal:1,PupilVertical:1,Rotation:0,Cross:0,MatcapDiffuse:1,MatcapSpec:1}))
        uniforms[name]={value:f['_'+name]??fallback};
    for(const [name,fallback] of Object.entries({ScleraColor:[1,1,1],IrisMainColor:[0,0,1],IrisSecondaryColor:[1,1,1],IrisTertiaryColor:[0,0,0],PupilColor:[.2,.2,.2],PupilSecondaryColor:[0,0,0],PupilTertiaryColor:[1,1,1],MatcapSubColor:[0,0,0]})){
        const color=c['_'+name];uniforms[name]={value:new THREE.Vector3(...(color?[color.r,color.g,color.b]:fallback))};
    }
    const offset=c._Offset;uniforms.Offset={value:new THREE.Vector2(offset?.r||0,offset?.g||0)};
    const file=source.textures._MatcapTexture;
    const map=file?await loader.loadAsync(new URL(file,assetBase).href):new THREE.DataTexture(new Uint8Array([255,0,0,255]),1,1);
    // Matcap RGB stores diffuse, highlight and colored reflection masks.
    map.colorSpace=THREE.NoColorSpace;map.needsUpdate=true;uniforms.Matcap={value:map};
    return new THREE.ShaderMaterial({name:source.name,uniforms,side:THREE.DoubleSide,
        defines:source.shader==='Hero/Pet/EyeSquare'?{SQUARE_EYE:1}:{},
        vertexShader:`
            #include <common>
            #include <skinning_pars_vertex>
            uniform float Rotation;
            uniform vec2 Offset;
            varying vec2 eyeUV;
            varying vec2 matcapUV;
            void main(){
                vec2 centered=uv-.5;
                float s=sin(Rotation),c=cos(Rotation);
                eyeUV=mat2(c,s,-s,c)*centered+.5+Offset;
                #include <skinbase_vertex>
                #include <beginnormal_vertex>
                #include <skinnormal_vertex>
                #include <defaultnormal_vertex>
                matcapUV=normalize(transformedNormal).xy*.499+.5;
                #include <begin_vertex>
                #include <skinning_vertex>
                #include <project_vertex>
            }`,
        fragmentShader:`
            uniform sampler2D Matcap;
            uniform float Iris,IrisScale,IrisBlend,IrisShadow,PupilHorizontal,PupilVertical,Cross,MatcapDiffuse,MatcapSpec;
            uniform vec3 ScleraColor,IrisMainColor,IrisSecondaryColor,IrisTertiaryColor,PupilColor,PupilSecondaryColor,PupilTertiaryColor,MatcapSubColor;
            varying vec2 eyeUV;
            varying vec2 matcapUV;
            float softEdge(float distance){return clamp((1.-distance)/max(fwidth(distance),.00001),0.,1.);}
            float curve(float x){return x*x*(3.-2.*x);}
            void main(){
                vec2 p=eyeUV*2.-1.;
                vec3 color;
                #ifdef SQUARE_EYE
                    vec4 d=abs(p.xyxy)-vec4(PupilHorizontal,PupilVertical,PupilVertical,PupilHorizontal);
                    vec4 fade=clamp(1.-10.*d,0.,1.);
                    vec2 rim=max(vec2(min(fade.x,fade.y),min(fade.z,fade.w))-.25,0.);
                    color=mix(ScleraColor,PupilSecondaryColor,curve(rim.x));
                    color=mix(color,PupilSecondaryColor,curve(rim.y)*Cross);
                    vec4 edge=clamp(1.-d/max(fwidth(d),vec4(.00001)),0.,1.);
                    color=mix(color,PupilColor,min(edge.x,edge.y));
                    color=mix(color,PupilColor,min(edge.z,edge.w)*Cross);
                #else
                    float radius=length(p/max(IrisScale,.00001));
                    float blend=max(mix(fwidth(radius),1.,IrisBlend),.00001);
                    float iris=clamp((1.-radius)/blend,0.,1.)*Iris;
                    vec3 irisColor=mix(IrisSecondaryColor,IrisMainColor,smoothstep(.35,.65,eyeUV.y));
                    irisColor=mix(irisColor,IrisMainColor*IrisShadow,smoothstep(.75,1.,radius));
                    color=mix(ScleraColor,IrisTertiaryColor,(1.-smoothstep(.5,1.25,radius))*Iris);
                    color=mix(color,irisColor,iris);
                    float pupil=length(p/max(IrisScale*vec2(PupilHorizontal,PupilVertical),vec2(.00001)));
                    color=mix(color,PupilTertiaryColor,1.-smoothstep(.25,1.5,pupil));
                    vec3 pupilColor=mix(PupilColor,PupilSecondaryColor,max(1.-pupil,0.));
                    color=mix(color,pupilColor,softEdge(pupil));
                #endif
                vec3 reflection=texture2D(Matcap,matcapUV).rgb;
                color=color*reflection.r*MatcapDiffuse+reflection.b*MatcapSubColor+reflection.g*MatcapSpec;
                // shortcut: retain the game's gamma-space eye colors; board lighting and EyeFX particles remain simplified.
                gl_FragColor=vec4(color,1.);
            }`
    });
}
