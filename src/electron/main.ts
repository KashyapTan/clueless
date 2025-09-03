import {app, BrowserWindow} from 'electron';
import path from 'path';
import {isDev} from './utils.js';
import { startPythonServer } from './pythonApi.js';

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

    const mainWindow = new BrowserWindow({
        width: 800,
        height: 500,
        minWidth: 400,
        minHeight: 300,
        title: 'Clueless',
        frame: false,
        transparent: true,
        resizable: true,
        alwaysOnTop: true,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        // skipTaskbar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        }
    });

    // Strengthen always-on-top level (optional):
    mainWindow.setAlwaysOnTop(true, 'screen-saver'); // or 'floating'

    // Show across virtual desktops / fullscreen spaces:
    mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

    if (isDev()){
        mainWindow.loadURL('http://localhost:5123');
    }
    else{
        mainWindow.loadFile(path.join(app.getAppPath(), '/dist-react/index.html'));
    }
})