import { useEffect, useState } from 'react';
import { listChannels, playlistUrls } from '../api';
import type { Channel } from '../types';
import { Play, Copy, Search, Caret } from '../icons';
import PlayerOverlay from './PlayerOverlay';
import HelpTip from './HelpTip';

export default function ChannelsPanel() {
  const [rows, setRows] = useState<Channel[]>([]);
  const [playing, setPlaying] = useState<Channel | null>(null);
  const [q, setQ] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState('');
  const urls = playlistUrls();

  useEffect(() => { listChannels('latest').then(setRows); }, []);

  const copy = (path: string) => {
    navigator.clipboard.writeText(location.origin + path);
    setCopied(path);
    setTimeout(() => setCopied(c => (c === path ? '' : c)), 1200);
  };
  const toggle = (g: string) => setCollapsed(prev => {
    const next = new Set(prev);
    next.has(g) ? next.delete(g) : next.add(g);
    return next;
  });
  const meta = (c: Channel) => [
    c.resolution ? c.resolution + 'p' : '—',
    c.speed ? `${c.speed} Mb/s` : null,
    c.status,
  ].filter(Boolean).join(' · ');

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
        <div className="card-head"><h2>订阅地址</h2><HelpTip id="channels" /></div>
        <div className="card-body flush">
          <div className="sub-list">
            {(['full', 'compact', 'txt'] as const).map(k => (
              <div key={k} className="sub-row">
                <span className="url">{location.origin + urls[k]}</span>
                <button className={`copy-btn ${copied === urls[k] ? 'copied' : ''}`}
                  onClick={() => copy(urls[k])} aria-label="复制地址"><Copy /></button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>频道</h2>
          <span className="badge badge-count">{shown.length} / {rows.length}</span>
        </div>
        <div className="card-body">
          <div className="search-bar" style={{ marginBottom: 20 }}>
            <Search />
            <input className="inp" type="search" value={q} placeholder="搜索频道名 / 分组…"
              onChange={e => setQ(e.target.value)} aria-label="搜索频道名或分组" />
          </div>
          {groups.map(([g, list]) => {
            const off = collapsed.has(g);
            return (
              <div key={g}>
                <div className={`group-title ${off ? 'collapsed' : ''}`} onClick={() => toggle(g)}>
                  <Caret />{g} <span className="cnt">({list.length})</span>
                </div>
                {!off && (
                  <div className="ch-grid">
                    {list.map(c => (
                      <div key={c.id} className="ch-card">
                        <div className="ch-name">{c.name}</div>
                        <div className="ch-meta">{meta(c)}</div>
                        <div className="ch-foot">
                          <span />
                          <button className="ch-play" onClick={() => setPlaying(c)}>
                            <Play />试看</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {shown.length === 0 && <div className="no-result">没有匹配的频道</div>}
        </div>
      </div>

      {playing && <PlayerOverlay url={playing.url} name={playing.name}
        onClose={() => setPlaying(null)} />}
    </>
  );
}
