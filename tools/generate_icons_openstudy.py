"""
Regenerate all Tauri bundle icons + tray icon from the new OpenStudy logomark.

Uses Playwright (already available) to rasterize the square SVG favicon to a
1024x1024 master PNG, then Pillow to fan out to every size Tauri's bundler
references (see tauri.conf.json -> bundle.icon).
"""
import os
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SQUARE_SVG = ROOT / "frontend" / "public" / "favicon.svg"
ICON_DIR = ROOT / "frontend" / "src-tauri" / "icons"
PUBLIC_DIR = ROOT / "frontend" / "public"
MASTER_PNG = ROOT / "tools" / "openstudy_master_1024.png"

PNG_SIZES = {
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
    "icon.png": 512,
    "icon_source.png": 1024,
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
}

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def rasterize_svg_to_png(svg_path: Path, out_path: Path, size: int = 1024) -> None:
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<style>html,body{{margin:0;padding:0;background:transparent;}}
svg{{display:block;width:{size}px;height:{size}px;}}</style></head>
<body>{svg_path.read_text(encoding='utf-8')}</body></html>"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size})
        page.set_content(html, wait_until="domcontentloaded")
        page.evaluate("document.fonts.ready")
        elem = page.query_selector("svg")
        elem.screenshot(path=str(out_path), omit_background=True)
        browser.close()


def main() -> int:
    if not SQUARE_SVG.exists():
        print(f"ERROR: missing {SQUARE_SVG}")
        return 1

    ICON_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Rasterizing {SQUARE_SVG.name} -> {MASTER_PNG.name} @ 1024x1024 ...")
    rasterize_svg_to_png(SQUARE_SVG, MASTER_PNG, size=1024)

    master = Image.open(MASTER_PNG).convert("RGBA")
    print(f"Master image mode={master.mode} size={master.size}")

    for name, sz in PNG_SIZES.items():
        out = ICON_DIR / name
        master.resize((sz, sz), Image.Resampling.LANCZOS).save(out)
        print(f"  wrote {out.relative_to(ROOT)}")

    ico_imgs = [master.resize(s, Image.Resampling.LANCZOS) for s in ICO_SIZES]
    ico_out = ICON_DIR / "icon.ico"
    ico_imgs[0].save(ico_out, format="ICO", sizes=ICO_SIZES, append_images=ico_imgs[1:])
    print(f"  wrote {ico_out.relative_to(ROOT)}")

    try:
        icns_out = ICON_DIR / "icon.icns"
        master.resize((1024, 1024), Image.Resampling.LANCZOS).save(icns_out, format="ICNS")
        print(f"  wrote {icns_out.relative_to(ROOT)}")
    except Exception as e:
        print(f"  WARN: ICNS write failed ({e}); leaving existing icon.icns in place")

    tray = master.resize((32, 32), Image.Resampling.LANCZOS)
    tray_out = PUBLIC_DIR / "tray_icon.png"
    tray.save(tray_out)
    print(f"  wrote {tray_out.relative_to(ROOT)}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
