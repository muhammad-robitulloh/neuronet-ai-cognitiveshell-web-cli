import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Dashboard() {
  const [systemInfo, setSystemInfo] = useState(null);

  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/system_info`);
        setSystemInfo(response.data);
      } catch (error) {
        console.error('Error fetching system info:', error);
      }
    };

    fetchSystemInfo();
  }, []);

  return (
    <div>
      <h2>Dashboard</h2>
      <p>Welcome to your AI Web Dashboard!</p>
      {systemInfo && (
        <div className="system-info">
          <h3>System Information</h3>
          <p><strong>OS:</strong> {systemInfo.os}</p>
          <p><strong>Shell:</strong> {systemInfo.shell}</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
