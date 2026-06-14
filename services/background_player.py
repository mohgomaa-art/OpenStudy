import asyncio
import io
import time
import soundfile as sf
import sounddevice as sd
from services.lean_memory import memory_layer
from services.audio import audio_service

class BackgroundPlayer:
    def __init__(self):
        self.mode = "GAMING" # Default mode
        self.is_running = False
        self.task = None

    def set_mode(self, new_mode: str):
        """GAMING, WORK, BROWSE"""
        self.mode = new_mode.upper()
        print(f"[BackgroundPlayer] Mode changed to {self.mode}")

    async def _play_audio_bytes(self, wav_bytes: bytes):
        try:
            data, fs = sf.read(io.BytesIO(wav_bytes))
            sd.play(data, fs)
            sd.wait() # Block until audio is finished playing
        except Exception as e:
            print(f"[BackgroundPlayer] Error playing audio: {e}")

    def auto_detect_mode(self):
        import sys
        if sys.platform != "win32":
            return
        import ctypes
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return
            
            # Get window title
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
            else:
                title = ""
            
            # Get window class name
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value.lower()

            gaming_keywords = ["steam", "epic games", "gog", "ubisoft", "ea desktop", "riot client", 
                               "genshin", "minecraft", "valorant", "cyberpunk", "witcher", "lol", 
                               "dota", "counter-strike", "csgo", "cs2", "roblox", "fortnite", "overwatch",
                               "game", "elden ring", "unity", "unreal", "gta", "fifa"]
            
            work_keywords = ["visual studio", "vscode", "sublime", "notepad++", "word", "excel", 
                             "powerpoint", "pdf", "acrobat", "foxit", "zoom", "teams", "slack", 
                             "discord", "powershell", "terminal", "github", "overleaf", "obsidian", 
                             "notion", "matlab", "pydantic", "anaconda", "pycharm", "jupyter"]
            
            browse_keywords = ["chrome", "firefox", "edge", "safari", "opera", "brave", "browser"]

            detected_mode = None
            if any(k in title or k in class_name for k in gaming_keywords):
                detected_mode = "GAMING"
            elif any(k in title or k in class_name for k in work_keywords):
                detected_mode = "WORK"
            elif any(k in title or k in class_name for k in browse_keywords):
                detected_mode = "BROWSE"

            if detected_mode and detected_mode != self.mode:
                self.set_mode(detected_mode)
        except Exception:
            pass

    async def run_loop(self):
        self.is_running = True
        print(f"[BackgroundPlayer] Started loop in {self.mode} mode.")
        
        last_played_time = time.time()
        
        while self.is_running:
            now = time.time()
            elapsed_mins = (now - last_played_time) / 60.0
            
            # Auto-detect active window class/title on Windows every 4 seconds
            if int(now) % 4 == 0:
                self.auto_detect_mode()
            
            should_play = False
            content_type = "fact" # default to fact
            
            if self.mode == "GAMING" and elapsed_mins >= 5:
                should_play = True
                content_type = "fact"
            elif self.mode == "WORK" and elapsed_mins >= 15:
                should_play = True
                content_type = "question"
            elif self.mode == "BROWSE" and elapsed_mins >= 10:
                should_play = True
                content_type = "question"
                
            if should_play:
                node = memory_layer.get_next_node_to_play()
                if node:
                    text_to_play = node[content_type]
                    if content_type == "fact" and node.get("example"):
                        text_to_play += f" For example: {node['example']}"
                    
                    print(f"[BackgroundPlayer] Playing {content_type}: {text_to_play}")
                    
                    # Synthesize via Kokoro (CPU)
                    try:
                        audio_bytes = await audio_service.synthesize(text_to_play)
                        await self._play_audio_bytes(audio_bytes)
                        memory_layer.mark_played(node["node_id"])
                        
                        if content_type == "question":
                            # Wait for user input or just pause for 10 seconds?
                            # For a true interactive layer, we would trigger VAD here.
                            # For now, we simulate waiting.
                            print("[BackgroundPlayer] Waiting 10s for potential answer...")
                            await asyncio.sleep(10)
                            
                    except Exception as e:
                         print(f"[BackgroundPlayer] TTS failed: {e}")
                
                last_played_time = time.time()
                
            await asyncio.sleep(1) # check every second

    def start(self):
        if not self.is_running:
            self.task = asyncio.create_task(self.run_loop())

    def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()

bg_player = BackgroundPlayer()
