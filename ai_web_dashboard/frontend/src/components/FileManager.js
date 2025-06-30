import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function FileManager() {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/files`);
      setFiles(response.data.files);
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  };

  const handleFileClick = async (filename) => {
    try {
      const response = await axios.post(`${API_URL}/api/files/read`, { filename });
      setSelectedFile(filename);
      setFileContent(response.data.content);
    } catch (error) {
      console.error('Error reading file:', error);
    }
  };

  const handleDeleteClick = async (filename) => {
    try {
      await axios.delete(`${API_URL}/api/files/delete`, { data: { filename } });
      fetchFiles();
      setSelectedFile(null);
      setFileContent('');
    } catch (error) {
      console.error('Error deleting file:', error);
    }
  };

  return (
    <div className="file-manager">
      <div className="file-list">
        <h3>Generated Files</h3>
        <ul>
          {files.map((file) => (
            <li key={file} onClick={() => handleFileClick(file)}>
              {file}
              <button onClick={(e) => { e.stopPropagation(); handleDeleteClick(file); }}>Delete</button>
            </li>
          ))}
        </ul>
      </div>
      <div className="file-content">
        {selectedFile && (
          <>
            <h4>{selectedFile}</h4>
            <pre>{fileContent}</pre>
          </>
        )}
      </div>
    </div>
  );
}

export default FileManager;
