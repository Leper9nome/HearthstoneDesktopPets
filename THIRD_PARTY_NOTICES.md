# Third-party software and source availability

The project's MIT license covers its original code. It does not relicense game content or third-party components. Neither the source repository nor portable archive includes Hearthstone models, textures, audio, icons, exported data tables or pet screenshots.

## Source components

- **砰砰解析台 / PengPeng Workbench**: https://github.com/AsaMisogi/Heartstone-Tool-Resource-Lab — MIT, Copyright (c) 2026 朝禊ASOGI. The local Unity reader under `vendor/pengpeng` is derived from revision `331301b00258780f2a8c1a613c4ce00c8a6413aa`. License: `licenses/PENGPENG-LICENSE.txt`. Related architecture originally references Hermes: https://github.com/Fbigame/Hermes; its ISC attribution is retained in `licenses/HERMES-LICENSE.txt`.
- **Three.js**: https://github.com/mrdoob/three.js — MIT; included as local JavaScript modules with `licenses/THREE-LICENSE.txt`.
- **App icon**: the paw-shaped `app.svg` is original project artwork, covered by this project's MIT license.

## Portable runtime

- **CPython 3.13.5** — Python Software Foundation license. Source: https://www.python.org/downloads/release/python-3135/ . The build copies `PYTHON-LICENSE.txt`.
- **PySide6 / Shiboken6 6.8.3 / Qt 6.8.3** — open-source LGPLv3/GPL terms as specified by each component. Qt libraries are dynamically linked and remain replaceable in `_internal`. This project places no restriction on reverse engineering for debugging modifications to LGPL components. License texts are included in `licenses/`. Corresponding sources: https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz and https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.8.3 . Qt WebEngine includes Chromium and other independently licensed components; its upstream third-party notices and source are part of the Qt WebEngine sources. The `qtwebengine` attribution is accessible through the embedded engine's `qtwebengine://qt` page when using the stock engine.
- **UnityPy 1.25.4** — MIT; https://github.com/K0lb3/UnityPy . Build-time modification to `export/__init__.py` changes eager exporter imports to a lazy `__getattr__`; its full implementation is in `scripts/build.py`. FMOD extraction is excluded from the portable build.
- **Pillow, lz4, Brotli, texture2ddecoder, etcpak, astc-encoder-py, fsspec, attrs, tpk-ar and archspec** — each keeps its own upstream license. The build copies installed package license files and records versions in `DEPENDENCIES.json`. Source distributions are available at the versioned PyPI links included in `_internal/licenses/dependencies`.

## Audio decoder

**vgmstream r2168**, unmodified official Windows x64 release: https://github.com/vgmstream/vgmstream/releases/tag/r2168 . Source: https://github.com/vgmstream/vgmstream/tree/r2168 . The decoder package is downloaded during build with a pinned SHA-256 and retains its COPYING, README and USAGE files.

vgmstream uses an ISC-style license. Its DLL dependencies include FFmpeg (LGPL), mpg123 (LGPL), libvorbis, CELT and Speex (BSD-style licenses). Source and build instructions: https://github.com/vgmstream/vgmstream/blob/r2168/doc/BUILD.md and the release's associated build configuration. Upstream component sources are available at https://ffmpeg.org/download.html, https://www.mpg123.de/download.shtml, https://downloads.xiph.org/releases/vorbis/, https://downloads.xiph.org/releases/celt/ and https://downloads.xiph.org/releases/speex/ . The binary decoder and its DLLs are kept separate and replaceable.

The portable distribution does not bundle FMOD libraries. Installing UnityPy's regular Python dependencies for development may install fmod_toolkit transitively; those binaries are explicitly excluded from release output.
