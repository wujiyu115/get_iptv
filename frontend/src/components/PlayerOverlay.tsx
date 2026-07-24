import { useEffect, useRef } from 'react';
import { proxyUrl } from '../api';

interface Props { url: string; name: string; onClose: () => void; }

export default function PlayerOverlay({ url, name, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    let player: any;
    let hls: any;
    let cancelled = false;
    const video = videoRef.current!;
    const src = proxyUrl(url);  // route through backend to dodge CORS/mixed-content
    const isHls = /\.m3u8(\?|$)/i.test(url);
    const isTs = /\.(ts|flv)(\?|$)/i.test(url) || url.startsWith('mpegts');

    (async () => {
      if (isHls) {
        // Safari plays HLS natively; elsewhere use hls.js
        if (video.canPlayType('application/vnd.apple.mpegurl')) {
          video.src = src;
          video.play().catch(() => {});
          return;
        }
        try {
          const Hls = (await import('hls.js')).default;
          if (cancelled) return;
          if (Hls.isSupported()) {
            hls = new Hls();
            hls.loadSource(src);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
            return;
          }
        } catch { /* fall through */ }
        video.src = src;
        video.play().catch(() => {});
        return;
      }
      if (isTs) {
        try {
          const mpegts = (await import('mpegts.js')).default;
          if (cancelled) return;
          if (mpegts.isSupported()) {
            player = mpegts.createPlayer({ type: 'mse', isLive: true, url: src });
            player.attachMediaElement(video);
            player.load();
            player.play().catch(() => {});
            return;
          }
        } catch { /* fall through to native */ }
      }
      video.src = src;
      video.play().catch(() => {});
    })();

    return () => {
      cancelled = true;
      window.removeEventListener('keydown', onKey);
      if (player) { try { player.destroy(); } catch { /* noop */ } }
      if (hls) { try { hls.destroy(); } catch { /* noop */ } }
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
