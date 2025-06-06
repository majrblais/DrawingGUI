#this version before this comment works but blocky
#!/usr/bin/env python3
import sys
import os
import time
if getattr(sys, 'frozen', False):
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(sys._MEIPASS, 'platforms')

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import logging
from PIL import Image
from osgeo import gdal, osr


def safe_showinfo(title, message):
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception as e:
        print(f"[INFO] {title}: {message}")


class MaskEditor:
    def __init__(self, image_dir, mask_dir, output_mask_dir, screen_width, screen_height):
        self.image_dir = image_dir
        self.mask_dir = mask_dir.strip() if mask_dir.strip() != "" else None
        self.output_mask_dir = output_mask_dir
        self.screen_width = screen_width
        self.screen_height = screen_height
        '''
        for folder in [self.image_dir, self.mask_dir]:
            if folder and os.path.isdir(folder):
                for fname in os.listdir(folder):
                    if fname.lower().endswith(".tfw"):
                        try:
                            os.remove(os.path.join(folder, fname))
                        except Exception:
                            pass
        '''
        os.makedirs(self.output_mask_dir, exist_ok=True)

        if not self.mask_dir:
            sys.exit("Error: A mask folder must be provided.")

        self.mask_files = sorted([
            f for f in os.listdir(self.mask_dir)
            if os.path.isfile(os.path.join(self.mask_dir, f)) and not f.lower().endswith(".tfw")
        ])

        if len(self.mask_files) == 0:
            safe_showinfo("Error", "No mask files found in the mask folder.")
            sys.exit(0)

        self.image_files = []
        for mf in self.mask_files:
            img_path = os.path.join(self.image_dir, mf)
            if os.path.exists(img_path):
                self.image_files.append(mf)
            else:
                sys.exit(f"Error: Corresponding image file not found for mask: {mf}")

        self.current_index = 0
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.show_mask_overlay = False
        self.is_drawing = False
        self.is_erasing = False
        self.last_point = None
        self.brush_size = 2
        self.line_mode_active = False
        self.line_points = []
        self.connected_lines_stack = []
        self.cached_image = None
        self.cached_mask = None
        self.drawn_mask = None
        self.undo_stack = []
        self.running = True
        self.live_drawing = True

    def save_state_to_undo_stack(self):
        if self.cached_mask is not None:
            self.undo_stack.append(self.cached_mask.copy())

    def draw_on_mask(self, event, x, y, flags, param):
        resize_factor_x, resize_factor_y = self.resize_factors
        crop_x1, crop_y1 = self.crop_offsets
        mask_x = int(x / resize_factor_x) + crop_x1
        mask_y = int(y / resize_factor_y) + crop_y1

        if self.line_mode_active:
            if event == cv2.EVENT_LBUTTONDOWN:
                self.line_points.append((mask_x, mask_y))
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            self.save_state_to_undo_stack()
            self.is_drawing = True
            self.last_point = (mask_x, mask_y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.is_drawing = False
            self.last_point = None
        elif event == cv2.EVENT_MOUSEMOVE and self.is_drawing:
            if 0 <= mask_x < self.cached_mask.shape[1] and 0 <= mask_y < self.cached_mask.shape[0]:
                value = 0 if self.is_erasing else 255
                if self.last_point is not None:
                    cv2.line(self.cached_mask, self.last_point, (mask_x, mask_y), value, self.brush_size)
                self.last_point = (mask_x, mask_y)

    def connect_points(self):
        if len(self.line_points) > 1:
            self.save_state_to_undo_stack()
            connected_lines = []
            for i in range(1, len(self.line_points)):
                cv2.line(self.cached_mask, self.line_points[i - 1], self.line_points[i], 255, self.brush_size)
                connected_lines.append((self.line_points[i - 1], self.line_points[i]))
            self.connected_lines_stack.append(connected_lines)
        self.line_points = []

    def undo_last_connected_lines(self):
        if self.connected_lines_stack:
            self.save_state_to_undo_stack()
            last_lines = self.connected_lines_stack.pop()
            for line in last_lines:
                cv2.line(self.cached_mask, line[0], line[1], 0, self.brush_size)

    def load_image_and_mask(self, image_path, mask_path):
        self.cached_image = cv2.imread(image_path)
        if mask_path is not None:
            mask_ds = gdal.Open(mask_path)
            if mask_ds is None:
                raise ValueError(f"Failed to open mask: {mask_path}")
            band = mask_ds.GetRasterBand(1)
            mask = band.ReadAsArray()
            mask = np.where(mask > 127, 255, 0).astype(np.uint8)
            self.cached_mask = mask.copy()
        else:
            self.cached_mask = np.zeros((self.cached_image.shape[0], self.cached_image.shape[1]), dtype=np.uint8)
        self.undo_stack = []
        self.connected_lines_stack = []
        self.line_points = []
        self.live_drawing = True


    def clear_mask(self):
        if self.cached_mask is not None:
            self.save_state_to_undo_stack()
            self.cached_mask = np.zeros_like(self.cached_mask)

    def prev_image(self):
        self.current_index = (self.current_index - 1 + len(self.image_files)) % len(self.image_files)
        self.load_current_image()

    def next_image(self):
        self.current_index = (self.current_index + 1) % len(self.image_files)
        self.load_current_image()

    def load_current_image(self):
        image_path = os.path.join(self.image_dir, self.image_files[self.current_index])
        mask_path = os.path.join(self.mask_dir, self.mask_files[self.current_index]) if self.mask_dir else None
        self.pan_x, self.pan_y, self.zoom_factor = 0, 0, 1.0
        self.load_image_and_mask(image_path, mask_path)

    def zoom_in(self): self.zoom_factor = min(self.zoom_factor * 1.2, 10.0)
    def zoom_out(self): self.zoom_factor = max(self.zoom_factor / 1.2, 1.0)
    def pan_up(self): self.pan_y = max(self.pan_y - int(400 / self.zoom_factor), -self.cached_image.shape[0] // 2)
    def pan_down(self): self.pan_y = min(self.pan_y + int(400 / self.zoom_factor), self.cached_image.shape[0] // 2)
    def pan_left(self): self.pan_x = max(self.pan_x - int(400 / self.zoom_factor), -self.cached_image.shape[1] // 2)
    def pan_right(self): self.pan_x = min(self.pan_x + int(400 / self.zoom_factor), self.cached_image.shape[1] // 2)

    def toggle_mask_overlay(self): self.show_mask_overlay = not self.show_mask_overlay

    def save_mask(self):
        image_filename = self.image_files[self.current_index]
        image_path = os.path.join(self.image_dir, image_filename)
        mask_path = os.path.join(self.mask_dir, image_filename)
        tfw_path = os.path.splitext(mask_path)[0] + ".tfw"
        output_path = os.path.join(self.output_mask_dir, os.path.splitext(image_filename)[0] + ".tif")
        output_tfw_path = os.path.join(self.output_mask_dir, os.path.basename(tfw_path))

        # Open image for georeferencing
        src_ds = gdal.Open(image_path)
        if src_ds is None:
            print(f"[!] Failed to open source image: {image_path}")
            return

        geo_transform = src_ds.GetGeoTransform()
        projection = src_ds.GetProjection()

        driver = gdal.GetDriverByName('GTiff')
        dst_ds = driver.Create(
            output_path,
            self.cached_mask.shape[1],
            self.cached_mask.shape[0],
            1,
            gdal.GDT_Byte
        )

        dst_ds.SetGeoTransform(geo_transform)
        dst_ds.SetProjection(projection)

        binary_mask = np.where(self.cached_mask > 127, 255, 0).astype(np.uint8)
        dst_ds.GetRasterBand(1).WriteArray(binary_mask)
        dst_ds.GetRasterBand(1).SetNoDataValue(0)

        dst_ds.FlushCache()
        dst_ds = None
        print(f"[✓] Mask saved with georeferencing to: {output_path}")

        # Move TFW file from mask folder to output folder
        if os.path.exists(tfw_path):
            try:
                os.makedirs(self.output_mask_dir, exist_ok=True)
                os.replace(tfw_path, output_tfw_path)
                print(f"[→] Moved TFW file to: {output_tfw_path}")
            except Exception as e:
                print(f"[!] Failed to move TFW file: {e}")

        # Remove the original mask .tif file
        if os.path.exists(mask_path):
            try:
                os.remove(mask_path)
            except Exception:
                pass

        del self.mask_files[self.current_index]
        del self.image_files[self.current_index]

        if not self.mask_files:
            safe_showinfo("Done", "All masks processed. Exiting.")
            self.cached_image = np.zeros_like(self.cached_image)
            self.cached_mask = np.zeros_like(self.cached_mask)
            self.quit_editor()
            return

        if self.current_index >= len(self.image_files):
            self.current_index = 0

        self.load_current_image()

    def undo(self):
        if self.undo_stack:
            self.cached_mask = self.undo_stack.pop()

    def toggle_eraser(self): self.is_erasing = not self.is_erasing
    def toggle_line_mode(self): self.line_mode_active = not self.line_mode_active; self.line_points = []
    def connect_points_cmd(self): self.connect_points() if self.line_mode_active else None
    def quit_editor(self):
        self.running = False
        cv2.destroyAllWindows()
        try:
            # This closes all Tkinter windows
            for widget in tk._default_root.winfo_children():
                widget.destroy()
            tk._default_root.quit()
            tk._default_root.destroy()
        except:
            pass
        finally:
            sys.exit(0)  # Graceful exit


    def display_image(self):
        combined = self.cached_image.copy()
        if self.show_mask_overlay:
            combined[self.cached_mask > 0] = [0, 255, 0]

        h, w = combined.shape[:2]
        crop_w = int(w / self.zoom_factor)
        crop_h = int(h / self.zoom_factor)
        cx, cy = w // 2, h // 2
        x1 = max(0, min(cx - crop_w // 2 + self.pan_x, w - crop_w))
        y1 = max(0, min(cy - crop_h // 2 + self.pan_y, h - crop_h))
        x2, y2 = x1 + crop_w, y1 + crop_h

        cropped = combined[y1:y2, x1:x2]
        cropped_mask = self.cached_mask[y1:y2, x1:x2]
        scale = min(self.screen_width / cropped.shape[1], self.screen_height / cropped.shape[0])
        nw, nh = int(cropped.shape[1] * scale), int(cropped.shape[0] * scale)
        resized = cv2.resize(cropped, (nw, nh), interpolation=cv2.INTER_AREA)
        resized_mask = cv2.resize(cropped_mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
        self.resize_factors = (nw / cropped.shape[1], nh / cropped.shape[0])
        self.crop_offsets = (x1, y1)

        if self.show_mask_overlay:
            resized[resized_mask > 0] = [0, 255, 0]

        if self.line_mode_active:
            for px, py in self.line_points:
                dx = int((px - x1) * self.resize_factors[0])
                dy = int((py - y1) * self.resize_factors[1])
                cv2.circle(resized, (dx, dy), 5, (0, 0, 255), -1)

        cv2.imshow('Image Viewer', resized)

    def run(self):
        self.load_current_image()
        cv2.namedWindow('Image Viewer')
        cv2.setMouseCallback('Image Viewer', self.draw_on_mask)
        while self.running:
            self.display_image()
            key = cv2.waitKey(1) & 0xFF
            if key == ord('a'): self.prev_image()
            elif key == ord('d'): self.next_image()
            elif key == ord('p'): self.connect_points_cmd()
            elif key == ord('+'): self.zoom_in()
            elif key == ord('-'): self.zoom_out()
            elif key == ord('i'): self.pan_up()
            elif key == ord('k'): self.pan_down()
            elif key == ord('j'): self.pan_left()
            elif key == ord('l'): self.pan_right()
            elif key == ord('t'): self.toggle_mask_overlay()
            elif key == ord('s'): self.save_mask()
            elif key == ord('z'): self.undo()
            elif key == ord('e'): self.toggle_eraser()
            elif key == ord('o'): self.toggle_line_mode()
            elif key == ord('f'): self.brush_size = min(self.brush_size + 1, 50)
            elif key == ord('g'): self.brush_size = max(self.brush_size - 1, 1)
            elif key == 27: self.quit_editor()


def open_config_window():
    config = {}
    root = tk.Tk()
    root.title("Mask Editor Configuration")

    image_dir_var = tk.StringVar()
    mask_dir_var = tk.StringVar()
    output_dir_var = tk.StringVar()
    screen_width_var = tk.IntVar(value=1920)
    screen_height_var = tk.IntVar(value=900)

    def browse_dir(var, title):
        selected = filedialog.askdirectory(title=title)
        if selected:
            var.set(selected)

    tk.Label(root, text="Primary Image Folder:").grid(row=0, column=0, sticky="w")
    tk.Entry(root, textvariable=image_dir_var, width=50).grid(row=0, column=1)
    tk.Button(root, text="Browse", command=lambda: browse_dir(image_dir_var, "Select Primary Image Folder")).grid(row=0, column=2)

    tk.Label(root, text="Mask Folder:").grid(row=1, column=0, sticky="w")
    tk.Entry(root, textvariable=mask_dir_var, width=50).grid(row=1, column=1)
    tk.Button(root, text="Browse", command=lambda: browse_dir(mask_dir_var, "Select Mask Folder")).grid(row=1, column=2)

    tk.Label(root, text="Output Mask Folder:").grid(row=2, column=0, sticky="w")
    tk.Entry(root, textvariable=output_dir_var, width=50).grid(row=2, column=1)
    tk.Button(root, text="Browse", command=lambda: browse_dir(output_dir_var, "Select Output Folder")).grid(row=2, column=2)

    tk.Label(root, text="Screen Width:").grid(row=3, column=0, sticky="w")
    tk.Scale(root, from_=800, to=3840, orient=tk.HORIZONTAL, variable=screen_width_var).grid(row=3, column=1, sticky="ew")

    tk.Label(root, text="Screen Height:").grid(row=4, column=0, sticky="w")
    tk.Scale(root, from_=600, to=2160, orient=tk.HORIZONTAL, variable=screen_height_var).grid(row=4, column=1, sticky="ew")

    def submit():
        if not image_dir_var.get() or not output_dir_var.get():
            messagebox.showerror("Error", "Primary image and output folders are required.")
            return
        config['image_dir'] = image_dir_var.get()
        config['mask_dir'] = mask_dir_var.get()
        config['output_mask_dir'] = output_dir_var.get()
        config['screen_width'] = screen_width_var.get()
        config['screen_height'] = screen_height_var.get()
        root.destroy()

    tk.Button(root, text="Launch Editor", command=submit).grid(row=5, column=1, pady=10)
    root.mainloop()
    return config
def start_control_panel(editor):
    def panel():
        cp = tk.Tk()
        cp.title("Control Panel")

        nav_frame = tk.LabelFrame(cp, text="Navigation")
        nav_frame.grid(row=0, column=0, padx=5, pady=5)
        tk.Button(nav_frame, text="Prev (a)", command=editor.prev_image).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(nav_frame, text="Next (d)", command=editor.next_image).grid(row=0, column=1, padx=2, pady=2)

        zoom_frame = tk.LabelFrame(cp, text="Zoom")
        zoom_frame.grid(row=1, column=0, padx=5, pady=5)
        tk.Button(zoom_frame, text="Zoom In (+)", command=editor.zoom_in).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(zoom_frame, text="Zoom Out (-)", command=editor.zoom_out).grid(row=0, column=1, padx=2, pady=2)

        pan_frame = tk.LabelFrame(cp, text="Pan")
        pan_frame.grid(row=2, column=0, padx=5, pady=5)
        tk.Button(pan_frame, text="Up (i)", command=editor.pan_up).grid(row=0, column=1)
        tk.Button(pan_frame, text="Left (j)", command=editor.pan_left).grid(row=1, column=0)
        tk.Button(pan_frame, text="Right (l)", command=editor.pan_right).grid(row=1, column=2)
        tk.Button(pan_frame, text="Down (k)", command=editor.pan_down).grid(row=2, column=1)

        other = tk.LabelFrame(cp, text="Tools")
        other = tk.LabelFrame(cp, text="Tools")
        brush_frame = tk.LabelFrame(cp, text="Brush Size")
        brush_frame.grid(row=4, column=0, padx=5, pady=5)

        brush_slider = tk.Scale(brush_frame, from_=1, to=50, orient=tk.HORIZONTAL, length=200)
        brush_slider.set(editor.brush_size)
        brush_slider.pack()

        def update_brush_size(val):
            editor.brush_size = int(val)

        brush_slider.config(command=update_brush_size)

        other.grid(row=3, column=0, padx=5, pady=5)
        tk.Button(other, text="Toggle Mask (t)", command=editor.toggle_mask_overlay).grid(row=0, column=0)
        tk.Button(other, text="Save Mask (s)", command=editor.save_mask).grid(row=0, column=1)
        tk.Button(other, text="Undo (z)", command=editor.undo).grid(row=1, column=0)
        tk.Button(other, text="Eraser (e)", command=editor.toggle_eraser).grid(row=1, column=1)
        tk.Button(other, text="Line Mode (o)", command=editor.toggle_line_mode).grid(row=2, column=0)
        tk.Button(other, text="Connect (p)", command=editor.connect_points_cmd).grid(row=2, column=1)
        tk.Button(other, text="Clear (c)", command=editor.clear_mask).grid(row=3, column=0)
        tk.Button(other, text="Quit (ESC)", command=editor.quit_editor).grid(row=3, column=1)

        cp.mainloop()

    threading.Thread(target=panel, daemon=True).start()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    config = open_config_window()
    editor = MaskEditor(
        config['image_dir'],
        config['mask_dir'],
        config['output_mask_dir'],
        config['screen_width'],
        config['screen_height']
    )
    start_control_panel(editor)

    editor.run()


if __name__ == "__main__":
    main()
