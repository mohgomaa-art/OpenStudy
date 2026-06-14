import os
from playwright.sync_api import sync_playwright

def export_to_pdf(html_path: str, pdf_path: str = None) -> str:
    """
    Launches headless Playwright chromium to load the generated HTML page
    and capture a high-resolution PDF document.
    """
    if not pdf_path:
        pdf_path = html_path.replace(".html", ".pdf")
        
    abs_html = os.path.abspath(html_path)
    abs_pdf = os.path.abspath(pdf_path)
    
    print(f"[PDF Export] Loading file {abs_html}...")
    
    try:
        with sync_playwright() as p:
            # Launch chromium (headless) with local file permissions to allow cross-origin iframe resizing
            browser = p.chromium.launch(args=[
                "--allow-file-access-from-files",
                "--disable-web-security"
            ])
            # Set viewport to portrait aspect ratio to match standard Letter dimensions
            page = browser.new_page(viewport={"width": 1024, "height": 1325})
            
            # Navigate to the local file
            page.goto(f"file:///{abs_html}")
            
            # Wait for layout rendering, animations, and iframes to stabilize
            page.wait_for_timeout(2000)

            # Auto-resize nested iframes to prevent content clipping in chat session exports
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
                            // Add extra padding to prevent accidental vertical scrollbars
                            iframe.style.height = (height + 25) + 'px';
                            iframe.style.overflow = 'visible';
                            doc.body.style.overflow = 'visible';
                            doc.body.style.height = 'auto';
                        }
                    });
                } catch (e) {
                    console.error("Iframe auto-resize failed:", e);
                }
            """)
            page.wait_for_timeout(500)

            # Inject CSS to override dark theme to premium print-ready light theme in all frames
            css_content = """
                /* 1. Hide interactive user interface elements */
                button,
                a.button,
                .controls-overlay,
                [onclick*="zoom"],
                [onclick*="resetZoom"],
                [onclick*="prevCard"],
                [onclick*="nextCard"],
                [onclick*="markAsLearnt"],
                [onclick*="prevStep"],
                [onclick*="nextStep"],
                [onclick*="clearSymptoms"],
                [onclick*="resetGame"],
                .pointer-events-none,
                .absolute.bottom-4.right-4,
                .absolute.top-4.left-4 {
                    display: none !important;
                }

                /* 2. Page and main scrollable layout reset */
                html, body {
                    background-color: #ffffff !important;
                    background: #ffffff !important;
                    color: #1e293b !important;
                    overflow: visible !important;
                    height: auto !important;
                    min-height: 0 !important;
                    margin: 0 !important;
                    padding: 20px !important;
                }

                main, #root {
                    background-color: #ffffff !important;
                    background: #ffffff !important;
                    overflow: visible !important;
                    height: auto !important;
                    min-height: 0 !important;
                    display: block !important;
                    width: 100% !important;
                }

                /* 3. Panel/container overrides */
                .glass-panel {
                    background-color: #ffffff !important;
                    background: #ffffff !important;
                    border-color: #e2e8f0 !important;
                    color: #334155 !important;
                    box-shadow: none !important;
                    backdrop-filter: none !important;
                    -webkit-backdrop-filter: none !important;
                    height: auto !important;
                    min-height: 0 !important;
                    max-height: none !important;
                    overflow: visible !important;
                }

                /* Reset fixed heights on visual panels (e.g. mindmap, concept_tree, etc.) */
                .w-full.h-\[600px\],
                .w-full.h-\[650px\],
                [class*="h-\["] {
                    height: auto !important;
                    min-height: 0 !important;
                    max-height: none !important;
                    overflow: visible !important;
                }

                /* Force SVGs to expand to full size instead of collapsing or locking */
                svg, .mindmap-svg {
                    width: 100% !important;
                    height: auto !important;
                    max-height: none !important;
                    overflow: visible !important;
                    background-color: #ffffff !important;
                    background: #ffffff !important;
                }

                /* 4. Override Tailwind background colors (dark styles to light styles) */
                [class*="bg-zinc-"], 
                [class*="bg-slate-"], 
                [class*="bg-black"], 
                [class*="bg-gray-"], 
                [class*="bg-neutral-"],
                [class*="bg-purple-950"],
                [class*="bg-zinc-950"] {
                    background-color: #f8fafc !important;
                    background-image: none !important;
                }

                /* Remove gradient colors */
                [class*="from-"], [class*="via-"], [class*="to-"] {
                    background-image: none !important;
                    background-color: #f8fafc !important;
                }

                /* 5. Override text colors for high readability */
                [class*="text-white"], 
                [class*="text-zinc-100"], 
                [class*="text-zinc-200"], 
                [class*="text-slate-100"], 
                [class*="text-slate-200"] {
                    color: #0f172a !important;
                }

                [class*="text-zinc-300"], 
                [class*="text-zinc-400"], 
                [class*="text-slate-300"], 
                [class*="text-slate-400"] {
                    color: #334155 !important;
                }

                [class*="text-zinc-500"],
                [class*="text-slate-500"] {
                    color: #64748b !important;
                }

                /* 6. Override border colors */
                [class*="border-zinc-"], 
                [class*="border-slate-"], 
                [class*="border-white"] {
                    border-color: #cbd5e1 !important;
                }

                /* Keep accent colors for links/lines inside SVG */
                path.connector-line, line, .flow-arrow {
                    stroke-opacity: 0.8 !important;
                }

                /* Specific template adjustments */
                .timeline-card {
                    background-color: #f8fafc !important;
                    border-color: #e2e8f0 !important;
                }
                .summary-card {
                    background-color: #ffffff !important;
                    border-color: #cbd5e1 !important;
                }

                /* Explicit overrides for older/fallback chat export formats */
                .title {
                    color: #0f172a !important;
                }
                .message-row {
                    page-break-inside: avoid !important;
                }
                .message-user {
                    background-color: #f1f5f9 !important;
                    border-color: #cbd5e1 !important;
                    color: #0f172a !important;
                }
                .message-assistant {
                    background-color: #ffffff !important;
                    border-color: #e2e8f0 !important;
                    color: #334155 !important;
                }
                .sender-user {
                    color: #2563eb !important;
                }
                .sender-assistant {
                    color: #059669 !important;
                }
                
                /* Clean up inline whites and darks */
                [style*="color:#ffffff"], [style*="color: #ffffff"] {
                    color: #0f172a !important;
                }
                [style*="color:#f1f5f9"], [style*="color: #f1f5f9"] {
                    color: #1e293b !important;
                }
                [style*="color:#e2e8f0"], [style*="color: #e2e8f0"] {
                    color: #334155 !important;
                }
                [style*="color:#cbd5e1"], [style*="color: #cbd5e1"] {
                    color: #475569 !important;
                }
                [style*="background:#0d0d0d"] {
                    background: #f8fafc !important;
                    color: #0f172a !important;
                    border-color: #e2e8f0 !important;
                }
                [style*="background:#161925"] {
                    background: #f1f5f9 !important;
                    border-color: #cbd5e1 !important;
                    color: #0f172a !important;
                }
                [style*="background:rgba(30,30,40,0.6)"] {
                    background: #f8fafc !important;
                    border-color: #cbd5e1 !important;
                }
                [style*="background:#1a1c29"], [style*="background: #1a1c29"] {
                    background: #f0f9ff !important;
                    color: #1e293b !important;
                }
                [style*="background:#11261d"], [style*="background: #11261d"] {
                    background: #f0fdf4 !important;
                    color: #1e293b !important;
                }
                [style*="background:#251229"], [style*="background: #251229"] {
                    background: #faf5ff !important;
                    color: #1e293b !important;
                }
                [style*="background:#2a1515"], [style*="background: #2a1515"] {
                    background: #fef2f2 !important;
                    color: #1e293b !important;
                }
            """

            for frame in page.frames:
                try:
                    frame.add_style_tag(content=css_content)
                except Exception as ex:
                    pass
            
            # Generate PDF (print background to ensure styled panels are colored)
            page.pdf(
                path=abs_pdf, 
                format="Letter", 
                print_background=True, 
                margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"}
            )
            browser.close()
            
        print(f"[PDF Export] Saved PDF: {abs_pdf}")
        return abs_pdf
    except Exception as e:
        safe_msg = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"[ERROR] PDF export failed: {safe_msg}")
        # Hint at running playwright install if binaries are missing
        if "Executable" in str(e) or "playwright install" in str(e).lower():
            print("[PDF Export] Hint: You may need to run 'playwright install chromium' to fetch browser binaries.")
        raise e
