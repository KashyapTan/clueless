import {app, BrowserWindow} from 'electron';
import path from 'path';
import {isDev} from './utils.js';

app.on('ready', ()=>{
    const mainWindow = new BrowserWindow({
        width: 800,
        height: 500,
        minWidth: 400,
        minHeight: 300,
        title: 'Clueless',
        frame: false,
        transparent: true,
        resizable: true,
    });
    if (isDev()){
        mainWindow.loadURL('http://localhost:5123');
    }
    else{
        mainWindow.loadFile(path.join(app.getAppPath(), '/dist-react/index.html'));
    }
})