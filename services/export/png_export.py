import os
from playwright.sync_api import sync_playwright


def export_to_png(html_path: str, png_path: str = None) -> str:
    """Headless Chromium screenshot of an HTML file to PNG."""
    if not png_path:
        png_path = html_path.replace(".html", ".png")
    abs_html = os.path.abspath(html_path)
    abs_png = os.path.abspath(png_path)
    print(f"[PNG Export] Loading {abs_html}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"file:///{abs_html}")
            page.wait_for_timeout(2000)
            page.screenshot(path=abs_png, full_page=True)
            browser.close()
        print(f"[PNG Export] Saved {abs_png}")
        return abs_png
    except Exception as e:
        safe_msg = str(e).encode("ascii", "ignore").decode("ascii")
        print(f"[ERROR] PNG export failed: {safe_msg}")
        if "Executable" in str(e) or "playwright install" in str(e).lower():
            print("[PNG Export] Hint: run 'playwright install chromium' to fetch browser binaries.")
        raise e
