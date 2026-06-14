import time
from services.lean_memory import memory_layer
from services.llm import llm_service

def generate_all_content(progress_callback=None, node_ids=None):
    """Runs a loop to pre-generate facts and questions for all pending nodes.
    This should run OFFLINE, before the user starts gaming/working.
    """
    print("[ContentGenerator] Starting offline generation loop...")
    
    pending_nodes = memory_layer.get_all_nodes_without_content()
    if node_ids is not None:
        node_ids_set = set(node_ids)
        pending_nodes = [n for n in pending_nodes if n["node_id"] in node_ids_set]
        
    total_pending = len(pending_nodes)
    processed = 0
    
    if progress_callback:
        progress_callback(processed, total_pending, "Starting content generation...")
        
    for node in pending_nodes:
        print(f"[ContentGenerator] Processing Node: {node['title']}")
        if progress_callback:
            progress_callback(processed, total_pending, f"Generating for: {node['title']}")
            
        prompt = f"""You are an ADHD study companion pre-processing study material.
Read the following content and generate a highly engaging, concise JSON response.
Do NOT output any markdown blocks or extra text, JUST valid JSON.

CONTENT TO PROCESS:
{node['raw_content']}

REQUIRED JSON FORMAT:
{{
    "fact": "A single, highly interesting one-sentence fact about this topic.",
    "question": "A simple multiple-choice question to test understanding.",
    "example": "A quick, relatable real-world example.",
    "mnemonic": "A short, catchy memory hook or acronym if applicable (otherwise empty string)."
}}
"""
        
        try:
            result = llm_service.generate_json(prompt)
            result_lower = {k.lower(): v for k, v in result.items()} if result else {}

            if result_lower and "fact" in result_lower:
                memory_layer.update_generated_content(
                    node_id=node["node_id"],
                    fact=str(result_lower.get("fact", "No fact generated.")),
                    question=str(result_lower.get("question", "No question generated.")),
                    example=str(result_lower.get("example", "")),
                    mnemonic=str(result_lower.get("mnemonic", ""))
                )
                print(f"[ContentGenerator] Success for {node['node_id']}")
            else:
                # Mark as failed to avoid infinite retry loop in current run
                memory_layer.update_generated_content(
                    node_id=node["node_id"],
                    fact="Failed to parse content.",
                    question="Failed to parse question.",
                    example="",
                    mnemonic=""
                )
                print(f"[ContentGenerator] No usable JSON for {node['node_id']}")
        except Exception as e:
            print(f"[ContentGenerator] Error processing {node['node_id']}: {e}")
            memory_layer.update_generated_content(
                node_id=node["node_id"],
                fact="Failed to parse content.",
                question="Failed to parse question.",
                example="",
                mnemonic=""
            )
            
        processed += 1
        if progress_callback:
            progress_callback(processed, total_pending, f"Processed {processed}/{total_pending} nodes")
            
        # Give a short breather
        time.sleep(1)

    print("[ContentGenerator] Content generation complete.")
    if progress_callback:
        progress_callback(processed, total_pending, "Complete")

if __name__ == "__main__":
    generate_all_content()
