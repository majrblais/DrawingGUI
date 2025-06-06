# 🛠️ Road Mask Editor GUI

A Python-based GUI for refining and correcting segmentation masks exported from ArcGIS Pro’s **Export Training Data for Deep Learning** tool. This tool allows you to visually inspect `.tif` masks overlaid on source imagery, draw or erase mask content, and save georeferenced binary mask files.
There are three main steps:
- Generate matching image-roads data using arcgis export training data.
- Launch the GUI using python or exe file
- Edit and save your segmentation masks

### 🎥 Video Tutorial

A short video tutorial is included ([📺 Watch Tutorial](./tutorial.mp4)) It demonstrates:
- How to prepare your folders.
- How to launch and use the GUI.
- How to fix georeferencing using `fix_geo_ref_exe.py`.

We recommend watching it before starting your workflow.



## ✅ Step 1: Export Data from ArcGIS

Use ArcGIS Pro's **Export Training Data for Deep Learning** tool.
Select these parameters with a specific zone after loading the world imagery and CRSNO predicted road layer. 
This will create a matching images-road dataset of the selected zone.

### Recommended Parameters:

| Parameter                 | Value                                                       |
|---------------------------|-------------------------------------------------------------|
| Input Raster              | World Imagery                                               |
| Additional Input Raster   | CRSNO.TIF (Contact Laurie)                                  |
| Output Folder             | Folder where `gui.py` resides or any project path           |
| Input Mask Polygon        | Custom polygon area (e.g., square AOI)                      |
| Image Format              | TIFF                                                        |
| Tile Size X/Y             | 4000                                                        |
| Stride X/Y                | 4000                                                        |
| Reference System          | MAP_SPACE                                                   |
| Metadata Format           | Classified Tiles                                            |
| Environment - Cell Size   | 0.5                                                         |
| All Other Parameters      | Leave as Default                                            |

This generates:
- `images/` → input imagery tiles (`.tif`)
- `images2/` → segmentation masks (`.tif`)
### 📌 Tip

Use the ArcGIS Export Training Data tool on specific drawn extents This allows multiple users to work on different regions in parallel, improving productivity.


---

## ✅ Step 2: Install Python Environment

You can use either the Python source or the provided Windows `.exe`.

### 🐍 Option A: Python (Recommended)
This option automatically appends the georeference to the .tif file so only that file is needed.

1. Install [Anaconda](https://www.anaconda.com/products/distribution)

2. Open **Anaconda Prompt**:

```bash
conda create -n mask-editor-env python=3.10 -y
conda activate mask-editor-env
conda install -c conda-forge opencv numpy pillow gdal tk -y
```



### 🐍 Option B: Executable file (gui.exe)

This is a compiled version of `gui.py` bundled into a standalone Windows executable. It has been tested on Windows 11 and functions as expected for editing and saving masks. However, due to packaging limitations, the `.tif` masks saved by the `.exe` version do not retain embedded georeferencing. As a workaround, corresponding `.tfw` world files are saved alongside each mask. To restore proper georeferencing, use the `fix_geo_ref_exe.py` script.

---

## ✅ Step 3: Run the Tool

### ▶️ Python

Run the script from the folder where `gui.py` is located:

```bash
python gui.py
```

or use the executable 

```bash
gui.exe
```

When prompted:
- **Primary Image Folder**: `images/`
- **Mask Folder**: `images2/`
- **Output Mask Folder**: e.g., `newmasks/`

---
---
---

# Useful information
---
## 🖱️ Controls

| Action                  | Key / Button      |
|-------------------------|-------------------|
| Next / Prev Image       | `d` / `a`         |
| Zoom In / Out           | `+` / `-`         |
| Pan (Up/Down/Left/Right)| `i/k/j/l`         |
| Toggle Mask Overlay     | `t`               |
| Toggle Eraser           | `e`               |
| Toggle Line Mode        | `o`               |
| Connect Points          | `p`               |
| Clear Mask              | `c`               |
| Undo                    | `z`               |
| Save Mask               | `s`               |
| Quit GUI                | `ESC`             |

---

## 📁 Example Folder Structure

```
project_root/
├── gui.py                 # main Python GUI script
├── images/                # input tiles
├── images2/               # predicted road masks
├── newmasks/              # output folder for python source
├── exe/              	   # output folder executable
```

### 📂 The `.data/` Folder

The `.data` folder in this repository is included as a **reference example** only. It contains sample imagery and masks for testing.

> ❗ **Important:** Before working on a new region, you should **delete the `.data/` folder** to avoid confusion. Replace it with fresh imagery and masks exported from ArcGIS Pro.

---

## 💾 Saving Masks

When pressing **Save Mask**:
- Mask is saved as `.tif` with original georeferencing from the corresponding image.
- All `.tfw` and input mask files for that tile are deleted.
- Mask values are guaranteed binary (`0` or `255`).
- The original input image is untouched.

### Known Issues:
- GUI may freeze on exit due to lingering threads. If it happens, use `Ctrl+Shift+Esc` to terminate from Task Manager.


### Keeping Track of the Finished Files

The mask files (`./images2`) are deleted as they are saved into a new folder. The .tif file is delted while the .tfw is moved into the selectedc third folder. This is done to manage what has been done and not done.

---

## ⚙️ Functionality Overview

### ✔️ Features:
- Loads georeferenced `.tif` masks using **GDAL** instead of OpenCV for full TIFF support.
- Automatically binarizes masks (`>127 → 255`, `<=127 → 0`).
- Preserves original spatial metadata (GeoTransform & Projection).
- Displays masks as overlays (toggleable).
- Allows drawing/erasing with adjustable brush.
- Supports line-based editing and undo history.


---






## 👷 Development Notes

- The mask loading now uses GDAL to improve compatibility and precision for GeoTIFF files.
- The blocky output was previously due to OpenCV interpolation issues — resolved by binarizing using GDAL on load.
- All modifications are visualized live and applied only upon saving.

---



## 🛠️ Additional Notes

### 🧭 Georeferencing Fix — `fix_geo_ref_exe.py`

When using the compiled executable version of the GUI (`gui.exe`), saved `.tif` mask files may lack proper georeferencing due to limitations in how spatial metadata is handled.

To resolve this, a standalone script named **`fix_geo_ref_exe.py`** is provided. This script:
- Scans a folder for `.tif` images and their corresponding `.tfw` world files.
- Extracts the affine transformation from the `.tfw` file.
- Embeds the georeferencing into the image using the `rasterio` library.
- Outputs corrected GeoTIFFs into a `georeferenced/` subfolder.

> 🔧 **Note:** You can set the appropriate coordinate reference system (CRS) by modifying the EPSG code in the script (default is `EPSG:3857`).

#### ✅ When to use it
- If you used the `.exe` version to edit and save masks.
- If your saved `.tif` masks are not recognized as georeferenced in GIS software.

---
