import React, { useState, useEffect, useRef, useCallback } from 'react';
import AutoDebugPopup from './AutoDebugPopup';
import ExecutionApprovalPopup from './ExecutionApprovalPopup';
import RenderedMessage from './RenderedMessage';
import { Box, TextField, IconButton, List, ListItem, Paper, Typography, CircularProgress } from '@mui/material';
import { AttachFile, Send, Cancel } from '@mui/icons-material';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8002';

function Chat({ chatId, setHistory, history, onExecuteCommand, showReasoning }) {
  const [message, setMessage] = useState('');
  const [processingState, setProcessingState] = useState(null);
  const [debugRequest, setDebugRequest] = useState(null);
  const [approvalRequest, setApprovalRequest] = useState(null);
  const [attachedFile, setAttachedFile] = useState(null);
  const messagesEndRef = useRef(null);
  const controllerRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [history, scrollToBottom]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setAttachedFile(file);
    }
  };

  const handleRemoveFile = () => {
    setAttachedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const streamAndProcessResponses = async (url, body, currentMessageId) => {
    const controller = new AbortController();
    controllerRef.current = controller;

    let reader;
    let decoder;
    let buffer = '';

    const handleAgentRequestApproval = (chunk) => {
      setApprovalRequest(chunk.content);
      setProcessingState('Awaiting user approval for execution...');
    };

    const handleAutoDebugRequest = (chunk) => {
      setDebugRequest(chunk.content);
      setProcessingState('Awaiting user confirmation for auto-debug...');
    };

    const handleDoneChunk = () => {
      setHistory(prev => prev.map(msg => msg.id === currentMessageId ? { ...msg, isStreaming: false } : msg));
      setProcessingState(null);
      handleRemoveFile();
    };

    const handleStatusChunk = (chunk) => {
      setProcessingState(chunk.content);
    };

    const handleMessageChunk = (chunk, currentMessageId) => {
        setHistory(prevHistory => {
            return prevHistory.map(msg => {
                if (msg.id === currentMessageId) {
                    const newMsg = { ...msg, chunks: [...(msg.chunks || [])] };

                    // Correct placement: Update hadReasoning after newMsg is created
                    if (chunk.type === 'reasoning_chunk' || chunk.type === 'thought_process_chunk') {
                        newMsg.hadReasoning = true;
                    }

                    const lastChunk = newMsg.chunks.length > 0 ? newMsg.chunks[newMsg.chunks.length - 1] : null;

                    // Updated list of chunk types that can be combined
                    const COMBINABLE_CHUNK_TYPES = ['conversation_chunk', 'reasoning_chunk', 'agent_analysis_chunk', 'thought_process_chunk'];

                    if (COMBINABLE_CHUNK_TYPES.includes(chunk.type) &&
                        lastChunk && lastChunk.type === chunk.type &&
                        typeof lastChunk.content === 'string' && typeof chunk.content === 'string') {
                        
                        const updatedChunk = { ...lastChunk, content: lastChunk.content + chunk.content };
                        newMsg.chunks[newMsg.chunks.length - 1] = updatedChunk;
                    } else {
                        newMsg.chunks.push({
                            type: chunk.type,
                            content: chunk.content,
                            format: chunk.format || 'markdown',
                        });
                    }
                    return newMsg;
                }
                return msg;
            });
        });
    };

    const processBuffer = (currentMessageId) => {
        let newlineIndex;
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
          const line = buffer.substring(0, newlineIndex).trim();
          buffer = buffer.substring(newlineIndex + 1);

          if (line) {
            try {
              const chunk = JSON.parse(line);
              
              if (chunk.type === 'agent_request_approval') {
                handleAgentRequestApproval(chunk);
              } else if (chunk.type === 'auto_debug_request') {
                handleAutoDebugRequest(chunk);
              } else if (chunk.type === 'done') {
                handleDoneChunk();
              } else if (chunk.type === 'status') {
                handleStatusChunk(chunk);
              } else {
                handleMessageChunk(chunk, currentMessageId);
              }
            } catch (e) {
              console.error('Error parsing JSON chunk:', e, line);
            }
          }
        }
      };

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Network response was not ok');
      }

      reader = response.body.getReader();
      decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
            if(buffer.length > 0) processBuffer(currentMessageId);
            setHistory(prev => prev.map(msg => msg.id === currentMessageId ? { ...msg, isStreaming: false } : msg));
            setProcessingState(null);
            handleRemoveFile();
            break;
        }
        buffer += decoder.decode(value, { stream: true });
        processBuffer(currentMessageId);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        setHistory(prev => [...prev, { role: 'error', chunks: [{ type: 'error', content: `Operation canceled.`, format: 'error' }], id: Date.now() }]);
      } else {
        setHistory(prev => [...prev, { role: 'error', chunks: [{ type: 'error', content: `Error: ${error.message}`, format: 'error' }], id: Date.now() }]);
      }
      setProcessingState(null);
      handleRemoveFile();
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!message.trim() && !attachedFile) return;

    const userMessage = { role: 'user', content: message, id: Date.now() };
    const currentMessageId = Date.now() + 1; // Ensure unique ID
    const aiMessage = { role: 'ai', chunks: [], id: currentMessageId, isStreaming: true, isReasoningExpanded: false, hadReasoning: false };

    // Combine state updates for instant user message feedback
    setHistory(prev => {
        console.log("Chat.js: handleSendMessage - User message added to history:", userMessage);
        return [...prev, userMessage, aiMessage];
    });
    setMessage('');
    setProcessingState('AI is thinking...');

    let attachedFilePath = null;
    if (attachedFile) {
        setProcessingState('Uploading file...');
        const formData = new FormData();
        formData.append('file', attachedFile);

        try {
            const uploadResponse = await fetch(`${API_URL}/api/files/upload`, {
                method: 'POST',
                body: formData,
            });

            if (!uploadResponse.ok) {
                const errorData = await uploadResponse.json();
                throw new Error(errorData.detail || 'File upload failed');
            }

            const uploadResult = await uploadResponse.json();
            attachedFilePath = uploadResult.path;
            setProcessingState('File uploaded. AI is thinking...');

        } catch (error) {
            setHistory(prev => [...prev, { role: 'error', chunks: [{ type: 'error', content: `Error: ${error.message}`, format: 'error' }], id: Date.now() }]);
            setProcessingState(null);
            handleRemoveFile();
            return; // Stop if upload fails
        }
    }

    await streamAndProcessResponses(`${API_URL}/api/chat`, {
        chat_id: chatId,
        message: userMessage.content,
        attached_file_path: attachedFilePath
    }, currentMessageId);
  };

  const handleApprovalConfirm = async (command) => {
    setApprovalRequest(null);
    setHistory(prev => [...prev, { role: 'ai', chunks: [{type: 'message_chunk',                 content: `> Approved execution: ${command}`}], id: Date.now() }]);
    setProcessingState('Executing command...');
    const currentMessageId = Date.now();
    const aiMessage = { role: 'ai', chunks: [], id: currentMessageId, isStreaming: true, isReasoningExpanded: false };
    setHistory(prev => [...prev, aiMessage]);
    await streamAndProcessResponses(`${API_URL}/api/agent/execute`, { 
        chat_id: chatId, 
        command: command 
    }, currentMessageId);
  };

  const handleApprovalCancel = () => {
    setApprovalRequest(null);
    setHistory(prev => [...prev, { role: 'ai', chunks: [{type: 'message_chunk', content: 'Command execution canceled by user.'}], id: Date.now() }]);
    setProcessingState(null);
  };

  const handleDebugConfirm = async (requestId) => {
    console.log("Auto-debug confirmed for", requestId);
    setDebugRequest(null);
    setProcessingState(null);
  };

  const handleDebugCancel = () => {
    setDebugRequest(null);
    setHistory(prev => [...prev, { role: 'ai', chunks: [{ type: 'message_chunk', content: 'Auto-debug canceled by user.', format: 'markdown' }], id: Date.now() }]);
    setProcessingState(null);
  };

  const handleCancel = () => {
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
  };

  const toggleReasoning = (id) => {
    setHistory(prev => prev.map(msg => msg.id === id ? { ...msg, isReasoningExpanded: !msg.isReasoningExpanded } : msg));
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      <List sx={{ flexGrow: 1, overflowY: 'auto', p: { xs: 1, sm: 2 } }}>
        {history.map((msg) => (
          <ListItem key={msg.id} sx={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <Paper
              elevation={1}
              sx={{
                p: { xs: 1, sm: 1.5 },
                borderRadius: '20px',
                maxWidth: '75%',
                minWidth: '100px',
                wordBreak: 'break-word',
                overflowWrap: 'break-word',
                background: msg.role === 'user' 
                  ? 'linear-gradient(45deg, #8a3ab9, #bc2a8d, #e95950, #fccc63)' 
                  : '#e0e0e0',
                color: msg.role === 'user' ? 'white' : '#333',
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                cursor: msg.role === 'ai' ? 'pointer' : 'default',
              }}
              onClick={() => msg.role === 'ai' && toggleReasoning(msg.id)}
            >
              <RenderedMessage message={msg} showReasoning={showReasoning} />
            </Paper>
          </ListItem>
        ))}
        {processingState && (
          <ListItem sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', width: '100%' }}>
            <Paper elevation={3} sx={{ p: 2, bgcolor: 'background.paper', color: 'text.primary', width: '100%', my: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    <Typography component="span" sx={{ fontStyle: 'italic' }}>{processingState}</Typography>
                </Box>
            </Paper>
          </ListItem>
        )}
        {approvalRequest && (
            <ExecutionApprovalPopup 
                request={approvalRequest} 
                onConfirm={handleApprovalConfirm} 
                onCancel={handleApprovalCancel} 
            />
        )}
        {debugRequest && (
          <AutoDebugPopup
            request={debugRequest}
            onConfirm={handleDebugConfirm}
            onCancel={handleDebugCancel}
          />
        )}
        <div ref={messagesEndRef} />
      </List>
      <Box component="form" onSubmit={handleSendMessage} sx={{ p: 2, display: 'flex', alignItems: 'center' }}>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          disabled={!!processingState || !!debugRequest || !!approvalRequest}
          style={{ display: 'none' }}
        />
        <IconButton onClick={() => fileInputRef.current.click()} disabled={!!processingState || !!debugRequest || !!approvalRequest}>
          <AttachFile />
        </IconButton>
        {attachedFile && (
          <Box sx={{ display: 'flex', alignItems: 'center', mr: 1 }}>
            <Typography variant="body2">{attachedFile.name}</Typography>
            <IconButton onClick={handleRemoveFile} size="small">X</IconButton>
          </Box>
        )}
        <TextField
          fullWidth
          multiline
          minRows={1}
          maxRows={5}
          variant="outlined"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type your message..."
          disabled={!!processingState || !!debugRequest || !!approvalRequest}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              setMessage(prev => prev + '\n');
            }
          }}
        />
        {processingState ? (
          <IconButton onClick={handleCancel} color="secondary" sx={{ ml: 1 }}>
            <Cancel />
          </IconButton>
        ) : (
          <IconButton type="submit" color="primary" disabled={!!debugRequest || !!approvalRequest || (!message.trim() && !attachedFile)} sx={{ ml: 1 }}>
            <Send />
          </IconButton>
        )}
      </Box>
    </Box>
  );
}

export default Chat;
