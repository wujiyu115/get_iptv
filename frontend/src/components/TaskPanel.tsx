import { useEffect, useRef, useState } from 'react';
import { runTask, getStatus, getSchedule, setSchedule, logsUrl } from '../api';
import type { Schedule } from '../types';

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

  const run = async () => {
    try { await runTask(); } catch { alert('已有任务在运行'); }
  };
  const saveSched = async () => { if (sched) { await setSchedule(sched); alert('已保存'); } };

  return (
    <>
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn primary" onClick={run} disabled={status === 'running'}>
            {status === 'running' ? '运行中…' : '立即运行'}
          </button>
          <span>状态: {status}</span>
          {stage && <span className="seg"><button className="active">{stage}</button></span>}
        </div>
        <div ref={logRef} className="logs" style={{ marginTop: 12 }}>
          {logs.join('\n')}
        </div>
      </div>
      {sched && (
        <div className="card">
          <h3>调度设置</h3>
          <div style={{ display: 'grid', gap: 10, maxWidth: 420 }}>
            <label>模式
              <select value={sched.update_mode}
                onChange={e => setSched({ ...sched, update_mode: e.target.value as 'interval' | 'time' })}>
                <option value="interval">interval（间隔小时）</option>
                <option value="time">time（每日定点）</option>
              </select>
            </label>
            {sched.update_mode === 'interval' ? (
              <label>间隔(小时)
                <input type="number" value={sched.update_interval}
                  onChange={e => setSched({ ...sched, update_interval: Number(e.target.value) })} />
              </label>
            ) : (
              <label>定点(逗号分隔 HH:MM)
                <input value={sched.update_times.join(',')}
                  onChange={e => setSched({ ...sched, update_times: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
              </label>
            )}
            <label>时区
              <input value={sched.time_zone}
                onChange={e => setSched({ ...sched, time_zone: e.target.value })} />
            </label>
            <label><input type="checkbox" checked={sched.update_startup}
              onChange={e => setSched({ ...sched, update_startup: e.target.checked })} /> 启动即跑</label>
            <button className="btn" onClick={saveSched}>保存调度</button>
          </div>
        </div>
      )}
    </>
  );
}
