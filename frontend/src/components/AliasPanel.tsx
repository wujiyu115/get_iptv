import { useEffect, useState } from 'react';
import { listAliases, createAlias, updateAlias, deleteAlias } from '../api';
import type { Alias } from '../types';
import { Plus, Trash } from '../icons';
import HelpTip from './HelpTip';

const BLANK = { canonical: '', pattern: '', is_regex: 0 };

export default function AliasPanel() {
  const [rows, setRows] = useState<Alias[]>([]);
  const [draft, setDraft] = useState(BLANK);
  const reload = () => listAliases().then(setRows);
  useEffect(() => { reload(); }, []);
  const add = async () => {
    if (!draft.canonical || !draft.pattern) return;
    await createAlias(draft); setDraft(BLANK); reload();
  };
  const toggleRegex = async (a: Alias) => {
    await updateAlias(a.id, { is_regex: a.is_regex ? 0 : 1 }); reload();
  };
  const remove = async (id: number) => { await deleteAlias(id); reload(); };

  return (
    <div className="card">
      <div className="card-head">
        <h2>频道别名 · 归一</h2><HelpTip id="aliases" />
        <span className="badge badge-count">{rows.length}</span>
      </div>
      <div className="card-body flush">
        <table className="tbl responsive">
          <thead>
            <tr><th>规范名 canonical</th><th>匹配 pattern</th><th className="center">正则</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map(a => (
              <tr key={a.id}>
                <td data-label="规范名" className="name-strong">{a.canonical}</td>
                <td data-label="pattern" className="url">{a.pattern}</td>
                <td data-label="正则" className="center">
                  <input type="checkbox" className="chk" checked={!!a.is_regex}
                    onChange={() => toggleRegex(a)} /></td>
                <td style={{ textAlign: 'right' }}>
                  <button className="icon-trash" onClick={() => remove(a.id)} aria-label="删除"><Trash /></button></td>
              </tr>
            ))}
            <tr className="row-add">
              <td data-label="规范名"><input className="inp" value={draft.canonical} placeholder="CCTV1"
                onChange={e => setDraft({ ...draft, canonical: e.target.value })} /></td>
              <td data-label="pattern"><input className="inp mono" value={draft.pattern} placeholder="^CCTV[-\s]?1"
                onChange={e => setDraft({ ...draft, pattern: e.target.value })} /></td>
              <td className="center"><input type="checkbox" className="chk" checked={!!draft.is_regex}
                onChange={e => setDraft({ ...draft, is_regex: e.target.checked ? 1 : 0 })} /></td>
              <td style={{ textAlign: 'right' }}>
                <button className="btn-icon-add" onClick={add} aria-label="添加别名"><Plus /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
