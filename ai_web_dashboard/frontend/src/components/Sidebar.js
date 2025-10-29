import React from 'react';
import { Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Divider, useMediaQuery, useTheme, Box } from '@mui/material';
import { Terminal as TerminalIcon, Chat as ChatIcon, History, Analytics, Settings as SettingsIcon, RestartAlt, Computer as ComputerIcon } from '@mui/icons-material';

const Sidebar = ({ isOpen, toggleDrawer, setActiveTab, handleRestartUI, activeTab }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const menuItems = [
    { text: 'Shell', icon: <TerminalIcon />, tab: 'shell' },
    { text: 'Chat', icon: <ChatIcon />, tab: 'chat' },
    { text: 'Shell History', icon: <History />, tab: 'shell_history' },
    { text: 'Analytics', icon: <Analytics />, tab: 'analytics' },
    { text: 'Settings', icon: <SettingsIcon />, tab: 'settings' },
    { text: 'System', icon: <ComputerIcon />, tab: 'system' },
  ];

  const drawerContent = (
    <Box sx={{ width: 240 }}>
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton onClick={() => setActiveTab(item.tab)} selected={activeTab === item.tab}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Divider />
      <List>
        <ListItem disablePadding>
          <ListItemButton onClick={handleRestartUI}>
            <ListItemIcon><RestartAlt /></ListItemIcon>
            <ListItemText primary="Restart UI" />
          </ListItemButton>
        </ListItem>
      </List>
    </Box>
  );

  return (
    <Drawer
      anchor="left"
      open={isOpen}
      onClose={toggleDrawer}
      variant={isMobile ? 'temporary' : 'persistent'}
      sx={{
        width: 240,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: 240,
          boxSizing: 'border-box',
        },
      }}
    >
      {drawerContent}
    </Drawer>
  );
};

export default Sidebar;
