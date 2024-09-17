import tkinter as tk
from tkinter import filedialog
import rawpy
from PIL import Image
import os
import subprocess
import concurrent.futures


def desqueeze_image(file_path):
    try:
        # Load the DNG image using rawpy
        with rawpy.imread(file_path) as raw:
            # Use camera white balance for post-processing
            rgb_array = raw.postprocess(use_camera_wb=True)
            
        # Convert to PIL image
        img = Image.fromarray(rgb_array)

        # Calculate the new width for the desqueezed image
        original_width, original_height = img.size
        new_width = int(original_width * 1.5)

        # Resize the image to desqueeze it
        desqueezed_img = img.resize((new_width, original_height))

        # Create the output file path with the suffix "-desqueezed"
        base, ext = os.path.splitext(file_path)
        output_path = f"{base}-desqueezed.tiff"

        # Save the desqueezed image as a TIFF file
        desqueezed_img.save(output_path, format='TIFF')

        # Copy metadata from the original file to the new file, ignoring minor errors
        subprocess.run(['exiftool', '-TagsFromFile', file_path, '-all:all', '-overwrite_original', '-m', output_path])

        print(f"Saved desqueezed image to: {output_path}")
    except Exception as e:
        print(f"Failed to process {file_path}: {e}")

def main():
    # Create a Tkinter root window (it won't be shown)
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    # Open a file dialog to select DNG files
    file_paths = filedialog.askopenfilenames(
        title="Select DNG files",
        filetypes=[("DNG files", "*.dng")]
    )

    # Use ThreadPoolExecutor to process images in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(desqueeze_image, file_path) for file_path in file_paths]
        for future in concurrent.futures.as_completed(futures):
            future.result()  # To raise any exception that occurred during processing

    print("Complete")

if __name__ == "__main__":
    main()
