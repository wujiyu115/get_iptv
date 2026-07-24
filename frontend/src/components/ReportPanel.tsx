import { useEffect, useState } from 'react';
import { getReport } from '../api';
import type { Report } from '../types';
import HelpTip from './HelpTip';

export default function ReportPanel() {
  const [r, setR] = useState<Report | null>(null);
  useEffect(() => { getReport().then(setR); }, []);
  if (!r) return <div className="card">加载中…</div>;

  return (
    <>
      <div className="card">
        <h3>清晰度分布<HelpTip id="report" /></h3>
        {Object.entries(r.resolution).map(([k, v]) => (
          <div key={k}>{k}: {v}</div>
        ))}
      </div>
      <div className="card">
        <h3>分组统计（{Object.keys(r.groups).length} 组）</h3>
        {Object.entries(r.groups).map(([k, v]) => (
          <span key={k} className="seg" style={{ margin: 2, display: 'inline-flex' }}>
            <button>{k}: {v}</button>
          </span>
        ))}
      </div>
      <div className="card">
        <h3>源健康度</h3>
        <table>
          <thead><tr><th>源</th><th>启用</th><th>失败次数</th><th>最近成功</th></tr></thead>
          <tbody>{r.sources.map(s => (
            <tr key={s.id}><td>{s.name}</td><td>{s.enabled ? '✓' : '✗'}</td>
              <td>{s.fail_count}</td><td>{s.last_ok_at?.slice(0, 16) || '-'}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <div className="card">
        <h3>历史跑批</h3>
        <table>
          <thead><tr><th>#</th><th>开始</th><th>结束</th><th>状态</th><th>统计</th></tr></thead>
          <tbody>{r.runs.map(run => (
            <tr key={run.id}><td>{run.id}</td><td>{run.started_at?.slice(0, 16)}</td>
              <td>{run.finished_at?.slice(0, 16) || '-'}</td><td>{run.status}</td>
              <td>{run.stats_json}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
