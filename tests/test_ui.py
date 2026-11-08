"""Optional real-game integration test; output stays in the supplied data directory."""
import sys,json,traceback,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import data_dir
from desktop_pet import Desktop,Page
from manager import PetManager
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);parser.add_argument('--game');args=parser.parse_args()
app=QApplication(sys.argv);view=QWebEngineView();view.setPage(Page(view));view.resize(630,630);view.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint);view.setAttribute(Qt.WA_TranslucentBackground);view.page().setBackgroundColor(QColor(0,0,0,0))
bridge=Desktop(view);channel=QWebChannel(view.page());channel.registerObject('desktop',bridge);view.page().setWebChannel(channel)
data=data_dir(args.data_dir);manager=PetManager(view,bridge,data);phase=0

def loaded(raw):
    global phase
    try:
        r=json.loads(raw)
        if r['variant']!=manager.selected['id']:return
        assert not r['errors'] and r['renderFrames']>0
        assert view.windowOpacity()==0
        manager.ready(raw);assert view.windowOpacity()==1
        if phase==0:
            phase=1;view.page().runJavaScript('petZoom(.35)',lambda _:manager.select('nightmare'))
        elif phase==1:
            assert abs(r['view']['zoom']-1.35)<1e-8;phase=2;manager.select('deathling')
        else:
            assert abs(r['view']['zoom']-1.35)<1e-8
            manager.panel.grab().save(str(data/'panel-test.png'))
            manager.panel.close();assert not manager.panel.isVisible() and manager.tray.isVisible() and view.isVisible()
            manager.open_panel();assert manager.panel.isVisible()
            assert manager.settings.value('selected')=='deathling'
            print('PASS: local scan/import, assets, audio, preview, pet/skin switching, zoom and tray',flush=True)
            manager.quit()
    except Exception:traceback.print_exc();app.exit(1)

bridge.ready_callback=loaded;manager.start()
if args.game and not manager.catalog:manager.start_job('scan',game=args.game)
elif not manager.catalog:
    assert not manager.pets.isEnabled() and not view.isVisible()
    manager.panel.grab().save(str(data/'empty-panel-test.png'))
    print('PASS: empty first launch opens without game assets',flush=True)
    QTimer.singleShot(300,manager.quit)
QTimer.singleShot(180000,lambda:app.exit(2));sys.exit(app.exec())
