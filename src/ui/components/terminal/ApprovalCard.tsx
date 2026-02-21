/**
 * Approval Card Component.
 * 
 * Rendered inside the terminal panel when a command needs user approval.
 * Shows the command, working directory, and Allow/Deny/Allow & Remember buttons.
 */

interface ApprovalCardProps {
  command: string;
  cwd: string;
  onAllow: () => void;
  onDeny: () => void;
  onAllowRemember: () => void;
}

export function ApprovalCard({
  command,
  cwd,
  onAllow,
  onDeny,
  onAllowRemember,
}: ApprovalCardProps) {
  return (
    <div className="terminal-approval-card">
      <div className="approval-header">
        🖥 Xpdite wants to run a command
      </div>
      <div className="approval-command">
        <code>$ {command}</code>
      </div>
      {cwd && (
        <div className="approval-cwd">
          in: {cwd}
        </div>
      )}
      <div className="approval-actions">
        <button className="btn-deny" onClick={onDeny}>
          Deny
        </button>
        <button className="btn-allow" onClick={onAllow}>
          Allow
        </button>
        <button className="btn-allow-remember" onClick={onAllowRemember}>
          Allow &amp; Remember
        </button>
      </div>
    </div>
  );
}
