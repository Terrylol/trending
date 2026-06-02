import React from 'react';
import {AbsoluteFill, Audio, getInputProps, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene, SceneSegmentProps, TrendingVideoProps} from './types';
import {TitleScene} from './TitleScene';
import {ProjectScene} from './ProjectScene';
import {EndingScene} from './EndingScene';

export const SceneSegment: React.FC<{date: string; scene: Scene; sceneIndex?: number}> = (props) => {
  const input = getInputProps() as Partial<TrendingVideoProps & SceneSegmentProps>;
  const sceneIndex = input.sceneIndex ?? props.sceneIndex ?? 0;
  const scene = input.scene ?? input.scenes?.[sceneIndex] ?? props.scene;
  const date = input.date ?? props.date;
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const fadeIn = interpolate(frame, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [Math.max(1, durationInFrames - 10), durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{backgroundColor: '#f8fafc', opacity: fadeIn * fadeOut}}>
      {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
      {scene.type === 'title' ? <TitleScene date={date} /> : null}
      {scene.type === 'project' && scene.project ? (
        <ProjectScene project={scene.project} index={scene.index ?? sceneIndex} />
      ) : null}
      {scene.type === 'ending' ? <EndingScene /> : null}
    </AbsoluteFill>
  );
};
