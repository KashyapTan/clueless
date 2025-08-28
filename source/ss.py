import tkinter as tk
from tkinter import filedialog
import PIL.ImageGrab as ImageGrab
from PIL import Image, ImageTk
import os
import datetime
from pynput import keyboard
import threading

class ScreenshotService:
    def __init__(self, callback=None):
        self.listener = None
        self.running = False
        self.callback = callback  # Function to call when screenshot is taken
        self.capturing = False
        self._lock = threading.Lock()

    def _do_capture(self, save_folder):
        try:
            path = take_region_screenshot(save_folder)
            if path:
                print(f"Screenshot saved: {path}")
                if self.callback:
                    threading.Thread(target=self.callback, args=(path,), daemon=True).start()
            else:
                print("Screenshot cancelled.")
        finally:
            with self._lock:
                self.capturing = False

    def start_listener(self, save_folder="screenshots"):
        """Start listening for Ctrl+Shift+Alt+S keyboard shortcut (strict)."""
        self.running = True
        print("Screenshot service started. Press Ctrl+Shift+Alt+S to take a region screenshot.")
        print("Press Ctrl+C to stop the service.")

        def on_activate():
            with self._lock:
                if self.capturing:
                    return
                self.capturing = True
            print("Hotkey detected! Starting region selection...")
            threading.Thread(target=self._do_capture, args=(save_folder,), daemon=True).start()

        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<ctrl>+<shift>+<alt>+s'),
            on_activate
        )

        def for_canonical(f):
            return lambda k: f(self.listener.canonical(k))

        self.listener = keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release)
        )
        self.listener.start()
        try:
            self.listener.join()
        except KeyboardInterrupt:
            print("\nScreenshot service stopped.")
            self.running = False

    def stop_listener(self):
        """Stop the keyboard listener."""
        if self.listener:
            self.listener.stop()
            self.running = False

def take_region_screenshot(save_folder="screenshots"):
    """
    Opens a region selection tool and returns the path to the saved screenshot
    """
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    class RegionSelector:
        def __init__(self):
            self.start_x = 0
            self.start_y = 0
            self.end_x = 0
            self.end_y = 0
            self.rect_id = None
            self.result_path = None
            
        def select_region(self):
            root = tk.Tk()
            root.attributes('-fullscreen', True)
            root.attributes('-alpha', 0.3)
            root.configure(bg='grey')
            root.attributes('-topmost', True)
            root.withdraw()  # Hide initially
            
            root.after(100, self._show_selector, root)
            root.mainloop()
            return self.result_path
            
        def _show_selector(self, root):
            root.deiconify()
            screen = ImageGrab.grab()
            screen_rgba = screen.convert('RGBA')
            overlay = Image.new('RGBA', screen_rgba.size, (0, 0, 0, 500))
            dimmed = Image.alpha_composite(screen_rgba, overlay)
            dimmed_photo = ImageTk.PhotoImage(dimmed)
            original_photo = ImageTk.PhotoImage(screen)
            canvas = tk.Canvas(root, cursor="cross")
            canvas.pack(fill=tk.BOTH, expand=True)
            canvas.create_image(0, 0, anchor=tk.NW, image=dimmed_photo, tags=("base",))
            canvas.dimmed_photo = dimmed_photo
            canvas.original_photo = original_photo

            def on_button_press(event):
                self.start_x = event.x
                self.start_y = event.y

            def on_move_press(event):
                canvas.delete('reveal')
                canvas.delete('outline')
                self.end_x = event.x
                self.end_y = event.y
                x1 = min(self.start_x, self.end_x)
                y1 = min(self.start_y, self.end_y)
                x2 = max(self.start_x, self.end_x)
                y2 = max(self.start_y, self.end_y)
                if x2 > x1 and y2 > y1:
                    region = screen.crop((x1, y1, x2, y2))
                    region_photo = ImageTk.PhotoImage(region)
                    canvas.create_image(x1, y1, anchor=tk.NW, image=region_photo, tags=('reveal',))
                    canvas._reveal_photo = region_photo
                    canvas.create_rectangle(x1, y1, x2, y2, outline='white', width=3, tags=('outline',))
                
            def on_button_release(event):
                self.end_x = event.x
                self.end_y = event.y
                root.withdraw()
                root.update()
                x1 = min(self.start_x, self.end_x)
                y1 = min(self.start_y, self.end_y)
                x2 = max(self.start_x, self.end_x)
                y2 = max(self.start_y, self.end_y)
                if x2 > x1 and y2 > y1:
                    region_screenshot = screen.crop((x1, y1, x2, y2))
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    filepath = os.path.join(save_folder, filename)
                    region_screenshot.save(filepath)
                    self.result_path = filepath
                root.destroy()
                
            def on_escape(event):
                root.destroy()
                
            canvas.bind("<Button-1>", on_button_press)
            canvas.bind("<B1-Motion>", on_move_press)
            canvas.bind("<ButtonRelease-1>", on_button_release)
            canvas.bind("<Escape>", on_escape)
            root.bind("<Escape>", on_escape)
            instructions = tk.Label(
                root, 
                text="Click & drag to select region. Press ESC to cancel.",
                bg="grey", fg="black", font=("Roboto", 12)
            )
            instructions.pack(side=tk.TOP, fill=tk.X)
            canvas.focus_set()
            canvas.screen_photo = original_photo
    
    selector = RegionSelector()
    return selector.select_region()

def start_screenshot_service(save_folder="screenshots", callback=None):
    """Start the screenshot service with keyboard shortcut"""
    service = ScreenshotService(callback)
    try:
        service.start_listener(save_folder)
    except KeyboardInterrupt:
        print("\nService stopped by user.")
    return service

if __name__ == "__main__":
    print("Starting screenshot service...")
    print("Press Ctrl+Shift+Alt+S to take a region screenshot")
    print("Press Ctrl+C to exit")
    start_screenshot_service("screenshots")