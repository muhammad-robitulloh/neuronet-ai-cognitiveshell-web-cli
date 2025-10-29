import React from 'react';
import './AutoDebugPopup.css';

function AutoDebugPopup({ request, onConfirm, onCancel }) {
  if (!request) return null;

  return (
    <div className="auto-debug-popup-overlay">
      <div className="auto-debug-popup">
        <h3>Auto-Debug Suggested</h3>
        <p>An error was detected. Would you like to let the AI attempt to fix it?</p>
        <div className="error-details">
          <strong>Error:</strong>
          <pre>{request.error_details}</pre>
        </div>
        <div className="popup-buttons">
          <button onClick={() => onConfirm(request.request_id)} className="confirm-button">Yes, proceed</button>
          <button onClick={onCancel} className="cancel-button">No, cancel</button>
        </div>
      </div>
    </div>
  );
}

export default AutoDebugPopup;