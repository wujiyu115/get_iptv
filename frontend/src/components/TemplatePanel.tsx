import { useEffect, useState } from 'react';
import { listTemplates, createTemplate, deleteTemplate } from '../api';
import type { Template } from '../types';
import { Plus, Trash } from '../icons';

const BLANK = { canonical: '', group_title: '', logo: '', sort: 0 };

export default function TemplatePanel() {
  const [rows, setRows] = useState<Template[]>([]);
  const [draft, setDraft] = useState(BLANK);
  const reload = () => listTemplates().then(setRows);
  useEffect(() => { reload(); }, []);
  const add = async () => {
    if (!draft.canonical) return;
    await createTemplate(draft); setDraft(BLANK); reload();
  };
  const remove = async (id: number) => { await deleteTemplate(id); reload(); };

  return (
    <div className="card">
      <h3>频道模板菜单（空=收录全部）</h3>
      <table>
        <thead><tr><th>频道</th><th>分组</th><th>台标</th><th>排序</th><th></th></tr></thead>
        <tbody>
          {rows.map(t => (
            <tr key={t.id}>
              <td>{t.canonical}</td><td>{t.group_title}</td>
              <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.logo}</td>
              <td>{t.sort}</td>
              <td><button className="btn danger" onClick={() => remove(t.id)}><Trash /></button></td>
            </tr>
          ))}
          <tr>
            <td><input value={draft.canonical} placeholder="CCTV1"
              onChange={e => setDraft({ ...draft, canonical: e.target.value })} /></td>
            <td><input value={draft.group_title} placeholder="央视"
              onChange={e => setDraft({ ...draft, group_title: e.target.value })} /></td>
            <td><input value={draft.logo} placeholder="http://logo"
              onChange={e => setDraft({ ...draft, logo: e.target.value })} /></td>
            <td><input type="number" value={draft.sort} style={{ width: 60 }}
              onChange={e => setDraft({ ...draft, sort: Number(e.target.value) })} /></td>
            <td><button className="btn primary" onClick={add}><Plus /></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
