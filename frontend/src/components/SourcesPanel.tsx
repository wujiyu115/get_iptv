import { useEffect, useState } from 'react';
import { listSources, createSource, updateSource, deleteSource, getProxy, setProxy, sourceGithubUpdated } from '../api';
import type { Source } from '../types';
import { Plus, Trash, Search } from '../icons';
import { fmtLocal } from '../time';
import HelpTip from './HelpTip';

const BLANK = { name: '', url: '', type: 'm3u' as const };

export default function SourcesPanel() {
  const [rows, setRows] = useState<Source[]>([]);
  const [draft, setDraft] = useState(BLANK);
  const [q, setQ] = useState('');
  const [proxyOpen, setProxyOpen] = useState(false);
  const [proxyVal, setProxyVal] = useState('');
  const [proxySaving, setProxySaving] = useState(false);
  const [ghUpdated, setGhUpdated] = useState<Record<number, string | null>>({});
  const [ghBusy, setGhBusy] = useState<number | null>(null);

  const reload = () => listSources().then(setRows);
  useEffect(() => { reload(); }, []);

  // Not auto-fetched: GitHub's API is rate-limited (60/h unauth). Each row is
  // fetched on demand — one click = one API call for that source only.
  const loadGithubTime = async (id: number) => {
    setGhBusy(id);
    try { const { updated } = await sourceGithubUpdated(id); setGhUpdated(p => ({ ...p, [id]: updated })); }
    catch { alert('获取失败（可能触发 GitHub 速率限制，稍后再试）'); }
    finally { setGhBusy(null); }
  };

  const openProxy = async () => {
    const { http_proxy } = await getProxy();
    setProxyVal(http_proxy);
    setProxyOpen(true);
  };
  const saveProxy = async () => {
    setProxySaving(true);
    try { await setProxy(proxyVal.trim()); setProxyOpen(false); }
    finally { setProxySaving(false); }
  };

  const kw = q.trim().toLowerCase();
  const shown = kw ? rows.filter(s =>
    (s.name + ' ' + s.url + ' ' + s.type).toLowerCase().includes(kw)) : rows;

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
    <>
    <div className="card">
      <div className="card-head">
        <h2>抓取源</h2><HelpTip id="sources" />
        <span className="badge badge-count">{shown.length} / {rows.length}</span>
        <button className="btn btn-ghost" style={{ marginLeft: 8 }} onClick={openProxy}>代理设置</button>
      </div>
      <div className="card-body">
        <div className="search-bar">
          <Search />
          <input className="inp" type="search" value={q} placeholder="搜索名称 / URL / 类型…"
            onChange={e => setQ(e.target.value)} />
        </div>
      </div>
      <div className="card-body flush">
        <table className="tbl responsive">
          <thead>
            <tr><th>名称</th><th>URL</th><th>类型</th>
              <th className="center">启用</th><th className="center">代理</th>
              <th className="num">失效</th><th>最近成功</th><th>更新时间</th><th></th></tr>
          </thead>
          <tbody>
            {shown.map(s => (
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
                  {fmtLocal(s.last_ok_at)}</td>
                <td data-label="更新时间" className="mono" style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {s.id in ghUpdated
                    ? (ghUpdated[s.id] ? fmtLocal(ghUpdated[s.id]!) : '—')
                    : <button className="btn btn-ghost" style={{ padding: '2px 10px', fontSize: 12 }}
                        onClick={() => loadGithubTime(s.id)} disabled={ghBusy === s.id}>
                        {ghBusy === s.id ? '…' : '更新'}
                      </button>}</td>
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
              <td colSpan={3} style={{ textAlign: 'right' }}>
                <button className="btn-icon-add" onClick={add} aria-label="添加源"><Plus /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    {proxyOpen && (
      <div className="overlay" onClick={() => setProxyOpen(false)}>
        <div className="card proxy-modal" onClick={e => e.stopPropagation()}>
          <div className="card-head"><h2>代理设置</h2></div>
          <div className="card-body">
            <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 10 }}>
              抓取时对勾选「代理」的源生效。留空则不使用代理。
            </p>
            <input className="inp" value={proxyVal} placeholder="http://host:port"
              autoFocus onChange={e => setProxyVal(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') saveProxy(); }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn btn-ghost" onClick={() => setProxyOpen(false)}>取消</button>
              <button className="btn btn-primary" disabled={proxySaving} onClick={saveProxy}>保存</button>
            </div>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
