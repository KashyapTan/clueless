import React from 'react';
import '../CSS/SettingsModels.css';
const SettingsModels: React.FC = () => {
  return (
      <div className="settings-models-section">
          <div className="settings-models-ollama-section">
              <div className="settings-models-ollama-header">
                Ollama
              </div>
              <div className="settings-models-ollama-content">
                <div className="settings-models-ollama-model">qwen1</div>
                <div className="settings-models-ollama-model">qwen2</div>
                <div className="settings-models-ollama-model">qwen3</div>
              </div>
              <div className="settings-models-anthropic-header">
                Anthropic
              </div>
              <div className="settings-models-anthropic-content">
                <div className="settings-models-anthropic-model">claude1</div>
                <div className="settings-models-anthropic-model">claude2</div>
                <div className="settings-models-anthropic-model">claude3</div>
              </div>
              <div className="settings-models-gemini-header">
                Gemini
              </div>
              <div className="settings-models-gemini-content">
                <div className="settings-models-gemini-model">gemini1</div>
                <div className="settings-models-gemini-model">gemini2</div>
                <div className="settings-models-gemini-model">gemini3</div>
              </div>
              <div className="settings-models-openai-header">
                OpenAI
              </div>
              <div className="settings-models-openai-content">
                <div className="settings-models-openai-model">openai1</div>
                <div className="settings-models-openai-model">openai2</div>
                <div className="settings-models-openai-model">openai3</div>
              </div>
          </div>
      </div>
  );
};

export default SettingsModels;
export { SettingsModels };
