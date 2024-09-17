import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog

def apply_motion_blur(video_path, output_path):
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print("Error: Couldn't open the video file.")
        return
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    frame_count = 0
    avg_frame = None
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            break
            
        frame_count += 1
        frame_f32 = frame.astype(np.float32)
        
        if avg_frame is None:
            avg_frame = frame_f32
        else:
            avg_frame = cv2.addWeighted(frame_f32, 0.2, avg_frame, 0.8, 0)
        
        blurred_frame = cv2.GaussianBlur(avg_frame, (15, 15), 0)
        
        out.write(blurred_frame.astype(np.uint8))

    cap.release()
    out.release()
    print(f"Processed video saved at {output_path}")

def main():
    root = tk.Tk()
    root.withdraw()
    
    file_paths = filedialog.askopenfilenames(title="Select .mp4 files", filetypes=[("MP4 files", "*.mp4")])
    
    if not file_paths:
        print("No files selected.")
        return
    
    for i, file_path in enumerate(file_paths):
        output_path = f"output_{i}.mp4"
        print(f"Processing {file_path}...")
        apply_motion_blur(file_path, output_path)

if __name__ == "__main__":
    main()
