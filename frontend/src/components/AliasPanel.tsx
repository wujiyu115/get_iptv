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
      <h3>频道别名（归一）<HelpTip id="aliases" /></h3>
      <table>
        <thead><tr><th>规范名 canonical</th><th>匹配 pattern</th><th>正则</th><th></th></tr></thead>
        <tbody>
          {rows.map(a => (
            <tr key={a.id}>
              <td>{a.canonical}</td><td>{a.pattern}</td>
              <td><input type="checkbox" checked={!!a.is_regex} onChange={() => toggleRegex(a)} /></td>
              <td><button className="btn danger" onClick={() => remove(a.id)}><Trash /></button></td>
            </tr>
          ))}
          <tr>
            <td><input value={draft.canonical} placeholder="CCTV1"
              onChange={e => setDraft({ ...draft, canonical: e.target.value })} /></td>
            <td><input value={draft.pattern} placeholder="^CCTV[-\\s]?1"
              onChange={e => setDraft({ ...draft, pattern: e.target.value })} /></td>
            <td><input type="checkbox" checked={!!draft.is_regex}
              onChange={e => setDraft({ ...draft, is_regex: e.target.checked ? 1 : 0 })} /></td>
            <td><button className="btn primary" onClick={add}><Plus /></button></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
