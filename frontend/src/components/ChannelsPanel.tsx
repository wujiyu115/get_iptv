import { useEffect, useState } from 'react';
import { listChannels, playlistUrls } from '../api';
import type { Channel } from '../types';
import { Play, Copy } from '../icons';
import PlayerOverlay from './PlayerOverlay';
import HelpTip from './HelpTip';

export default function ChannelsPanel() {
  const [rows, setRows] = useState<Channel[]>([]);
  const [playing, setPlaying] = useState<Channel | null>(null);
  const [q, setQ] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const urls = playlistUrls();

  const toggle = (g: string) => setCollapsed(prev => {
    const next = new Set(prev);
    next.has(g) ? next.delete(g) : next.add(g);
    return next;
  });

  useEffect(() => { listChannels('latest').then(setRows); }, []);
  const copy = (path: string) => navigator.clipboard.writeText(location.origin + path);

  const kw = q.trim().toLowerCase();
  const shown = kw
    ? rows.filter(c => (c.name + ' ' + (c.group_title || '')).toLowerCase().includes(kw))
    : rows;

  const groups: [string, Channel[]][] = [];
  const idx = new Map<string, Channel[]>();
  for (const c of shown) {
    const g = c.group_title || '未分组';
    let arr = idx.get(g);
    if (!arr) { arr = []; idx.set(g, arr); groups.push([g, arr]); }
    arr.push(c);
  }

  return (
    <>
      <div className="card">
        <h3>订阅地址<HelpTip id="channels" /></h3>
        {(['full', 'compact', 'txt'] as const).map(k => (
          <div key={k} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <code style={{ flex: 1 }}>{location.origin + urls[k]}</code>
            <button className="btn" onClick={() => copy(urls[k])}><Copy /></button>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>频道（{shown.length}/{rows.length}）</h3>
        <input value={q} onChange={e => setQ(e.target.value)}
          placeholder="搜索频道/分组…"
          style={{ width: '100%', marginBottom: 12, boxSizing: 'border-box' }} />
        {groups.map(([g, list]) => (
          <div key={g} style={{ marginBottom: 18 }}>
            <div onClick={() => toggle(g)}
              style={{ fontWeight: 600, margin: '4px 0 8px', color: 'var(--fg2)',
                cursor: 'pointer', userSelect: 'none' }}>
              {collapsed.has(g) ? '▸' : '▾'} {g}（{list.length}）
            </div>
            {!collapsed.has(g) && <div className="grid-ch">
              {list.map(c => (
                <div key={c.id} className="card" style={{ margin: 0 }}>
                  <div style={{ fontWeight: 600 }}>{c.name}</div>
                  <div style={{ color: 'var(--fg2)', fontSize: 12 }}>
                    {c.resolution ? c.resolution + 'p' : '—'}
                    {c.speed ? ` · ${c.speed}M/s` : ''} · {c.status}
                  </div>
                  <button className="btn primary" style={{ marginTop: 8 }}
                    onClick={() => setPlaying(c)}><Play /> 试播</button>
                </div>
              ))}
            </div>}
          </div>
        ))}
      </div>
      {playing && <PlayerOverlay url={playing.url} name={playing.name}
        onClose={() => setPlaying(null)} />}
    </>
  );
}
