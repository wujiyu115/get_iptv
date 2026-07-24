import { useEffect, useState } from 'react';
import { getReport } from '../api';
import type { Report } from '../types';
import { fmtLocal } from '../time';
import HelpTip from './HelpTip';

const resClass = (k: string) => {
  const n = parseInt(k, 10);
  if (n >= 1080) return 'hd';
  if (n >= 720) return 'md';
  return 'sd';
};

export default function ReportPanel() {
  const [r, setR] = useState<Report | null>(null);
  useEffect(() => { getReport().then(setR); }, []);
  if (!r) return <div className="card"><div className="card-body">加载中…</div></div>;

  const resEntries = Object.entries(r.resolution).sort((a, b) => parseInt(b[0]) - parseInt(a[0]));
  const resTotal = resEntries.reduce((s, [, v]) => s + v, 0) || 1;
  const groupEntries = Object.entries(r.groups).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <div className="card">
        <div className="card-head">
          <h2>清晰度分布</h2><HelpTip id="report" />
          <span className="card-head hint" style={{ padding: 0, marginLeft: 'auto' }}>共 {resTotal} 频道</span>
        </div>
        <div className="card-body">
          <div className="res-grid">
            {resEntries.map(([k, v]) => (
              <div key={k} className={`res-item ${resClass(k)}`}>
                <div className="res-top">
                  <span className="res-label">{parseInt(k) ? k + 'p' : k}</span>
                  <span className="res-num mono">{v}</span>
                </div>
                <div className="bar"><span style={{ width: `${(v / resTotal) * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>分组统计</h2>
          <span className="badge badge-count">{groupEntries.length} 组</span>
        </div>
        <div className="card-body">
          <div className="chip-cloud">
            {groupEntries.map(([n, c]) => (
              <span key={n} className="chip"><span className="cdot" />{n} <b>{c}</b></span>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h2>源健康度</h2></div>
        <div className="card-body flush">
          <table className="tbl responsive">
            <thead><tr><th>源</th><th className="center">启用</th><th className="num">失效次数</th><th>最近成功</th></tr></thead>
            <tbody>
              {r.sources.map(s => (
                <tr key={s.id}>
                  <td data-label="源" className="name-strong">{s.name}</td>
                  <td data-label="启用" className="center"><span className={`dot-status ${s.enabled ? 'ok' : 'fail'}`} /></td>
                  <td data-label="失效" className="num mono">{s.fail_count}</td>
                  <td data-label="最近成功" className="mono" style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                    {fmtLocal(s.last_ok_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h2>历史跑批</h2></div>
        <div className="card-body flush">
          <table className="tbl responsive">
            <thead><tr><th className="num">#</th><th>开始</th><th>结束</th><th className="center">状态</th><th>统计</th></tr></thead>
            <tbody>
              {r.runs.map(run => (
                <tr key={run.id}>
                  <td data-label="#" className="num mono">{run.id}</td>
                  <td data-label="开始" className="mono" style={{ fontSize: 12.5 }}>{fmtLocal(run.started_at)}</td>
                  <td data-label="结束" className="mono" style={{ fontSize: 12.5, color: 'var(--muted)' }}>{fmtLocal(run.finished_at)}</td>
                  <td data-label="状态" className="center">
                    {run.status === 'done'
                      ? <span className="badge badge-ok">done</span>
                      : run.status === 'failed'
                        ? <span className="badge badge-fail">failed</span>
                        : <span className="badge badge-count">{run.status}</span>}
                  </td>
                  <td data-label="统计" className="mono" style={{ fontSize: 12.5, color: 'var(--muted)' }}>{run.stats_json}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
