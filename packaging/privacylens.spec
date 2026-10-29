# Build with: pyinstaller packaging/privacylens.spec (run from the repo root, see build_exe.bat)
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path(SPECPATH).parent

datas = [
    (str(root / "web"), "web"),
    (str(root / "scenarios"), "scenarios"),
    (str(root / "config"), "config"),
    (str(root / "eval" / "results.json"), "eval"),
    (str(root / "eval" / "run_eval.py"), "eval"),
    (str(root / "eval" / "adversarial_cases.json"), "eval"),
    (str(root / ".env.example"), "."),
]
binaries = []
hiddenimports = [
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on",
    "multipart", "anyio._backends._asyncio", "psutil", "httpx", "dotenv", "PIL",
]

# The playwright package carries its node driver; cv2 carries the Haar cascade xml files.
for package in ("playwright", "cv2"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += collect_data_files("cv2")

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["app.server", "app.agent", "app.runner"],
    excludes=["pytest", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PrivacyLens", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="PrivacyLens")
