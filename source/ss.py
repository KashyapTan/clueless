import tkinter as tk
from tkinter import filedialog
import PIL.ImageGrab as ImageGrab
from PIL import Image, ImageTk
import os
import datetime
from pynput import keyboard
import threading
import sys
import platform
import time

# Fix for high DPI displays on Windows
if platform.system() == "Windows":
    try:
        import ctypes
        from ctypes import wintypes
        
        # Set DPI awareness for the process - try multiple methods for better compatibility
        try:
            # Windows 10, version 1703 and later (best option)
            ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        except:
            try:
                # Windows 10, version 1607 and later  
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except:
                try:
                    # Windows Vista and later (fallback)
                    ctypes.windll.user32.SetProcessDPIAware()
                except:
                    pass  # Fallback: do nothing if DPI functions aren't available
                
        def get_dpi_scale():
            """Get the DPI scaling factor for the primary monitor"""
            try:
                # Try to get DPI for the monitor containing the cursor
                try:
                    # Get cursor position
                    cursor_pos = wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
                    
                    # Get monitor handle for the cursor position
                    monitor = ctypes.windll.user32.MonitorFromPoint(
                        cursor_pos, 1  # MONITOR_DEFAULTTOPRIMARY
                    )
                    
                    # Get DPI for this specific monitor (Windows 10+)
                    dpi_x = ctypes.c_uint()
                    dpi_y = ctypes.c_uint()
                    ctypes.windll.shcore.GetDpiForMonitor(
                        monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)  # MDT_EFFECTIVE_DPI
                    )
                    return dpi_x.value / 96.0
                except:
                    # Fallback to system DPI
                    hdc = ctypes.windll.user32.GetDC(0)
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                    ctypes.windll.user32.ReleaseDC(0, hdc)
                    return dpi / 96.0
            except:
                return 1.0
                
    except ImportError:
        def get_dpi_scale():
            return 1.0
else:
    def get_dpi_scale():
        return 1.0

class ScreenshotService:
    def __init__(self, callback=None, start_callback=None):
        self.listener = None
        self.running = False
        self.callback = callback  # Function to call when screenshot is taken
        self.start_callback = start_callback  # Function to call when screenshot capture starts
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
        """Start listening for Alt+. keyboard shortcut (strict)."""
        self.running = True
        print("Screenshot service started. Press Alt+. to take a region screenshot.")
        print("Press Ctrl+C to stop the service.")

        def on_activate():
            with self._lock:
                if not self.running:  # Check if service is still running
                    return
                if self.capturing:
                    return
                self.capturing = True
            print("Hotkey detected! Starting region selection...")
            
            # Call the start callback if provided
            if self.start_callback:
                threading.Thread(target=self.start_callback, daemon=True).start()
                
            threading.Thread(target=self._do_capture, args=(save_folder,), daemon=True).start()

        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<alt>+.'),
            on_activate
        )

        def on_press(key):
            if self.listener and self.running:
                hotkey.press(self.listener.canonical(key))
        
        def on_release(key):
            if self.listener and self.running:
                hotkey.release(self.listener.canonical(key))

        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self.listener.start()
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nScreenshot service stopped.")
        finally:
            self.stop_listener()

    def stop_listener(self):
        """Stop the keyboard listener."""
        self.running = False
        if self.listener:
            try:
                self.listener.stop()
                print("Keyboard listener stopped")
            except Exception as e:
                print(f"Error stopping keyboard listener: {e}")
            self.listener = None

def take_region_screenshot(save_folder="screenshots", debug=False):
    """
    Opens a region selection tool and returns the path to the saved screenshot
    """
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    class RegionSelector:
        def __init__(self, debug=False):
            self.start_x = 0
            self.start_y = 0
            self.end_x = 0
            self.end_y = 0
            self.rect_id = None
            self.result_path = None
            self.dpi_scale = get_dpi_scale()
            self.debug = debug
            
        def select_region(self):
            root = tk.Tk()
            
            # Configure Tkinter for high DPI on Windows
            if platform.system() == "Windows":
                try:
                    root.tk.call('tk', 'scaling', self.dpi_scale)
                except:
                    pass
            
            root.attributes('-fullscreen', True)
            root.attributes('-alpha', 1.0)  # Fully visible for region selection UI
            root.configure(bg='grey')
            root.attributes('-topmost', True)
            root.withdraw()  # Hide initially
            
            root.after(100, self._show_selector, root)
            root.mainloop()
            return self.result_path
            
        def _show_selector(self, root):
            root.deiconify()
            
            # Capture the screen at full resolution first
            screen = ImageGrab.grab()
            screen_width, screen_height = screen.size
            
            # Get Tkinter's view of screen dimensions
            root.update_idletasks()
            tk_width = root.winfo_screenwidth()
            tk_height = root.winfo_screenheight()
            
            # Calculate coordinate transformation ratios
            # These handle the case where Tkinter coordinates != actual pixels
            scale_x = screen_width / tk_width
            scale_y = screen_height / tk_height
            
            if self.debug:
                print(f"Debug: Screen resolution: {screen_width}x{screen_height}")
                print(f"Debug: Tkinter resolution: {tk_width}x{tk_height}")
                print(f"Debug: Scale factors: {scale_x:.3f}x, {scale_y:.3f}y")
                print(f"Debug: DPI scale: {self.dpi_scale:.3f}")
            
            # Create display version - scale down screen capture to match Tkinter's coordinate system
            # This ensures the preview matches what the user will select
            if scale_x != 1.0 or scale_y != 1.0:
                display_screen = screen.resize((tk_width, tk_height), Image.Resampling.LANCZOS)
            else:
                display_screen = screen
            # Create dimmed overlay for the display
            screen_rgba = display_screen.convert('RGBA')
            overlay = Image.new('RGBA', screen_rgba.size, (0, 0, 0, 100))
            dimmed = Image.alpha_composite(screen_rgba, overlay)
            dimmed_photo = ImageTk.PhotoImage(dimmed)
            original_photo = ImageTk.PhotoImage(display_screen)
            
            canvas = tk.Canvas(root, cursor="cross")
            canvas.pack(fill=tk.BOTH, expand=True)
            canvas.create_image(0, 0, anchor=tk.NW, image=dimmed_photo, tags=("base",))
            
            # Store references to prevent garbage collection
            canvas.dimmed_photo = dimmed_photo  # type: ignore
            canvas.original_photo = original_photo  # type: ignore

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
                    # Use display coordinates for the preview
                    region = display_screen.crop((x1, y1, x2, y2))
                    region_photo = ImageTk.PhotoImage(region)
                    canvas.create_image(x1, y1, anchor=tk.NW, image=region_photo, tags=('reveal',))
                    canvas._reveal_photo = region_photo  # type: ignore
                    canvas.create_rectangle(x1, y1, x2, y2, outline='white', width=2, tags=('outline',))
                
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
                    # Convert Tkinter coordinates to actual screen pixel coordinates
                    actual_x1 = int(x1 * scale_x)
                    actual_y1 = int(y1 * scale_y)
                    actual_x2 = int(x2 * scale_x)
                    actual_y2 = int(y2 * scale_y)
                    
                    # Ensure coordinates are within screen bounds
                    actual_x1 = max(0, min(actual_x1, screen_width))
                    actual_y1 = max(0, min(actual_y1, screen_height))
                    actual_x2 = max(0, min(actual_x2, screen_width))
                    actual_y2 = max(0, min(actual_y2, screen_height))
                    
                    if self.debug:
                        print(f"Debug: Tkinter coords: ({x1},{y1}) to ({x2},{y2})")
                        print(f"Debug: Actual coords: ({actual_x1},{actual_y1}) to ({actual_x2},{actual_y2})")
                    
                    # Crop from the original full-resolution screen capture
                    region_screenshot = screen.crop((actual_x1, actual_y1, actual_x2, actual_y2))
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    filepath = os.path.join(save_folder, filename)
                    region_screenshot.save(filepath)
                    self.result_path = filepath
                    
                    if self.debug:
                        print(f"Debug: Saved {region_screenshot.size[0]}x{region_screenshot.size[1]} screenshot")
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
                bg="black", fg="white", font=("Arial", 12)
            )
            instructions.place(relx=0.5, rely=0.02, anchor=tk.N)
            canvas.focus_set()
            canvas.screen_photo = original_photo  # type: ignore
    
    selector = RegionSelector(debug)
    return selector.select_region()

def take_region_screenshot_debug(save_folder="screenshots"):
    """
    Debug version of take_region_screenshot that shows coordinate mapping info
    """
    return take_region_screenshot(save_folder, debug=True)

def take_fullscreen_screenshot(save_folder="screenshots"):
    """
    Capture entire screen without UI overlay.
    Returns the path to the saved screenshot.
    """
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    try:
        # Capture the entire screen
        screen = ImageGrab.grab()
        
        # Generate unique filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"fullscreen_{timestamp}.png"
        filepath = os.path.join(save_folder, filename)
        
        # Save the screenshot
        screen.save(filepath)
        print(f"Fullscreen screenshot saved: {filepath}")
        
        return filepath
    except Exception as e:
        print(f"Error taking fullscreen screenshot: {e}")
        return None

def create_thumbnail(image_path, max_size=(300, 300)):
    """
    Create a base64 encoded thumbnail from an image file.
    Returns base64 string for preview display.
    """
    import base64
    from io import BytesIO
    
    try:
        with Image.open(image_path) as img:
            # Create thumbnail preserving aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to base64 with good quality
            buffer = BytesIO()
            img.save(buffer, format='PNG', optimize=False)
            buffer.seek(0)
            
            return base64.b64encode(buffer.read()).decode('utf-8')
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return None

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
    print("Press Alt+. to take a region screenshot")
    print("Press Ctrl+C to exit")
    start_screenshot_service("screenshots")