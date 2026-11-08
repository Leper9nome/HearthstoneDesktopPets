"""Selection panel, tray and background local-asset import."""
from bubble_menu import random_variant
import json,sys,base64,io,hashlib
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QUrlQuery,QTimer,QSettings,QSize,QProcess
from PySide6.QtGui import QIcon,QPixmap
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QPushButton,QComboBox,QVBoxLayout,QFrame,QSystemTrayIcon,QMenu,QFileDialog
from paths import APP,read_json

class Panel(QWidget):
    quitting=False
    def closeEvent(self,event):
        if self.quitting:event.accept();return
        self.hide();event.ignore()

class PetManager:
    def __init__(self,view,desktop,data):
        self.view=view;self.desktop=desktop;self.data=data
        self.settings=QSettings(str(data/'preferences.ini'),QSettings.IniFormat)
        self.catalog=[];self.selected=None;self.loaded=None;self.loaded_model=None;self.loaded_menu_assets=None
        self.library={};self.queue=[];self.process=None;self.busy=None;self.failed=set();self.quitting=False
        self.panel=Panel();self.panel.setWindowTitle('炉石桌面伙伴');self.panel.setWindowFlags(Qt.Window|Qt.WindowMinimizeButtonHint|Qt.WindowCloseButtonHint);self.panel.setFixedSize(420,570)
        icon=QIcon(str(APP/'app.svg'));self.panel.setWindowIcon(icon);QApplication.instance().setWindowIcon(icon);QApplication.instance().setQuitOnLastWindowClosed(False)
        self.panel.setStyleSheet('''
        QWidget { background:#151c24; color:#e8eef4; font-family:"Microsoft YaHei"; font-size:13px; }
        QLabel { background:transparent; }
        QLabel#title { font-size:21px; font-weight:600; }
        QLabel#muted { color:#95a6b7; font-size:12px; }
        QLabel#name { font-size:18px; font-weight:600; }
        QLabel#status { color:#83d8b6; font-size:12px; }
        QPushButton { background:#222d3a; border:1px solid #354253; border-radius:9px; padding:11px 8px; text-align:left; }
        QPushButton:hover { background:#2a3949; }
        QPushButton:checked { background:#203c3a; border:1px solid #78cfb0; }
        QPushButton:focus,QComboBox:focus { border:1px solid #9fe6d0; }
        QFrame#preview { background:#202b37; border:1px solid #344151; border-radius:12px; }
        QComboBox { background:#222d3a; border:1px solid #354253; border-radius:8px; padding:9px 12px; min-height:20px; }
        QComboBox::drop-down { border:0; width:28px; }
        QComboBox QAbstractItemView { background:#222d3a; selection-background-color:#376558; padding:6px; }
        ''')
        layout=QVBoxLayout(self.panel);layout.setContentsMargins(22,18,22,16);layout.setSpacing(9)
        title=QLabel('炉石桌面伙伴');title.setObjectName('title');layout.addWidget(title)
        self.subtitle=QLabel('首次使用，请选择本机炉石安装目录');self.subtitle.setObjectName('muted');layout.addWidget(self.subtitle)
        self.directory=QPushButton('选择炉石目录');self.directory.clicked.connect(self.choose_directory);layout.addWidget(self.directory)
        self.pets=QComboBox();self.pets.setAccessibleName('选择宠物');self.pets.setIconSize(QSize(28,28));self.pets.setMaxVisibleItems(10)
        self.pets.currentIndexChanged.connect(self.choose_pet);layout.addWidget(self.pets)
        card=QFrame();card.setObjectName('preview');cl=QVBoxLayout(card);cl.setContentsMargins(12,8,12,8);cl.setSpacing(3)
        self.preview=QLabel();self.preview.setFixedHeight(132);self.preview.setAlignment(Qt.AlignCenter);cl.addWidget(self.preview)
        self.name=QLabel('等待本地导入');self.name.setObjectName('name');self.name.setAlignment(Qt.AlignCenter);cl.addWidget(self.name)
        self.description=QLabel('游戏素材仅保存在你的电脑上');self.description.setObjectName('muted');self.description.setWordWrap(True);self.description.setAlignment(Qt.AlignCenter);cl.addWidget(self.description);layout.addWidget(card)
        self.skins=QComboBox();self.skins.setAccessibleName('当前宠物的皮肤');self.skins.currentIndexChanged.connect(self.choose_skin);layout.addWidget(self.skins)
        self.import_all=QPushButton('导入全部宠物');self.import_all.clicked.connect(self.import_everything);layout.addWidget(self.import_all)
        self.status=QLabel('请选择炉石目录。导入后可离线使用。');self.status.setObjectName('status');self.status.setWordWrap(True);self.status.setMinimumHeight(36);layout.addWidget(self.status)
        layout.addStretch();note=QLabel('关闭面板后继续陪伴 · 右击托盘可打开或退出');note.setObjectName('muted');layout.addWidget(note)
        self.tray=QSystemTrayIcon(icon,self.panel);self.tray.setToolTip('炉石桌面伙伴')
        self.tray_menu=QMenu();self.tray_menu.addAction('打开面板',self.open_panel);self.tray_menu.addSeparator();self.tray_menu.addAction('退出',self.quit);self.tray.setContextMenu(self.tray_menu);self.tray.activated.connect(self.tray_activated)
        desktop.random_pet=self.random_pet;desktop.open_panel=self.open_panel;desktop.ready_callback=self.ready;desktop.quit_callback=self.quit
        self.timeout=QTimer(self.panel);self.timeout.setSingleShot(True);self.timeout.timeout.connect(lambda:self.status.setText('画面加载未完成，请重新选择宠物或检查运行日志。'))
        self.job_timer=QTimer(self.panel);self.job_timer.setInterval(250);self.job_timer.timeout.connect(self.job_progress)
        self.reload_library();self.refresh_panel()

    def reload_library(self):
        self.library=read_json(self.data/'library.json',{})
        imported={}
        for pid in {c['petId'] for c in self.library.get('entries',[])}:
            record=read_json(Path(self.library['cache'])/f'pet-{pid}.json',{})
            source=next(c for c in self.library['entries'] if c['petId']==pid)
            if record.get('signature')!=source.get('sourceSignature'):continue
            for entry in record.get('entries',[]):
                if Path(entry['localModel']).is_file():imported[entry['id']]=entry
        self.catalog=[imported.get(c['id'],c) for c in self.library.get('entries',[])]
        # Application camera fixes also apply to previously imported models.
        camera=read_json(APP/'camera.json',{})
        for entry in self.catalog:
            preset=camera.get(entry['id'],{})
            if preset.get('viewAngles') and entry.get('preview'):
                stamp=hashlib.sha256(json.dumps(preset,sort_keys=True).encode()).hexdigest()[:12]
                entry['preview']=str(Path(entry['preview']).with_name('preview-'+stamp+'.png'))
            entry.update(preset)
        key=self.selected['id'] if self.selected else self.settings.value('selected','ysera')
        self.selected=next((c for c in self.catalog if c['id']==key),self.catalog[0] if self.catalog else None)
        (self.data/'catalog.js').write_text('window.PET_CATALOG='+json.dumps(self.catalog,ensure_ascii=False)+';window.PET_MENU_ASSETS='+json.dumps(self.library.get('menuAssets',{}))+';',encoding='utf-8')

    def refresh_panel(self):
        self.pets.blockSignals(True);self.pets.clear()
        for pet in dict.fromkeys(c['pet'] for c in self.catalog):
            c=next(c for c in self.catalog if c['pet']==pet)
            self.pets.addItem(QIcon(c.get('icon',str(APP/'app.svg'))),c['petName'],pet)
        self.skins.blockSignals(True);self.skins.clear()
        if self.selected:
            c=self.selected;self.pets.setCurrentIndex(self.pets.findData(c['pet']))
            for entry in self.catalog:
                if entry['pet']==c['pet']:self.skins.addItem(entry['name'],entry['id'])
            self.skins.setCurrentIndex(self.skins.findData(c['id']));self.name.setText(c['name']);self.description.setText(c['description'])
            preview=Path(c.get('preview',''))
            self.preview.setPixmap(QPixmap(str(preview if preview.is_file() else c.get('icon',APP/'app.svg'))).scaled(340,132,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.pets.blockSignals(False);self.skins.blockSignals(False)
        self.pets.setEnabled(bool(self.catalog));self.skins.setEnabled(bool(self.catalog));self.import_all.setEnabled(bool(self.catalog))
        if self.catalog:
            count=len({c['pet'] for c in self.catalog});ready=sum('model' in c for c in self.catalog)
            self.subtitle.setText(f'{count} 位伙伴 · {len(self.catalog)} 款外观 · 已导入 {ready} 款')
            self.directory.setText('重新选择 / 扫描炉石目录');self.directory.setToolTip(self.library.get('game',''))

    def choose_directory(self):
        path=QFileDialog.getExistingDirectory(self.panel,'选择炉石安装目录',self.library.get('game',''))
        if path:self.start_job('scan',game=path)

    def choose_pet(self,index):
        pet=self.pets.itemData(index)
        if not pet:return
        saved=self.settings.value('skin/'+pet)
        entry=next((c for c in self.catalog if c['pet']==pet and c['id']==saved),next(c for c in self.catalog if c['pet']==pet))
        self.select(entry['id'])

    def choose_skin(self,index):
        key=self.skins.itemData(index)
        if key:self.select(key)

    def select(self,key,retry=True):
        entry=next((c for c in self.catalog if c['id']==key),None)
        if entry is None:raise ValueError('未知的宠物或皮肤')
        self.selected=entry;self.refresh_panel()
        if 'model' not in entry:
            if retry:self.failed.discard(entry['petId'])
            if entry['petId'] not in self.failed:
                if entry['petId'] not in self.queue and self.busy!=('import',entry['petId']):self.queue.insert(0,entry['petId'])
                self.status.setText('正在准备本地素材…');self.pump()
            return
        assets=self.library.get('menuAssets',{})
        if self.loaded==key and self.loaded_model==entry['model'] and self.loaded_menu_assets==assets:return
        self.loaded_menu_assets=dict(assets)
        self.desktop.variant=entry;self.desktop.view_locked=False;self.view.setWindowTitle(entry['name']+' · 桌面伙伴')
        self.view.setWindowOpacity(0);self.view.show()
        url=QUrl.fromLocalFile(str(APP/'web/index.html'));query=QUrlQuery();query.addQueryItem('pet',key);query.addQueryItem('catalog',QUrl.fromLocalFile(str(self.data/'catalog.js')).toString());url.setQuery(query)
        self.status.setText('正在唤醒 '+entry['name']+'…');self.view.load(url);self.timeout.start(15000)

    def ready(self,raw):
        if not raw or not self.selected:return
        result=json.loads(raw)
        if result.get('variant')!=self.selected['id']:return
        self.timeout.stop()
        if result.get('errors'):self.status.setText('加载失败，请查看运行日志。');return
        self.view.setWindowOpacity(1);self.loaded=self.selected['id'];self.loaded_model=self.selected['model']
        self.settings.setValue('selected',self.loaded);self.settings.setValue('skin/'+self.selected['pet'],self.loaded);self.settings.sync()
        if not self.process:self.status.setText('●  已在桌面陪伴你')
        self.tray.setToolTip('炉石桌面伙伴 · '+self.selected['name'])
        preview=Path(self.selected['preview']);key=self.loaded
        if not preview.is_file():
            def save(value):
                if not value:return
                from PIL import Image
                im=Image.open(io.BytesIO(base64.b64decode(value.split(',')[1]))).convert('RGBA');box=im.getbbox()
                if box:im.crop(box).save(preview)
                if self.selected and self.selected['id']==key:self.refresh_panel()
            self.view.page().runJavaScript('petInspect()',save)
        print('Pet ready: '+self.loaded,flush=True)

    def import_everything(self):
        self.failed.clear()
        for pid in dict.fromkeys(c['petId'] for c in self.catalog if 'model' not in c):
            if pid not in self.queue and self.busy!=('import',pid):self.queue.append(pid)
        self.pump()
        if not self.process:self.status.setText('所有本地可用外观均已导入。')

    def pump(self):
        if self.process or not self.queue or self.quitting:return
        self.start_job('import',self.queue.pop(0))

    def start_job(self,mode,pid=None,game=None):
        if self.process:return
        self.busy=(mode,pid);self.job_game=game or self.library.get('game','');self.job_log=self.data/'import.log';self.job_log.write_text('',encoding='utf-8')
        self.directory.setEnabled(False);self.status.setText('正在读取本地资源…')
        self.process=QProcess(self.panel)
        args=[] if getattr(sys,'frozen',False) else [str(APP/'main.py')]
        args+=['--worker',mode,'--game',self.job_game,'--data-dir',str(self.data),'--job-log',str(self.job_log)]
        if pid is not None:args+=['--pet-id',str(pid)]
        self.process.finished.connect(self.job_finished)
        self.process.errorOccurred.connect(lambda error:self.job_finished(-1) if error==QProcess.FailedToStart else None)
        self.job_timer.start();self.process.start(sys.executable,args)

    def job_progress(self):
        if not self.process:return
        lines=self.job_log.read_text(encoding='utf-8',errors='replace').strip().splitlines()
        if lines:self.status.setText(lines[-1][:160])

    def job_finished(self,code,status=None):
        if not self.process:return
        mode,pid=self.busy;self.job_timer.stop();self.process.deleteLater();self.process=None;self.busy=None;self.directory.setEnabled(True)
        if self.quitting:return
        if code:
            self.failed.add(pid);lines=self.job_log.read_text(encoding='utf-8',errors='replace').strip().splitlines()
            self.status.setText(('读取失败：'+(lines[-1] if lines else '无法启动导入进程'))[:180]);self.status.setToolTip(str(self.job_log))
            self.pump();return
        self.reload_library();self.refresh_panel()
        if self.selected:self.select(self.selected['id'],retry=False)
        self.pump()

    def random_pet(self):
        entry=random_variant(self.catalog,self.selected)
        if entry:self.select(entry['id'])

    def open_panel(self):self.panel.showNormal();self.panel.raise_();self.panel.activateWindow()
    def tray_activated(self,reason):
        if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick):self.open_panel()
    def start(self):
        self.tray.show();self.open_panel()
        if self.selected and 'model' in self.selected:self.select(self.selected['id'])
        game=self.library.get('game')
        if game and Path(game).is_dir():self.start_job('scan',game=game)
    def quit(self):
        self.quitting=True;self.queue.clear();self.job_timer.stop()
        if self.process:
            self.process.kill();self.process.waitForFinished(3000)
        self.tray.hide();self.timeout.stop();self.panel.quitting=True;self.panel.close();self.view.close();QApplication.quit()
