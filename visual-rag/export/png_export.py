import os
from playwright.sync_api import sync_playwright

def export_to_png(html_path: str, png_path: str = None) -> str:
    """
    Launches headless Playwright chromium to load the generated HTML page
    and capture a high-resolution PNG screenshot.
    """
    if not png_path:
        png_path = html_path.replace(".html", ".png")
        
    abs_html = os.path.abspath(html_path)
    abs_png = os.path.abspath(png_path)
    
    print(f"[PNG Export] Loading file {abs_html}...")
    
    try:
        with sync_playwright() as p:
            # Launch chromium (headless)
            browser = p.chromium.launch()
            # Set a premium viewport size
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            
            # Navigate to the local file
            page.goto(f"file:///{abs_html}")
            
            # Wait for layout rendering and D3 animations to stabilize
            page.wait_for_timeout(2000)
            
            # Capture full page screenshot
            page.screenshot(path=abs_png, full_page=True)
            browser.close()
            
        print(f"[PNG Export] Saved screenshot: {abs_png}")
        return abs_png
    except Exception as e:
        safe_msg = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"[ERROR] PNG export failed: {safe_msg}")
        # Hint at running playwright install if binaries are missing
        if "Executable" in str(e) or "playwright install" in str(e).lower():
            print("[PNG Export] Hint: You may need to run 'playwright install chromium' to fetch browser binaries.")
        raise e
