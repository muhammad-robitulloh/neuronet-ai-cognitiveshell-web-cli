import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    Box, Typography, TextField, Button, Switch, FormControlLabel, FormGroup,
    Checkbox, Paper, IconButton, Dialog, DialogTitle, DialogContent,
    DialogActions, List, ListItem, ListItemText, Snackbar, Alert
} from '@mui/material';
import { Delete, Visibility, Close } from '@mui/icons-material';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialDark } from 'react-syntax-highlighter/dist/esm/styles/prism';


const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8002';

const Settings = ({ showReasoning, setShowReasoning }) => {
    const [config, setConfig] = useState({});
    const [apiKey, setApiKey] = useState('');
    const [baseUrl, setBaseUrl] = useState('');
    const [statusMessage, setStatusMessage] = useState('');
    const [aiGeneratedFiles, setAiGeneratedFiles] = useState([]);
    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [systemJsonFiles, setSystemJsonFiles] = useState([]);
    const [selectedFileContent, setSelectedFileContent] = useState(null);
    const [defaultMaxTokens, setDefaultMaxTokens] = useState(1000);
    const [defaultTemperature, setDefaultTemperature] = useState(0.7);
    const [reasoningEnabled, setReasoningEnabled] = useState(false);
    const [reasoningModel, setReasoningModel] = useState('');
    const [reasoningMaxTokens, setReasoningMaxTokens] = useState(200);
    const [reasoningTemperature, setReasoningTemperature] = useState(0.7);
    const [reasoningApplyToModels, setReasoningApplyToModels] = useState([]);
    const [telegramEnabled, setTelegramEnabled] = useState(false);
    const [telegramBotToken, setTelegramBotToken] = useState('');
    const [telegramChatId, setTelegramChatId] = useState('');
    const [webSearchEnabled, setWebSearchEnabled] = useState(false);
    // eslint-disable-next-line no-unused-vars
    const [googleApiKey, setGoogleApiKey] = useState('');
    // eslint-disable-next-line no-unused-vars
    const [googleCseId, setGoogleCseId] = useState('');
    const [serperApiKey, setSerperApiKey] = useState('');
    const [openSnackbar, setOpenSnackbar] = useState(false);
    const [snackbarMessage, setSnackbarMessage] = useState('');
    const [snackbarSeverity, setSnackbarSeverity] = useState('success'); // can be 'success', 'error', 'info', 'warning'
    const [openClearHistoryDialog, setOpenClearHistoryDialog] = useState(false);
    const [openDeleteFileDialog, setOpenDeleteFileDialog] = useState(false);
    const [filePathToDelete, setFilePathToDelete] = useState(null);

    // State to track initial settings for reload detection
    const [initialSettings, setInitialSettings] = useState({});

    const allLlmModels = [
        'CODE_GEN_MODEL', 'ERROR_FIX_MODEL', 'CONVERSATION_MODEL',
        'COMMAND_CONVERSION_MODEL', 'FILENAME_GEN_MODEL', 'INTENT_DETECTION_MODEL',
    ];

    const fetchAllSettings = async () => {
        try {
            const [configRes, apiKeyRes, baseUrlRes, filesRes, telegramRes, webSearchRes] = await Promise.all([
                axios.get(`${API_URL}/api/settings/llm_config`),
                axios.get(`${API_URL}/api/settings/api_key`),
                axios.get(`${API_URL}/api/settings/llm_base_url`),
                axios.get(`${API_URL}/api/files`),
                axios.get(`${API_URL}/api/settings/telegram_bot`),
                axios.get(`${API_URL}/api/settings/web_search`)
            ]);
            
            const initialConfig = configRes.data || {};
            const processedConfig = {};

            setReasoningEnabled(initialConfig.REASONING_ENABLED || false);
            setReasoningModel(initialConfig.REASONING_MODEL || '');
            setReasoningMaxTokens(initialConfig.REASONING_MAX_TOKENS || 200);
            setReasoningTemperature(initialConfig.REASONING_TEMPERATURE || 0.7);
            setReasoningApplyToModels(initialConfig.REASONING_APPLY_TO_MODELS || []);
            setDefaultMaxTokens(initialConfig.DEFAULT_MAX_TOKENS || 1000);
            setDefaultTemperature(initialConfig.DEFAULT_TEMPERATURE || 0.7);

            for (const key in initialConfig) {
                if (!key.startsWith('REASONING_') && key !== 'DEFAULT_MAX_TOKENS' && key !== 'DEFAULT_TEMPERATURE') {
                    processedConfig[key] = initialConfig[key];
                }
            }
            setConfig(processedConfig);
            setApiKey(apiKeyRes.data.api_key || '');
            setBaseUrl(baseUrlRes.data.llm_base_url || '');
            setAiGeneratedFiles(filesRes.data.generated_files || []);
            setUploadedFiles(filesRes.data.uploaded_files || []);
            setSystemJsonFiles(filesRes.data.system_json_files || []);
            setTelegramEnabled(telegramRes.data.telegram_enabled || false);
            setTelegramBotToken(telegramRes.data.telegram_bot_token || '');
            setTelegramChatId(telegramRes.data.telegram_chat_id || '');
            setWebSearchEnabled(webSearchRes.data.web_search_enabled || false);
            setGoogleApiKey(webSearchRes.data.google_api_key || '');
            setGoogleCseId(webSearchRes.data.google_cse_id || '');
            setSerperApiKey(webSearchRes.data.serper_api_key || '');

            // Store initial state for comparison on save
            setInitialSettings({
                reasoningEnabled: initialConfig.REASONING_ENABLED || false,
                telegramEnabled: telegramRes.data.telegram_enabled || false,
                webSearchEnabled: webSearchRes.data.web_search_enabled || false,
            });

        } catch (error) {
            console.error("Failed to fetch settings:", error);
            showSnackbar(`Error: Failed to load settings. ${error.message}`, 'error');
        }
    };

    useEffect(() => {
        fetchAllSettings();
    }, []);

    const handleConfigChange = (e) => {
        const { name, value } = e.target;
        setConfig(prev => ({ ...prev, [name]: value }));
    };

    const handleReasoningApplyToModelsChange = (e) => {
        const { value, checked } = e.target;
        setReasoningApplyToModels(prev =>
            checked ? [...prev, value] : prev.filter(model => model !== value)
        );
    };

    const handleSave = async () => {
        // Detect changes that require a reload
        const needsReload = 
            initialSettings.reasoningEnabled !== reasoningEnabled ||
            initialSettings.telegramEnabled !== telegramEnabled ||
            initialSettings.webSearchEnabled !== webSearchEnabled;

        try {
            const configToSend = {
                ...config,
                REASONING_ENABLED: reasoningEnabled,
                REASONING_MODEL: reasoningModel,
                REASONING_MAX_TOKENS: reasoningMaxTokens,
                REASONING_TEMPERATURE: reasoningTemperature,
                REASONING_APPLY_TO_MODELS: reasoningApplyToModels,
                DEFAULT_MAX_TOKENS: defaultMaxTokens,
                DEFAULT_TEMPERATURE: defaultTemperature,
            };

            await Promise.all([
                axios.put(`${API_URL}/api/settings/llm_config`, configToSend),
                axios.put(`${API_URL}/api/settings/api_key`, { key: "OPENROUTER_API_KEY", value: apiKey }),
                axios.put(`${API_URL}/api/settings/llm_base_url`, { key: "LLM_BASE_URL", value: baseUrl }),
                axios.put(`${API_URL}/api/settings/telegram_bot`, {
                    telegram_enabled: telegramEnabled,
                    telegram_bot_token: telegramBotToken,
                    telegram_chat_id: telegramChatId,
                }),
                axios.put(`${API_URL}/api/settings/web_search`, {
                    web_search_enabled: webSearchEnabled,
                    serper_api_key: serperApiKey,
                }),
            ]);

            if (needsReload) {
                showSnackbar('Settings saved! The page will now reload to apply critical changes.', 'success');
                setTimeout(() => {
                    window.location.reload(true); // true forces a hard refresh from the server
                }, 2000); // Wait 2 seconds to allow user to read the message
            } else {
                showSnackbar('Settings saved successfully!', 'success');
                fetchAllSettings(); // Re-fetch to update initialSettings state
            }

        } catch (error) {
            console.error("Failed to save settings:", error);
            showSnackbar(`Error: ${error.response?.data?.detail || error.message}`, 'error');
        }
    };

    const handleConfirmClearHistory = async () => {
        setOpenClearHistoryDialog(false);
        try {
            const response = await axios.post(`${API_URL}/api/history/clear`);
            showSnackbar(response.data.message, 'success');
        } catch (error) {
            console.error("Failed to clear history:", error);
            showSnackbar(`Error: ${error.response?.data?.detail || error.message}`, 'error');
        }
    };

    const handleClearHistory = async () => {
        setOpenClearHistoryDialog(true);
    };

    const handleReadFile = async (filePath) => {
        try {
            const response = await axios.post(`${API_URL}/api/files/read`, { file_path: filePath });
            setSelectedFileContent({ filename: filePath.split('/').pop(), content: response.data.content });
        } catch (error) {
            console.error(`Failed to read file ${filePath}:`, error);
            showSnackbar(`Error reading file: ${error.response?.data?.detail || error.message}`, 'error');
        }
    };

    const handleDeleteFile = async (filePath) => {
        setFilePathToDelete(filePath);
        setOpenDeleteFileDialog(true);
    };

    const handleConfirmDeleteFile = async () => {
        setOpenDeleteFileDialog(false);
        try {
            const response = await axios.delete(`${API_URL}/api/files/delete`, { data: { file_path: filePathToDelete } });
            showSnackbar(response.data.message, 'success');
            fetchAllSettings();
        } catch (error) {
            console.error(`Failed to delete file ${filePathToDelete}:`, error);
            showSnackbar(`Error deleting file: ${error.response?.data?.detail || error.message}`, 'error');
        } finally {
            setFilePathToDelete(null);
        }
    };

    const handleCancelDeleteFile = () => {
        setOpenDeleteFileDialog(false);
        setFilePathToDelete(null);
    };

    const getHintText = (key) => {        const hints = {            OPENROUTER_API_KEY: 'Your API key for OpenRouter.ai. Required for accessing LLM models.',            LLM_BASE_URL: 'The base URL for the LLM API endpoint. Default is OpenRouter.',            CODE_GEN_MODEL: 'The LLM model used for generating code.',            ERROR_FIX_MODEL: 'The LLM model used for fixing errors in code.',            CONVERSATION_MODEL: 'The LLM model used for general conversation.',            COMMAND_CONVERSION_MODEL: 'The LLM model used for converting natural language to shell commands.',            FILENAME_GEN_MODEL: 'The LLM model used for generating filenames.',            INTENT_DETECTION_MODEL: 'The LLM model used for detecting user intent.',            REASONING_ENABLED: 'Enable or disable the AI\'s reasoning process before generating a response.',            REASONING_MODEL: 'The LLM model used specifically for generating reasoning explanations.',            REASONING_MAX_TOKENS: 'The maximum number of tokens for the reasoning model\'s output. Affects length of explanation.',            REASONING_TEMPERATURE: 'Controls the randomness of the reasoning model\'s output. Lower values are more deterministic.',            REASONING_APPLY_TO_MODELS: 'Select which AI functionalities (based on their primary model) should trigger reasoning.',            TELEGRAM_ENABLED: 'Enable or disable the Telegram bot integration.',            TELEGRAM_BOT_TOKEN: 'The API token obtained from BotFather for your Telegram bot.',            TELEGRAM_CHAT_ID: 'The specific chat ID to restrict bot interaction to. Leave empty for public access.',            WEB_SEARCH_ENABLED: 'Enable or disable online web search capabilities.',            SERPER_API_KEY: 'Your Serper.dev API Key. Required if web search is enabled.',            DEFAULT_MAX_TOKENS: 'The default maximum number of tokens for all LLM models.',            DEFAULT_TEMPERATURE: 'The default temperature for all LLM models. Higher values increase randomness.',        };        return hints[key] || 'No hint available for this setting.';    };    const handleCloseSnackbar = (event, reason) => {        if (reason === 'clickaway') {            return;        }        setOpenSnackbar(false);    };    const showSnackbar = (message, severity) => {        setSnackbarMessage(message);        setSnackbarSeverity(severity);        setOpenSnackbar(true);    };

    const getFileLanguage = (filename) => {
        const extension = filename.split('.').pop();
        switch (extension) {
            case 'js': return 'javascript';
            case 'ts': return 'typescript';
            case 'py': return 'python';
            case 'sh': return 'bash';
            case 'json': return 'json';
            case 'md': return 'markdown';
            case 'css': return 'css';
            case 'html': return 'html';
            case 'xml': return 'xml';
            case 'yaml': return 'yaml';
            case 'yml': return 'yaml';
            case 'log': return 'bash'; // Logs often contain shell commands or similar
            default: return 'text';
        }
    };

    const renderFileSection = (title, files, canDelete) => (
        <Box mb={4}>
            <Typography variant="h6" gutterBottom>{title}</Typography>
            <Paper elevation={2} sx={{ p: 2 }}>
                {files.length === 0 ? (
                    <Typography>No files found.</Typography>
                ) : (
                    <List dense>
                        {files.map(file => (
                            <ListItem key={file.path} secondaryAction={
                                <Box>
                                    <IconButton edge="end" aria-label="read" onClick={() => handleReadFile(file.path)}>
                                        <Visibility />
                                    </IconButton>
                                    {canDelete && (
                                        <IconButton edge="end" aria-label="delete" onClick={() => handleDeleteFile(file.path)}>
                                            <Delete />
                                        </IconButton>
                                    )}
                                </Box>
                            }>
                                <ListItemText primary={file.name} />
                            </ListItem>
                        ))}
                    </List>
                )}
            </Paper>
        </Box>
    );

    return (
        <Box p={3}>
            <Typography variant="h4" gutterBottom>Application Settings</Typography>
            {statusMessage && <Typography color={statusMessage.startsWith('Error') ? 'error' : 'success'}>{statusMessage}</Typography>}

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>Display Settings</Typography>
                <FormControlLabel
                    control={<Switch checked={showReasoning} onChange={(e) => setShowReasoning(e.target.checked)} />}
                    label="Show AI Reasoning"
                />
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>API & Base URL</Typography>
                <TextField label="OpenRouter API Key" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} fullWidth margin="normal" helperText={getHintText('OPENROUTER_API_KEY')} />
                <TextField label="LLM Base URL" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} fullWidth margin="normal" helperText={getHintText('LLM_BASE_URL')} />
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>Global LLM Settings</Typography>
                <TextField label="Default Max Tokens" type="number" value={defaultMaxTokens} onChange={(e) => setDefaultMaxTokens(parseInt(e.target.value))} fullWidth margin="normal" helperText={getHintText('DEFAULT_MAX_TOKENS')} />
                <TextField label="Default Temperature" type="number" value={defaultTemperature} onChange={(e) => setDefaultTemperature(parseFloat(e.target.value))} fullWidth margin="normal" inputProps={{ step: 0.1 }} helperText={getHintText('DEFAULT_TEMPERATURE')} />
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>LLM Model Configuration</Typography>
                {Object.entries(config).map(([key, value]) => (
                    <TextField key={key} label={key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} name={key} value={value} onChange={handleConfigChange} fullWidth margin="normal" helperText={getHintText(key)} />
                ))}
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>Reasoning Settings</Typography>
                <FormControlLabel control={<Switch checked={reasoningEnabled} onChange={(e) => setReasoningEnabled(e.target.checked)} />} label="Enable Reasoning" />
                {reasoningEnabled && (
                    <Box pl={2}>
                        <TextField label="Reasoning Model" value={reasoningModel} onChange={(e) => setReasoningModel(e.target.value)} fullWidth margin="normal" helperText={getHintText('REASONING_MODEL')} />
                        <TextField label="Reasoning Max Tokens" type="number" value={reasoningMaxTokens} onChange={(e) => setReasoningMaxTokens(parseInt(e.target.value))} fullWidth margin="normal" helperText={getHintText('REASONING_MAX_TOKENS')} />
                        <TextField label="Reasoning Temperature" type="number" value={reasoningTemperature} onChange={(e) => setReasoningTemperature(parseFloat(e.target.value))} fullWidth margin="normal" inputProps={{ step: 0.1 }} helperText={getHintText('REASONING_TEMPERATURE')} />
                        <Typography>Apply Reasoning to Models</Typography>
                        <FormGroup>
                            {allLlmModels.map(modelKey => (
                                <FormControlLabel key={modelKey} control={<Checkbox value={modelKey} checked={reasoningApplyToModels.includes(modelKey)} onChange={handleReasoningApplyToModelsChange} />} label={modelKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} />
                            ))}
                        </FormGroup>
                    </Box>
                )}
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>Telegram Bot Settings</Typography>
                <FormControlLabel control={<Switch checked={telegramEnabled} onChange={(e) => setTelegramEnabled(e.target.checked)} />} label="Enable Telegram Bot" />
                {telegramEnabled && (
                    <Box pl={2}>
                        <TextField label="Telegram Bot Token" type="password" value={telegramBotToken} onChange={(e) => setTelegramBotToken(e.target.value)} fullWidth margin="normal" helperText={getHintText('TELEGRAM_BOT_TOKEN')} />
                        <TextField label="Telegram Chat ID (Optional)" value={telegramChatId} onChange={(e) => setTelegramChatId(e.target.value)} fullWidth margin="normal" helperText={getHintText('TELEGRAM_CHAT_ID')} />
                    </Box>
                )}
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>Web Search Settings</Typography>
                <FormControlLabel control={<Switch checked={webSearchEnabled} onChange={(e) => setWebSearchEnabled(e.target.checked)} />} label="Enable Web Search" />
                {webSearchEnabled && (
                    <Box pl={2}>
                        <TextField label="Serper.dev API Key" type="password" value={serperApiKey} onChange={(e) => setSerperApiKey(e.target.value)} fullWidth margin="normal" helperText={getHintText('SERPER_API_KEY')} />
                    </Box>
                )}
            </Paper>

            <Button variant="contained" color="primary" onClick={handleSave} sx={{ mb: 3 }}>Save All Settings</Button>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>Chat History Management</Typography>
                <Typography paragraph>Clear all your past chat conversations and shell command history. This action is irreversible.</Typography>
                <Button variant="contained" color="secondary" onClick={handleClearHistory}>Clear All Chat History</Button>
            </Paper>

            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>File Manager</Typography>
                {renderFileSection("AI Generated Files", aiGeneratedFiles, true)}
                {renderFileSection("Uploaded Files", uploadedFiles, true)}
                {renderFileSection("System Files (Internal)", systemJsonFiles, false)}
            </Paper>

            <Dialog open={!!selectedFileContent} onClose={() => setSelectedFileContent(null)} fullWidth maxWidth="md">
                <DialogTitle>{selectedFileContent?.filename}</DialogTitle>
                <DialogContent>
                    <SyntaxHighlighter 
                        style={materialDark} 
                        language={getFileLanguage(selectedFileContent?.filename || '')} 
                        showLineNumbers
                    >
                        {selectedFileContent?.content}
                    </SyntaxHighlighter>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSelectedFileContent(null)}>Close</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={openClearHistoryDialog} onClose={() => setOpenClearHistoryDialog(false)}>
                <DialogTitle>Confirm Clear History</DialogTitle>
                <DialogContent>
                    <Typography>Are you sure you want to clear all chat history? This action cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenClearHistoryDialog(false)}>Cancel</Button>
                    <Button onClick={handleConfirmClearHistory} color="secondary">Clear History</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={openDeleteFileDialog} onClose={handleCancelDeleteFile}>
                <DialogTitle>Confirm Delete File</DialogTitle>
                <DialogContent>
                    <Typography>Are you sure you want to delete {filePathToDelete?.split('/').pop()}? This action cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCancelDeleteFile}>Cancel</Button>
                    <Button onClick={handleConfirmDeleteFile} color="secondary">Delete File</Button>
                </DialogActions>
            </Dialog>

            <Snackbar open={openSnackbar} autoHideDuration={6000} onClose={handleCloseSnackbar}>
                <Alert onClose={handleCloseSnackbar} severity={snackbarSeverity} sx={{ width: '100%' }}>
                    {snackbarMessage}
                </Alert>
            </Snackbar>
        </Box>
    );
};

export default Settings;
