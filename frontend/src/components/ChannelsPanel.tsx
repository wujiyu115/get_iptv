import { useEffect, useState } from 'react';
import { listChannels, playlistUrls } from '../api';
import type { Channel } from '../types';
import { Play, Copy } from '../icons';
import PlayerOverlay from './PlayerOverlay';

export default function ChannelsPanel() {
  const [rows, setRows] = useState<Channel[]>([]);
  const [playing, setPlaying] = useState<Channel | null>(null);
  const urls = playlistUrls();

  useEffect(() => { listChannels('latest').then(setRows); }, []);
  const copy = (path: string) => navigator.clipboard.writeText(location.origin + path);

  return (
    <>
      <div className="card">
        <h3>订阅地址</h3>
        {(['full', 'compact', 'txt'] as const).map(k => (
          <div key={k} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <code style={{ flex: 1 }}>{location.origin + urls[k]}</code>
            <button className="btn" onClick={() => copy(urls[k])}><Copy /></button>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>频道（{rows.length}）</h3>
        <div className="grid-ch">
          {rows.map(c => (
            <div key={c.id} className="card" style={{ margin: 0 }}>
              <div style={{ fontWeight: 600 }}>{c.name}</div>
              <div style={{ color: 'var(--fg2)', fontSize: 12 }}>
                {c.group_title} · {c.resolution ? c.resolution + 'p' : '—'} ·
                {c.speed ? ` ${c.speed}M/s` : ''} · {c.status}
              </div>
              <button className="btn primary" style={{ marginTop: 8 }}
                onClick={() => setPlaying(c)}><Play /> 试播</button>
            </div>
          ))}
        </div>
      </div>
      {playing && <PlayerOverlay url={playing.url} name={playing.name}
        onClose={() => setPlaying(null)} />}
    </>
  );
}
