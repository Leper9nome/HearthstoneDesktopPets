# The app uses WebEngineWidgets and has no external QML interface or QML imports.
from PyInstaller.utils.hooks.qt import add_qt6_dependencies
hiddenimports,binaries,datas=add_qt6_dependencies(__file__)
