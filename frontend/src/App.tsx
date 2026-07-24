import { useEffect, useState } from 'react';
import { Sun, Moon } from './icons';
import SourcesPanel from './components/SourcesPanel';
import AliasPanel from './components/AliasPanel';
import TemplatePanel from './components/TemplatePanel';
import TaskPanel from './components/TaskPanel';
import ChannelsPanel from './components/ChannelsPanel';
import ReportPanel from './components/ReportPanel';

type Tab = 'sources' | 'aliases' | 'templates' | 'task' | 'channels' | 'report';
const TABS: { k: Tab; label: string }[] = [
  { k: 'sources', label: '源' }, { k: 'aliases', label: '别名' },
  { k: 'templates', label: '模板' }, { k: 'task', label: '任务' },
  { k: 'channels', label: '频道' }, { k: 'report', label: '报告' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('task');
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('iptv-theme') as 'dark' | 'light') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('iptv-theme', theme);
  }, [theme]);

  return (
    <>
      <header>
        <div className="brand">IPTV 聚合服务</div>
        <div className="tools">
          <div className="seg">
            {TABS.map(t => (
              <button key={t.k} className={tab === t.k ? 'active' : ''}
                onClick={() => setTab(t.k)}>{t.label}</button>
            ))}
          </div>
          <button className="icon-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            {theme === 'dark' ? <Sun /> : <Moon />}
          </button>
        </div>
      </header>
      <main>
        {tab === 'sources' && <SourcesPanel />}
        {tab === 'aliases' && <AliasPanel />}
        {tab === 'templates' && <TemplatePanel />}
        {tab === 'task' && <TaskPanel />}
        {tab === 'channels' && <ChannelsPanel />}
        {tab === 'report' && <ReportPanel />}
      </main>
    </>
  );
}
