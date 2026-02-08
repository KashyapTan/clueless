import React from 'react';
import { useOutletContext } from 'react-router-dom';
import TitleBar from '../components/TitleBar';

const MeetingAlbum: React.FC = () => {
  const { setMini } = useOutletContext<{ setMini: (val: boolean) => void }>();

  return (
    <div style={{ padding: '2rem', width: '100%', height: '100%', position: 'relative' }}>
      <TitleBar onClearContext={() => {}} setMini={setMini} />
      <div className="response-area">
        <h1>Recorded Meetings Album</h1>
        <p>Meeting recordings content goes here.</p>
      </div>
    </div>
  );
};

export default MeetingAlbum;
