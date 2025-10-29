import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Box, Typography, CircularProgress, Alert, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8002';

function AIAnalytics() {
  const [tokenUsage, setTokenUsage] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTokenUsage = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/analytics/token_usage`);
        setTokenUsage(response.data.token_usage);
      } catch (err) {
        setError(err);
        console.error("Error fetching token usage:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchTokenUsage();
  }, []);

  if (loading) return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
      <CircularProgress />
      <Typography variant="h6" sx={{ ml: 2 }}>Loading analytics...</Typography>
    </Box>
  );
  if (error) return (
    <Box sx={{ p: 3 }}>
      <Alert severity="error">Error: {error.message}</Alert>
    </Box>
  );

  const chartData = {
    labels: tokenUsage.map((entry, index) => `Call ${index + 1} (${entry.model})`),
    datasets: [
      {
        label: 'Prompt Tokens',
        data: tokenUsage.map(entry => entry.prompt_tokens),
        backgroundColor: 'rgba(75, 192, 192, 0.6)',
      },
      {
        label: 'Completion Tokens',
        data: tokenUsage.map(entry => entry.completion_tokens),
        backgroundColor: 'rgba(153, 102, 255, 0.6)',
      },
      {
        label: 'Total Tokens',
        data: tokenUsage.map(entry => entry.total_tokens),
        backgroundColor: 'rgba(255, 159, 64, 0.6)',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'LLM Token Usage Over Time',
      },
    },
    scales: {
      x: {
        stacked: true,
      },
      y: {
        stacked: true,
        beginAtZero: true,
      },
    },
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>AI Response Analytics</Typography>
      {tokenUsage.length > 0 ? (
        <Paper elevation={3} sx={{ p: 2, mb: 3 }}>
          <Bar data={chartData} options={chartOptions} />
        </Paper>
      ) : (
        <Typography>No token usage data available yet. Interact with the AI to generate some!</Typography>
      )}

      <Typography variant="h5" gutterBottom sx={{ mt: 4 }}>Raw Data</Typography>
      {tokenUsage.length > 0 ? (
        <TableContainer component={Paper} elevation={3}>
          <Table sx={{ minWidth: 650 }} aria-label="token usage table">
            <TableHead>
              <TableRow>
                <TableCell>Timestamp</TableCell>
                <TableCell>Model</TableCell>
                <TableCell align="right">Prompt Tokens</TableCell>
                <TableCell align="right">Completion Tokens</TableCell>
                <TableCell align="right">Total Tokens</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tokenUsage.map((entry, index) => (
                <TableRow key={index}>
                  <TableCell component="th" scope="row">
                    {new Date(entry.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell>{entry.model}</TableCell>
                  <TableCell align="right">{entry.prompt_tokens}</TableCell>
                  <TableCell align="right">{entry.completion_tokens}</TableCell>
                  <TableCell align="right">{entry.total_tokens}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Box>
  );
}

export default AIAnalytics;
