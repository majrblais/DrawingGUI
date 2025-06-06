import os
import rasterio
from rasterio.transform import Affine
from rasterio.enums import Resampling

# Your folder path
folder_path = r"E:\Desktop\GUI\data\newmasks"
output_folder = os.path.join(folder_path, "georeferenced")
os.makedirs(output_folder, exist_ok=True)

# List all tif files
for file_name in os.listdir(folder_path):
    if file_name.lower().endswith(".tif"):
        base_name = os.path.splitext(file_name)[0]
        tif_path = os.path.join(folder_path, file_name)
        tfw_path = os.path.join(folder_path, base_name + ".tfw")

        if not os.path.exists(tfw_path):
            print(f"[SKIP] No TFW file for: {file_name}")
            continue

        # Read TFW
        with open(tfw_path, "r") as f:
            lines = f.readlines()
            if len(lines) < 6:
                print(f"[ERROR] Invalid TFW file: {tfw_path}")
                continue

            try:
                pixel_width = float(lines[0])
                rotation_x = float(lines[1])
                rotation_y = float(lines[2])
                pixel_height = float(lines[3])
                top_left_x = float(lines[4])
                top_left_y = float(lines[5])

                transform = Affine(pixel_width, rotation_x, top_left_x,
                                   rotation_y, pixel_height, top_left_y)
            except Exception as e:
                print(f"[ERROR] Failed to parse TFW for {file_name}: {e}")
                continue

        # Read image and write new GeoTIFF
        with rasterio.open(tif_path) as src:
            profile = src.profile.copy()
            data = src.read()

            # Update profile with georeferencing
            profile.update({
                'transform': transform,
                'crs': 'EPSG:3857'  # CHANGE THIS to your actual projection!
            })

            output_path = os.path.join(output_folder, base_name + "_geo.tif")

            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(data)

        print(f"[OK] Saved: {output_path}")
