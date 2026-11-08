import json,zlib,re
from UnityPy.helpers.MeshHelper import MeshHandler
from vendor.pengpeng.common import safe_name
from animation_sampling import sample_clip

CANONICAL=['Idle_Neutral','Idle_Happy','Emote_Greetings','Emote_Wow','Emote_Threaten','Reaction_Poke_Small','Reaction_Happy_Big','Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out','Sequence_Flying_Idle']
def clip_name(name):
    low=name.lower().replace('nuetral','neutral')
    if 'mirror' in low:return None
    if low.startswith('pet_rabbitath_'):low=low[len('pet_rabbitath_'):];low=re.sub(r'_v\d+$','',low)
    if low.startswith('pet_nzoth_'):low=low[len('pet_nzoth_'):]
    return next((n for n in CANONICAL if n.lower()==low),None)

def export_model(reader,inventory,candidates,root,pid,skin):
    tree=lambda o:o.read_typetree()
    ptr=reader.pointer
    identity=lambda o:(o.assets_file.name,o.path_id)
    options=[x for x in candidates if x['pet_id']==pid and x['skin']==skin]
    # Prefer the complete standalone wrapper when imported mesh roots share its name.
    options.sort(key=lambda x:(x['materials'].count(x['materials'][-1]),x['bundle']))
    rec=options[0];out=root/f'pet_{pid}_{skin}';out.mkdir(parents=True,exist_ok=True)
    renderer=next(o for o in reader.load(rec['bundle']).objects if o.path_id==rec['renderer'])
    st=tree(renderer);go=ptr(renderer,st['m_GameObject'])
    tr=next(ptr(go,c['component']) for c in tree(go)['m_Component'] if ptr(go,c['component']).type.name=='Transform')
    while tree(tr)['m_Father']['m_PathID']:tr=ptr(tr,tree(tr)['m_Father'])
    nodes=[];ids={};paths={}
    def walk(o,parent=-1,path=''):
        t=tree(o);name=tree(ptr(o,t['m_GameObject']))['m_Name'];i=len(nodes);path=path+'/'+name if parent>=0 else ''
        ids[identity(o)]=i
        nodes.append({'name':name,'parent':parent,'position':list(t['m_LocalPosition'].values()),'quaternion':list(t['m_LocalRotation'].values()),'scale':list(t['m_LocalScale'].values()),'path':path.strip('/')})
        for p in t['m_Children']:walk(ptr(o,p),i,path)
    walk(tr)
    for i,n in enumerate(nodes):
        parts=n['path'].split('/')
        for j in range(len(parts)):
            h=zlib.crc32('/'.join(parts[j:]).encode());assert h not in paths or paths[h]==i
            paths[h]=i
    md=ptr(renderer,st['m_Mesh']).read();mh=MeshHandler(md);mh.process()
    matrices=[[getattr(m,f'e{row}{col}') for col in range(4) for row in range(4)] for m in md.m_BindPose]
    bones=[ids[identity(ptr(renderer,p))] for p in st['m_Bones']]
    assert len(matrices)==len(bones) and all(abs(sum(w)-1)<.003 for w in mh.m_BoneWeights)
    materials=[]
    for p in st['m_Materials']:
        obj=ptr(renderer,p);t=tree(obj);props=t['m_SavedProperties'];textures={}
        for key,entry in props['m_TexEnvs']:
            if entry['m_Texture']['m_PathID']:
                texture=ptr(obj,entry['m_Texture']).read();filename=safe_name(texture.m_Name)+'.png';texture.image.save(out/filename);textures[key]=filename
        materials.append({'name':t['m_Name'],'shader':tree(ptr(obj,t['m_Shader'])).get('m_ParsedForm',{}).get('m_Name',''),'textures':textures,'floats':dict(props['m_Floats']),'colors':dict(props['m_Colors'])})
    clips=[];sources=[]
    for row in inventory:
        if not row['bundle'].startswith(f'initial_base_pet_{pid}_global-'):continue
        selected=[o for o in row['objects'] if o['type']=='AnimationClip' and clip_name(o['name'])]
        if not selected:continue
        objects={o.path_id:o for o in reader.load(row['bundle']).objects}
        for entry in selected:
            name=clip_name(entry['name'])
            if any(c['name']==name for c in clips):continue
            raw=tree(objects[entry['id']]);clip=sample_clip(raw,paths,allow_missing=True);clip['sourceName']=raw['m_Name'];clip['name']=name
            assert len(clip['tracks'])>10,(pid,skin,name,'No matching skeleton')
            clips.append(clip);sources.append({'bundle':row['bundle'],'path_id':entry['id'],'name':raw['m_Name']})
    assert {'Idle_Neutral','Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out'}<={c['name'] for c in clips},(pid,skin,[c['name'] for c in clips])
    model={'nodes':nodes,'bones':bones,'inverseBindMatrices':matrices,'positions':mh.m_Vertices,'normals':mh.m_Normals,'uv':mh.m_UV0,'indices':mh.m_IndexBuffer,'skinIndices':mh.m_BoneIndices,'skinWeights':mh.m_BoneWeights,'groups':[{'start':s.firstByte//(2 if mh.m_Use16BitIndices else 4),'count':s.indexCount,'material':i} for i,s in enumerate(md.m_SubMeshes)],'materials':materials,'clips':clips}
    (out/'pet-data.js').write_text('window.PET_DATA='+json.dumps(model,separators=(',',':'))+';',encoding='utf-8')
    (out/'source.json').write_text(json.dumps({'model':rec,'animationSources':sources,'omittedBindings':{c['name']:c['omittedBindings'] for c in clips if c['omittedBindings']}},ensure_ascii=False,indent=2),encoding='utf-8')
    return model
