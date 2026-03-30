"""
AURORA Holographic Processor - Step 1: MiDaS Depth + Parallax
Generates 3D depth perception for the LED Fan display.
"""
import os
import cv2
import torch
import numpy as np
import time

class HologramProcessor:
    def __init__(self, device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        print(f"[Hologram] Initializing MiDaS on {self.device}...")
        
        # Load MiDaS Small (Speed-optimized for RTX 3050)
        self.midas = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
        self.midas.to(self.device)
        self.midas.eval()
        
        # Load Transforms
        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        self.transform = midas_transforms.small_transform

    def generate_depth(self, img_path):
        """Estimate depth from the avatar photo."""
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        input_batch = self.transform(img).to(self.device)

        with torch.no_grad():
            prediction = self.midas(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()
        # Normalize for visualization
        depth_map = (depth_map - depth_map.min()) / (depth_map.max() - depth_map.min())
        return depth_map

    def apply_parallax(self, img_path, depth_map, offset_x=10, offset_y=5):
        """Shift pixels based on depth to create a 3D floating illusion."""
        img = cv2.imread(img_path)
        h, w = img.shape[:2]
        
        # Prepare black background for the Fan
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        
        # Create displacement grid
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        
        # Deep parts (background) move less, close parts (avatar) move more
        # This creates the '3D Parallax' effect
        new_x = x + (depth_map * offset_x)
        new_y = y + (depth_map * offset_y)
        
        # Remap original image onto displaced coordinates
        parallax_frame = cv2.remap(img, new_x, new_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0))
        return parallax_frame

    def main_loop(self, avatar_path):
        """Generate a 3D parallax + lip-sync loop on a black background."""
        print(f"[Hologram] Processing 3D Depth for {avatar_path}...")
        depth = self.generate_depth(avatar_path)
        
        # Audio path to watch
        audio_file = os.path.join("gui", "temp_speech.mp3")
        last_audio_time = 0
        is_talking = False

        # Create a window for the LED Fan HDMI Out
        cv2.namedWindow("AURORA_3D_FAN", cv2.WND_PROP_FULLSCREEN)
        
        t = 0
        while True:
            # Check if AURORA is currently speaking (based on file timestamp)
            if os.path.exists(audio_file):
                mtime = os.path.getmtime(audio_file)
                if mtime > last_audio_time:
                    last_audio_time = mtime
                    is_talking = True
                    talking_start = time.time()
                
                # Assume talking lasts 5 seconds or until manually stopped
                if is_talking and (time.time() - talking_start > 5):
                    is_talking = False
            
            # Oscillate parallax for floating effect
            off_x = np.sin(t) * 15
            off_y = np.cos(t * 0.5) * 8
            
            # --- Lip Sync Integration Hook ---
            # When MuseTalk frames are ready, they should be merged here.
            # Currently implementing a high-tech mouth-jitter for immediate use.
            frame = self.apply_parallax(avatar_path, depth, off_x, off_y)
            
            if is_talking:
                # Add a high-freq 'Neural Jitter' to simulate speaking activity
                jitter = np.sin(t * 20) * 3
                frame = self.apply_parallax(avatar_path, depth, off_x + jitter, off_y + jitter)
            
            # Show on BLACK background (important for Fan transparency)
            cv2.imshow("AURORA_3D_FAN", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            t += 0.05
        
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Test run
    processor = HologramProcessor()
    # Replace with your actual avatar photo
    avatar = "gui/avatar.png"
    if os.path.exists(avatar):
        processor.main_loop(avatar)
    else:
        print("[!] Avatar file not found in gui/avatar.png")
