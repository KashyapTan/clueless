import { spawn, ChildProcess, SpawnOptions } from 'child_process';
import path from 'path';
import { app } from 'electron';
import { isDev } from './utils.js';
import fs from 'fs';
import net from 'net';

let pythonProcess: ChildProcess | null = null;
let detectedPort: number = 8000;

async function findAvailablePort(startPort: number = 8000): Promise<number> {
    for (let port = startPort; port < startPort + 10; port++) {
        const server = net.createServer();
        try {
            await new Promise<void>((resolve, reject) => {
                server.once('error', reject);
                server.once('listening', () => {
                    server.close();
                    resolve();
                });
                server.listen(port);
            });
            return port;
        } catch {
            continue;
        }
    }
    throw new Error(`No available ports found in range ${startPort}-${startPort + 9}`);
}

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
        // In production, also try virtual environment first since we're likely distributing with it
        const venvPython = path.join(process.cwd(), '.venv', 'Scripts', 'python.exe');
        if (fs.existsSync(venvPython)) {
            return venvPython;
        }
        
        // Try bundled Python
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

async function killProcessesOnPorts(ports: number[]): Promise<void> {
    const { exec } = await import('child_process');
    const { promisify } = await import('util');
    const execAsync = promisify(exec);
    
    for (const port of ports) {
        try {
            // Find processes using the port on Windows
            const { stdout } = await execAsync(`netstat -ano | findstr :${port}`);
            const lines = stdout.split('\n').filter(line => line.includes('LISTENING'));
            
            for (const line of lines) {
                const parts = line.trim().split(/\s+/);
                const pid = parts[parts.length - 1];
                if (pid && !isNaN(parseInt(pid))) {
                    try {
                        // Check if it's a Python process before killing
                        const { stdout: processInfo } = await execAsync(`tasklist /FI "PID eq ${pid}" /NH`);
                        if (processInfo.toLowerCase().includes('python')) {
                            console.log(`Terminating Python process ${pid} on port ${port}`);
                            await execAsync(`taskkill /F /PID ${pid}`);
                        }
                    } catch {
                        // Ignore errors when checking/killing processes
                    }
                }
            }
        } catch {
            // Port not in use or other error, continue
        }
    }
}

export async function startPythonServer(): Promise<void> {
    // Only clean up existing processes in production, not in development
    if (!isDev()) {
        console.log('Checking for existing Python processes on ports 8000-8004...');
        await killProcessesOnPorts([8000, 8001, 8002, 8003, 8004]);
    }
    
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
                
                // Extract port number from server output
                const portMatch = output.match(/Starting server on port (\d+)/);
                if (portMatch) {
                    detectedPort = parseInt(portMatch[1]);
                    console.log(`Detected server port: ${detectedPort}`);
                }
                
                // Check if server started successfully
                if (output.includes('Starting FastAPI WebSocket server') || 
                    output.includes('Application startup complete')) {
                    serverStarted = true;
                }
            });

            pythonProcess.stderr?.on('data', (data) => {
                const error = data.toString();
                console.error(`Python stderr: ${error}`);
                
                // Handle port binding errors specifically
                if (error.includes('error while attempting to bind on address') || 
                    error.includes('Address already in use')) {
                    console.log('Port conflict detected, Python server will try alternative ports...');
                    return; // Don't reject immediately, let Python handle port finding
                }
                
                // If we see other startup failures, reject immediately
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
        setTimeout(() => {
            const checkServerPorts = async () => {
                try {
                    // Try to find the server on the detected port or fallback ports
                    const portsToTry = [detectedPort, 8000, 8001, 8002, 8003, 8004];
                    let serverFound = false;
                    
                for (const port of portsToTry) {
                    try {
                        // Test if the server is responding on this port
                        // Try a simple GET request to the root endpoint instead of WebSocket
                        const controller = new AbortController();
                        const timeoutId = setTimeout(() => controller.abort(), 1000);
                        
                        const response = await fetch(`http://localhost:${port}/`, {
                            method: 'GET',
                            signal: controller.signal
                        }).catch(() => null);
                        
                        clearTimeout(timeoutId);
                        
                        if (response && (response.status === 404 || response.status === 200)) {
                            // 404 is expected for FastAPI root if no route is defined
                            // 200 means there's a route defined
                            detectedPort = port;
                            console.log(`Python server found on port ${port}`);
                            serverFound = true;
                            break;
                        }
                    } catch {
                        // Continue to next port
                        continue;
                    }
                }                    if (serverFound || serverStarted) {
                        console.log('Python server started successfully');
                        resolve();
                    } else {
                        console.error('Python server failed to start - no response on any port');
                        reject(new Error('Python server failed to start'));
                    }
                } catch (error) {
                    console.error('Error checking Python server status:', error);
                    reject(error);
                }
            };
            
            checkServerPorts();
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

export function getServerPort(): number {
    return detectedPort;
}

// Cleanup on app quit
app.on('before-quit', () => {
    stopPythonServer();
});

app.on('window-all-closed', () => {
    stopPythonServer();
});
