import argparse
import os
import glob
import json
import webbrowser
from pipeline import Pipeline
import config
from export import export_to_png, export_to_anki, export_to_pdf
from rich.console import Console
from rich.table import Table

console = Console()

def get_latest_file() -> str:
    """Finds the most recently modified HTML file in the output directory."""
    files = glob.glob(os.path.join(config.OUTPUT_DIR, "*.html"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def main():
    parser = argparse.ArgumentParser(
        description="Visual Learning RAG — Local AI Study Assistant v1.0"
    )
    sub = parser.add_subparsers(dest="command")

    # Ingest Command
    p_ingest = sub.add_parser("ingest", help="Parse and index documents into ChromaDB")
    p_ingest.add_argument("path", help="Absolute or relative path to file/folder to ingest")

    # Search Command
    p_search = sub.add_parser("search", help="Search the local vector knowledge base")
    p_search.add_argument("query", help="Search string query")
    p_search.add_argument("-n", type=int, default=config.DEFAULT_N_RESULTS, help="Number of results to retrieve")
    p_search.add_argument("--type", default=None, help="Filter by cognitive knowledge type")

    # Generate Command
    p_gen = sub.add_parser("generate", help="Create interactive HTML visual study aids")
    p_gen.add_argument("query", help="Study concept/query to generate visualizer for")
    p_gen.add_argument("--type", default="auto", choices=[
        "auto", "mind_map", "flashcard", "flowchart", "timeline",
        "comparison_table", "ddx_matrix", "cycle_diagram", "drag_drop",
        "sequence_builder", "wordle_game", "boss_battle", "clinical_vignette",
        "summary_sheet", "mnemonic_card", "concept_tree", "pathophysiology_flow",
        "anatomy_cross_section", "mcq_single_best", "true_false_streak"
    ], help="Override automatic template selection")
    p_gen.add_argument("--open", action="store_true", help="Open generated file in browser immediately")
    p_gen.add_argument("--png", action="store_true", help="Capture and export visual page as PNG")
    p_gen.add_argument("--pdf", action="store_true", help="Capture and export visual page as PDF")
    p_gen.add_argument("--anki", action="store_true", help="Export as Anki deck (applies to flashcard visuals)")

    # Last Command
    sub.add_parser("last", help="Open the latest generated HTML visual in browser")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    pipe = Pipeline()

    if args.command == "ingest":
        console.print(f"[bold purple]Starting Ingest on:[/bold purple] {args.path}")
        try:
            pipe.ingest(args.path)
            console.print("[bold green]✔ Ingestion completed successfully.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Ingest Error:[/bold red] {e}")

    elif args.command == "search":
        console.print(f"[bold purple]Searching knowledge base for:[/bold purple] '{args.query}' (filter: {args.type})")
        try:
            results = pipe.search_kb(args.query, args.n, args.type)
            if not results:
                console.print("[yellow]No relevant chunks found.[/yellow]")
                return
                
            table = Table(title=f"Search Results for: '{args.query}'", show_header=True, header_style="bold magenta")
            table.add_column("Score", style="dim", width=8)
            table.add_column("Source", style="cyan", width=20)
            table.add_column("Location (Page/Section)", style="green", width=22)
            table.add_column("Cognitive Type", style="yellow", width=15)
            table.add_column("Snippet (first 80 chars)", style="white")

            for r in results:
                score_str = f"{r['score']:.3f}"
                meta = r["meta"]
                loc_str = f"Page {meta.get('page', 1)} ({meta.get('section', 'Gen')})"
                k_type = meta.get("knowledge_type", "mixed")
                snippet = r["text"].replace("\n", " ")[:80] + "..."
                table.add_row(score_str, meta.get("source", "Unknown"), loc_str, k_type, snippet)
                
            console.print(table)
        except Exception as e:
            console.print(f"[bold red]Search Error:[/bold red] {e}")

    elif args.command == "generate":
        console.print(f"[bold purple]Generating visual aid for concept:[/bold purple] '{args.query}'")
        try:
            # Generate HTML
            out_file = pipe.generate(args.query, args.type)
            console.print(f"[bold green]✔ Visualizer generated successfully:[/bold green] {out_file}")
            
            # Browser Open
            if args.open:
                abs_path = os.path.abspath(out_file)
                console.print(f"[cyan]Opening in default browser:[/cyan] {abs_path}")
                webbrowser.open(f"file:///{abs_path}")
                
            # PNG screenshot export
            if args.png:
                console.print("[cyan]Capturing high-resolution PNG screenshot via Playwright...[/cyan]")
                png_file = export_to_png(out_file)
                console.print(f"[bold green]✔ Saved PNG screenshot:[/bold green] {png_file}")
                
            # PDF export
            if args.pdf:
                console.print("[cyan]Capturing high-resolution PDF document via Playwright...[/cyan]")
                pdf_file = export_to_pdf(out_file)
                console.print(f"[bold green]✔ Saved PDF document:[/bold green] {pdf_file}")
                
            # Anki APKG export
            if args.anki:
                # To get the flashcard JSON, we extract dataset const in generated HTML
                # Or we can generate it again, but since we have the output html path,
                # let's look at its companion JSON or extract it.
                # Actually, it's easier to verify if the template type was flashcard.
                # If we parsed it, we can inspect output html or re-generate.
                # Let's inspect the html file for VISUAL_DATA
                try:
                    with open(out_file, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    start_str = "const VISUAL_DATA = "
                    start_idx = html_content.find(start_str)
                    if start_idx != -1:
                        end_idx = html_content.find(";", start_idx)
                        json_str = html_content[start_idx + len(start_str):end_idx].strip()
                        visual_json = json.loads(json_str)
                        
                        if visual_json.get("template") == "flashcard":
                            console.print("[cyan]Exporting flashcards to Anki package...[/cyan]")
                            apkg_file = export_to_anki(visual_json)
                            console.print(f"[bold green]✔ Saved Anki deck package:[/bold green] {apkg_file}")
                        else:
                            console.print("[yellow]Anki export is only supported for 'flashcard' visual templates.[/yellow]")
                except Exception as ex:
                    console.print(f"[bold red]Anki Export Error:[/bold red] {ex}")
                    
        except Exception as e:
            console.print(f"[bold red]Generation Error:[/bold red] {e}")

    elif args.command == "last":
        latest = get_latest_file()
        if not latest:
            console.print("[bold yellow]No generated visualizers found in output folder.[/bold yellow]")
        else:
            abs_path = os.path.abspath(latest)
            console.print(f"[bold purple]Opening latest visualizer:[/bold purple] {abs_path}")
            webbrowser.open(f"file:///{abs_path}")

if __name__ == "__main__":
    main()
