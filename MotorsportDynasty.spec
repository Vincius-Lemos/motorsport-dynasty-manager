# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('data', 'data'),
    ('gui', 'gui'),
    ('game', 'game'),
]
binaries = []
hiddenimports = [
    'game.i18n',
    'game.career',
    'game.driver_career',
    'game.manager_career',
    'game.player_profile',
    'game.save_load',
    'game.offers',
    'game.transfer_market',
    'game.super_licence',
    'game.academies',
    'game.injuries',
    'game.qualifying',
    'game.race_engine',
    'game.models',
    'game.housing',
    'game.job_search',
    'gui.scenes',
    'gui.widgets',
    'gui.theme',
    'gui.app',
]
tmp_ret = collect_all('pygame')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['play.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MotorsportDynasty',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
