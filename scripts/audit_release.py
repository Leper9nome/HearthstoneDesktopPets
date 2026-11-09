"""Fail closed: release source uses an explicit list, not an exclusion-only copy."""
import argparse,hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE_FILES={
 'main.py','paths.py','desktop_pet.py','manager.py','camera_settings.py','importer.py','export_model.py','animation_sampling.py','click_through.py','bubble_menu.py','menu_assets.py',
 'app.svg','camera.svg','camera.json','README.md','LICENSE','THIRD_PARTY_NOTICES.md','.gitignore',
 'requirements.txt','requirements-build.txt','requirements.lock',
 'web/index.html','web/viewer.js','web/ground-shadow.js','web/bubble-menu.js','web/bubble-menu.css','web/idle-actions.js','web/eye-material.js','web/three.core.js','web/three.module.js',
 'vendor/__init__.py','vendor/pengpeng/__init__.py','vendor/pengpeng/unity.py','vendor/pengpeng/bundle.py','vendor/pengpeng/common.py','vendor/pengpeng/storage.py',
 'scripts/build.py','scripts/audit_release.py','scripts/hooks/hook-PySide6.QtQml.py','tests/test_core.py','tests/test_camera_settings.py','tests/test_ui.py','tests/test_click_through.py','tests/test_ground_shadow.py','tests/test_eye_material.py','tests/test_texture_wrapping.py','tests/test_bubble_menu.py','.github/workflows/build.yml'
}
FORBIDDEN={'.unity3d','.fsb','.wav','.ogg','.mp3','.sqlite3','.ini','.lnk'}

def source_files():
    files=[ROOT/name for name in SOURCE_FILES]
    files+=list((ROOT/'licenses').rglob('*.txt'))
    if any(not p.is_file() for p in files):raise ValueError('Source manifest references a missing file')
    return sorted(files)

def audit_files(files,base):
    names=[]
    for path in files:
        name=path.relative_to(base).as_posix();lower=name.lower()
        if path.suffix.lower() in FORBIDDEN or Path(lower).name in ('pet-data.js','catalog.js','library.json','available.json','source.json','preferences.ini','card-name.ttf','menu-assets.js','menu-ui.json'):
            raise ValueError('Game asset or user data in release: '+name)
        if any(part in ('pets','cache','audio','璧勬枡','menu-assets') for part in Path(lower).parts):raise ValueError('Local cache in release: '+name)
        if path.suffix in ('.js','.json'):
            content=path.read_text(encoding='utf-8')
            if 'window.PET_DATA=' in content or 'window.PET_SOUNDS=' in content:raise ValueError('Exported game data in release: '+name)
        names.append(name)
    return names

def source_zip(output):
    files=source_files();audit_files(files,ROOT)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in files:archive.write(path,'HearthstoneDesktopPets/'+path.relative_to(ROOT).as_posix())
    return len(files)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-zip');args=p.parse_args()
    count=source_zip(args.source_zip) if args.source_zip else len(audit_files(source_files(),ROOT))
    print(f'PASS: {count} explicitly allowed source files; no exported game assets')
