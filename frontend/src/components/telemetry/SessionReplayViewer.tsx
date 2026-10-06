import React, { useState, useEffect, useRef } from "react";
import "./replay.css";

export interface ReplayFrame {
  step: number;
  id: string;
  role: string;
  content: string;
  timestamp: string;
  tool_name?: string;
  tool_args?: Record<string, any>;
  tool_output?: string;
}

export interface ReplayData {
  session_id: string;
  repo: string;
  issue_number?: number;
  title: string;
  status: string;
  started_at: string;
  duration_seconds: number;
  total_tokens: number;
  cost_usd: number;
  total_frames: number;
  frames: ReplayFrame[];
}

interface Props {
  replay: ReplayData;
  onClose?: () => void;
}

export const SessionReplayViewer: React.FC<Props> = ({ replay, onClose }) => {
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const total = replay.frames.length;
  const currentFrame = replay.frames[currentStep] || replay.frames[0];

  useEffect(() => {
    if (isPlaying) {
      const intervalMs = Math.max(250, 1000 / playbackSpeed);
      timerRef.current = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev >= total - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, intervalMs);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, playbackSpeed, total]);

  return (
    <div className="replay-modal-backdrop">
      <div className="replay-modal-container">
        <header className="replay-header">
          <div className="replay-title-wrap">
            <span className="replay-badge">SESSION REPLAY</span>
            <h3>{replay.title}</h3>
            <span className="replay-sub">{replay.repo} #{replay.issue_number || ""}</span>
          </div>
          <div className="replay-meta-stats">
            <div className="stat-pill"><strong>Cost:</strong> ${replay.cost_usd.toFixed(4)}</div>
            <div className="stat-pill"><strong>Tokens:</strong> {replay.total_tokens.toLocaleString()}</div>
            {onClose && <button className="replay-close-btn" onClick={onClose}>✕</button>}
          </div>
        </header>

        <main className="replay-stage">
          {currentFrame && (
            <div className="frame-card">
              <div className="frame-meta">
                <span className={`role-tag role-${currentFrame.role.toLowerCase()}`}>
                  {currentFrame.role}
                </span>
                <span className="frame-time">{currentFrame.timestamp}</span>
                {currentFrame.tool_name && (
                  <span className="tool-tag">🔧 {currentFrame.tool_name}</span>
                )}
              </div>

              <div className="frame-content">
                <pre className="frame-text">{currentFrame.content}</pre>
                {currentFrame.tool_args && (
                  <div className="tool-box">
                    <span className="box-label">Args:</span>
                    <pre>{JSON.stringify(currentFrame.tool_args, null, 2)}</pre>
                  </div>
                )}
                {currentFrame.tool_output && (
                  <div className="tool-box output-box">
                    <span className="box-label">Output:</span>
                    <pre>{currentFrame.tool_output}</pre>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>

        <footer className="replay-controls">
          <div className="scrubber-row">
            <input
              type="range"
              min={0}
              max={Math.max(0, total - 1)}
              value={currentStep}
              onChange={(e) => setCurrentStep(Number(e.target.value))}
              className="scrub-slider"
            />
            <span className="step-counter">
              Step {currentStep + 1} / {total}
            </span>
          </div>

          <div className="buttons-row">
            <button className="play-btn" onClick={() => setIsPlaying(!isPlaying)}>
              {isPlaying ? "⏸ Pause" : "▶ Play"}
            </button>
            <button className="step-btn" onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}>
              ⏮ Prev
            </button>
            <button className="step-btn" onClick={() => setCurrentStep((s) => Math.min(total - 1, s + 1))}>
              Next ⏭
            </button>
            <div className="speed-selector">
              {[1, 2, 4].map((s) => (
                <button
                  key={s}
                  className={`speed-btn ${playbackSpeed === s ? "active" : ""}`}
                  onClick={() => setPlaybackSpeed(s)}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};
