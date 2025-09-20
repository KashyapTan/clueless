import {app, BrowserWindow} from 'electron';
import path from 'path';
import {isDev} from './utils.js';
import { startPythonServer, stopPythonServer } from './pythonApi.js';

let mainWindow: BrowserWindow | null = null;

app.on('ready', async ()=>{
    // Only start Python server in production mode
    // In development, the dev:pyserver script handles this
    if (!isDev()) {
        try {
            await startPythonServer();
            console.log('Python server started successfully');
        } catch (error) {
            console.error('Failed to start Python server:', error);
        }
    } else {
        console.log('Development mode: Python server should be started by dev:pyserver script');
    }

    mainWindow = new BrowserWindow({
        width: 400,
        height: 400,
        minWidth: 30,
        minHeight: 20,
        title: 'Clueless',
        frame: false,
        transparent: true,
        resizable: true,
        alwaysOnTop: true,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        }
    });

    // Strengthen always-on-top level (optional):
    mainWindow.setAlwaysOnTop(true, 'screen-saver'); // or 'floating'
    mainWindow.setContentProtection(true); // Prevent screen capture on some OSes

    // Show across virtual desktops / fullscreen spaces:
    // mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

    // Handle window closed event
    mainWindow.on('closed', async () => {
        console.log('Main window closed, cleaning up...');
        await stopPythonServer();
        mainWindow = null;
    });

    // Handle window close event (before window is actually closed)
    mainWindow.on('close', async () => {
        console.log('Main window closing, initiating cleanup...');
        await stopPythonServer();
    });

    if (isDev()){
        mainWindow.loadURL('http://localhost:5123');
    }
    else{
        mainWindow.loadFile(path.join(app.getAppPath(), '/dist-react/index.html'));
    }
})

// Handle all windows closed
app.on('window-all-closed', async () => {
    console.log('All windows closed, stopping Python server...');
    await stopPythonServer();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Handle app before quit
app.on('before-quit', async () => {
    console.log('App is quitting, cleaning up processes...');
    await stopPythonServer();
});

// Handle app will quit
app.on('will-quit', async () => {
    console.log('App will quit, final cleanup...');
    await stopPythonServer();
});