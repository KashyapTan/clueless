import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import '../../CSS/SettingsConnections.css';

interface GoogleStatus {
  connected: boolean;
  email: string | null;
  auth_in_progress: boolean;
}

/**
 * SettingsConnections — the "Connections" tab inside Settings.
 *
 * Displays connection cards for external services (Google).
 * Handles the OAuth flow for connecting/disconnecting Google account,
 * which enables Gmail and Calendar MCP tools.
 *
 * Users just click "Connect" and the browser opens for Google login.
 * No credentials file upload required.
 */
const SettingsConnections: React.FC = () => {
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus>({
    connected: false,
    email: null,
    auth_in_progress: false,
  });
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState('');

  // Fetch Google connection status
  const fetchStatus = useCallback(async () => {
    try {
      const status = await api.getGoogleStatus();
      setGoogleStatus(status);
      setError('');
    } catch {
      setError('Could not reach the backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Handle Connect button click — opens browser for Google login
  const handleConnect = async () => {
    setConnecting(true);
    setError('');

    try {
      const result = await api.connectGoogle();
      if (result.success) {
        await fetchStatus();
      } else {
        setError(result.error || 'Connection failed');
      }
    } catch {
      setError('Could not reach the server. Is it running?');
    } finally {
      setConnecting(false);
    }
  };

  // Handle Disconnect button click
  const handleDisconnect = async () => {
    setError('');
    try {
      const result = await api.disconnectGoogle();
      if (result.success) {
        setGoogleStatus((prev) => ({
          ...prev,
          connected: false,
          email: null,
        }));
      } else {
        setError(result.error || 'Disconnect failed');
      }
    } catch {
      setError('Failed to disconnect');
    }
  };

  return (
    <div className="settings-connections-section">
      <div className="settings-connections-header">Connections</div>
      <div className="settings-connections-subtitle">
        Connect external services to give Clueless more tools!
      </div>

      {error && <div className="settings-connections-error">{error}</div>}

      <div className="settings-connections-grid">
        {/* Google Connection Card */}
        <div className={`settings-connection-card ${googleStatus.connected ? 'connected' : ''}`}>
          <div className="settings-connection-card-icon">
            <svg viewBox="0 0 24 24" width="28" height="28">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
          </div>

          <div className="settings-connection-card-info">
            <div className="settings-connection-card-title">Google</div>
            <div className="settings-connection-card-desc">
              {loading
                ? 'Checking...'
                : googleStatus.connected
                  ? `Connected as ${googleStatus.email || 'your account'}`
                  : 'Gmail & Calendar access'}
            </div>
          </div>

          <div className="settings-connection-card-services">
            <span className="settings-connection-service-badge">Gmail</span>
            <span className="settings-connection-service-badge">Calendar</span>
          </div>

          <div className="settings-connection-card-actions">
            {googleStatus.connected ? (
              <button
                className="settings-connection-btn disconnect"
                onClick={handleDisconnect}
              >
                Disconnect
              </button>
            ) : connecting ? (
              <button className="settings-connection-btn connecting" disabled>
                Connecting...
              </button>
            ) : (
              <button
                className="settings-connection-btn connect"
                onClick={handleConnect}
                disabled={loading}
              >
                Connect
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsConnections;
