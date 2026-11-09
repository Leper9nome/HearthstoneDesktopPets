"""Build an asset-free Windows folder distribution and source archive."""
import argparse,hashlib,importlib.util,importlib.metadata,json,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_release import ROOT,audit_files,source_zip

DECODER_URL='https://github.com/vgmstream/vgmstream/releases/download/r2168/vgmstream-win64.zip'
DECODER_SHA256='692d45070852a35c1fa42726aa3c9de528e44eec925d37d99b1074256b99a229'
PACKAGES=['PySide6','PySide6-Essentials','PySide6-Addons','shiboken6','UnityPy','Pillow','lz4','brotli','texture2ddecoder','etcpak','astc-encoder-py','fsspec','attrs','tpk-ar','archspec']

def decoder():
    folder=ROOT/'decoder';folder.mkdir(exist_ok=True)
    archive=ROOT/'build/decoder.zip';archive.parent.mkdir(exist_ok=True)
    if not archive.exists():urllib.request.urlretrieve(DECODER_URL,archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=DECODER_SHA256:raise ValueError('Decoder checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).name!=name:raise ValueError('Unexpected decoder archive path')
        z.extractall(folder)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'dist');parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    decoder()
    if args.prepare_only:return
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    work=ROOT/'build';work.mkdir(exist_ok=True)
    # UnityPy eagerly imports its optional FMOD exporter even for textures.
    # Lazy exports keep its public API while allowing our vgmstream-only build.
    unity=Path(importlib.util.find_spec('UnityPy').origin).parent
    exports=unity/'export/__init__.py';original=exports.read_bytes()
    exports.write_text("from importlib import import_module\n__all__=['AudioClipConverter','MeshExporter','MeshRendererExporter','SpriteHelper','Texture2DConverter']\ndef __getattr__(name):\n    if name in __all__:\n        value=import_module('.'+name,__name__);globals()[name]=value;return value\n    raise AttributeError(name)\n",encoding='utf-8')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--name','HearthstoneDesktopPets','--paths',str(ROOT),'--additional-hooks-dir',str(ROOT/'scripts/hooks'),'--distpath',str(output),'--workpath',str(work/'pyinstaller'),'--specpath',str(work),
      '--exclude-module','fmod_toolkit','--exclude-module','pyfmodex','--exclude-module','UnityPy.export.AudioClipConverter','--exclude-module','numpy','--collect-data','UnityPy','--collect-data','archspec',
      '--hidden-import','UnityPy.export.Texture2DConverter','--hidden-import','UnityPy.export.SpriteHelper','--hidden-import','UnityPy.export.MeshExporter']
    for name in ['web','app.svg','camera.svg','camera.json','decoder','licenses','LICENSE','THIRD_PARTY_NOTICES.md']:
        command+=['--add-data',str(ROOT/name)+';'+(name if (ROOT/name).is_dir() else '.')]
    command.append(str(ROOT/'main.py'))
    try:subprocess.run(command,check=True,cwd=ROOT)
    finally:exports.write_bytes(original)
    portable=output/'HearthstoneDesktopPets'
    shutil.copy2(ROOT/'README.md',portable/'README.md');shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.md',portable/'THIRD_PARTY_NOTICES.md')
    notices=portable/'_internal/licenses/dependencies';notices.mkdir(parents=True,exist_ok=True)
    versions={}
    for name in PACKAGES:
        distribution=importlib.metadata.distribution(name);versions[name]=distribution.version
        dest=notices/name;dest.mkdir(exist_ok=True)
        for path in distribution.files or []:
            if any(part.lower() in ('licenses','license') for part in path.parts) or path.name.lower().startswith(('license','copying','notice')):
                source=Path(distribution.locate_file(path))
                if source.is_file():
                    target=dest/(hashlib.sha256(str(path).encode()).hexdigest()[:6]+'-'+path.name);shutil.copy2(source,target)
        (dest/'SOURCE.txt').write_text(f'{name} {distribution.version}\nhttps://pypi.org/project/{name}/{distribution.version}/\n',encoding='utf-8')
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.exists():shutil.copy2(python_license,notices/'PYTHON-LICENSE.txt')
    (portable/'DEPENDENCIES.json').write_text(json.dumps(versions,indent=2),encoding='utf-8')
    files=[p for p in portable.rglob('*') if p.is_file()]
    audit_files(files,portable)
    if any('fmod' in p.name.lower() for p in files):raise ValueError('FMOD must not be redistributed in this build')
    archive=output/'HearthstoneDesktopPets-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in files:z.write(path,'HearthstoneDesktopPets/'+path.relative_to(portable).as_posix())
    source=output/'HearthstoneDesktopPets-source.zip';source_zip(source)
    (output/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in [archive,source])+'\n',encoding='ascii')
    (output/'release-audit.json').write_text(json.dumps({'asset_scan':'passed','files':len(files),'fmod_binaries':0,'archives':[archive.name,source.name]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Built asset-free portable and source archives:',output)

if __name__=='__main__':main()
