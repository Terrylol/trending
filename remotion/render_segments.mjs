import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {getCompositions, renderMedia} from '@remotion/renderer';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const argValue = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
};
const argNumber = (name, fallback) => {
  const value = Number(argValue(name, fallback));
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} must be a positive number`);
  }
  return value;
};
const parseSceneIndexes = (value, sceneCount) => {
  if (!value || value === 'all') {
    return Array.from({length: sceneCount}, (_, i) => i);
  }
  return value.split(',').map((part) => {
    const index = Number(part.trim());
    if (!Number.isInteger(index) || index < 0 || index >= sceneCount) {
      throw new Error(`Invalid --scene-index value: ${part}`);
    }
    return index;
  });
};

const inputPath = argValue('--input', path.join(projectRoot, 'output/remotion_input.json'));
const outDir = argValue('--out-dir', path.join(projectRoot, 'output/remotion_segments'));
const width = argNumber('--width', 1280);
const height = argNumber('--height', 720);
const concurrency = argNumber('--concurrency', 1);
const crf = argNumber('--crf', 18);
const x264Preset = argValue('--x264-preset', 'medium');
const jpegQuality = argNumber('--jpeg-quality', 90);
const segmentRetries = Math.max(1, Math.floor(argNumber('--segment-retries', 2)));
const cleanOutDir = process.argv.includes('--clean-out-dir');

if (!fs.existsSync(inputPath)) {
  throw new Error(`input not found: ${inputPath}`);
}

const inputProps = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
if (!Array.isArray(inputProps.scenes) || inputProps.scenes.length === 0) {
  throw new Error('inputProps.scenes must be a non-empty array');
}

const sceneIndexes = parseSceneIndexes(argValue('--scene-index', 'all'), inputProps.scenes.length);

if (cleanOutDir) {
  fs.rmSync(outDir, {recursive: true, force: true});
}
fs.mkdirSync(outDir, {recursive: true});

const serveUrl = await bundle({
  entryPoint: path.join(__dirname, 'src/index.ts'),
  webpackOverride: (config) => config,
});

const compositions = await getCompositions(serveUrl, {inputProps});
const composition = compositions.find((c) => c.id === 'SceneSegment');
if (!composition) {
  throw new Error('Composition SceneSegment not found');
}

console.log(`Render settings: ${width}x${height}, fps=${inputProps.fps ?? composition.fps}, concurrency=${concurrency}, crf=${crf}, x264Preset=${x264Preset}, segmentRetries=${segmentRetries}, cleanOutDir=${cleanOutDir}`);

for (const i of sceneIndexes) {
  const scene = inputProps.scenes[i];
  const sceneProps = {
    ...inputProps,
    sceneIndex: i,
    scene,
  };
  const outputLocation = path.join(outDir, `segment_${String(i).padStart(2, '0')}.mp4`);
  const durationInFrames = Math.max(1, Number(scene.durationFrames ?? 1));

  for (let attempt = 1; attempt <= segmentRetries; attempt++) {
    console.log(`Rendering segment ${i + 1}/${inputProps.scenes.length}: ${durationInFrames} frames -> ${outputLocation} (attempt ${attempt}/${segmentRetries})`);
    try {
      await renderMedia({
        composition: {
          ...composition,
          durationInFrames,
          fps: Number(inputProps.fps ?? composition.fps),
          width,
          height,
        },
        serveUrl,
        codec: 'h264',
        audioCodec: 'aac',
        outputLocation,
        inputProps: sceneProps,
        chromiumOptions: {gl: 'swangle'},
        concurrency,
        imageFormat: 'jpeg',
        jpegQuality,
        crf,
        x264Preset,
        pixelFormat: 'yuv420p',
        forSeamlessAacConcatenation: true,
        overwrite: true,
      });
      break;
    } catch (error) {
      console.error(`Segment ${i} failed on attempt ${attempt}/${segmentRetries}`);
      console.error(error);
      if (attempt >= segmentRetries) {
        throw error;
      }
    }
  }
}

console.log(`Rendered ${sceneIndexes.length} segment(s) in ${outDir}`);
