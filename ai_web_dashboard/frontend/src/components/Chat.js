import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const ws = useRef(null);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_URL}/api/chat`, { chat_id: 1, message: input });
      const aiResponse = response.data;

      if (aiResponse.type === 'shell_command') {
        // Handle WebSocket connection for shell output
        ws.current = new WebSocket(`${API_URL.replace('http', 'ws')}/ws/shell_output/1`);
        ws.current.onopen = () => {
          ws.current.send(JSON.stringify({ command: aiResponse.command }));
        };
        ws.current.onmessage = (event) => {
          const data = JSON.parse(event.data);
          setMessages(prev => [...prev, { sender: 'ai', text: data.content, type: data.type }]);
        };
        ws.current.onclose = () => {
          setIsLoading(false);
        };
      } else {
        setMessages(prev => [...prev, { sender: 'ai', text: aiResponse.message, type: aiResponse.type }]);
        setIsLoading(false);
      }
    } catch (error) {
      setMessages(prev => [...prev, { sender: 'ai', text: 'Error communicating with the backend.', type: 'error' }]);
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="message-list">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.sender}`}>
            <p>{msg.text}</p>
          </div>
        ))}
      </div>
      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type your message..."
          disabled={isLoading}
        />
        <button onClick={handleSend} disabled={isLoading}>
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default Chat;
