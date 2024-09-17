import tkinter as tk
from tkinter import filedialog, ttk
import numpy as np
import rawpy
from PIL import Image, ImageTk, ExifTags
import threading
import subprocess
import os
import queue
import psutil
import sys
from fractions import Fraction

# Get the script directory and the path to exiftool
script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
exiftool_path = os.path.join(script_directory, "exiftool.exe")

# Queue for inter-thread communication
result_queue = queue.Queue()

def get_exposure_time(file_path):
    """Get the exposure time from EXIF data as a Fraction."""
    with Image.open(file_path) as image:
        img_exif = image.getexif()
        for (k, v) in img_exif.items():
            if ExifTags.TAGS.get(k) == 'ExposureTime':
                exposure_time = v
                if isinstance(exposure_time, tuple) and len(exposure_time) == 2:
                    # Exposure time is a fraction
                    return Fraction(exposure_time[0], exposure_time[1])
                else:
                    # Exposure time is a float
                    return Fraction(exposure_time)
    return Fraction(0)

def process_image(file_path, index, total_files):
    """Process a single image file and put the result in the queue."""
    with rawpy.imread(file_path) as raw:
        img = raw.postprocess().astype(np.float32)
    result_queue.put((index, img))
    progress_var.set(index + 1)
    status_var.set(f"Processed image {index + 1}/{total_files}")
    app.update_idletasks()  # Update the UI

def update_preview_image(average_image_array):
    """Update the preview image in the UI."""
    img = Image.fromarray(np.uint8(average_image_array))
    img.thumbnail((600, 600))
    img_tk = ImageTk.PhotoImage(img)
    preview_image_label.config(image=img_tk)
    preview_image_label.image = img_tk

def process_images_thread(file_paths):
    """Process the selected images into the queue."""
    total_files = len(file_paths)
    for index, file_path in enumerate(file_paths):
        process_image(file_path, index, total_files)

def average_images_thread(file_paths, save_path, stacking_method, total_exposure_time):
    """Perform stacking of images based on the selected method."""
    total_files = len(file_paths)
    average_image = None
    processed_count = 0
    images_list = []

    while processed_count < total_files:
        try:
            index, img = result_queue.get(timeout=0.1)
            processed_count += 1

            if stacking_method == 'Mean':
                if average_image is None:
                    average_image = img
                else:
                    average_image = (average_image * (processed_count - 1) + img) / processed_count

            elif stacking_method == 'Maximum':
                if average_image is None:
                    average_image = img
                else:
                    average_image = np.maximum(average_image, img)

            elif stacking_method == 'Minimum':
                if average_image is None:
                    average_image = img
                else:
                    average_image = np.minimum(average_image, img)

            elif stacking_method == 'Sigma Clipping':
                images_list.append(img)

            if processed_count % 100 == 0 or processed_count == total_files:
                if stacking_method != 'Sigma Clipping':
                    update_preview_image(average_image)

            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            details_var.set(f"Threads: {os.cpu_count()}\nCPU utilization: {cpu_percent}%\nMemory utilization: {memory_percent}%")

        except queue.Empty:
            pass

    if stacking_method == 'Sigma Clipping':
        # Stack images into a numpy array
        stack = np.stack(images_list, axis=0)
        # Compute mean and standard deviation along the stack axis
        mean = np.mean(stack, axis=0)
        std = np.std(stack, axis=0)
        # Sigma clipping threshold
        sigma = 2  # You can adjust the sigma value as needed
        # Create a mask of values within the sigma threshold
        mask = np.abs(stack - mean) <= sigma * std
        # Replace outliers with NaN
        clipped_stack = np.where(mask, stack, np.nan)
        # Compute mean ignoring NaN values
        average_image = np.nanmean(clipped_stack, axis=0)
        # Replace NaN values with zeros
        average_image = np.nan_to_num(average_image)
        update_preview_image(average_image)

    # Save the stacked image with EXIF data
    average_image = np.clip(average_image, 0, 255).astype(np.uint8)
    img = Image.fromarray(average_image)
    img_exif = img.getexif()
    # Set total exposure time in EXIF data
    img_exif[33434] = (total_exposure_time.numerator, total_exposure_time.denominator)
    img.save(save_path, exif=img_exif)

    status_var.set("Finished!")
    app.bell()

def process_images():
    """Process the selected images."""
    file_paths = filedialog.askopenfilenames(title="Select .dng files", filetypes=[("DNG files", "*.dng")])
    if not file_paths:
        status_var.set("No files selected.")
        return

    total_exposure_time = Fraction(0)
    for file_path in file_paths:
        total_exposure_time += get_exposure_time(file_path)

    stacking_method = stacking_method_var.get()
    save_dir = os.path.dirname(file_paths[0])
    first_file_name = os.path.splitext(os.path.basename(file_paths[0]))[0]
    total_exposure_time_float = float(total_exposure_time)
    save_filename = f"{first_file_name}_{stacking_method}_{total_exposure_time_float:.2f}s.tiff"
    save_path = os.path.join(save_dir, save_filename)

    status_var.set("Starting to process images...")
    progress_var.set(0)
    progress_bar.config(maximum=len(file_paths))

    threads = [
        threading.Thread(target=process_images_thread, args=(file_paths,)),
        threading.Thread(target=average_images_thread, args=(file_paths, save_path, stacking_method, total_exposure_time)),
    ]

    for t in threads:
        t.start()

app = tk.Tk()
app.title("DNG Averager")
app.configure(bg='#f0f0f0')

frame = ttk.Frame(app, padding="20 20 20 20")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

title_font = ('Arial', 14, 'bold')
label_font = ('Arial', 12)

title_label = ttk.Label(frame, text="DNG Averager", font=title_font)
title_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 20))

files_label = ttk.Label(frame, text="Select DNG files to average:", font=label_font)
files_label.grid(row=1, column=0, sticky=tk.W, padx=(10, 0))
select_files_button = ttk.Button(frame, text="Select files", command=process_images)
select_files_button.grid(row=1, column=1, sticky=tk.E, padx=(0, 10))

# Add a label for stacking method
stacking_label = ttk.Label(frame, text="Select stacking method:", font=label_font)
stacking_label.grid(row=2, column=0, sticky=tk.W, padx=(10, 0))

stacking_method_var = tk.StringVar(value="Mean")

mean_radio = ttk.Radiobutton(frame, text='Mean', variable=stacking_method_var, value='Mean')
mean_radio.grid(row=2, column=1, sticky=tk.W)

max_radio = ttk.Radiobutton(frame, text='Maximum', variable=stacking_method_var, value='Maximum')
max_radio.grid(row=3, column=1, sticky=tk.W)

min_radio = ttk.Radiobutton(frame, text='Minimum', variable=stacking_method_var, value='Minimum')
min_radio.grid(row=4, column=1, sticky=tk.W)

sigma_clip_radio = ttk.Radiobutton(frame, text='Sigma Clipping', variable=stacking_method_var, value='Sigma Clipping')
sigma_clip_radio.grid(row=5, column=1, sticky=tk.W)

status_var = tk.StringVar()
status_label = ttk.Label(frame, textvariable=status_var, font=label_font)
status_label.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0), pady=(20, 0))

progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(frame, variable=progress_var, mode='determinate')
progress_bar.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 10), pady=(10, 0))

details_var = tk.StringVar()
details_label = ttk.Label(frame, textvariable=details_var, font=label_font, wraplength=400, justify=tk.LEFT)
details_label.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0), pady=(20, 0))

preview_image_label = ttk.Label(frame)
preview_image_label.grid(row=9, column=0, columnspan=2, padx=(10, 10), pady=(20, 0))

app.mainloop()
