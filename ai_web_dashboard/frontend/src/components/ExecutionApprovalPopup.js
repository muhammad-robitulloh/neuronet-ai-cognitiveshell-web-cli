import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, Box } from '@mui/material';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const ExecutionApprovalPopup = ({ request, onConfirm, onCancel }) => {
  if (!request) return null;

  return (
    <Dialog open={true} onClose={onCancel} fullWidth maxWidth="md">
      <DialogTitle>Command Execution Approval</DialogTitle>
      <DialogContent>
        <Typography gutterBottom>
          The AI proposes to run the following command. Please review it carefully before proceeding.
        </Typography>
        <Box sx={{ my: 2 }}>
          <SyntaxHighlighter language="bash" style={materialDark}>
            {request.command}
          </SyntaxHighlighter>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Warning: Executing commands can modify your files and system state. Only approve commands if you understand what they do and trust the source.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} color="secondary">
          Cancel
        </Button>
        <Button onClick={() => onConfirm(request.command)} variant="contained" color="primary">
          Execute Command
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ExecutionApprovalPopup;
