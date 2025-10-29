
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import Terminal from './Terminal';
import Settings from './Settings';
import ChatHistory from './ChatHistory';
import Chat from './Chat';
import AIAnalytics from './AIAnalytics';
import Sidebar from './Sidebar';
import SystemInfo from './SystemInfo';
import { AppBar, Toolbar, Typography, IconButton, Box, Snackbar, Alert } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8002';

function Dashboard() {
  const [activeTab, setActiveTab] = useState('shell');
  const [chatHistory, setChatHistory] = useState(() => {
    const savedHistory = localStorage.getItem('chatHistory');
    return savedHistory ? JSON.parse(savedHistory) : [];
  });
  const [shellHistory, setShellHistory] = useState(() => {
    const savedHistory = localStorage.getItem('shellHistory');
    return savedHistory ? JSON.parse(savedHistory) : [];
  });
  const [commandToExecute, setCommandToExecute] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [openSnackbar, setOpenSnackbar] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState('success'); // can be 'success', 'error', 'info', 'warning'
  const [showReasoning, setShowReasoning] = useState(true); // Add state for reasoning visibility
  const chatId = 0;

  useEffect(() => {
    localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
    axios.post(`${API_URL}/api/history/save`, { history_type: 'chat', history: chatHistory });
  }, [chatHistory]);

  useEffect(() => {
    localStorage.setItem('shellHistory', JSON.stringify(shellHistory));
    axios.post(`${API_URL}/api/history/save`, { history_type: 'shell', history: shellHistory });
  }, [shellHistory]);

  

  

  const handleCloseSnackbar = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpenSnackbar(false);
  };

  const showSnackbar = (message, severity) => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setOpenSnackbar(true);
  };
    const addToShellHistory = useCallback((item) => {
    setShellHistory(prev => [...prev, item]);
  }, []);

  const handleExecuteCommandInTerminal = useCallback((command) => {
    setCommandToExecute(command);
    setActiveTab('shell');
  }, []);

  const handleClearAllHistory = useCallback(async () => {
    try {
      await axios.post(`${API_URL}/api/clear_history`);
      setShellHistory([]);
      setChatHistory([]);
      localStorage.removeItem('chatHistory');
      localStorage.removeItem('shellHistory');
      showSnackbar("All history cleared!", 'success');
    } catch (error) {
      console.error('Error clearing history:', error);
      showSnackbar("Failed to clear history.", 'error');
    }
  }, []);

  const handleRestartUI = useCallback(() => {
    setChatHistory([]);
    setShellHistory([]);
    setCommandToExecute(null);
    localStorage.removeItem('chatHistory');
    localStorage.removeItem('shellHistory');
    showSnackbar("UI has been reset!", 'success');
  }, []);

  const toggleDrawer = () => {
    setIsDrawerOpen(!isDrawerOpen);
  };

  const handleTabClick = (tabName) => {
    setActiveTab(tabName);
    setIsDrawerOpen(false);
  };

  const renderMainContent = () => {
    switch (activeTab) {
      case 'shell':
        return <Terminal chatId={chatId} onNewMessage={addToShellHistory} commandToExecute={commandToExecute} setCommandToExecute={setCommandToExecute} />;
      case 'chat':
        return <Chat chatId={chatId} setHistory={setChatHistory} history={chatHistory} onExecuteCommand={handleExecuteCommandInTerminal} showReasoning={showReasoning} />;
      case 'shell_history':
        return <ChatHistory history={shellHistory} chatId={chatId} onClearHistory={handleClearAllHistory} />;
      case 'analytics':
        return <AIAnalytics />;
      case 'settings':
        return <Settings showReasoning={showReasoning} setShowReasoning={setShowReasoning} />;
      case 'system':
        return <SystemInfo />;
      default:
        return <Terminal chatId={chatId} onNewMessage={addToShellHistory} commandToExecute={commandToExecute} setCommandToExecute={setCommandToExecute} />;
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <IconButton
            edge="start"
            color="inherit"
            aria-label="menu"
            sx={{ mr: 2 }}
            onClick={toggleDrawer}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Cognitive Shell
          </Typography>
        </Toolbar>
      </AppBar>
      <Sidebar
        isOpen={isDrawerOpen}
        toggleDrawer={toggleDrawer}
        setActiveTab={handleTabClick}
        handleRestartUI={handleRestartUI}
        activeTab={activeTab}
      />
      <Box 
        component="main" 
        sx={{ 
          flexGrow: 1, 
          p: activeTab === 'shell' ? 0 : { xs: 1, sm: 2, md: 3 }, 
          overflowY: 'auto',
          transition: 'margin-left 0.3s',
          marginLeft: { sm: isDrawerOpen ? '240px' : '0' }
        }}
      >
        {renderMainContent()}
      </Box>
      <Snackbar open={openSnackbar} autoHideDuration={6000} onClose={handleCloseSnackbar}>
        <Alert onClose={handleCloseSnackbar} severity={snackbarSeverity} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default Dashboard;
