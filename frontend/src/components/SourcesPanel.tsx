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
      <div className="card-head">
        <h2>抓取源</h2><HelpTip id="sources" />
        <span className="badge badge-count">{rows.length}</span>
      </div>
      <div className="card-body flush">
        <table className="tbl responsive">
          <thead>
            <tr><th>名称</th><th>URL</th><th>类型</th>
              <th className="center">启用</th><th className="center">代理</th>
              <th className="num">失效</th><th>最近成功</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map(s => (
              <tr key={s.id}>
                <td data-label="名称" className="name-strong">{s.name}</td>
                <td data-label="URL" className="url">{s.url}</td>
                <td data-label="类型"><span className="badge badge-type">{s.type}</span></td>
                <td data-label="启用" className="center">
                  <input type="checkbox" className="chk" checked={!!s.enabled}
                    onChange={() => toggle(s, 'enabled')} /></td>
                <td data-label="代理" className="center">
                  <input type="checkbox" className="chk" checked={!!s.use_proxy}
                    onChange={() => toggle(s, 'use_proxy')} /></td>
                <td data-label="失效" className="num">
                  {s.fail_count ? <span className="badge badge-fail">{s.fail_count}</span> : '0'}</td>
                <td data-label="最近成功" className="mono" style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {s.last_ok_at?.slice(0, 16) || '—'}</td>
                <td style={{ textAlign: 'right' }}>
                  <button className="icon-trash" onClick={() => remove(s.id)} aria-label="删除"><Trash /></button></td>
              </tr>
            ))}
            <tr className="row-add">
              <td data-label="名称"><input className="inp" value={draft.name} placeholder="名称"
                onChange={e => setDraft({ ...draft, name: e.target.value })} /></td>
              <td data-label="URL" colSpan={2}><input className="inp" value={draft.url} placeholder="https://…"
                onChange={e => setDraft({ ...draft, url: e.target.value })} /></td>
              <td colSpan={3}>
                <select className="inp" style={{ maxWidth: 120 }} value={draft.type}
                  onChange={e => setDraft({ ...draft, type: e.target.value as 'm3u' | 'txt' })}>
                  <option value="m3u">m3u</option><option value="txt">txt</option>
                </select></td>
              <td colSpan={2} style={{ textAlign: 'right' }}>
                <button className="btn-icon-add" onClick={add} aria-label="添加源"><Plus /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
