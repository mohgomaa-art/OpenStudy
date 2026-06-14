import os
from pathlib import Path
from docling.document_converter import DocumentConverter

SUPPORTED_FORMATS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".html", ".epub", ".png", ".jpg",
    ".jpeg", ".tiff", ".txt", ".md"
}

# Lazy initialization of converter to avoid overhead during import
_converter = None

def get_converter():
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter

def parse_file(path: str) -> list[dict]:
    """
    Parses a document. Uses PyMuPDF as the primary parser for PDFs for speed and safety.
    Uses Docling for docx, pptx, and other document formats.
    """
    filename = Path(path).name
    suffix = Path(path).suffix.lower()
    
    if suffix == ".pdf":
        print(f"[Parser] PDF detected. Using PyMuPDF for fast, safe extraction: {filename}")
        try:
            import fitz
            doc = fitz.open(path)
            chunks = []
            current_section = "Introduction"
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text().strip()
                if not text:
                    continue
                # Split page text into lines or paragraphs
                lines = text.split("\n")
                current_block = []
                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        if current_block:
                            block_text = " ".join(current_block)
                            if len(block_text) >= 40:
                                chunks.append({
                                    "text": block_text,
                                    "source": filename,
                                    "page": page_idx + 1,
                                    "label": "Paragraph",
                                    "section": current_section,
                                })
                            current_block = []
                        continue
                    
                    # Detect potential heading
                    if len(line_str) < 60 and (line_str.isupper() or any(h in line_str.lower() for h in ["chapter", "section", "lecture", "renal", "kidney", "injury"])):
                        if current_block:
                            block_text = " ".join(current_block)
                            if len(block_text) >= 40:
                                chunks.append({
                                    "text": block_text,
                                    "source": filename,
                                    "page": page_idx + 1,
                                    "label": "Paragraph",
                                    "section": current_section,
                                })
                            current_block = []
                        current_section = line_str
                    else:
                        current_block.append(line_str)
                
                # Append last block of the page
                if current_block:
                    block_text = " ".join(current_block)
                    if len(block_text) >= 40:
                        chunks.append({
                            "text": block_text,
                            "source": filename,
                            "page": page_idx + 1,
                            "label": "Paragraph",
                            "section": current_section,
                        })
            print(f"[Parser] PyMuPDF successfully extracted {len(chunks)} blocks from {filename}.")
            return chunks
        except Exception as fe:
            print(f"[Parser] PyMuPDF failed: {fe}. Falling back to Docling...")
            
    if suffix in [".png", ".jpg", ".jpeg", ".tiff"]:
        print(f"[Parser] Image detected. Using pytesseract for OCR: {filename}")
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(path)
            text = pytesseract.image_to_string(img).strip()
            chunks = []
            if text:
                lines = text.split("\n")
                current_block = []
                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        if current_block:
                            block_text = " ".join(current_block)
                            if len(block_text) >= 10:
                                chunks.append({
                                    "text": block_text,
                                    "source": filename,
                                    "page": 1,
                                    "label": "OCR Text",
                                    "section": "Image Content",
                                })
                            current_block = []
                    else:
                        current_block.append(line_str)
                if current_block:
                    block_text = " ".join(current_block)
                    if len(block_text) >= 10:
                        chunks.append({
                            "text": block_text,
                            "source": filename,
                            "page": 1,
                            "label": "OCR Text",
                            "section": "Image Content",
                        })
            print(f"[Parser] Tesseract successfully extracted {len(chunks)} blocks from {filename}.")
            return chunks
        except ImportError:
            print("[Parser] pytesseract or PIL not installed. Falling back to Docling...")
        except Exception as fe:
            print(f"[Parser] pytesseract failed: {fe}. Falling back to Docling...")

    # Fallback to Docling
    try:
        converter = get_converter()
        result = converter.convert(path)
        doc = result.document
        chunks = []
        
        current_section = "Introduction"
        
        # Iterate over document elements in reading order
        for item, level in doc.iterate_items():
            # Get label (e.g. SectionHeader, Paragraph, Table)
            label = str(getattr(item, 'label', ''))
            
            # Extract text based on item type
            item_type = type(item).__name__
            text = ""
            
            if item_type == "TableItem":
                try:
                    # Try to export table to markdown representation
                    text = item.export_to_markdown(doc=doc).strip()
                except Exception:
                    text = getattr(item, 'text', '').strip()
            else:
                text = getattr(item, 'text', '').strip()
                
            if not text:
                continue
                
            # Update current section if it's a heading
            is_heading = any(h in label.lower() for h in ("header", "title", "heading"))
            if is_heading:
                current_section = text
                
            # Skip very short paragraph/text items to avoid indexing noise
            if len(text) < 40 and not is_heading and item_type != "TableItem":
                continue
                
            # Extract page number if available (1-based)
            page = 1
            if getattr(item, 'prov', None) and len(item.prov) > 0:
                # page_no is 1-based in modern docling versions
                page = item.prov[0].page_no
                
            chunks.append({
                "text": text,
                "source": filename,
                "page": page,
                "label": label if label else item_type,
                "section": current_section,
            })
        return chunks
    except Exception as e:
        print(f"[Parser] Docling also failed on {filename} due to: {e}")
        raise e

def parse_folder(folder: str) -> dict[str, list[dict]]:
    """Batch parse all supported files in a folder."""
    results = {}
    folder_path = Path(folder)
    if not folder_path.exists():
        print(f"[WARN] Folder not found: {folder}")
        return results
        
    for file in folder_path.rglob("*"):
        if file.suffix.lower() in SUPPORTED_FORMATS:
            try:
                print(f"[Ingest] Parsing {file.name}...")
                results[file.name] = parse_file(str(file))
            except Exception as e:
                print(f"[SKIP] Error parsing {file.name}: {e}")
    return results
