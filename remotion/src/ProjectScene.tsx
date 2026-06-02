import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Project} from './types';
import {colors, fontFamily} from './theme';

const shorten = (text = '', max = 180) => (text.length > max ? `${text.slice(0, max)}…` : text);
const getRepoPath = (url = '') => {
  try {
    const u = new URL(url);
    return u.hostname === 'github.com' ? `github.com${u.pathname}`.replace(/\/$/, '') : url;
  } catch {
    return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
  }
};

const reveal = (frame: number, start: number, len = 20) => interpolate(frame, [start, start + len], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

const softShadow = '0 14px 34px rgba(15,23,42,.13)';
const readableFont = [
  'Inter',
  'HarmonyOS Sans SC',
  'Noto Sans CJK SC',
  'Noto Sans SC',
  'Source Han Sans SC',
  'PingFang SC',
  'Microsoft YaHei',
  'Arial',
  'sans-serif',
].join(',');

const Badge: React.FC<{children: React.ReactNode; color?: string; light?: boolean; delay?: number}> = ({children, color = '#e2e8f0', light, delay = 0}) => {
  const frame = useCurrentFrame();
  const p = reveal(frame, delay, 14);
  return (
    <div style={{
      padding: '6px 12px',
      borderRadius: 10,
      background: light ? 'rgba(255,255,255,.92)' : color,
      color: light ? '#475569' : 'white',
      fontSize: 20,
      fontWeight: 800,
      lineHeight: 1,
      whiteSpace: 'nowrap',
      boxShadow: '0 6px 14px rgba(15,23,42,.08)',
      opacity: p,
      transform: `translateY(${(1 - p) * 10}px)`,
    }}>{children}</div>
  );
};

export const ProjectScene: React.FC<{project: Project; index: number; audio?: string}> = ({project, index}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const accent = colors[index % colors.length];
  const enter = spring({frame, fps, config: {damping: 18, stiffness: 90}});
  const rank = spring({frame: frame - 6, fps, config: {damping: 14, stiffness: 110}});
  const titleReveal = reveal(frame, 8, 20);
  const imageReveal = reveal(frame, 22, 22);
  const chartReveal = reveal(frame, 34, 22);
  const textReveal = reveal(frame, 42, 24);
  const transitionOut = interpolate(frame, [Math.max(1, durationInFrames - 14), durationInFrames], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const imageScale = interpolate(frame, [0, durationInFrames], [0.985, 1.015], {extrapolateRight: 'clamp'});
  const imageY = Math.sin(frame / 52) * 3;
  const narrative = project.narrative ?? {};
  const hook = narrative.hook || project.description || '';
  const body = narrative.body || '';
  const cta = narrative.call_to_action || '';
  const preview = project.public_preview_image || project.preview_image;
  const starHistory = project.star_history_image || project.star_history_chart;
  const repoPath = getRepoPath(project.url || '');

  return (
    <AbsoluteFill style={{fontFamily: readableFont || fontFamily, background: '#f8fafc', overflow: 'hidden'}}>
      <AbsoluteFill style={{background: `linear-gradient(118deg, #f8fafc 0%, #eff6ff 54%, #fdf2f8 100%)`}} />
      <div style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at ${10 + Math.sin(frame / 40) * 2}% ${15 + Math.cos(frame / 44) * 3}%, ${accent}24, transparent 34%), radial-gradient(circle at ${90 - Math.sin(frame / 52) * 3}% ${86 - Math.cos(frame / 56) * 3}%, #0ea5e922, transparent 36%)`}} />
      <div style={{position: 'absolute', left: -80, top: 465, width: 390, height: 390, borderRadius: '50%', border: `24px solid ${accent}10`, transform: `translateX(${Math.sin(frame / 40) * 10}px) rotate(${frame * 0.06}deg)`}} />
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: interpolate(frame, [0, 18], [0, 12], {extrapolateRight: 'clamp'}), background: accent}} />
      <div style={{position: 'absolute', right: 38, top: 0, fontSize: 150, lineHeight: 1, fontWeight: 950, color: '#e2e8f0', opacity: .42, transform: `translateX(${(1 - rank) * 44}px) scale(${0.86 + rank * 0.14})`}}>0{index + 1}</div>

      <div style={{position: 'absolute', left: 54, right: 54, top: 24, opacity: titleReveal, transform: `translateY(${(1 - enter) * 18}px)`}}>
        <div style={{fontSize: 46, fontWeight: 950, color: '#0b1220', letterSpacing: -.75, maxWidth: 850, lineHeight: 1.02, textShadow: '0 1px 0 rgba(255,255,255,.8)', clipPath: `inset(0 ${Math.max(0, 100 - titleReveal * 100)}% 0 0)`}}>{project.name}</div>
        <div style={{display: 'flex', gap: 9, alignItems: 'center', marginTop: 13, maxWidth: 900, overflow: 'hidden'}}>
          <Badge color={accent} delay={15}>{project.language || 'Unknown'}</Badge>
          <Badge light delay={19}>★ {(project.stars ?? 0).toLocaleString()}</Badge>
          {project.license ? <Badge light delay={23}>{project.license}</Badge> : null}
          {(project.topics || []).slice(0, 3).map((t, n) => <Badge key={t} light delay={27 + n * 4}>#{t}</Badge>)}
        </div>
        <div style={{height: 3, background: '#e2e8f0', marginTop: 17, borderRadius: 99, overflow: 'hidden'}}>
          <div style={{height: '100%', width: `${titleReveal * 100}%`, background: accent}} />
        </div>
      </div>

      <div style={{position: 'absolute', left: 54, top: 166, width: 484, height: 500, opacity: imageReveal, transform: `translateX(${(1 - imageReveal) * -30}px)`}}>
        <div style={{width: '100%', height: 266, borderRadius: 20, overflow: 'hidden', background: 'linear-gradient(135deg, #ffffff, #f8fafc)', boxShadow: softShadow, border: '2px solid white'}}>
          <div style={{height: 26, display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px', background: 'linear-gradient(180deg, #f8fafc, #eef2f7)', borderBottom: '1px solid #e2e8f0'}}>
            <span style={{width: 8, height: 8, borderRadius: '50%', background: '#f87171'}} />
            <span style={{width: 8, height: 8, borderRadius: '50%', background: '#fbbf24'}} />
            <span style={{width: 8, height: 8, borderRadius: '50%', background: '#34d399'}} />
            <span style={{marginLeft: 8, padding: '3px 10px', borderRadius: 999, background: 'rgba(255,255,255,.78)', color: '#94a3b8', fontSize: 11, fontWeight: 800, letterSpacing: .1}}>project preview</span>
          </div>
          <div style={{width: '100%', height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            {preview ? (
              <Img src={staticFile(preview)} style={{width: '100%', height: '100%', objectFit: 'contain', objectPosition: 'center center', transform: `translateY(${imageY}px) scale(${imageScale})`}} />
            ) : (
              <div style={{height: '100%', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: `linear-gradient(135deg, ${accent}, #0f172a)`, color: 'white', fontSize: 36, fontWeight: 900}}>GitHub</div>
            )}
          </div>
        </div>

        <div style={{marginTop: 17, height: 194, padding: '12px 14px 18px', borderRadius: 18, background: 'rgba(255,255,255,.96)', boxShadow: '0 10px 26px rgba(15,23,42,.09)', border: '1px solid #dbeafe', opacity: chartReveal, transform: `translateY(${(1 - chartReveal) * 14}px)`}}>
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7}}>
            <div>
              <div style={{fontSize: 16, color: '#334155', fontWeight: 950, letterSpacing: .2}}>Star History</div>
              <div style={{fontSize: 11, color: '#94a3b8', fontWeight: 800, marginTop: 1}}>stars over time</div>
            </div>
            <div style={{fontSize: 14, color: accent, fontWeight: 900, padding: '4px 8px', borderRadius: 999, background: `${accent}12`}}>Trending</div>
          </div>
          {starHistory ? (
            <Img src={staticFile(starHistory)} style={{width: '100%', height: 137, objectFit: 'contain', objectPosition: 'center center', filter: 'saturate(1.06) contrast(1.02)'}} />
          ) : (
            <div style={{height: 137, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 12, background: '#f1f5f9', color: '#64748b', fontSize: 18, fontWeight: 800}}>Star history unavailable</div>
          )}
        </div>

        <div style={{marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 9, maxWidth: '100%', padding: '7px 10px 7px 9px', borderRadius: 999, background: 'rgba(255,255,255,.48)', border: '1px solid rgba(148,163,184,.26)', color: '#64748b', opacity: reveal(frame, 48, 18), transform: `translateY(${(1 - reveal(frame, 48, 18)) * 10}px)`}}>
          <Img src={staticFile('generated/github_logo.png')} style={{width: 22, height: 22, objectFit: 'contain', flex: '0 0 auto', opacity: .72}} />
          <div style={{fontSize: 17, color: '#64748b', fontWeight: 760, letterSpacing: .05, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textShadow: '0 1px 0 rgba(255,255,255,.7)'}}>{repoPath}</div>
        </div>
      </div>

      <div style={{position: 'absolute', left: 580, right: 54, top: 182, bottom: 48, opacity: textReveal, transform: `translateX(${(1 - textReveal) * 34}px)`}}>
        <Section title="亮点" accent={accent} delay={44}>{shorten(hook, 76)}</Section>
        <div style={{height: 20}} />
        <Section title="介绍" accent={accent} delay={66}>{shorten(body || project.description || '', 150)}</Section>
        {cta ? <div style={{marginTop: 23, fontSize: 27, lineHeight: 1.32, color: accent, fontWeight: 900, letterSpacing: .15, opacity: reveal(frame, 88, 18), textShadow: '0 1px 0 rgba(255,255,255,.75)', clipPath: `inset(0 ${Math.max(0, 100 - reveal(frame, 88, 18) * 100)}% 0 0)`}}>{shorten(cta, 48)}</div> : null}
      </div>
      <div style={{position: 'absolute', inset: 0, background: accent, transform: `translateX(${(1 - transitionOut) * 100}%)`, opacity: transitionOut * 0.9}} />
    </AbsoluteFill>
  );
};

const Section: React.FC<{title: string; accent: string; delay: number; children: React.ReactNode}> = ({title, accent, delay, children}) => {
  const frame = useCurrentFrame();
  const p = reveal(frame, delay, 22);
  return (
    <div style={{opacity: p, transform: `translateY(${(1 - p) * 16}px)`}}>
      <div style={{display: 'inline-flex', padding: '7px 16px 8px', borderRadius: 12, background: accent, color: 'white', fontSize: 27, fontWeight: 950, lineHeight: 1, boxShadow: '0 7px 18px rgba(15,23,42,.12)'}}>{title}</div>
      <div style={{marginTop: 14, paddingLeft: 16, borderLeft: `5px solid ${accent}55`, fontSize: 28, lineHeight: 1.52, color: '#263445', fontWeight: 560, letterSpacing: .16, textWrap: 'pretty', textShadow: '0 1px 0 rgba(255,255,255,.55)', clipPath: `inset(0 ${Math.max(0, 100 - p * 100)}% 0 0)`}}>{children}</div>
    </div>
  );
};
