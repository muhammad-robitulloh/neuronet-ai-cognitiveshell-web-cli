import React, { useEffect, useRef, useState } from 'react';
import { Terminal as Xterm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import './Terminal.css';
import { IconButton, Typography, Box } from '@mui/material';

// Detect if the user is on a mobile device
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

const Terminal = ({ onNewMessage, commandToExecute, setCommandToExecute }) => {
    const terminalRef = useRef(null);
    const xtermRef = useRef(null);
    const wsRef = useRef(null);
    const fitAddonRef = useRef(null); // Ref to hold the fit addon instance
    const [fontSize, setFontSize] = useState(isMobile ? 10 : 15); // Set initial font size based on device

    useEffect(() => {
        const xterm = new Xterm({
            cursorBlink: true,
            fontSize: fontSize,
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4',
            },
            allowTransparency: true,
        });

        const fitAddon = new FitAddon();
        fitAddonRef.current = fitAddon; // Store addon in ref
        const webLinksAddon = new WebLinksAddon();
        xterm.loadAddon(fitAddon);
        xterm.loadAddon(webLinksAddon);

        xterm.open(terminalRef.current);
        fitAddon.fit();

        xtermRef.current = xterm;

        const wsUrl = `ws://${window.location.hostname}:8002/ws/shell/0`;
        wsRef.current = new WebSocket(wsUrl);

        wsRef.current.onopen = () => {
            const welcomeMsg = 'Welcome to the interactive terminal!\r\n';
            xterm.write(welcomeMsg);
            if (onNewMessage) onNewMessage({ type: 'info', content: welcomeMsg.trim() });
            const initialSize = { resize: { cols: xterm.cols, rows: xterm.rows } };
            wsRef.current.send(JSON.stringify(initialSize));
        };

        wsRef.current.onmessage = (event) => {
            xterm.write(event.data);
            if (onNewMessage) onNewMessage({ type: 'output', content: event.data });
        };

        wsRef.current.onclose = () => {
            const closeMsg = '\r\nConnection closed.';
            xterm.write(closeMsg);
            if (onNewMessage) onNewMessage({ type: 'error', content: 'Connection closed.' });
        };

        const onDataHandler = xterm.onData(data => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(data);
            }
        });

        const onResizeHandler = xterm.onResize(({ cols, rows }) => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                const size = { resize: { cols, rows } };
                wsRef.current.send(JSON.stringify(size));
            }
        });

        const resizeObserver = new ResizeObserver(() => {
            fitAddon.fit();
        });
        resizeObserver.observe(terminalRef.current);

        return () => {
            onDataHandler.dispose();
            onResizeHandler.dispose();
            resizeObserver.disconnect();
            wsRef.current?.close();
            xterm.dispose();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [onNewMessage]);

    useEffect(() => {
        if (xtermRef.current) {
            xtermRef.current.options.fontSize = fontSize;
            // Use the ref to get the fit addon instance
            if (fitAddonRef.current) {
                fitAddonRef.current.fit();
            }
        }
    }, [fontSize]);

    useEffect(() => {
        if (commandToExecute && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(commandToExecute + '\r');
            if (onNewMessage) onNewMessage({ type: 'command', content: `$ ${commandToExecute}` });
            if (setCommandToExecute) setCommandToExecute(null);
        }
    }, [commandToExecute, onNewMessage, setCommandToExecute]);

    const handleZoom = (direction) => {
        setFontSize(prevSize => {
            const newSize = direction === 'in' ? prevSize + 1 : prevSize - 1;
            return Math.max(10, Math.min(40, newSize)); // Clamp font size between 10 and 40
        });
    };

    return (
        <Box className="terminal-container">
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1, bgcolor: '#333', color: 'white' }}>
                <Typography variant="subtitle1">Terminal</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <IconButton size="small" onClick={() => handleZoom('out')} sx={{ color: 'white' }}>-</IconButton>
                    <Typography variant="body2" sx={{ mx: 1 }}>{fontSize}px</Typography>
                    <IconButton size="small" onClick={() => handleZoom('in')} sx={{ color: 'white' }}>+</IconButton>
                </Box>
            </Box>
            <div id="terminal-wrapper" ref={terminalRef} className="terminal-wrapper"></div>
        </Box>
    );
};

export default Terminal;
