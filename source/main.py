from ollama import chat
from ss import take_region_screenshot, start_screenshot_service
import threading
import time
import os
import glob
import shutil

def clear_screenshots_folder(folder_path="screenshots"):
    """Clear all files in the screenshots folder"""
    try:
        if os.path.exists(folder_path):
            for file_path in glob.glob(os.path.join(folder_path, "*")):
                os.remove(file_path)
            print(f"Cleared screenshots folder: {folder_path}")
    except Exception as e:
        print(f"Error clearing folder: {e}")

def process_screenshot(image_path):
    """Process screenshot with AI and then clear the folder"""
    user_query = input("Please enter your query for the screenshot: ")
    print(f"\nProcessing screenshot + Query")
    
    try:
        response = chat(
            model='qwen2.5vl:7b',
            messages=[
                {
                    'role': 'user',
                    'content': user_query,
                    'images': [image_path],
                }
            ],
            stream=True
        )

        print("Response: \n")
        for chunk in response:
            if 'message' in chunk and 'content' in chunk['message']:
                print(chunk['message']['content'], end='', flush=True)
        print()  # Add newline at the end
            
    except Exception as e:
        print(f"Error processing with AI: {e}")
    
    # Clear the screenshots folder after processing
    folder_path = os.path.dirname(image_path)
    clear_screenshots_folder(folder_path)
    print("-" * 50)
    print("Screenshot processed. Exiting program...")
    
    # Exit the program
    os._exit(0)

def main():
    print("Starting screenshot service in background...")
    print("Press Ctrl+Shift+Alt+S anytime to take a screenshot")
    print("Screenshots will be processed and then deleted automatically")
    print("The service will run until you close this program")
    
    # Start the service in a separate thread with AI callback
    service_thread = threading.Thread(
        target=start_screenshot_service, 
        args=("screenshots", process_screenshot),
        daemon=True
    )
    service_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        return

if __name__ == "__main__":
    main()