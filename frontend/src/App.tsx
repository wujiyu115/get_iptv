import { useEffect, useState } from 'react';
import {
  TabSources, TabAliases, TabTemplate, TabTasks, TabChannels, TabReport,
} from './icons';
import SourcesPanel from './components/SourcesPanel';
import AliasPanel from './components/AliasPanel';
import TemplatePanel from './components/TemplatePanel';
import TaskPanel from './components/TaskPanel';
import ChannelsPanel from './components/ChannelsPanel';
import ReportPanel from './components/ReportPanel';

type Tab = 'sources' | 'aliases' | 'templates' | 'task' | 'channels' | 'report';
const TABS: { k: Tab; label: string; Icon: () => JSX.Element }[] = [
  { k: 'sources', label: '数据源', Icon: TabSources },
  { k: 'aliases', label: '别名', Icon: TabAliases },
  { k: 'templates', label: '模板', Icon: TabTemplate },
  { k: 'task', label: '任务', Icon: TabTasks },
  { k: 'channels', label: '频道', Icon: TabChannels },
  { k: 'report', label: '报告', Icon: TabReport },
];

export default function App() {
  const [tab, setTab] = useState<Tab>(
    () => (localStorage.getItem('iptv-tab') as Tab) || 'task');
  const [dark, setDark] = useState<boolean>(() => {
    const saved = localStorage.getItem('iptv-theme');
    if (saved) return saved === 'dark';
    return matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (dark) root.setAttribute('data-theme', 'dark');
    else root.removeAttribute('data-theme');
    localStorage.setItem('iptv-theme', dark ? 'dark' : 'light');
  }, [dark]);

  const select = (k: Tab) => {
    setTab(k);
    localStorage.setItem('iptv-tab', k);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <>
      <div className="decor" aria-hidden="true">
        <svg className="ridge" viewBox="0 0 1440 460" preserveAspectRatio="none"
          fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round">
          <path d="M0 420 L210 250 L340 330 L520 170 L690 300 L860 150 L1040 290 L1210 200 L1440 340" opacity=".55" />
          <path d="M0 460 L180 320 L360 400 L560 250 L760 380 L980 240 L1180 360 L1440 260 L1440 460 Z" fill="currentColor" fillOpacity=".05" strokeOpacity=".8" />
          <path d="M0 460 L260 380 L470 440 L700 340 L940 430 L1200 350 L1440 420 L1440 460 Z" fill="currentColor" fillOpacity=".08" strokeOpacity=".45" />
        </svg>
      </div>

      <div className="tabs-wrap">
        <nav className="tabs" role="tablist">
          {TABS.map(({ k, label, Icon }) => (
            <button key={k} className={`tab ${tab === k ? 'active' : ''}`} role="tab"
              aria-selected={tab === k} onClick={() => select(k)}>
              <Icon /> {label}
            </button>
          ))}
          <button className="icon-btn theme-toggle" aria-label="切换深色模式"
            onClick={() => setDark(d => !d)}>
            <svg className="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
            <svg className="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4.2" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
          </button>
        </nav>
      </div>

      <main>
        <div className="panel">
          {tab === 'sources' && <SourcesPanel />}
          {tab === 'aliases' && <AliasPanel />}
          {tab === 'templates' && <TemplatePanel />}
          {tab === 'task' && <TaskPanel />}
          {tab === 'channels' && <ChannelsPanel />}
          {tab === 'report' && <ReportPanel />}
        </div>
      </main>
    </>
  );
}
