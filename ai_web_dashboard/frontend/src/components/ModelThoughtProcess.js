import React from 'react';
import { Paper, Typography, Box, CircularProgress, IconButton } from '@mui/material';
import { ExpandMore, ChevronRight } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ErrorBoundary from './ErrorBoundary'; // Import the ErrorBoundary

const ModelThoughtProcess = ({ reasoning, reasoningEnabled, isStreaming, isExpanded }) => {

    if (!reasoningEnabled || !reasoning) {
        return null;
    }

    return (
        <Paper elevation={1} sx={{ p: 2, mt: 1, bgcolor: '#424242', borderLeft: '4px solid #1976d2' }}>
            <Box 
                sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }} 
            >
                <IconButton size="small">{isExpanded ? <ExpandMore /> : <ChevronRight />}</IconButton>
                <Typography variant="h6" sx={{ mr: 1, color: 'white' }}>Model's Thought Process</Typography>
                {isStreaming && <CircularProgress size={20} />}
            </Box>
            {isExpanded && (
                <Typography component="div" sx={{ whiteSpace: 'pre-wrap', pl: 4, mt: 1 }}>
                    <ErrorBoundary fallback={<p>Error rendering thought process.</p>}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {reasoning}
                        </ReactMarkdown>
                    </ErrorBoundary>
                </Typography>
            )}
        </Paper>
    );
};

export default ModelThoughtProcess;
