import { createRoot } from 'react-dom/client';
import './index.css';

// NOTE: Task 19 will introduce App.tsx and switch this to `render(<App />)`.
// Placeholder render keeps the scaffold build green without pulling in App yet.
createRoot(document.getElementById('root')!).render(<div className="brand">IPTV 聚合服务</div>);
