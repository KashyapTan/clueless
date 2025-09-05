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
        // In production, use the PyInstaller-generated executable
        const resourcesPath = process.resourcesPath;
        const serverExecutable = path.join(resourcesPath, 'python-server', 'clueless-server.exe');
        
        if (fs.existsSync(serverExecutable)) {
            return serverExecutable;
        }
        
        // Fallback: try in app directory
        const appPath = path.dirname(process.execPath);
        const fallbackExecutable = path.join(appPath, 'resources', 'python-server', 'clueless-server.exe');
        
        if (fs.existsSync(fallbackExecutable)) {
            return fallbackExecutable;
        }
        
        throw new Error(`Python server executable not found at: ${serverExecutable} or ${fallbackExecutable}`);
    }
}

function getPythonServerArgs(): string[] {
    if (isDev()) {
        // In development, run as module
        return ['-m', 'source.main'];
    } else {
        // In production, the PyInstaller executable doesn't need arguments
        // as it's a standalone executable
        return [];
    }
}

async function killProcessesOnPorts(ports: number[]): Promise<void> {
    const { exec } = await import('child_process');
    const { promisify } = await import('util');
    const execAsync = promisify(exec);
    
    for (const port of ports) {
        try {
            console.log(`Checking for processes on port ${port}...`);
            
            // Find processes using the port on Windows
            const { stdout } = await execAsync(`netstat -ano | findstr :${port}`);
            const lines = stdout.split('\n').filter(line => line.includes('LISTENING'));
            
            for (const line of lines) {
                const parts = line.trim().split(/\s+/);
                const pid = parts[parts.length - 1];
                if (pid && !isNaN(parseInt(pid))) {
                    try {
                        // Check if process exists and get its name
                        const { stdout: processInfo } = await execAsync(`tasklist /FI "PID eq ${pid}" /NH /FO CSV`);
                        const processLines = processInfo.split('\n').filter(line => line.trim());
                        
                        for (const processLine of processLines) {
                            if (processLine.includes(pid)) {
                                const processName = processLine.split(',')[0].replace(/"/g, '').toLowerCase();
                                
                                // Kill if it's Python, our app, or related processes
                                if (processName.includes('python') || 
                                    processName.includes('clueless') ||
                                    processName.includes('uvicorn') ||
                                    processName.includes('fastapi')) {
                                    console.log(`Terminating process ${processName} (PID: ${pid}) on port ${port}`);
                                    await execAsync(`taskkill /F /PID ${pid}`);
                                } else {
                                    console.log(`Found process ${processName} on port ${port}, but not terminating (not our process)`);
                                }
                            }
                        }
                    } catch {
                        // Process might have already exited, try to kill anyway
                        try {
                            await execAsync(`taskkill /F /PID ${pid}`);
                            console.log(`Force killed process ${pid} on port ${port}`);
                        } catch {
                            // Ignore if we can't kill it
                        }
                    }
                }
            }
        } catch (error) {
            // Port not in use or other error, continue
            console.log(`No processes found on port ${port} or error checking: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
    
    // Also try to kill any remaining Python processes that might be our server
    try {
        console.log('Checking for any remaining Python processes...');
        const { stdout: allPythonProcesses } = await execAsync(`tasklist /FI "IMAGENAME eq python.exe" /NH /FO CSV`);
        const pythonLines = allPythonProcesses.split('\n').filter(line => line.trim() && line.includes('python.exe'));
        
        for (const line of pythonLines) {
            const parts = line.split(',');
            if (parts.length >= 2) {
                const pid = parts[1].replace(/"/g, '');
                if (pid && !isNaN(parseInt(pid))) {
                    try {
                        // Check command line to see if it's our server
                        const { stdout: cmdLine } = await execAsync(`wmic process where "ProcessId=${pid}" get CommandLine /value`);
                        if (cmdLine.includes('clueless-server') || 
                            cmdLine.includes('source.main') || 
                            cmdLine.includes('uvicorn') ||
                            cmdLine.includes('fastapi')) {
                            console.log(`Terminating Python server process (PID: ${pid})`);
                            await execAsync(`taskkill /F /PID ${pid}`);
                        }
                    } catch {
                        // Ignore errors when checking command line
                    }
                }
            }
        }
    } catch (error) {
        console.log(`Error checking for Python processes: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
}

export async function startPythonServer(): Promise<void> {
    // Clean up any existing processes on startup (both dev and production)
    console.log('Cleaning up any existing processes before starting...');
    await killProcessesOnPorts([8000, 8001, 8002, 8003, 8004]);
    
    // Wait a moment for cleanup to complete
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    return new Promise((resolve, reject) => {
        const pythonPath = findPythonExecutable();
        const args = getPythonServerArgs();
        
        console.log(`Starting Python server...`);
        console.log(`Python executable: ${pythonPath}`);
        console.log(`Args: ${args.join(' ')}`);

        const options: SpawnOptions = {
            stdio: ['pipe', 'pipe', 'pipe']
        };

        // Set working directory appropriately
        if (isDev()) {
            options.cwd = process.cwd();
        } else {
            // For PyInstaller executable, we can use the directory where the executable is located
            const executableDir = path.dirname(pythonPath);
            options.cwd = executableDir;
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

export async function stopPythonServer(): Promise<void> {
    console.log('Stopping Python server...');
    
    // First try to gracefully stop the process
    if (pythonProcess) {
        try {
            pythonProcess.kill('SIGTERM');
            
            // Wait a bit for graceful shutdown
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // If still running, force kill
            if (!pythonProcess.killed) {
                pythonProcess.kill('SIGKILL');
            }
        } catch (error) {
            console.error('Error stopping Python process:', error);
        }
        pythonProcess = null;
    }
    
    // Also kill any remaining Python processes on the known ports
    try {
        await killProcessesOnPorts([8000, 8001, 8002, 8003, 8004]);
    } catch (error) {
        console.error('Error killing processes on ports:', error);
    }
    
    console.log('Python server cleanup completed');
}

export function getServerPort(): number {
    return detectedPort;
}

// Cleanup on app quit
app.on('before-quit', async () => {
    await stopPythonServer();
});

app.on('window-all-closed', async () => {
    await stopPythonServer();
});
