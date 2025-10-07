from PIL import Image, UnidentifiedImageError
import os
import shutil

input_folder = "master-product_images"
output_folder = "master-product_images-webp"

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    input_path = os.path.join(input_folder, filename)
    output_filename = os.path.splitext(filename)[0] + ".webp"
    output_path = os.path.join(output_folder, output_filename)

    try:
        with Image.open(input_path) as img:
            img.save(output_path, "webp")
        #print(output_path)
    except UnidentifiedImageError:
        # Copy original image if it can't be opened by Pillow
        fallback_path = os.path.join(output_folder, filename)
        shutil.copy2(input_path, fallback_path)
        #print(fallback_path)
    except Exception as e:
        print(f"filename {e}")
