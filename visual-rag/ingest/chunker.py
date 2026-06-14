from langchain_text_splitters import RecursiveCharacterTextSplitter
import config

# We use character-based size. Assuming ~4 chars per token, we can use CHUNK_SIZE directly 
# or multiply it to get a rough character equivalence. Let's use config.CHUNK_SIZE and 
# config.CHUNK_OVERLAP directly as specified.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " "],
)

def chunk_items(items: list[dict]) -> list[dict]:
    """
    Split long text items while preserving and propagating metadata.
    Short items (tables, headers) pass through unchanged.
    """
    chunks = []
    for item in items:
        # Check if item is already smaller than chunk size or is a table
        # We don't want to split tables because markdown tables get destroyed by character splitting.
        is_table = "table" in str(item.get("label", "")).lower()
        
        if len(item["text"]) <= config.CHUNK_SIZE or is_table:
            chunks.append(item)
        else:
            splits = splitter.split_text(item["text"])
            for i, split in enumerate(splits):
                chunks.append({
                    **item,
                    "text": split,
                    "chunk_idx": i
                })
    return chunks
