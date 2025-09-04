import subprocess
import sys
import os
import shutil
from pathlib import Path

def build_python_server():
    """Build the Python server using PyInstaller"""
    
    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Create dist directory if it doesn't exist
    dist_dir = project_root / "dist-python"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(exist_ok=True)
    
    # Activate virtual environment and run PyInstaller
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print(f"Virtual environment not found at: {venv_python}")
        print("Please run 'npm run install:python' first.")
        sys.exit(1)
    
    # Build command
    cmd = [
        str(venv_python),
        "-m", "PyInstaller",
        "--clean",
        "--distpath", str(dist_dir),
        "--workpath", str(project_root / "build-temp"),
        "build-server.spec"
    ]
    
    print("Building Python server executable...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Python server built successfully!")
        print(f"Executable created at: {dist_dir / 'clueless-server.exe'}")
        
        # Verify the executable was created
        exe_path = dist_dir / "clueless-server.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Executable size: {size_mb:.1f} MB")
        else:
            print("❌ Executable not found after build")
            sys.exit(1)
            
    except subprocess.CalledProcessError as e:
        print("❌ Build failed!")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        sys.exit(1)
    
    # Clean up build artifacts
    build_temp = project_root / "build-temp"
    if build_temp.exists():
        shutil.rmtree(build_temp)
    
    print("Build complete!")

if __name__ == "__main__":
    build_python_server()
