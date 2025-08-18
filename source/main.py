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
        )

        if 'message' in response and 'content' in response['message']:
            print("Response: \n", response['message']['content'])
        else:
            print("Unexpected response format:", response)
            
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
    # Option 1: Start background service for Ctrl+Shift+S screenshots
    use_service = input('Do you want to start the screenshot service (Ctrl+Shift+Alt+S)? (y/n): ').lower() == 'y'
    
    if use_service:
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
    
    # Option 2: Take a screenshot immediately
    elif input('Do you want to take a screenshot now? (y/n): ').lower() == 'y':
        print("Starting screenshot tool...")
        path = take_region_screenshot("screenshots")
        if not path:
            print("No screenshot taken. Exiting.")
            return
        else:
            process_screenshot(path)
    else:
        # Option 3: Use existing image
        path = input('Please enter the path to the image: ')
        if path and os.path.exists(path):
            # Don't clear folder for existing images outside screenshots folder
            print(f"\nProcessing existing image...")
            response = chat(
                model='qwen2.5vl:7b',
                messages=[
                    {
                        'role': 'user',
                        'content': 'Analyze the content of this image. Then understand the context of the image and try to think about what a follow up task could be based on the content of the image. Based on the most likely follow up task, generate a response that would be appropriate to send to the user.',
                        'images': [path],
                    }
                ],
            )

            if 'message' in response and 'content' in response['message']:
                print("Response: \n", response['message']['content'])
            else:
                print("Unexpected response format:", response)
        else:
            print("Invalid path or file doesn't exist.")

if __name__ == "__main__":
    main()