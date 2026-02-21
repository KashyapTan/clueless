/**
 * Session Banner Component.
 * 
 * Persistent banner shown when session mode is active.
 * Displays a Stop button to end autonomous operation.
 */

interface SessionBannerProps {
  onStop: () => void;
}

export function SessionBanner({ onStop }: SessionBannerProps) {
  return (
    <div className="terminal-session-banner">
      <span className="session-banner-text">
        ⚡ Session Mode Active — Xpdite is running autonomously
      </span>
      <button className="btn-stop-session" onClick={onStop}>
        Stop
      </button>
    </div>
  );
}
