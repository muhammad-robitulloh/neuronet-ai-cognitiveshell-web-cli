import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Settings() {
  const [llmConfig, setLlmConfig] = useState({});
  const [apiKey, setApiKey] = useState('');
  const [llmBaseUrl, setLlmBaseUrl] = useState('');
  const [telegramConfig, setTelegramConfig] = useState({});

  useEffect(() => {
    fetchLlmConfig();
    fetchApiKey();
    fetchLlmBaseUrl();
    fetchTelegramConfig();
  }, []);

  const fetchLlmConfig = async () => {
    const response = await axios.get(`${API_URL}/api/settings/llm_config`);
    setLlmConfig(response.data);
  };

  const fetchApiKey = async () => {
    const response = await axios.get(`${API_URL}/api/settings/api_key`);
    setApiKey(response.data.api_key);
  };

  const fetchLlmBaseUrl = async () => {
    const response = await axios.get(`${API_URL}/api/settings/llm_base_url`);
    setLlmBaseUrl(response.data.llm_base_url);
  };

  const fetchTelegramConfig = async () => {
    const response = await axios.get(`${API_URL}/api/settings/telegram_config`);
    setTelegramConfig(response.data);
  };

  const handleLlmConfigChange = (e) => {
    setLlmConfig({ ...llmConfig, [e.target.name]: e.target.value });
  };

  const handleApiKeyChange = (e) => {
    setApiKey(e.target.value);
  };

  const handleLlmBaseUrlChange = (e) => {
    setLlmBaseUrl(e.target.value);
  };

  const handleTelegramConfigChange = (e) => {
    setTelegramConfig({ ...telegramConfig, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    await axios.put(`${API_URL}/api/settings/llm_config`, llmConfig);
    await axios.put(`${API_URL}/api/settings/api_key`, { api_key: apiKey });
    await axios.put(`${API_URL}/api/settings/llm_base_url`, { base_url: llmBaseUrl });
    await axios.put(`${API_URL}/api/settings/telegram_config`, telegramConfig);
    alert('Settings saved!');
  };

  return (
    <div className="settings">
      <h2>Settings</h2>
      <div className="settings-section">
        <h3>LLM Configuration</h3>
        {Object.keys(llmConfig).map((key) => (
          <div key={key}>
            <label>{key}</label>
            <input
              type="text"
              name={key}
              value={llmConfig[key]}
              onChange={handleLlmConfigChange}
            />
          </div>
        ))}
      </div>
      <div className="settings-section">
        <h3>API Key</h3>
        <input type="text" value={apiKey} onChange={handleApiKeyChange} />
      </div>
      <div className="settings-section">
        <h3>LLM Base URL</h3>
        <input type="text" value={llmBaseUrl} onChange={handleLlmBaseUrlChange} />
      </div>
      <div className="settings-section">
        <h3>Telegram Configuration</h3>
        <label>Chat ID</label>
        <input
          type="text"
          name="telegram_chat_id"
          value={telegramConfig.telegram_chat_id}
          onChange={handleTelegramConfigChange}
        />
        <label>Bot Token</label>
        <input
          type="text"
          name="telegram_bot_token"
          value={telegramConfig.telegram_bot_token}
          onChange={handleTelegramConfigChange}
        />
      </div>
      <button onClick={handleSave}>Save Settings</button>
    </div>
  );
}

export default Settings;
