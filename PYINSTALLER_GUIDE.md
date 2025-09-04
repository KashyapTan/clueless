# PyInstaller Build Process

This document explains the transition from bundling the Python virtual environment to using PyInstaller for creating a standalone Python executable.

## Overview

Previously, the entire Python virtual environment (`.venv`) was bundled with the Electron app, resulting in large distribution sizes (hundreds of MBs). Now, PyInstaller creates a single standalone executable (`clueless-server.exe`) that includes all Python dependencies, reducing the distribution size significantly.

## Build Process

### 1. PyInstaller Configuration

- **Spec file**: `build-server.spec` - Defines the build configuration
- **Build script**: `scripts/build-python-exe.py` - Automates the build process
- **Output**: `dist-python/clueless-server.exe` - Standalone executable (~24MB)

### 2. Key Changes

#### pythonApi.ts
- **Development**: Still uses virtual environment Python
- **Production**: Uses PyInstaller executable from `resources/python-server/`
- **No arguments needed**: The executable is self-contained

#### electron-builder.json
- **Removed**: Bundling of `.venv` and `source` directories
- **Added**: Only includes `dist-python` as `python-server` in resources

#### package.json
- **New script**: `build:python-exe` - Builds the PyInstaller executable
- **Updated build**: Includes Python executable build in the main build process

### 3. File Structure

```
Before (with bundled Python):
├── resources/
│   └── python/           # ~200MB+ virtual environment
│       ├── Scripts/
│       ├── Lib/
│       └── source/

After (with PyInstaller):
├── resources/
│   └── python-server/    # ~24MB standalone executable
│       └── clueless-server.exe
```

### 4. Build Commands

```bash
# Build Python executable only
npm run build:python-exe

# Full build (includes Python executable)
npm run build

# Distribution build
npm run dist
```

### 5. Development vs Production

#### Development
- Uses virtual environment: `.venv/Scripts/python.exe`
- Runs as module: `python -m source.main`
- Hot reloading supported

#### Production
- Uses PyInstaller executable: `resources/python-server/clueless-server.exe`
- No arguments needed (self-contained)
- Fast startup, smaller distribution

### 6. Benefits

1. **Smaller distribution size**: ~24MB vs ~200MB+
2. **Faster startup**: No Python environment initialization
3. **Self-contained**: No Python installation required on target machine
4. **Simplified deployment**: Single executable vs entire environment
5. **Better security**: Compiled bytecode vs source code

### 7. Troubleshooting

#### Missing Dependencies
If the executable fails due to missing modules, add them to `hiddenimports` in `build-server.spec`.

#### Build Failures
Check that all required packages are installed in the virtual environment:
```bash
npm run install:python
```

#### Runtime Errors
Use console mode in PyInstaller spec file to see error messages during development.

### 8. Future Improvements

- **Cross-platform builds**: Create executables for macOS and Linux
- **Optimization**: Further reduce executable size using UPX compression
- **Auto-updates**: Implement automatic executable updates
- **Caching**: Cache built executables to speed up repeated builds
