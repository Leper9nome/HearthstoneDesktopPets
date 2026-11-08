"""Extract the emote bubbles and Chinese card-name font into the local cache."""
import hashlib,uuid
from pathlib import Path
from paths import read_json,write_json

def signature(reader,names):
    h=hashlib.sha256(b'bubble-menu-v1')
    for name in names:
        stat=(reader.root/name).stat();h.update(f'{name}:{stat.st_size}:{stat.st_mtime_ns}'.encode())
    return h.hexdigest()[:20]

def import_menu_assets(reader,cache):
    record=read_json(cache/'menu-ui.json',{})
    if record:
        try:
            if signature(reader,record['sources'])==record['signature'] and all(Path(p).is_file() for p in record['files']):return record['assets']
        except (OSError,KeyError):pass
    preferred='initial_base_global-c05a2d0e-texture-0.unity3d'
    bundles=sorted(reader.root.glob('initial_base_global-*-texture-*.unity3d'),key=lambda p:(p.name!=preferred,p.name))
    atlas=None;atlas_bundle=None
    for bundle in bundles:
        for obj in reader.load(bundle.name).objects:
            if obj.type.name=='Texture2D' and obj.read_typetree().get('m_Name')=='EmoteUI_Atlas':
                atlas=obj.read().image.convert('RGBA');atlas_bundle=bundle.name;break
        if atlas is not None:break
    if atlas is None:raise ValueError('本地客户端未找到 EmoteUI_Atlas 气泡图集')
    font_bundle='essential_base_zhcn-content-0.unity3d';font=None
    for obj in reader.load(font_bundle).objects:
        if obj.type.name=='Font':
            tree=obj.read_typetree()
            if tree.get('m_Name')=='GLEI00M_t':font=bytes(tree['m_FontData']);break
    if not font:raise ValueError('本地客户端未找到中文卡名隶书字体')
    sources=[atlas_bundle,font_bundle];stamp=signature(reader,sources)
    folder=cache/'menu-assets'/f'{stamp}-{uuid.uuid4().hex[:8]}';folder.mkdir(parents=True)
    assets={};files=[]
    # Atlas coordinates describe the three small bubbles and their purple highlights.
    for name,box in {'top':(0,0,280,224),'top-hover':(280,0,576,224),'middle':(0,448,288,640),'middle-hover':(288,448,592,640),'bottom':(0,224,280,448),'bottom-hover':(280,224,576,448)}.items():
        path=folder/(name+'.png');atlas.crop(tuple(round(v*atlas.width/1024) for v in box)).save(path);assets[name]=path.as_uri();files.append(str(path))
    path=folder/'card-name.ttf';path.write_bytes(font);assets['font']=path.as_uri();files.append(str(path))
    write_json(cache/'menu-ui.json',{'signature':stamp,'sources':sources,'files':files,'assets':assets})
    return assets
