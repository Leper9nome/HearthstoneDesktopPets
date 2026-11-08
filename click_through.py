"""Let Windows route clicks through empty pixels without resizing the pet."""
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QObject,QTimer,Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

user32=ctypes.windll.user32
user32.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
user32.GetWindowLongW.restype=ctypes.c_long
user32.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_long]
user32.SetWindowLongW.restype=ctypes.c_long
user32.GetAsyncKeyState.argtypes=[ctypes.c_int]
user32.GetAsyncKeyState.restype=ctypes.c_short
TRANSPARENT=0x20

def mouse_down():return any(user32.GetAsyncKeyState(key)&0x8000 for key in (1,2,4,5,6))

class ClickThrough(QObject):
    def __init__(self,view):
        super().__init__(view);self.view=view;self.pending=False;self.generation=0
        self.timer=QTimer(self);self.timer.setTimerType(Qt.PreciseTimer);self.timer.setInterval(16)
        self.timer.timeout.connect(self.poll);view.loadStarted.connect(self.loading);self.timer.start()

    def set_transparent(self,enabled):
        if not self.view.testAttribute(Qt.WA_WState_Created):return
        hwnd=int(self.view.winId());style=user32.GetWindowLongW(hwnd,-20)
        desired=(style|TRANSPARENT) if enabled else (style&~TRANSPARENT)
        if desired!=style:user32.SetWindowLongW(hwnd,-20,desired)

    def loading(self):
        self.generation+=1;self.pending=False;self.set_transparent(True)

    def poll(self):
        # Preserve capture for pet drags and for drags that began in other apps.
        if mouse_down() or QApplication.activePopupWidget():return
        if not self.view.isVisible() or self.view.windowOpacity()==0:
            self.set_transparent(True);return
        position=QCursor.pos();point=self.view.mapFromGlobal(position)
        if not self.view.rect().contains(point):
            self.set_transparent(True);return
        if self.pending:return
        self.pending=True;generation=self.generation
        def received(hit):
            if generation!=self.generation:return
            self.pending=False
            try:
                if QCursor.pos()!=position or mouse_down() or QApplication.activePopupWidget():return
                if not self.view.isVisible() or self.view.windowOpacity()==0:self.set_transparent(True);return
                self.set_transparent(not bool(hit))
            except RuntimeError:
                pass  # The WebEngine callback can arrive after the window is destroyed.
        self.view.page().runJavaScript(f'window.petHitTest?petHitTest({point.x()},{point.y()},{self.view.width()},{self.view.height()}):false',received)
