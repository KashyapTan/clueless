import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../CSS/TitleBar.css';
import cluelessLogo from '../assets/transparent-clueless-logo.png';
import settingsIcon from '../assets/settings-icon.svg';
import chatHistoryIcon from '../assets/chat-history-icon.svg';
import recordedMeetingsAlbumIcon from '../assets/recorded-meetings-album-icon.svg';
import newChatIcon from '../assets/new-chat-icon.svg';

interface TitleBarProps {
  onClearContext: () => void;
  setMini: (mini: boolean) => void;
}

const TitleBar: React.FC<TitleBarProps> = ({ onClearContext, setMini }) => {
  const navigate = useNavigate();

  return (
    <div className="title-bar">
      <div className="nav-bar">
        <div className="settingsButton" onClick={() => navigate('/settings')}>
          <img src={settingsIcon} alt="Settings" className='settings-icon' />
        </div>
        <div className="chatHistoryButton" onClick={() => navigate('/history')}>
          <img src={chatHistoryIcon} alt="Chat History" className='chat-history-icon'/>
        </div>
        <div className="recordedMeetingsAlbumButton" onClick={() => navigate('/album')}>
          <img src={recordedMeetingsAlbumIcon} alt="Recorded Meetings Album" className='recorded-meetings-album-icon'/>
        </div>
      </div>
      <div className="blank-space-to-drag" onClick={() => navigate('/')}></div>
      <div className="nav-bar-right-side">
        <div className="newChatButton" onClick={() => { onClearContext(); navigate('/', { state: { newChat: true } }); }} title="Start new chat">
          <img src={newChatIcon} alt="New Chat" className='new-chat-icon'/>
        </div>
        <div className="clueless-logo-holder">
          <img
            src={cluelessLogo}
            alt="Clueless Logo"
            className='clueless-logo'
            onClick={() => {
              console.log('Logo clicked, entering mini mode');
              setMini(true);
              window.electronAPI?.setMiniMode(true);
            }}
            style={{ cursor: 'pointer' }}
            title="Mini mode"
          />
        </div>
      </div>
    </div>
  );
};

export default TitleBar;
