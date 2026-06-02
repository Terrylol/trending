import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from './theme';

export const EndingScene: React.FC<{audio?: string}> = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 16, stiffness: 86}});
  const pulse = Math.sin(frame / 26) * 0.5 + 0.5;
  const wipe = interpolate(frame, [0, 30], [-18, 118], {extrapolateRight: 'clamp'});
  const outro = interpolate(frame, [Math.max(1, durationInFrames - 24), durationInFrames], [1, 0.86], {extrapolateLeft: 'clamp'});
  return (
    <AbsoluteFill style={{fontFamily, overflow: 'hidden', background: '#07143a'}}>
      <AbsoluteFill style={{background: 'linear-gradient(130deg, #2563eb 0%, #1e3a8a 50%, #0f172a 100%)'}} />
      <div style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at ${50 + Math.sin(frame / 40) * 5}% ${38 + Math.cos(frame / 44) * 4}%, rgba(255,255,255,.18), transparent 32%)`}} />
      {[0, 1].map((i) => (
        <div key={i} style={{position: 'absolute', width: 310 + i * 130, height: 310 + i * 130, borderRadius: '50%', left: 170 + i * 350, top: 120 - i * 25, border: '2px solid rgba(255,255,255,.12)', transform: `scale(${0.88 + pulse * 0.05 + i * 0.02}) rotate(${frame * (0.04 + i * 0.02)}deg)`}} />
      ))}
      <div style={{position: 'absolute', left: `${wipe}%`, top: -80, width: 110, height: 880, background: 'rgba(255,255,255,.1)', transform: 'rotate(18deg)'}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: 222, textAlign: 'center', opacity: outro, transform: `scale(${0.9 + enter * 0.1}) translateY(${(1 - enter) * 22}px)`}}>
        <div style={{fontSize: 66, fontWeight: 950, color: 'white', textShadow: '0 8px 22px rgba(0,0,0,.2)'}}>感谢观看</div>
        <div style={{fontSize: 38, fontWeight: 780, color: '#dbeafe', marginTop: 36, clipPath: `inset(0 ${Math.max(0, 100 - frame * 3)}% 0 0)`}}>每日更新 GitHub Trending</div>
      </div>
    </AbsoluteFill>
  );
};
