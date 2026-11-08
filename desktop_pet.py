"""Offline transparent desktop host for the extracted Ysera model."""
import json, sys, ctypes, os
from pathlib import Path
from PySide6.QtCore import Qt, QUrl, QObject, Slot, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel

from paths import APP

class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        if 'Error' in str(level):
            print(f'JS {source}:{line}: {message}',flush=True)

class Desktop(QObject):
    def __init__(self,view):
        super().__init__(view)
        self.view=view
        self.muted=True
        self.view_locked=False
        self.variant={'clips':[],'pet':''}
        self.ready_callback=None
        self.open_panel=None
        self.quit_callback=None

    @Slot()
    def ready(self):
        self.view.page().runJavaScript('if(window.petReady){petMute('+json.dumps(self.muted)+');petSetViewLocked('+json.dumps(self.view_locked)+')}')
        if self.ready_callback:
            self.view.page().runJavaScript('JSON.stringify(petCheck())',self.ready_callback)
    @Slot()
    def dragWindow(self):
        if self.view.windowHandle():
            self.view.windowHandle().startSystemMove()

    @Slot()
    def quit(self):
        if self.quit_callback:self.quit_callback()
        else:QApplication.quit()

    @Slot()
    def menu(self):
        menu=QMenu(self.view)
        clips=set(self.variant['clips'])
        if {'Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out'}<=clips:
            menu.addAction('摸摸她' if self.variant['pet']=='ysera' else '摸摸它',lambda:self.view.page().runJavaScript('petCommand("pet")'))
        for label,command in [('打个招呼','Emote_Greetings'),('开心一下','Reaction_Happy_Big'),('惊叹','Emote_Wow'),('威吓一下','Emote_Threaten'),('飞起来','Sequence_Flying_Idle'),('回到待机','Idle_Neutral')]:
            if command in clips:menu.addAction(label,lambda c=command:self.view.page().runJavaScript('petCommand('+json.dumps(c)+')'))
        menu.addSeparator()
        lock=menu.addAction('锁定视角')
        lock.setCheckable(True)
        lock.setChecked(self.view_locked)
        lock.toggled.connect(self.set_view_locked)
        reset=menu.addAction('恢复默认视角',lambda:self.view.page().runJavaScript('petResetView()'))
        reset.setEnabled(not self.view_locked)
        menu.addSeparator()
        if self.variant.get('sounds'):menu.addAction('开启声音' if self.muted else '关闭声音',self.toggle_sound)
        if self.open_panel:menu.addAction('打开管理面板',self.open_panel)
        menu.addAction('退出',self.quit)
        menu.exec(QCursor.pos())

    def toggle_sound(self):
        self.muted=not self.muted
        self.view.page().runJavaScript('petMute('+json.dumps(self.muted)+')')

    def set_view_locked(self,locked):
        self.view_locked=locked
        self.view.page().runJavaScript('petSetViewLocked('+json.dumps(locked)+')')

def run(data,check=False):
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Personal.HearthstoneDesktopPets')
    app=QApplication(sys.argv);app.setApplicationName('炉石桌面伙伴')
    import hashlib
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    server_name='HearthstoneDesktopPets-'+hashlib.sha256(str(data).lower().encode()).hexdigest()[:12]
    existing=QLocalSocket();existing.connectToServer(server_name)
    if existing.waitForConnected(300):
        existing.write(b'open');existing.waitForBytesWritten(300);return 0
    server=QLocalServer();server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(server_name):raise RuntimeError('无法建立本地面板入口：'+server.errorString())
    view=QWebEngineView();view.setWindowTitle('炉石桌面伙伴')
    view.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
    view.setAttribute(Qt.WA_TranslucentBackground);view.setStyleSheet('background:transparent')
    page=Page(view);view.setPage(page);page.setBackgroundColor(QColor(0,0,0,0))
    page.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls,True)
    page.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls,False)
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    class LocalOnly(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self,request):
            if request.requestUrl().scheme() not in ('file','qrc','data','blob','about'):request.block(True)
    interceptor=LocalOnly(page);page.profile().setUrlRequestInterceptor(interceptor)
    channel=QWebChannel(page);desktop=Desktop(view);channel.registerObject('desktop',desktop);page.setWebChannel(channel)
    view.resize(630,630);rect=app.primaryScreen().availableGeometry();view.move(rect.right()-670,rect.bottom()-660)
    from manager import PetManager
    manager=PetManager(view,desktop,data)
    def reopen_panel():
        while server.hasPendingConnections():
            connection=server.nextPendingConnection();connection.disconnectFromServer();connection.deleteLater()
        manager.open_panel()
    server.newConnection.connect(reopen_panel);manager.start()
    if check:
        from paths import write_json
        diagnostic=QTimer(manager.panel);diagnostic.setInterval(250)
        def inspect():
            if manager.process:return
            if manager.catalog and not manager.loaded:return
            diagnostic.stop()
            def save(raw=None):
                state=json.loads(raw) if raw else {'empty':True}
                state.update({'panelVisible':manager.panel.isVisible(),'trayVisible':manager.tray.isVisible(),'petVisible':view.isVisible(),'opacity':view.windowOpacity()})
                manager.panel.grab().save(str(data/'diagnostic-panel.png'))
                write_json(data/'diagnostic.json',state);manager.quit()
            if manager.loaded:page.runJavaScript('JSON.stringify(petCheck())',save)
            else:save()
        diagnostic.timeout.connect(inspect);diagnostic.start()
        QTimer.singleShot(60000,lambda:app.exit(2))
    return app.exec()
