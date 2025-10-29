
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './FileManager.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8002';

const FileList = ({ title, files, selectedFile, onFileClick, onDeleteClick }) => (
    <div className="file-category">
        <h4>{title}</h4>
        <ul>
            {files.map(file => (
                <li key={file.path} className={selectedFile === file.path ? 'selected' : ''}>
                    <span onClick={() => onFileClick(file.path)}>{file.name}</span>
                    {!file.is_system_file && (
                        <button onClick={() => onDeleteClick(file.path)} className="delete-btn">Delete</button>
                    )}
                </li>
            ))}
        </ul>
    </div>
);

const FileManager = () => {
    const [files, setFiles] = useState({ generated_files: [], uploaded_files: [], system_json_files: [] });
    const [selectedFile, setSelectedFile] = useState(null);
    const [fileContent, setFileContent] = useState('');

    const fetchFiles = async () => {
        try {
            const response = await axios.get(`${API_URL}/api/files`);
            setFiles(response.data || { generated_files: [], uploaded_files: [], system_json_files: [] });
        } catch (error) {
            console.error('Error fetching files:', error);
        }
    };

    useEffect(() => {
        fetchFiles();
    }, []);

    const handleFileClick = async (filePath) => {
        try {
            const response = await axios.post(`${API_URL}/api/files/read`, { file_path: filePath });
            setSelectedFile(filePath);
            setFileContent(response.data.content);
        } catch (error) {
            console.error('Error reading file:', error);
            alert(`Could not read file: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleDeleteClick = async (filePath) => {
        if (window.confirm(`Are you sure you want to delete ${filePath}?`)) {
            try {
                await axios.delete(`${API_URL}/api/files/delete`, { data: { file_path: filePath } });
                fetchFiles(); // Refetch files to update the list
                if (selectedFile === filePath) {
                    setSelectedFile(null);
                    setFileContent('');
                }
            } catch (error) {
                console.error('Error deleting file:', error);
                alert(`Could not delete file: ${error.response?.data?.detail || error.message}`);
            }
        }
    };

    return (
        <div className="file-manager-container">
            <div className="file-list-panel">
                <h3>File Explorer</h3>
                <button onClick={fetchFiles} className="refresh-btn">Refresh</button>
                <FileList 
                    title="System Files"
                    files={files.system_json_files}
                    selectedFile={selectedFile}
                    onFileClick={handleFileClick}
                    onDeleteClick={handleDeleteClick}
                />
                <FileList 
                    title="Generated Files"
                    files={files.generated_files}
                    selectedFile={selectedFile}
                    onFileClick={handleFileClick}
                    onDeleteClick={handleDeleteClick}
                />
                <FileList 
                    title="Uploaded Files"
                    files={files.uploaded_files}
                    selectedFile={selectedFile}
                    onFileClick={handleFileClick}
                    onDeleteClick={handleDeleteClick}
                />
            </div>
            <div className="file-content-panel">
                {selectedFile ? (
                    <pre><code>{fileContent}</code></pre>
                ) : (
                    <div className="placeholder">Select a file to view its content</div>
                )}
            </div>
        </div>
    );
};

export default FileManager;
