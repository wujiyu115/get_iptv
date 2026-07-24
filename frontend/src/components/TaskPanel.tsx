import { useEffect, useRef, useState } from 'react';
import { runTask, stopTask, getStatus, getSchedule, setSchedule, logsUrl } from '../api';
import type { Schedule } from '../types';
import { Play } from '../icons';
import { fmtLocal } from '../time';
import HelpTip from './HelpTip';

function LogLine({ raw }: { raw: string }) {
  const sp = raw.indexOf(' ');
  const ts = sp > 0 ? fmtLocal(raw.slice(0, sp)) : '';
  const msg = sp > 0 ? raw.slice(sp + 1) : raw;
  const cls = /FAIL/i.test(msg) ? 'fail'
    : /(\bok\b|reachable|playable|done|✓)/i.test(msg) ? 'ok'
      : /stage:/i.test(msg) ? 'info' : '';
  return <div><span className="t">{ts}</span>  <span className={cls}>{msg}</span></div>;
}

export default function TaskPanel() {
  const [logs, setLogs] = useState<string[]>([]);
  const [stage, setStage] = useState('');
  const [status, setStatus] = useState('idle');
  const [sched, setSched] = useState<Schedule | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSchedule().then(setSched);
    const es = new EventSource(logsUrl());
    es.onmessage = e => setLogs(prev => [...prev.slice(-500), e.data]);
    const poll = setInterval(() => {
      getStatus().then(s => { setStage(s.stage); setStatus(s.status); });
    }, 1500);
    return () => { es.close(); clearInterval(poll); };
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const [stopping, setStopping] = useState(false);
  const run = async () => {
    try { await runTask(); } catch { alert('已有任务在运行'); }
  };
  const stop = async () => {
    setStopping(true);
    try { await stopTask(); } catch { /* nothing running */ }
  };
  const saveSched = async () => { if (sched) { await setSchedule(sched); alert('已保存'); } };

  const running = status === 'running';
  useEffect(() => { if (!running) setStopping(false); }, [running]);
  const pillCls = running ? '' : status === 'failed' ? 'fail' : 'idle';

  return (
    <>
      <div className="card">
        <div className="card-head">
          <div className="toolbar" style={{ flex: 1 }}>
            <button className="btn btn-primary" onClick={run} disabled={running}>
              <Play /> {running ? '运行中…' : '运行一次'}
            </button>
            {running && (
              <button className="btn btn-danger-ghost" onClick={stop} disabled={stopping}>
                {stopping ? '停止中…' : '中断'}
              </button>
            )}
            <span className={`pill-run ${pillCls}`} style={{ marginLeft: 'auto' }}>
              {running && <span className="pulse" />}
              状态：{status}{stage ? ` · ${stage}` : ''}
            </span>
          </div>
        </div>
        <div className="card-body">
          <div className="console mono" ref={logRef} role="log" aria-live="polite">
            {logs.map((l, i) => <LogLine key={i} raw={l} />)}
          </div>
        </div>
      </div>

      {sched && (
        <div className="card">
          <div className="card-head"><h2>调度设置</h2><HelpTip id="task" /></div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 18 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>模式</span>
                <select className="inp" value={sched.update_mode}
                  onChange={e => setSched({ ...sched, update_mode: e.target.value as 'interval' | 'time' })}>
                  <option value="interval">interval · 间隔小时</option>
                  <option value="time">time · 每日定点</option>
                </select>
              </label>
              {sched.update_mode === 'interval' ? (
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>间隔（小时）</span>
                  <input className="inp mono" type="number" value={sched.update_interval}
                    onChange={e => setSched({ ...sched, update_interval: Number(e.target.value) })} />
                </label>
              ) : (
                <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>定点（逗号分隔 HH:MM）</span>
                  <input className="inp mono" value={sched.update_times.join(',')}
                    onChange={e => setSched({ ...sched, update_times: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
                </label>
              )}
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>时区</span>
                <input className="inp" value={sched.time_zone}
                  onChange={e => setSched({ ...sched, time_zone: e.target.value })} />
              </label>
            </div>
            <label className="switch" style={{ marginTop: 20 }}>
              <input type="checkbox" checked={sched.update_startup}
                onChange={e => setSched({ ...sched, update_startup: e.target.checked })} />
              <span className="track" />启动即跑
            </label>
            <div style={{ marginTop: 22 }}>
              <button className="btn btn-primary" onClick={saveSched}>保存调度</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
