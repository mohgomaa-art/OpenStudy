import os
from playwright.sync_api import sync_playwright


def export_to_pdf(html_path: str, pdf_path: str = None) -> str:
    """Headless Chromium print of an HTML file to PDF, with light-theme overrides for chat export."""
    if not pdf_path:
        pdf_path = html_path.replace(".html", ".pdf")
    abs_html = os.path.abspath(html_path)
    abs_pdf = os.path.abspath(pdf_path)
    print(f"[PDF Export] Loading {abs_html}...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=[
                "--allow-file-access-from-files",
                "--disable-web-security",
            ])
            page = browser.new_page(viewport={"width": 1024, "height": 1325})
            page.goto(f"file:///{abs_html}")
            page.wait_for_timeout(2000)

            # Resize nested iframes so embedded content doesn't get clipped
            page.evaluate("""
                try {
                    const iframes = document.querySelectorAll('iframe');
                    iframes.forEach(iframe => {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        if (doc && doc.body) {
                            const height = Math.max(
                                doc.body.scrollHeight,
                                doc.documentElement.scrollHeight,
                                doc.body.offsetHeight,
                                doc.documentElement.offsetHeight
                            );
                            iframe.style.height = (height + 25) + 'px';
                            iframe.style.overflow = 'visible';
                            doc.body.style.overflow = 'visible';
                            doc.body.style.height = 'auto';
                        }
                    });
                } catch (e) { console.error("Iframe resize failed:", e); }
            """)
            page.wait_for_timeout(500)

            css_content = """
                button, a.button, .controls-overlay,
                [onclick*="zoom"], [onclick*="resetZoom"],
                [onclick*="prevCard"], [onclick*="nextCard"],
                [onclick*="markAsLearnt"], [onclick*="prevStep"], [onclick*="nextStep"],
                [onclick*="clearSymptoms"], [onclick*="resetGame"],
                .pointer-events-none,
                .absolute.bottom-4.right-4, .absolute.top-4.left-4 { display: none !important; }
                html, body {
                    background: #ffffff !important; color: #1e293b !important;
                    overflow: visible !important; height: auto !important;
                    min-height: 0 !important; margin: 0 !important; padding: 20px !important;
                }
                main, #root {
                    background: #ffffff !important; overflow: visible !important;
                    height: auto !important; min-height: 0 !important;
                    display: block !important; width: 100% !important;
                }
                .glass-panel {
                    background: #ffffff !important; border-color: #e2e8f0 !important;
                    color: #334155 !important; box-shadow: none !important;
                    backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
                    height: auto !important; min-height: 0 !important;
                    max-height: none !important; overflow: visible !important;
                }
                [class*="h-\\["] { height: auto !important; min-height: 0 !important; max-height: none !important; overflow: visible !important; }
                svg, .mindmap-svg { width: 100% !important; height: auto !important; max-height: none !important; overflow: visible !important; background: #ffffff !important; }
                [class*="bg-zinc-"], [class*="bg-slate-"], [class*="bg-black"], [class*="bg-gray-"], [class*="bg-neutral-"], [class*="bg-purple-950"], [class*="bg-zinc-950"] { background-color: #f8fafc !important; background-image: none !important; }
                [class*="from-"], [class*="via-"], [class*="to-"] { background-image: none !important; background-color: #f8fafc !important; }
                [class*="text-white"], [class*="text-zinc-100"], [class*="text-zinc-200"], [class*="text-slate-100"], [class*="text-slate-200"] { color: #0f172a !important; }
                [class*="text-zinc-300"], [class*="text-zinc-400"], [class*="text-slate-300"], [class*="text-slate-400"] { color: #334155 !important; }
                [class*="text-zinc-500"], [class*="text-slate-500"] { color: #64748b !important; }
                [class*="border-zinc-"], [class*="border-slate-"], [class*="border-white"] { border-color: #cbd5e1 !important; }
                .title { color: #0f172a !important; }
                .message-row { page-break-inside: avoid !important; }
                .message-user { background: #f1f5f9 !important; border-color: #cbd5e1 !important; color: #0f172a !important; }
                .message-assistant { background: #ffffff !important; border-color: #e2e8f0 !important; color: #334155 !important; }
                .sender-user { color: #2563eb !important; }
                .sender-assistant { color: #059669 !important; }
            """
            for frame in page.frames:
                try:
                    frame.add_style_tag(content=css_content)
                except Exception:
                    pass

            page.pdf(
                path=abs_pdf,
                format="Letter",
                print_background=True,
                margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"},
            )
            browser.close()
        print(f"[PDF Export] Saved {abs_pdf}")
        return abs_pdf
    except Exception as e:
        safe_msg = str(e).encode("ascii", "ignore").decode("ascii")
        print(f"[ERROR] PDF export failed: {safe_msg}")
        if "Executable" in str(e) or "playwright install" in str(e).lower():
            print("[PDF Export] Hint: run 'playwright install chromium' to fetch browser binaries.")
        raise e
