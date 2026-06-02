import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {getCompositions, renderStill} from '@remotion/renderer';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const inputPath = process.argv.includes('--input') ? process.argv[process.argv.indexOf('--input') + 1] : path.join(projectRoot, 'output/remotion_input.json');
const outDir = process.argv.includes('--out-dir') ? process.argv[process.argv.indexOf('--out-dir') + 1] : path.join(projectRoot, 'output/remotion_stills');

const inputProps = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
fs.mkdirSync(outDir, {recursive: true});

const serveUrl = await bundle({entryPoint: path.join(__dirname, 'src/index.ts')});
const compositions = await getCompositions(serveUrl, {inputProps});
const composition = compositions.find((c) => c.id === 'TrendingVideo');
if (!composition) throw new Error('Composition TrendingVideo not found');

let frame = 12;
for (let i = 0; i < inputProps.scenes.length; i++) {
  const scene = inputProps.scenes[i];
  const out = path.join(outDir, `scene_${String(i).padStart(2, '0')}.png`);
  await renderStill({
    composition,
    serveUrl,
    inputProps,
    frame: Math.min(frame, composition.durationInFrames - 1),
    output: out,
    imageFormat: 'png',
    chromiumOptions: {gl: 'swangle'},
  });
  console.log(`still ${i}: ${out}`);
  frame += scene.durationFrames;
}
