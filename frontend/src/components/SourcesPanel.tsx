import { useEffect, useState } from 'react';
import { listSources, createSource, updateSource, deleteSource } from '../api';
import type { Source } from '../types';
import { Plus, Trash } from '../icons';
import HelpTip from './HelpTip';

const BLANK = { name: '', url: '', type: 'm3u' as const };

export default function SourcesPanel() {
  const [rows, setRows] = useState<Source[]>([]);
  const [draft, setDraft] = useState(BLANK);

  const reload = () => listSources().then(setRows);
  useEffect(() => { reload(); }, []);

  const add = async () => {
    if (!draft.name || !draft.url) return;
    await createSource(draft);
    setDraft(BLANK);
    reload();
  };
  const toggle = async (s: Source, field: 'enabled' | 'use_proxy') => {
    await updateSource(s.id, { [field]: s[field] ? 0 : 1 });
    reload();
  };
  const remove = async (id: number) => { await deleteSource(id); reload(); };

  return (
    <div className="card">
      <h3>抓取源<HelpTip id="sources" /></h3>
      <table>
        <thead><tr><th>名称</th><th>URL</th><th>类型</th><th>启用</th>
          <th>代理</th><th>失败</th><th>最近成功</th><th></th></tr></thead>
        <tbody>
          {rows.map(s => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.url}</td>
              <td>{s.type}</td>
              <td><input type="checkbox" checked={!!s.enabled} onChange={() => toggle(s, 'enabled')} /></td>
              <td><input type="checkbox" checked={!!s.use_proxy} onChange={() => toggle(s, 'use_proxy')} /></td>
              <td>{s.fail_count}</td>
              <td>{s.last_ok_at?.slice(0, 16) || '-'}</td>
              <td><button className="btn danger" onClick={() => remove(s.id)}><Trash /></button></td>
            </tr>
          ))}
          <tr>
            <td><input value={draft.name} placeholder="名称"
              onChange={e => setDraft({ ...draft, name: e.target.value })} /></td>
            <td><input value={draft.url} placeholder="https://..."
              onChange={e => setDraft({ ...draft, url: e.target.value })} /></td>
            <td>
              <select value={draft.type}
                onChange={e => setDraft({ ...draft, type: e.target.value as 'm3u' | 'txt' })}>
                <option value="m3u">m3u</option><option value="txt">txt</option>
              </select>
            </td>
            <td colSpan={4} />
            <td><button className="btn primary" onClick={add}><Plus /></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
