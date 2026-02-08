import React from 'react';
import { useOutletContext } from 'react-router-dom';
import TitleBar from '../components/TitleBar';
import '../CSS/ChatHistory.css';

const ChatHistory: React.FC = () => {
  const { setMini } = useOutletContext<{ setMini: (val: boolean) => void }>();

  return (
    <>
      <TitleBar onClearContext={() => {}} setMini={setMini} />
          <div className="chat-history-container">
              <div className="chat-history-search-box-container">
                  <form className='chat-history-search-box-form'>
                        <input type="text" placeholder="Search chat history..." className="chat-history-search-box-input"/>
                  </form>
              </div>
              <div className="chat-history-list-title">
                  <div className="chat-history-description">Description</div>
                  <div className="chat-history-date">Date</div>
              </div>
              <div className="chat-history-list-container">
                <div className="chat-history-list-item">
                    <div className="chat-history-list-item-description">Chat with John about project updates</div>
                    <div className="chat-history-list-item-date">2024-06-01 10:30 AM</div>
                </div>
              </div>
          </div>
    </>
  );
};

export default ChatHistory;
