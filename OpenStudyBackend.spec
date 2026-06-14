# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('docs', 'docs'), ('services', 'services'), ('magic_engine', 'magic_engine')],
    hiddenimports=['uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.loops.auto', 'uvicorn.loops.asyncio', 'uvicorn.lifespan.on', 'uvicorn.lifespan.off', 'sqlite3', 'google.genai', 'google.genai.types', 'google.auth', 'google.auth.transport.requests', 'httpx', 'openai', 'anthropic', 'groq', 'fitz', 'docx', 'pptx', 'multipart', 'starlette.middleware.cors', 'starlette.responses', 'email_validator'],
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
    name='OpenStudyBackend',
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
