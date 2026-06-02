import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from './theme';

export const TitleScene: React.FC<{date: string; audio?: string}> = ({date}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 16, stiffness: 86}});
  const subtitle = interpolate(frame, [20, 48], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const sweep = interpolate(frame, [12, 62], [-24, 118], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{fontFamily, overflow: 'hidden', background: '#0f172a'}}>
      <AbsoluteFill style={{background: 'linear-gradient(132deg, #1e3a8a 0%, #2563eb 56%, #38bdf8 100%)'}} />
      <div style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at ${20 + Math.sin(frame / 34) * 4}% ${20 + Math.cos(frame / 38) * 3}%, rgba(255,255,255,.18), transparent 32%), radial-gradient(circle at ${78 - Math.sin(frame / 44) * 4}% ${62 - Math.cos(frame / 40) * 3}%, rgba(255,255,255,.13), transparent 30%)`}} />
      <div style={{position: 'absolute', width: 520, height: 520, borderRadius: '50%', right: -140, top: -105, border: '2px solid rgba(255,255,255,.15)', transform: `scale(${0.96 + Math.sin(frame / 36) * 0.025}) rotate(${frame * 0.04}deg)`}} />
      <div style={{position: 'absolute', width: 330, height: 330, borderRadius: '50%', left: -105, bottom: -105, border: '2px solid rgba(255,255,255,.12)', transform: `translate(${Math.sin(frame / 32) * 10}px, ${Math.cos(frame / 36) * 8}px)`}} />
      <div style={{position: 'absolute', left: `${sweep}%`, top: -110, width: 90, height: 900, background: 'rgba(255,255,255,.11)', transform: 'rotate(18deg)'}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: 194, textAlign: 'center', opacity: enter, transform: `translateY(${(1 - enter) * 30}px) scale(${0.94 + enter * 0.06})`}}>
        <div style={{fontSize: 68, fontWeight: 900, color: 'white', letterSpacing: 1.5, textShadow: '0 8px 22px rgba(0,0,0,.18)', clipPath: `inset(0 ${Math.max(0, 100 - enter * 100)}% 0 0)`}}>GitHub Trending</div>
        <div style={{margin: '24px auto 0', width: 350, height: 5, borderRadius: 999, background: 'rgba(255,255,255,.9)', transform: `scaleX(${subtitle})`, transformOrigin: 'center'}} />
        <div style={{marginTop: 36, fontSize: 36, color: '#e0f2fe', fontWeight: 700, opacity: subtitle, transform: `translateY(${(1 - subtitle) * 16}px)`}}>今日热门项目推荐 · {date}</div>
      </div>
    </AbsoluteFill>
  );
};
