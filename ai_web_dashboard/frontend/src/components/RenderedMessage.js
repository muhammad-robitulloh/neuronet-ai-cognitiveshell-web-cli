import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import a11yLight from 'react-syntax-highlighter/dist/esm/styles/prism/a11y-light';
import CollapsibleOutput from './CollapsibleOutput';
import './ModelThoughtProcess.css';
import { Box, Typography } from '@mui/material';

const RenderedMessage = ({ message, showReasoning }) => {
  // Destructure from message object. It can have 'content' (for user) or 'chunks' (for AI)
  const { role, content, chunks, isReasoningExpanded, hadReasoning } = message;
  const isUser = role === 'user';

  // Component for rendering code blocks with syntax highlighting
  const CodeBlock = ({ node, inline, className, children, ...props }) => {
    const match = /language-(\w+)/.exec(className || '');
    return !inline && match ? (
      <SyntaxHighlighter style={a11yDark} language={match[1]} PreTag="div" {...props}>
        {String(children).replace(/\\n$/, '')}
      </SyntaxHighlighter>
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  };

  // --- Render User Message ---
  if (isUser) {
    return <ReactMarkdown components={{ code: CodeBlock }}>{content}</ReactMarkdown>;
  }

  // --- Render AI Message ---
  if (!chunks || chunks.length === 0) {
    return null; // Don't render anything if there are no chunks yet
  }

  // Separate reasoning chunks from the main content chunks
  const reasoningContent = chunks
    .filter(c => c.type === 'reasoning_chunk' || c.type === 'thought_process_chunk')
    .map(c => c.content)
    .join('');
    
  const mainContentChunks = chunks.filter(c => c.type !== 'reasoning_chunk' && c.type !== 'thought_process_chunk');
  
  const hasReasoning = reasoningContent.length > 0;

  return (
    <Box className="message ai-message">
      {/* Render the collapsible reasoning section if enabled globally and if reasoning exists */}
      {hasReasoning && (
        <CollapsibleOutput title="Show Reasoning" isInitiallyCollapsed={!showReasoning}>
          <div className="thought-process">
            <ReactMarkdown components={{ code: CodeBlock }}>
              {reasoningContent}
            </ReactMarkdown>
          </div>
        </CollapsibleOutput>
      )}
      
      {/* Render the main content chunks */}
      {mainContentChunks.map((chunk, index) => {
        const key = `${message.id}-chunk-${index}`;

        switch (chunk.type) {
          case 'generated_code':            return (              <Box key={key} sx={{ my: 2 }}>                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5 }}>Generated Code ({chunk.content.filename}):</Typography>                <SyntaxHighlighter style={a11yLight} language={chunk.content.language || 'text'} PreTag="div">                  {String(chunk.content.code || '').replace(/\\n$/, '')}                </SyntaxHighlighter>              </Box>            );          case 'command':            return (              <Box key={key} sx={{ my: 2 }}>                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5 }}>Command:</Typography>                <SyntaxHighlighter style={a11yLight} language="bash" PreTag="div">                  {String(chunk.content).replace(/\\n$/, '')}                </SyntaxHighlighter>              </Box>            );          case 'shell_output':            return (              <Box key={key} sx={{ my: 2 }}>                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5 }}>Shell Output:</Typography>                <SyntaxHighlighter style={a11yLight} language="bash" PreTag="div">                  {String(chunk.content).replace(/\\n$/, '')}                </SyntaxHighlighter>              </Box>            );          case 'shell_error':            return (              <Box key={key} sx={{ my: 2 }}>                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5, color: 'error.main' }}>Shell Error:</Typography>                <SyntaxHighlighter style={a11yLight} language="bash" PreTag="div">                  {String(chunk.content).replace(/\\n$/, '')}                </SyntaxHighlighter>              </Box>            );                      case 'conversation_chunk':          case 'agent_analysis_chunk':          default:            return (              <Box key={key} sx={{ my: 1 }}>                <ReactMarkdown components={{ code: CodeBlock }}>                  {chunk.content}                </ReactMarkdown>              </Box>            );
        }
      })}
    </Box>
  );
};

export default RenderedMessage;
