import React from 'react';
import {Composition, getInputProps} from 'remotion';
import {TrendingVideo} from './TrendingVideo';
import {SceneSegment} from './SceneSegment';
import type {SceneSegmentProps, TrendingVideoProps} from './types';

const input = getInputProps() as Partial<TrendingVideoProps & SceneSegmentProps>;
const fps = input.fps ?? 24;
const scenes = input.scenes ?? [];
const durationInFrames = Math.max(1, scenes.reduce((sum, scene) => sum + scene.durationFrames, 0));
const segmentScene = input.scene ?? scenes[input.sceneIndex ?? 0];
const segmentDuration = Math.max(1, segmentScene?.durationFrames ?? 1);

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="TrendingVideo"
        component={TrendingVideo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={1280}
        height={720}
        defaultProps={{
          date: input.date ?? '',
          fps,
          scenes,
        }}
      />
      <Composition
        id="SceneSegment"
        component={SceneSegment}
        durationInFrames={segmentDuration}
        fps={fps}
        width={1280}
        height={720}
        defaultProps={{
          date: input.date ?? '',
          scene: segmentScene ?? {type: 'title', durationSeconds: 1, durationFrames: 1},
          sceneIndex: input.sceneIndex ?? 0,
        }}
      />
    </>
  );
};
