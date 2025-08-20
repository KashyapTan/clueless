import {app, BrowserWindow} from 'electron';
import path from 'path';
import {isDev} from './utils.js';

app.on('ready', ()=>{
    const mainWindow = new BrowserWindow({});
    if (isDev()){
        mainWindow.loadURL('http://localhost:5123');
    }
    else{
        mainWindow.loadFile(path.join(app.getAppPath(), '/dist-react/index.html'));
    }
})