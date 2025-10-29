import React, { useState } from 'react';
import { Box, Typography, IconButton, Collapse, Paper } from '@mui/material';
import { ExpandMore, ChevronRight } from '@mui/icons-material';

const CollapsibleSection = ({ title, children, isExpanded, onToggle }) => {
  return (
    <Paper elevation={1} sx={{ mt: 1, mb: 1, bgcolor: '#333', color: 'white' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          p: 1,
          cursor: 'pointer',
          bgcolor: '#444',
          '&:hover': {
            bgcolor: '#555',
          },
        }}
        onClick={onToggle}
      >
        <IconButton size="small" sx={{ color: 'white' }}>
          {isExpanded ? <ExpandMore /> : <ChevronRight />}
        </IconButton>
        <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>
          {title}
        </Typography>
      </Box>
      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2, borderTop: '1px solid #555' }}>
          {children}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default CollapsibleSection;
