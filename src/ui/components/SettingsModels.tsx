import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import '../CSS/SettingsModels.css';

interface OllamaModel {
  name: string;
  size: number;
  parameter_size: string;
  quantization: string;
}

/**
 * SettingsModels — the "Models" tab inside Settings.
 *
 * Responsibilities:
 * 1. Fetch all Ollama models installed on the machine (GET /api/models/ollama).
 * 2. Fetch which models the user has enabled (GET /api/models/enabled).
 * 3. Let the user toggle models on/off.
 * 4. Persist changes (PUT /api/models/enabled).
 *
 * The enabled models list is consumed by App.tsx's model-selector dropdown
 * so only toggled models appear there.
 */
const SettingsModels: React.FC = () => {
  // All Ollama models on the machine
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  // Names of models the user has toggled on
  const [enabledModels, setEnabledModels] = useState<string[]>([]);
  // Loading / error states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // --------------------------------------------------
  // Fetch data on mount
  // --------------------------------------------------
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      try {
        // Fire both requests in parallel
        const [models, enabled] = await Promise.all([
          api.getOllamaModels(),
          api.getEnabledModels(),
        ]);
        setOllamaModels(models);
        setEnabledModels(enabled);
      } catch {
        setError('Could not reach the backend. Is Ollama running?');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // --------------------------------------------------
  // Toggle a model on/off and persist
  // --------------------------------------------------
  const toggleModel = useCallback(
    async (modelName: string) => {
      // Use functional setState to avoid stale closure issues
      setEnabledModels((prev) => {
        const isEnabled = prev.includes(modelName);
        const updated = isEnabled
          ? prev.filter((m) => m !== modelName)
          : [...prev, modelName];

        // Persist to backend (SQLite) — fire-and-forget
        api.setEnabledModels(updated);

        return updated;
      });
    },
    [],
  );

  // --------------------------------------------------
  // Helper: human-readable file size
  // --------------------------------------------------
  const formatSize = (bytes: number) => {
    if (bytes === 0) return '';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  // --------------------------------------------------
  // Render
  // --------------------------------------------------
  return (
    <div className="settings-models-section">
      {/* ====== OLLAMA SECTION ====== */}
      <div className="settings-models-ollama-section">
        <div className="settings-models-ollama-header">Ollama</div>

        <div className="settings-models-ollama-content">
          {loading && (
            <div className="settings-models-ollama-model settings-models-loading">
              Loading models…
            </div>
          )}
          {error && (
            <div className="settings-models-ollama-model settings-models-error">
              {error}
            </div>
          )}
          {!loading && !error && ollamaModels.length === 0 && (
            <div className="settings-models-ollama-model settings-models-empty">
              No Ollama models found. Pull one with <code>ollama pull model-name</code>
            </div>
          )}
          {!loading &&
            ollamaModels.map((model) => {
              const isEnabled = enabledModels.includes(model.name);
              return (
                <div
                  key={model.name}
                  className={`settings-models-ollama-model ${isEnabled ? 'settings-models-enabled' : ''}`}
                  onClick={() => toggleModel(model.name)}
                >
                  <div className="settings-model-toggle">
                    <div className={`settings-model-toggle-track ${isEnabled ? 'active' : ''}`}>
                      <div className="settings-model-toggle-thumb" />
                    </div>
                  </div>
                  <div className="settings-model-info">
                    <span className="settings-model-name">{model.name}</span>
                    <span className="settings-model-meta">
                      {[model.parameter_size, model.quantization, formatSize(model.size)]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </div>
                </div>
              );
            })}
        </div>

        {/* ====== ANTHROPIC PLACEHOLDER ====== */}
        <div className="settings-models-anthropic-header">Anthropic</div>
        <div className="settings-models-anthropic-content">
          <div className="settings-models-anthropic-model settings-models-placeholder">Coming soon</div>
        </div>

        {/* ====== GEMINI PLACEHOLDER ====== */}
        <div className="settings-models-gemini-header">Gemini</div>
        <div className="settings-models-gemini-content">
          <div className="settings-models-gemini-model settings-models-placeholder">Coming soon</div>
        </div>

        {/* ====== OPENAI PLACEHOLDER ====== */}
        <div className="settings-models-openai-header">OpenAI</div>
        <div className="settings-models-openai-content">
          <div className="settings-models-openai-model settings-models-placeholder">Coming soon</div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModels;
export { SettingsModels };

