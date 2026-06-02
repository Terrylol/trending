import React from 'react';
import {AbsoluteFill, Sequence, Audio, staticFile} from 'remotion';
import type {TrendingVideoProps} from './types';
import {TitleScene} from './TitleScene';
import {ProjectScene} from './ProjectScene';
import {EndingScene} from './EndingScene';

export const TrendingVideo: React.FC<TrendingVideoProps> = ({date, scenes}) => {
  let from = 0;
  return (
    <AbsoluteFill style={{backgroundColor: '#f8fafc'}}>
      {scenes.map((scene, i) => {
        const currentFrom = from;
        from += scene.durationFrames;
        return (
          <Sequence key={`${scene.type}-${i}`} from={currentFrom} durationInFrames={scene.durationFrames}>
            {scene.audio ? <Audio src={staticFile(scene.audio)} /> : null}
            {scene.type === 'title' ? <TitleScene date={date} /> : null}
            {scene.type === 'project' && scene.project ? (
              <ProjectScene project={scene.project} index={scene.index ?? i} />
            ) : null}
            {scene.type === 'ending' ? <EndingScene /> : null}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
