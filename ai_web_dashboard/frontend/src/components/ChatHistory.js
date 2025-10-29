
import React from 'react';
import RenderedMessage from './RenderedMessage';
import { Box, Typography, Button, Paper } from '@mui/material';

const ChatHistory = ({ history, chatId, onClearHistory }) => {
    return (
        <Box sx={{ p: 3 }}>
            <Typography variant="h4" gutterBottom>Interaction History</Typography>
            <Button variant="contained" color="secondary" onClick={onClearHistory} sx={{ mb: 2 }}>Clear History</Button>
            <Box sx={{ maxHeight: '70vh', overflowY: 'auto' }}>
                {history.map((item, index) => (
                    <Paper
                        key={index}
                        elevation={1}
                        sx={{
                            p: { xs: 1, sm: 1.5 },
                            borderRadius: '20px',
                            maxWidth: '75%',
                            minWidth: '100px',
                            wordBreak: 'break-word',
                            overflowWrap: 'break-word',
                            background: item.role === 'user' 
                                ? 'linear-gradient(45deg, #8a3ab9, #bc2a8d, #e95950, #fccc63)' 
                                : '#e0e0e0',
                            color: item.role === 'user' ? 'white' : '#333',
                            alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start',
                            mb: 2,
                        }}
                    >
                        <RenderedMessage message={item} />
                    </Paper>
                ))}
            </Box>
        </Box>
    );
};

export default ChatHistory;
