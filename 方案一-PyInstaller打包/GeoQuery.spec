# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates')],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'engineio.async_drivers.threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',
        'Pillow',
        'matplotlib',
        'scipy',
        'numpy.testing',
        'numpy.random',
        'numpy.fft',
        'numpy.linalg',
        'numpy.core.tests',
        'numpy.distutils',
        'numpy.f2py',
        'numpy.ma',
        'numpy.matrixlib',
        'numpy.polynomial',
        'numpy._core.tests',
        'numpy._pyinstaller',
        'pandas.tests',
        'pandas.io.sas',
        'pandas.io.formats.style',
        'pandas.io.stata',
        'pandas.io.parquet',
        'pandas.io.feather_format',
        'pandas.io.gbq',
        'pandas.io.spss',
        'pandas.io.sql',
        'tkinter',
        'tkinter.ttk',
        '_tkinter',
        'unittest',
        'doctest',
        'xmlrpc',
        'pydoc',
        'pdb',
        'difflib',
        'argparse',
        'email',
        'html.parser',
        'http.server',
        'py_compile',
        'zipfile',
        'tarfile',
        'csv',
        'sqlite3',
        '_sqlite3',
        'ssl',
        '_ssl',
        'lzma',
        '_lzma',
        'bz2',
        '_bz2',
        'ftplib',
        'imaplib',
        'smtplib',
        'telnetlib',
        'xml.etree',
        'xml.dom',
        'xml.sax',
        'pyexpat',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeoQuery',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

EXCLUDE_BINARIES = {
    'libopenblas64__v0.3.21-gcc_10_3_0.dll',
    'libcrypto-1_1.dll',
    'libssl-1_1.dll',
    'sqlite3.dll',
}

filtered_binaries = [
    (name, path, typecode)
    for name, path, typecode in a.binaries
    if os.path.basename(name) not in EXCLUDE_BINARIES
]

coll = COLLECT(
    exe,
    filtered_binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeoQuery',
)
