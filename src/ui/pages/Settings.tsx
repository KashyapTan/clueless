import React from 'react';
import { useOutletContext } from 'react-router-dom';
import TitleBar from '../components/TitleBar';
import SettingsModels from '../components/SettingsModels';
import '../CSS/Settings.css';
import modelsIcon from '../assets/models.svg';
import connectionsIcon from '../assets/mcp.svg';
import ollamaIcon from '../assets/ollama.svg';
import anthropicIcon from '../assets/anthropic.svg';
import geminiIcon from '../assets/gemini.svg';
import openaiIcon from '../assets/openai.svg';

const Settings: React.FC = () => {
  const { setMini } = useOutletContext<{ setMini: (val: boolean) => void }>();

  return (
    <>
      <TitleBar onClearContext={() => {}} setMini={setMini} />
      <div className="settings-container">
        <div className="settings-side-bar">
          <div className="settings-models">
            <img src={modelsIcon} alt="Models" className='settings-icons'/>
            Models
          </div>
          <div className="settings-mcp-connections">
            <img src={connectionsIcon} alt="Connections" className='settings-icons'/>
            Connections
          </div>
          <div className="settings-ollama-model">
            <img src={ollamaIcon} alt="Ollama" className='settings-icons'/>
            Ollama
          </div>
          <div className="settings-anthropic-api-key">
            <img src={anthropicIcon} alt="Anthropic" className='settings-icons'/>
            Anthropic
          </div>
          <div className="settings-gemini-api-key">
            <img src={geminiIcon} alt="Gemini" className='settings-icons'/>
            Gemini
          </div>
          <div className="settings-openai-api-key">
            <img src={openaiIcon} alt="OpenAI" className='settings-icons'/>
            OpenAI
          </div>
        </div>
        <div className="settings-content">
          <SettingsModels />
        </div>
      </div>
    </>
  );
};

export default Settings;
