import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {getCompositions, renderMedia} from '@remotion/renderer';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const inputPath = process.argv.includes('--input') ? process.argv[process.argv.indexOf('--input') + 1] : path.join(projectRoot, 'output/remotion_input.json');
const outputPath = process.argv.includes('--output') ? process.argv[process.argv.indexOf('--output') + 1] : path.join(projectRoot, 'output/trending_video.mp4');

if (!fs.existsSync(inputPath)) {
  throw new Error(`input not found: ${inputPath}`);
}

const inputProps = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const serveUrl = await bundle({
  entryPoint: path.join(__dirname, 'src/index.ts'),
  webpackOverride: (config) => config,
});

const compositions = await getCompositions(serveUrl, {inputProps});
const composition = compositions.find((c) => c.id === 'TrendingVideo');
if (!composition) {
  throw new Error('Composition TrendingVideo not found');
}

console.log(`Rendering ${composition.durationInFrames} frames @ ${composition.fps}fps`);
await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  audioCodec: 'aac',
  outputLocation: outputPath,
  inputProps,
  chromiumOptions: {
    gl: 'swangle',
  },
  concurrency: 2,
  imageFormat: 'jpeg',
  jpegQuality: 92,
  overwrite: true,
});
console.log(`Rendered: ${outputPath}`);
