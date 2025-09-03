import { spawn, ChildProcess, SpawnOptions } from 'child_process';
import path from 'path';
import { app } from 'electron';
import { isDev } from './utils.js';
import fs from 'fs';

let pythonProcess: ChildProcess | null = null;

function findPythonExecutable(): string {
    if (isDev()) {
        // In development, use the virtual environment
        const venvPython = path.join(process.cwd(), '.venv', 'Scripts', 'python.exe');
        if (fs.existsSync(venvPython)) {
            return venvPython;
        }
        
        // Fallback to system Python
        return 'python';
    } else {
        // In production, try bundled Python first
        const resourcesPath = process.resourcesPath;
        const bundledPython = path.join(resourcesPath, 'python', 'Scripts', 'python.exe');
        
        if (fs.existsSync(bundledPython)) {
            return bundledPython;
        }
        
        // Fallback to system Python
        return 'python';
    }
}

function getPythonServerArgs(): string[] {
    if (isDev()) {
        // In development, run as module
        return ['-m', 'source.main'];
    } else {
        // In production, check if we have bundled source
        const resourcesPath = process.resourcesPath;
        const bundledMain = path.join(resourcesPath, 'python', 'source', 'main.py');
        
        if (fs.existsSync(bundledMain)) {
            return [bundledMain];
        }
        
        // Fallback to module approach
        return ['-m', 'source.main'];
    }
}

export async function startPythonServer(): Promise<void> {
    return new Promise((resolve, reject) => {
        const pythonPath = findPythonExecutable();
        const args = getPythonServerArgs();
        
        console.log(`Starting Python server...`);
        console.log(`Python path: ${pythonPath}`);
        console.log(`Args: ${args.join(' ')}`);

        const options: SpawnOptions = {
            stdio: ['pipe', 'pipe', 'pipe']
        };

        // Set working directory appropriately
        if (isDev()) {
            options.cwd = process.cwd();
        } else {
            const resourcesPath = process.resourcesPath;
            const pythonDir = path.join(resourcesPath, 'python');
            if (fs.existsSync(pythonDir)) {
                options.cwd = pythonDir;
            }
        }

        pythonProcess = spawn(pythonPath, args, options);
        let serverStarted = false;

        if (pythonProcess) {
            pythonProcess.stdout?.on('data', (data) => {
                const output = data.toString();
                console.log(`Python stdout: ${output}`);
                
                // Check if server started successfully
                if (output.includes('Starting FastAPI WebSocket server') || 
                    output.includes('Application startup complete')) {
                    serverStarted = true;
                }
            });

            pythonProcess.stderr?.on('data', (data) => {
                const error = data.toString();
                console.error(`Python stderr: ${error}`);
                
                // If we see an import error or other startup failure, reject immediately
                if (error.includes('ImportError') || 
                    error.includes('ModuleNotFoundError') || 
                    error.includes('SyntaxError')) {
                    if (!serverStarted) {
                        reject(new Error(`Python server failed to start: ${error}`));
                    }
                }
            });

            pythonProcess.on('error', (error) => {
                console.error(`Failed to start Python process: ${error}`);
                reject(error);
            });

            pythonProcess.on('close', (code) => {
                console.log(`Python process exited with code ${code}`);
                pythonProcess = null;
                if (code !== 0 && !serverStarted) {
                    reject(new Error(`Python process exited with code ${code}`));
                }
            });
        }

        // Give the server time to start up and check if it's actually running
        setTimeout(async () => {
            try {
                // Test if the server is responding
                const response = await fetch('http://localhost:8000/ws', {
                    method: 'GET',
                    headers: { 'Connection': 'Upgrade', 'Upgrade': 'websocket' }
                }).catch(() => null);
                
                if (response || serverStarted) {
                    console.log('Python server started successfully');
                    resolve();
                } else {
                    console.error('Python server failed to start - no response on port 8000');
                    reject(new Error('Python server failed to start'));
                }
            } catch (error) {
                console.error('Error checking Python server status:', error);
                reject(error);
            }
        }, 5000);
    });
}

export function stopPythonServer(): void {
    if (pythonProcess) {
        console.log('Stopping Python server...');
        pythonProcess.kill();
        pythonProcess = null;
    }
}

// Cleanup on app quit
app.on('before-quit', () => {
    stopPythonServer();
});

app.on('window-all-closed', () => {
    stopPythonServer();
});
