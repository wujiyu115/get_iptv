import { useEffect, useRef } from 'react';
import { proxyUrl, restreamUrl } from '../api';

interface Props { url: string; name: string; onClose: () => void; }

export default function PlayerOverlay({ url, name, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    let player: any;
    let hls: any;
    let cancelled = false;
    let fellBack = false;
    const video = videoRef.current!;
    const src = proxyUrl(url);  // route through backend to dodge CORS/mixed-content
    const isHls = /\.m3u8(\?|$)/i.test(url);
    const isTs = /\.(ts|flv)(\?|$)/i.test(url) || url.startsWith('mpegts');

    // Autoplay with sound is blocked unless muted — retry muted so it plays.
    const tryPlay = () => video.play().catch(() => {
      video.muted = true;
      video.play().catch(() => {});
    });

    // Compatibility fallback: some live streams (missing SPS/PPS, buffer holes)
    // stall in browser HLS. ffmpeg remuxes them into a clean continuous TS that
    // mpegts.js plays. Only used on failure so well-formed streams stay cheap.
    const fallbackRestream = async () => {
      if (fellBack || cancelled) return;
      fellBack = true;
      if (hls) { try { hls.destroy(); } catch { /* noop */ } hls = null; }
      if (player) { try { player.destroy(); } catch { /* noop */ } player = null; }
      try {
        const mpegts = (await import('mpegts.js')).default;
        if (cancelled || !mpegts.isSupported()) return;
        player = mpegts.createPlayer({ type: 'mse', isLive: true, url: restreamUrl(url) });
        player.attachMediaElement(video);
        player.load();
        tryPlay();
      } catch { /* nothing else to try */ }
    };

    (async () => {
      if (isHls) {
        if (video.canPlayType('application/vnd.apple.mpegurl')) {
          video.src = src;  // Safari native HLS
          tryPlay();
          return;
        }
        try {
          const Hls = (await import('hls.js')).default;
          if (cancelled) return;
          if (Hls.isSupported()) {
            hls = new Hls();
            hls.loadSource(src);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, tryPlay);
            hls.on(Hls.Events.ERROR, (_e: any, d: any) => {
              if (d.fatal) fallbackRestream();
            });
            return;
          }
        } catch { /* fall through */ }
        video.src = src;
        tryPlay();
        return;
      }
      if (isTs) {
        try {
          const mpegts = (await import('mpegts.js')).default;
          if (cancelled) return;
          if (mpegts.isSupported()) {
            player = mpegts.createPlayer({ type: 'mse', isLive: true, url: src });
            player.on(mpegts.Events.ERROR, () => fallbackRestream());
            player.attachMediaElement(video);
            player.load();
            tryPlay();
            return;
          }
        } catch { /* fall through to native */ }
      }
      video.src = src;
      tryPlay();
    })();

    // Stall watchdog: if playback is running but currentTime is frozen for ~6s,
    // switch to the ffmpeg restream path.
    let lastT = 0, stalls = 0;
    const watch = window.setInterval(() => {
      if (cancelled || fellBack) return;
      if (!video.paused && !video.ended) {
        if (Math.abs(video.currentTime - lastT) < 0.1) {
          if (++stalls >= 3) fallbackRestream();
        } else {
          stalls = 0;
        }
        lastT = video.currentTime;
      }
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(watch);
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
