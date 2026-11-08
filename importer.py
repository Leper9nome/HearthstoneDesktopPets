"""Read the user's installed game, exporting assets only into the user cache."""
import hashlib,json,re,subprocess,uuid
from pathlib import Path
from paths import APP,read_json,write_json
from vendor.pengpeng.unity import UnityReader
from vendor.pengpeng.storage import Store
from vendor.pengpeng.common import localized,safe_name
from export_model import export_model

FORMAT_VERSION=1

def progress(message):print(message,flush=True)

def game_root(path):
    path=Path(path).resolve()
    if not (path/'Data/Win/asset_manifest.unity3d').is_file() or not (path/'Data/Win/dbf.unity3d').is_file():
        raise ValueError('请选择包含 Hearthstone.exe 和 Data 文件夹的炉石安装目录，并完成游戏资源下载。')
    return path

def stamp(paths):
    h=hashlib.sha256(str(FORMAT_VERSION).encode())
    for p in sorted(set(paths)):
        st=p.stat();h.update(f'{p.name}:{st.st_size}:{st.st_mtime_ns}\n'.encode())
    return h.hexdigest()[:24]

def install_cache(game,data):
    return data/'cache'/hashlib.sha256(str(game).lower().encode()).hexdigest()[:16]

def reader_for(game,cache):
    files=list((game/'Data/Win').glob('asset_manifest*.unity3d'))
    return UnityReader(game,Store(cache/'index'/stamp(files)/'index.sqlite3'))

def scan(game,data):
    game=game_root(game);cache=install_cache(game,data);base=game/'Data/Win'
    if data==game or game in data.parents:raise ValueError('本地缓存必须放在游戏安装目录之外。')
    files=list(base.glob('initial_base_pet_*'))+list(base.glob('asset_manifest*.unity3d'))+[base/'dbf.unity3d']
    signature=stamp(files);old=read_json(cache/'available.json',{})
    if old.get('signature')==signature:
        write_json(data/'library.json',old);progress('本地资源目录已是最新。');return
    progress('读取本地宠物名称和外观清单…');reader=reader_for(game,cache)
    tables={Path(k).stem:o.read_typetree()['Records'] for k,o in reader.load('dbf.unity3d').container.items() if Path(k).stem in ('PET','PET_VARIANT')}
    if not tables.get('PET') or not tables.get('PET_VARIANT'):raise ValueError('当前客户端缺少可识别的宠物数据表。')
    installed={int(m[1]) for p in files if (m:=re.match(r'initial_base_pet_(\d+)_global-',p.name))}
    camera=read_json(APP/'camera.json',{});entries=[]
    signatures={pid:pet_stamp(reader,pid) for pid in installed}
    for pet in tables['PET']:
        pid=pet['m_ID']
        if pid not in installed:continue
        rows=[v for v in tables['PET_VARIANT'] if v['m_petId']==pid]
        for ordinal,v in enumerate(rows,1):
            skin=({8:4,9:3}.get(v['m_ID'],ordinal) if pid==3 else {23:3,24:2}.get(v['m_ID'],ordinal) if pid==8 else ordinal)
            key={(7,1):'ysera',(7,4):'nightmare',(9,1):'deathling'}.get((pid,skin),f'pet_{pid}_{skin}')
            entry={'id':key,'pet':{7:'ysera',9:'deathling'}.get(pid,f'pet_{pid}'),'petId':pid,'skin':skin,'variantId':v['m_ID'],'petName':localized(pet,'m_name'),'name':localized(v,'m_name'),'description':localized(v,'m_name','enus'),'iconRef':v['m_petIcon']}
            entry.update(camera.get(key,{'viewHeight':3.2,'faceMode':'pupils'}));entries.append(entry)
            entry['sourceSignature']=signatures[pid]
    if not entries:raise ValueError('本地没有宠物资源包。请先通过战网完成炉石资源下载，再重新扫描。')
    order=[7,9,3,15,16,4,6,8,10,12]
    entries.sort(key=lambda c:(order.index(c['petId']) if c['petId'] in order else 100+c['petId'],c['skin']))
    library={'game':str(game),'cache':str(cache),'signature':signature,'entries':entries}
    write_json(cache/'available.json',library);write_json(data/'library.json',library)
    progress(f'发现 {len(installed)} 只宠物、{len(entries)} 款外观。')

def inventory_for(reader,pid):
    inventory=[]
    files=sorted(reader.root.glob(f'initial_base_pet_{pid}_global-*.unity3d'))
    for index,path in enumerate(files):
        progress(f'检查资源包 {index+1}/{len(files)}…');objects=[]
        for obj in reader.load(path.name).objects:
            kind=obj.type.name
            if kind in ('AnimationClip','AudioClip','SkinnedMeshRenderer'):
                objects.append({'id':obj.path_id,'type':kind,'name':obj.read_typetree().get('m_Name','') if kind!='SkinnedMeshRenderer' else ''})
        inventory.append({'bundle':path.name,'objects':objects})
    return inventory

def discover(reader,inventory,pid):
    found=[]
    for row in inventory:
        if not any(o['type']=='SkinnedMeshRenderer' for o in row['objects']):continue
        for obj in reader.load(row['bundle']).objects:
            if obj.type.name!='SkinnedMeshRenderer':continue
            t=obj.read_typetree();go=reader.pointer(obj,t['m_GameObject']);g=go.read_typetree()
            tr=next(reader.pointer(go,c['component']) for c in g['m_Component'] if reader.pointer(go,c['component']).type.name=='Transform')
            while tr.read_typetree()['m_Father']['m_PathID']:tr=reader.pointer(tr,tr.read_typetree()['m_Father'])
            name=reader.pointer(tr,tr.read_typetree()['m_GameObject']).read_typetree()['m_Name'];match=re.fullmatch(r'PET_0?(\d+)_(\d+)_Model',name,re.I)
            if not match or int(match[1])!=pid:continue
            found.append({'pet_id':pid,'skin':int(match[2]),'bundle':row['bundle'],'renderer':obj.path_id,'materials':[reader.pointer(obj,p).read_typetree()['m_Name'] for p in t['m_Materials']]})
    return found

def pet_stamp(reader,pid):
    names={p.name for p in reader.root.glob(f'initial_base_pet_{pid}_global-*.unity3d')}
    for name in list(names):names.update(reader.dependencies.get(name,[]))
    files=[reader.root/n for n in names if (reader.root/n).is_file()]
    return stamp(files+list(reader.root.glob('asset_manifest*.unity3d'))+[reader.root/'dbf.unity3d'])

def audio_file(clip,target):
    from UnityPy.helpers.ResourceReader import get_resource_data
    raw=bytes(clip.m_AudioData) if clip.m_AudioData else get_resource_data(clip.m_Resource.m_Source,clip.object_reader.assets_file,clip.m_Resource.m_Offset,clip.m_Resource.m_Size)
    if raw[:4]==b'RIFF':target.write_bytes(raw);return
    if raw[:4]==b'OggS':target.with_suffix('.ogg').write_bytes(raw);return target.with_suffix('.ogg')
    decoder=APP/'decoder/vgmstream-cli.exe'
    if not decoder.is_file():raise FileNotFoundError('缺少随程序提供的声音解码器，请完整解压便携版。')
    bank=target.with_suffix('.fsb');bank.write_bytes(raw)
    try:
        subprocess.run([str(decoder),'-o',str(target),str(bank)],check=True,capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if not target.is_file() or target.stat().st_size<44:raise ValueError('声音导出为空。')
    finally:bank.unlink(missing_ok=True)

def import_pet(game,data,pid):
    game=game_root(game);cache=install_cache(game,data);library=read_json(cache/'available.json')
    if data==game or game in data.parents:raise ValueError('本地缓存必须放在游戏安装目录之外。')
    if not library:raise ValueError('请先扫描炉石安装目录。')
    entries=[dict(c) for c in library['entries'] if c['petId']==pid]
    if not entries:raise ValueError('本地清单中没有所选宠物。')
    reader=reader_for(game,cache);signature=pet_stamp(reader,pid)
    saved=read_json(cache/f'pet-{pid}.json',{})
    if saved.get('signature')==signature and all(Path(c['localModel']).is_file() for c in saved.get('entries',[])) and saved.get('entries'):
        progress('已导入，直接使用本地缓存。');return
    inventory=inventory_for(reader,pid);candidates=discover(reader,inventory,pid)
    # Unique generations let a failed or cancelled import leave the last working copy intact.
    generation=cache/'assets'/f'{pid}-{signature}-{uuid.uuid4().hex[:8]}'
    generation.mkdir(parents=True,exist_ok=True);audio=generation/'audio';audio.mkdir()
    commands={'Emote_Greetings':'emotegreetingsvo01','Emote_Wow':'emotewowvo01','Emote_Threaten':'emotethreatenvo01','Reaction_Happy_Big':'reactionhappybigvo01','pet':'sequencepetinvo01'}
    voices=[(row['bundle'],o) for row in inventory for o in row['objects'] if o['type']=='AudioClip']
    for entry in entries:
        skin=entry['skin'];progress('正在导入 '+entry['name']+'…')
        if not any(c['skin']==skin for c in candidates):raise ValueError(f"{entry['name']} 的模型尚未下载或格式不受支持，请更新游戏资源后重试。")
        model=export_model(reader,inventory,candidates,generation,pid,skin);folder=generation/f'pet_{pid}_{skin}'
        icon=folder/'icon.png';obj,_,_=reader.resolve(entry['iconRef']);obj.read().image.save(icon)
        sounds={}
        for command,ending in commands.items():
            options=[(b,o) for b,o in voices if o['name'].lower().replace('_','').endswith(ending)]
            options=[(b,o) for b,o in options if f'{pid}_{skin}_' in o['name'] or not re.search(r'\d+_[1-4]_',o['name'])]
            options.sort(key=lambda p:(f'{pid}_{skin}_' not in p[1]['name'],p[1]['name']))
            if not options:continue
            bundle,source=options[0];target=audio/(safe_name(source['name'])+'.wav')
            if not target.exists():
                clip=next(o for o in reader.load(bundle).objects if o.path_id==source['id']).read();target=audio_file(clip,target) or target
            sounds[command]=target.as_uri()
        soundfile=folder/'sounds.js';soundfile.write_text('window.PET_SOUNDS='+json.dumps(sounds)+';',encoding='utf-8')
        entry.update({'model':(folder/'pet-data.js').as_uri(),'localModel':str(folder/'pet-data.js'),'icon':str(icon),'preview':str(folder/'preview.png'),'sounds':soundfile.as_uri() if sounds else None,'clips':[c['name'] for c in model['clips']]})
    write_json(cache/f'pet-{pid}.json',{'signature':signature,'entries':entries})
    progress('导入完成。')
