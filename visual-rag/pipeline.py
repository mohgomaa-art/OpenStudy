import os
from pathlib import Path
from ingest import parse_file, parse_folder, classify_batch
from ingest.chunker import chunk_items
from db import store_chunks, search
from generate import route, suggest, generate_and_validate
from templates.renderer import render
import config

class Pipeline:
    def __init__(self):
        # Ensure outputs and study_db directories exist
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.DB_PATH, exist_ok=True)

    def ingest(self, path: str):
        """
        Ingest a file or a whole directory, parses contents,
        chunks them, runs the cognitive Knowledge Classifier pass,
        embeds them, and saves to ChromaDB.
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        parsed_files = {}
        if path_obj.is_dir():
            print(f"[Pipeline] Batch ingesting folder: {path}")
            parsed_files = parse_folder(str(path_obj))
        else:
            print(f"[Pipeline] Ingesting file: {path_obj.name}")
            try:
                parsed_files[path_obj.name] = parse_file(str(path_obj))
            except Exception as e:
                print(f"[ERROR] Failed to parse {path_obj.name}: {e}")
                return

        total_chunks = 0
        for filename, parsed_items in parsed_files.items():
            if not parsed_items:
                print(f"[Pipeline] No text extracted from {filename}. Skipping.")
                continue

            # 1. Chunking
            print(f"[Pipeline] Chunking parsed items for {filename}...")
            chunks = chunk_items(parsed_items)

            # 2. Knowledge Classifier LLM Pass
            print(f"[Pipeline] Running cognitive classifier pass on {len(chunks)} chunks for {filename}...")
            classified_chunks = classify_batch(chunks)
            total_chunks += len(classified_chunks)

            # 3. Database Storage (Includes batch embed + duplicate check)
            print(f"[Pipeline] Storing chunks for {filename} into ChromaDB...")
            store_chunks(classified_chunks, filename)

        print(f"[Pipeline] Ingest complete. Processed {len(parsed_files)} files, total {total_chunks} chunks.")

    def search_kb(self, query: str, n: int = None, knowledge_type: str = None) -> list[dict]:
        """Search the knowledge base vector DB with optional filters."""
        if n is None:
            n = config.DEFAULT_N_RESULTS
        print(f"[Pipeline] Searching for: '{query}' (top-{n}, filter: {knowledge_type})...")
        return search(query, n, knowledge_type_filter=knowledge_type)

    def suggest_visual(self, query: str) -> dict:
        """Retrieves context chunks and returns the suggested visual template with rationale."""
        retrieved = self.search_kb(query, n=config.DEFAULT_N_RESULTS)
        suggestion = suggest(query, retrieved)
        return {
            "suggestion": suggestion,
            "retrieved_chunks": retrieved
        }

    def generate(self, query: str, visual_type: str = "auto") -> str:
        """
        End-to-end generation v1.0:
        1. Searches ChromaDB for relevant concept chunks.
        2. Routes query to template (dominant knowledge_type or query override).
        3. Prompts LLM to output structured JSON with Pydantic self-correcting validation.
        4. Renders interactive HTML.
        """
        # 1. Retrieval
        retrieved = self.search_kb(query, n=config.DEFAULT_N_RESULTS)
        
        # 2. Routing
        if visual_type == "auto":
            dominant_source = None
            if retrieved:
                dominant_source = retrieved[0].get("meta", {}).get("source")
                
            recent_templates = []
            if dominant_source:
                try:
                    from services.lean_memory import memory_layer
                    recent_templates = memory_layer.get_recent_templates(dominant_source, limit=3)
                except Exception as e:
                    print(f"[WARN] Failed to fetch template history: {e}")
                    
            selected_type, rationale = route(query, retrieved, recent_for_source=recent_templates)
            print(f"[Pipeline] Auto-routed template: {selected_type} ({rationale})")
            
            if dominant_source:
                try:
                    from services.lean_memory import memory_layer
                    memory_layer.log_generated_visual(dominant_source, selected_type)
                except Exception as e:
                    print(f"[WARN] Failed to log generated template: {e}")
        else:
            selected_type = visual_type
            print(f"[Pipeline] User overridden template: {selected_type}")

        # 3. Context Construction
        if not retrieved:
            print("[WARN] No matching documents found in DB. Creating visual helper with fallback context.")
            context = f"Topic: {query}. Provide general study facts for this concept."
        else:
            context_blocks = []
            for r in retrieved:
                meta = r.get("meta", {})
                source_meta = f"Source: {meta.get('source', 'Unknown')} (Page {meta.get('page', 1)}), Section: {meta.get('section', 'General')}"
                context_blocks.append(f"[{source_meta}]\n{r['text']}")
            context = "\n\n---\n\n".join(context_blocks)

        # 4. LLM JSON Generation & Pydantic Validation
        print(f"[Pipeline] Generating JSON for '{selected_type}'...")
        visual_json = generate_and_validate(context, selected_type)
        
        # Override template name if LLM returned mismatched key
        visual_json["template"] = selected_type

        # 5. Rendering
        print("[Pipeline] Rendering final HTML visualizer...")
        output_file = render(visual_json)
        print(f"[Pipeline] Visual aid saved: {output_file}")
        
        return output_file
