import React from 'react';
import { useOutletContext } from 'react-router-dom';
import TitleBar from '../components/TitleBar';
import '../CSS/Settings.css';

const Settings: React.FC = () => {
  const { setMini } = useOutletContext<{ setMini: (val: boolean) => void }>();

  return (
    <div style={{ padding: '2rem', width: '100%', height: '100%', position: 'relative' }}>
      <TitleBar onClearContext={() => {}} setMini={setMini} />
      <div className="response-area">
        <h1>Settings</h1>
        <p>Settings page content goes here.</p>
      </div>
    </div>
  );
};

export default Settings;
