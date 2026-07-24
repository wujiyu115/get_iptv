import { useEffect, useState } from 'react';
import { listTemplates, createTemplate, deleteTemplate } from '../api';
import type { Template } from '../types';
import { Plus, Trash, Search } from '../icons';
import HelpTip from './HelpTip';

const BLANK = { canonical: '', group_title: '', logo: '', sort: 0 };

export default function TemplatePanel() {
  const [rows, setRows] = useState<Template[]>([]);
  const [draft, setDraft] = useState(BLANK);
  const [q, setQ] = useState('');
  const reload = () => listTemplates().then(setRows);
  useEffect(() => { reload(); }, []);

  const kw = q.trim().toLowerCase();
  const shown = kw ? rows.filter(t =>
    (t.canonical + ' ' + t.group_title).toLowerCase().includes(kw)) : rows;
  const add = async () => {
    if (!draft.canonical) return;
    await createTemplate(draft); setDraft(BLANK); reload();
  };
  const remove = async (id: number) => { await deleteTemplate(id); reload(); };

  return (
    <div className="card">
      <div className="card-head">
        <h2>频道模板菜单</h2><HelpTip id="templates" />
        <span className="card-head hint" style={{ padding: 0, marginLeft: 'auto' }}>留空 = 收录全部</span>
      </div>
      <div className="card-body">
        <div className="search-bar">
          <Search />
          <input className="inp" type="search" value={q} placeholder="搜索频道 / 分组…"
            onChange={e => setQ(e.target.value)} />
        </div>
      </div>
      <div className="card-body flush">
        <table className="tbl responsive">
          <thead>
            <tr><th>频道</th><th>分组</th><th>台标</th><th className="num">顺序</th><th></th></tr>
          </thead>
          <tbody>
            {shown.map(t => (
              <tr key={t.id}>
                <td data-label="频道" className="name-strong">{t.canonical}</td>
                <td data-label="分组"><span className="badge badge-type">{t.group_title}</span></td>
                <td data-label="台标" className="url">{t.logo}</td>
                <td data-label="顺序" className="num mono">{t.sort}</td>
                <td style={{ textAlign: 'right' }}>
                  <button className="icon-trash" onClick={() => remove(t.id)} aria-label="删除"><Trash /></button></td>
              </tr>
            ))}
            <tr className="row-add">
              <td data-label="频道"><input className="inp" value={draft.canonical} placeholder="CCTV1"
                onChange={e => setDraft({ ...draft, canonical: e.target.value })} /></td>
              <td data-label="分组"><input className="inp" value={draft.group_title} placeholder="央视"
                onChange={e => setDraft({ ...draft, group_title: e.target.value })} /></td>
              <td data-label="台标"><input className="inp mono" value={draft.logo} placeholder="http://logo…"
                onChange={e => setDraft({ ...draft, logo: e.target.value })} /></td>
              <td data-label="顺序"><input className="inp mono" type="number" value={draft.sort} style={{ maxWidth: 80 }}
                onChange={e => setDraft({ ...draft, sort: Number(e.target.value) })} /></td>
              <td style={{ textAlign: 'right' }}>
                <button className="btn-icon-add" onClick={add} aria-label="添加模板行"><Plus /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
