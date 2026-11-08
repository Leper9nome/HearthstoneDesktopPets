"""Application files are read-only; all user data lives outside the source tree."""
import os,sys,json
from pathlib import Path

APP=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

def data_dir(override=None):
    root=Path(override) if override else Path(os.environ.get('LOCALAPPDATA',Path.home()))/'HearthstoneDesktopPets'
    root=root.resolve()
    code_root=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else APP
    if root==code_root or code_root in root.parents:
        raise ValueError('请选择程序目录之外的数据目录，避免将本地素材混入源码或发布包。')
    root.mkdir(parents=True,exist_ok=True)
    return root

def read_json(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:return default

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
