/**
 * Mode selector component.
 * 
 * Buttons for selecting capture mode (fullscreen, precision, meeting).
 */
import React from 'react';
import type { CaptureMode } from '../../types';

interface ModeSelectorProps {
  captureMode: CaptureMode;
  meetingRecordingMode: boolean;
  onFullscreenMode: () => void;
  onPrecisionMode: () => void;
  onMeetingMode: () => void;
  regionSSIcon: string;
  fullscreenSSIcon: string;
  meetingRecordingIcon: string;
}

export function ModeSelector({
  captureMode,
  meetingRecordingMode,
  onFullscreenMode,
  onPrecisionMode,
  onMeetingMode,
  regionSSIcon,
  fullscreenSSIcon,
  meetingRecordingIcon,
}: ModeSelectorProps) {
  return (
    <div className="mode-selection-section">
      <div
        className={`regionssmode${captureMode === 'precision' ? '-active' : ''}`}
        onClick={onPrecisionMode}
        title="Talk to a specific region of your screen"
      >
        <img src={regionSSIcon} alt="Region Screenshot Mode" className="region-ss-icon" />
      </div>
      <div
        className={`fullscreenssmode${captureMode === 'fullscreen' ? '-active' : ''}`}
        onClick={onFullscreenMode}
        title="Talk to anything on your screen"
      >
        <img src={fullscreenSSIcon} alt="Full Screen Screenshot Mode" className="fullscreen-ss-icon" />
      </div>
      <div
        className={`meetingrecordermode${meetingRecordingMode ? '-active' : ''}`}
        onClick={onMeetingMode}
        title="Meeting recorder mode"
      >
        <img src={meetingRecordingIcon} alt="Meeting Recorder Mode" className="meeting-recording-icon" />
      </div>
    </div>
  );
}
