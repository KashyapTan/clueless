import { bundlePythonResources } from '../src/electron/pcResources.js';

console.log('Building Python resources for distribution...');
bundlePythonResources();
console.log('Build complete!');
