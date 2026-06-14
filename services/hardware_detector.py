"""
Stub hardware detector — returns conservative defaults for a 4 GB VRAM target.
Extend this if you want runtime tier-switching based on actual GPU memory.
"""

def detect_tier() -> dict:
    return {
        "tier": "cpu",
        "vram_mb": 0,
        "cuda_available": False,
        "gpu_name": "unknown",
    }

hardware_info = detect_tier()
