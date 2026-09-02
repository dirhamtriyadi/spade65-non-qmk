# Third-Party Notices

This notice accompanies prebuilt Spade65 desktop distributions. Spade65 itself
is released under the MIT license in LICENSE. The desktop distributions also
contain or interoperate with the components listed below. License identifiers
are SPDX expressions where upstream publishes one.

Versions below match the pinned release dependency manifest. The Linux release
uses the current CPython 3.13 patch selected by setup-python. Windows and the
universal macOS build use CPython 3.12.10 because pysysaudio 0.1.3 publishes
verified native wheels through CPython 3.12.

## Offline license bundle

Every release artifact contains the complete texts below:

- licenses/PERMISSIVE-LICENSES.txt: pywebview, Bottle, proxy_tools,
  cython-hidapi, QtPy, SoundCard, pysysaudio, pythonnet, clr_loader, cffi,
  pycparser, PyObjC, and the Microsoft WebView2 SDK LICENSE and NOTICE.
- licenses/NUMPY-2.1.3-LINUX-WHEEL-LICENSE.txt: NumPy's BSD terms plus the
  complete aggregate notices shipped by the Python 3.10/3.11 fallback wheel.
- licenses/NUMPY-2.5.2-LINUX-WHEEL-LICENSES.txt: every license file shipped by
  the pinned Python 3.12+ manylinux x86_64 wheel, including its aggregate
  OpenBLAS, LAPACK, libgfortran, and libquadmath notices.
- licenses/PYTHON-3.12.txt: CPython 3.12.10.
- licenses/PYTHON-3.13.txt: CPython 3.13.15 and typing_extensions 4.16.0.
- licenses/PYINSTALLER.txt: PyInstaller 6.22.2, its Bootloader Exception, and
  pyinstaller-hooks-contrib 2026.7.
- licenses/LGPL-3.0.txt, licenses/GPL-3.0.txt, and licenses/LGPL-2.1.txt:
  GNU terms shipped with the Linux PySide6/Qt distribution.
- licenses/Qt-6.11.2-LICENSE.Chromium: Chromium's BSD notice shipped by Qt
  WebEngine 6.11.2.
- licenses/QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html: an offline aggregate
  of all 126 unique attribution pages linked by Qt's official WebEngine 6.11.2
  licensing index, including component copyrights and license texts.
- licenses/GFDL-1.3-no-invariants-only.txt: the license covering the Qt
  documentation material reproduced by that offline aggregate.
- licenses/AppImage-type2-runtime-75849dc-LICENSE and
  licenses/AppImage-appimagetool-1.9.1-LICENSE: verbatim upstream terms for
  the embedded pinned AppImage runtime and the pinned packaging tool.

In the Linux AppImage these paths are rooted at
usr/share/doc/spade65/licenses. In the macOS application they are rooted at
Contents/Resources/Legal/licenses; the DMG also includes them at its root. The
Windows ZIP includes them in its top-level licenses directory. This offline
directory is intentionally a cross-platform superset. The presence of a
license text does not mean its component is bundled in every artifact; the
platform-specific component tables below define the actual runtime scope.

## Common runtime components

| Component | Version | License | Source |
| --- | --- | --- | --- |
| CPython | 3.12.10 (Windows/macOS); 3.13.x (Linux) | PSF-2.0 | <https://www.python.org/downloads/source/> |
| pywebview | 6.2.1 | BSD-3-Clause | <https://github.com/r0x0r/pywebview/tree/6.2.1> |
| Bottle | 0.13.4 | MIT | <https://github.com/bottlepy/bottle/tree/0.13.4> |
| proxy_tools | 0.1.0 | PyPI metadata says MIT; upstream LICENSE.txt is BSD-style | <https://github.com/jtushman/proxy_tools/blob/master/LICENSE.txt> |
| typing_extensions | 4.16.0 | PSF-2.0 | <https://github.com/python/typing_extensions/tree/4.16.0> |
| cython-hidapi | 0.15.0 | BSD-3-Clause option selected | <https://pypi.org/project/hidapi/0.15.0/#files> |

pywebview copyright (c) 2014-2017 Roman Sirokov. Bottle copyright (c)
2009-2024 Marcel Hellkamp. cython-hidapi copyright 2011 Gary Bishop. The PyPI
metadata for proxy_tools 0.1.0 labels it MIT, while its upstream LICENSE.txt
contains BSD-style terms; the offline bundle conservatively reproduces that
upstream LICENSE.txt verbatim.

CPython and typing_extensions use the Python Software Foundation License
Version 2. Their complete texts are included offline in
licenses/PYTHON-3.12.txt and licenses/PYTHON-3.13.txt.

## Linux AppImage: PySide6 and Qt

| Component | Version | License option used | Source |
| --- | --- | --- | --- |
| QtPy | 2.4.3 | MIT | <https://github.com/spyder-ide/qtpy/tree/v2.4.3> |
| PySide6 | 6.11.2 | LGPL-3.0-only | <https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.2> |
| PySide6-Addons | 6.11.2 | LGPL-3.0-only | same PySide source |
| PySide6-Essentials | 6.11.2 | LGPL-3.0-only | same PySide source |
| shiboken6 | 6.11.2 | LGPL-3.0-only | same PySide source |
| Qt libraries from the PySide6 wheels | 6.11.2 | upstream module-specific terms; LGPL-3.0 is selected for LGPL-covered libraries | <https://download.qt.io/official_releases/qt/6.11/6.11.2/single/> |
| Qt WebEngine and Chromium third-party code | Qt 6.11.2 snapshot | LGPL-3.0 for LGPL-covered Qt code; BSD and other terms for Chromium code | <https://code.qt.io/cgit/qt/qtwebengine.git/tag/?h=v6.11.2> |
| SoundCard | 0.4.6 | BSD-3-Clause | <https://github.com/bastibe/SoundCard/tree/0.4.6> |
| NumPy | 2.1.3 (Python 3.10/3.11); 2.5.2 (Python 3.12+) | BSD-3-Clause plus bundled-component terms | <https://github.com/numpy/numpy/tree/v2.5.2> |
| AppImage type-2 runtime | commit 75849dc | MIT plus the statically linked component terms named by upstream | <https://github.com/AppImage/type2-runtime/tree/75849dc> |
| appimagetool build tool | 1.9.1 | MIT; used at build time and not embedded as a tool | <https://github.com/AppImage/appimagetool/tree/1.9.1> |

The PySide6 metadata offers LGPL-3.0-only OR GPL-2.0-only OR
GPL-3.0-only. This distribution uses the LGPL-3.0-only option. The complete
LGPL version 3 text is in licenses/LGPL-3.0.txt. Because LGPL version 3
incorporates GPL version 3, the complete incorporated GPL text is in
licenses/GPL-3.0.txt. Including these texts does not change the MIT license of
the independently written Spade65 application.

These two files are verbatim copies of
<https://www.gnu.org/licenses/lgpl-3.0.txt> and
<https://www.gnu.org/licenses/gpl-3.0.txt>.
The complete QtPy MIT text is included in
licenses/PERMISSIVE-LICENSES.txt.
The exact Qt 6.11.2 LICENSE.Chromium and LGPL-2.1-or-later texts are included
as licenses/Qt-6.11.2-LICENSE.Chromium and licenses/LGPL-2.1.txt.

SoundCard uses the host PulseAudio-compatible server (including PipeWire's
PulseAudio service). Its complete BSD text is in
licenses/PERMISSIVE-LICENSES.txt. The NumPy manylinux wheel carries OpenBLAS,
LAPACK, libgfortran, and libquadmath. Every license file from the official
Python 3.12+ package wheel is preserved verbatim in
licenses/NUMPY-2.5.2-LINUX-WHEEL-LICENSES.txt; the Python 3.10/3.11 fallback
aggregate is in licenses/NUMPY-2.1.3-LINUX-WHEEL-LICENSE.txt.

Qt WebEngine includes Chromium and other third-party projects, including
components under LGPL 2/2.1 and numerous permissive licenses. Their exact
Qt-published attributions and terms are reproduced offline in
licenses/QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html. The document is generated
from Qt's official 6.11.2 licensing index and all 126 unique detail pages using
tools/update_qtwebengine_credits.py. It is a conservative superset of the
notices applicable to the unmodified PySide6 wheels. Those terms are separate
from the LGPL terms for Qt code.

The official Ubuntu-built AppImage also contains an artifact-derived inventory
at `usr/share/doc/spade65/linux-system-libraries`. Its JSON manifest maps every
system-origin native file in PyInstaller's COLLECT table to the owning dpkg
package and version; `dpkg-copyright/` contains each available Debian copyright
file. The official build fails if any such mapping is missing. A manual build
on a non-dpkg distribution instead records a clearly labeled source-path-only
inventory and does not claim complete system-package attribution.

### Corresponding source and relinking

The AppImage is assembled from the unmodified PySide6 6.11.2 wheels published
on PyPI. Spade65 does not intentionally patch Qt or PySide source. PyInstaller
may adjust binary loader search paths when assembling a relocatable directory.

Exact corresponding upstream source is available from:

- PySide and Shiboken 6.11.2:
  <https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.2>
- Qt 6.11.2 source:
  <https://download.qt.io/official_releases/qt/6.11/6.11.2/single/>
- Qt WebEngine 6.11.2 and its Chromium snapshot:
  <https://code.qt.io/cgit/qt/qtwebengine.git/tag/?h=v6.11.2>
- Spade65 application source and packaging scripts: the Git tag matching the
  downloaded release at
  <https://github.com/dirhamtriyadi/spade65-non-qmk>

The Qt libraries are dynamically linked. A recipient can inspect or replace
them as follows:

1. Run ./Spade65-Linux-x86_64.AppImage --appimage-extract.
2. Locate the libraries under
   squashfs-root/usr/lib/spade65/_internal/PySide6/Qt/lib/.
3. Replace applicable shared objects with ABI-compatible builds from the
   corresponding source above, preserving required sonames and dependencies.
4. Run the modified tree using squashfs-root/AppRun. Repacking is optional. To
   redistribute a new AppImage, use the appimagetool and runtime versions
   documented in packaging/build_linux.sh.

Spade65 applies no signature or technical restriction that prevents running
the extracted AppDir with compatible replacement libraries. The project does
not warrant compatibility with arbitrary modified Qt builds.

## Windows desktop components

| Component | Version | License | Source |
| --- | --- | --- | --- |
| pythonnet | 3.1.0 | MIT | <https://github.com/pythonnet/pythonnet/tree/v3.1.0> |
| clr_loader | 0.3.1 | MIT | <https://pypi.org/project/clr-loader/0.3.1/#files> |
| cffi | 2.1.1 | MIT-0 | <https://pypi.org/project/cffi/2.1.1/#files> |
| pycparser | 3.0 | BSD-3-Clause | <https://pypi.org/project/pycparser/3.0/#files> |
| pysysaudio | 0.1.3 | MIT | <https://github.com/scottjg/pysysaudio/tree/v0.1.3> |
| Microsoft WebView2 SDK assemblies delivered by pywebview | 1.0.3856.49 | BSD-3-Clause plus bundled third-party notices | <https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49> |

pythonnet copyright (c) 2006-2021 the contributors of the Python.NET project.
clr_loader copyright (c) 2019-2026 Benedikt Reinartz. pycparser copyright (c)
2008-2022 Eli Bendersky. Their complete texts and cffi's MIT-0 text are
included in licenses/PERMISSIVE-LICENSES.txt. pysysaudio's MIT text is included
there as well; the packaged CPython 3.12 wheel supplies the native WASAPI
loopback extension without bundling an audio driver.

The Microsoft Edge WebView2 Runtime and .NET Framework are system
prerequisites, not bundled components. Their installed versions are determined
by the target Windows machine. The SDK package's complete LICENSE.txt and
NOTICE.txt are reproduced in licenses/PERMISSIVE-LICENSES.txt.

## macOS desktop components

| Component | Version | License | Source |
| --- | --- | --- | --- |
| pyobjc-core | 12.2.2 | MIT | <https://pypi.org/project/pyobjc-core/12.2.2/#files> |
| pyobjc-framework-Cocoa | 12.2.2 | MIT | <https://pypi.org/project/pyobjc-framework-Cocoa/12.2.2/#files> |
| pyobjc-framework-Quartz | 12.2.2 | MIT | <https://pypi.org/project/pyobjc-framework-Quartz/12.2.2/#files> |
| pyobjc-framework-WebKit | 12.2.2 | MIT | <https://pypi.org/project/pyobjc-framework-WebKit/12.2.2/#files> |
| pyobjc-framework-Security | 12.2.2 | MIT | <https://pypi.org/project/pyobjc-framework-Security/12.2.2/#files> |
| pyobjc-framework-UniformTypeIdentifiers | 12.2.2 | MIT | <https://pypi.org/project/pyobjc-framework-UniformTypeIdentifiers/12.2.2/#files> |
| pysysaudio | 0.1.3 | MIT | <https://github.com/scottjg/pysysaudio/tree/v0.1.3> |

Copyright is held by Ronald Oussoren and other PyObjC contributors. Apple Cocoa
and WebKit are system frameworks and are not bundled in the DMG. The complete
PyObjC MIT text is included in licenses/PERMISSIVE-LICENSES.txt.
pysysaudio's MIT text is in the same file. Its universal2 native extension uses
the system Core Audio tap API; it requires macOS 14.2 or newer for system-audio
capture and does not bundle an audio driver.

## Build tooling present in the executables

The executable bundles contain the PyInstaller 6.22.2 bootloader. PyInstaller
is GPL-2.0-or-later WITH Bootloader-exception. Copyright (c) 2010-2023 the
PyInstaller Development Team; copyright (c) 2005-2009 Giovanni Bajo; based on
previous work copyright (c) 2002 McMillan Enterprises, Inc. The exact license
and Bootloader Exception are at
<https://github.com/pyinstaller/pyinstaller/blob/v6.22.2/COPYING.txt>.

The complete COPYING text, Bootloader Exception, and pinned community-hook
license are reproduced in licenses/PYINSTALLER.txt.

All third-party trademarks belong to their respective owners. These notices do
not grant trademark rights or imply endorsement.
