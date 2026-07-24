import { useEffect, useRef } from 'react';

interface Props { url: string; name: string; onClose: () => void; }

export default function PlayerOverlay({ url, name, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    let player: any;
    let cancelled = false;
    const video = videoRef.current!;
    (async () => {
      const isTs = /\.(ts|m3u8)(\?|$)/i.test(url) || url.startsWith('mpegts');
      if (isTs) {
        try {
          const mpegts = (await import('mpegts.js')).default;
          if (cancelled) return;
          if (mpegts.isSupported()) {
            player = mpegts.createPlayer({ type: 'mse', isLive: true, url });
            player.attachMediaElement(video);
            player.load();
            player.play().catch(() => {});
            return;
          }
        } catch { /* fall through to native */ }
      }
      video.src = url;
      video.play().catch(() => {});
    })();
    return () => {
      cancelled = true;
      window.removeEventListener('keydown', onKey);
      if (player) { try { player.destroy(); } catch { /* noop */ } }
    };
  }, [url, onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{ textAlign: 'center' }}>
        <div style={{ color: '#fff', marginBottom: 8 }}>{name}</div>
        <video ref={videoRef} controls autoPlay playsInline />
        <div style={{ marginTop: 10 }}>
          <button className="btn" onClick={onClose}>关闭 (Esc)</button>
        </div>
      </div>
    </div>
  );
}
