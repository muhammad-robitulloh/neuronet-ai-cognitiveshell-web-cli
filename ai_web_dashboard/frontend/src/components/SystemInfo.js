import React, { useState, useEffect } from 'react';
import { Box, Typography, Paper, Grid, CircularProgress } from '@mui/material';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import axios from 'axios';
import './SystemInfo.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8002';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#AF19FF', '#FF1919'];

const SystemInfo = () => {
    const [systemStats, setSystemStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchSystemStats = async () => {
        try {
            setLoading(true);
            const response = await axios.get(`${API_URL}/api/system_stats`);
            setSystemStats(response.data);
            setError(null);
        } catch (err) {
            console.error("Error fetching system stats:", err);
            if (err.response && err.response.data && err.response.data.detail) {
                setError(`Failed to fetch system statistics: ${err.response.data.detail}`);
            } else {
                setError("Failed to fetch system statistics. Please check the backend logs.");
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSystemStats();
        const interval = setInterval(fetchSystemStats, 3000); // Update every 3 seconds
        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <CircularProgress />
                <Typography variant="h6" sx={{ ml: 2 }}>Loading System Info...</Typography>
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{ p: 3, color: 'error.main' }}>
                <Typography variant="h6">Error: {error}</Typography>
            </Box>
        );
    }

    if (!systemStats) {
        return (
            <Box sx={{ p: 3 }}>
                <Typography variant="h6">No system data available.</Typography>
            </Box>
        );
    }

    const cpuData = systemStats.cpu_percent.map((percent, index) => ({
        name: `CPU Core ${index + 1}`,
        value: percent,
    }));

    const memoryData = [
        { name: 'Used', value: systemStats.memory_used },
        { name: 'Available', value: systemStats.memory_available },
    ];

    const swapData = [
        { name: 'Used', value: systemStats.swap_used },
        { name: 'Free', value: systemStats.swap_total - systemStats.swap_used },
    ];

    const formatBytes = (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    return (
        <Box className="system-info-container">
            <Typography variant="h4" gutterBottom className="system-info-title">System Overview</Typography>

            <Grid container spacing={3}>
                <Grid item xs={12} md={6} lg={4}>
                    <Paper className="system-info-card">
                        <Typography variant="h6" gutterBottom>CPU Usage</Typography>
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={cpuData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis domain={[0, 100]} />
                                <Tooltip formatter={(value) => `${value.toFixed(2)}%`} />
                                <Bar dataKey="value" fill="#8884d8" />
                            </BarChart>
                        </ResponsiveContainer>
                        <Typography variant="body1">Total Cores: {systemStats.cpu_count}</Typography>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6} lg={4}>
                    <Paper className="system-info-card">
                        <Typography variant="h6" gutterBottom>Memory Usage</Typography>
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={memoryData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {memoryData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(value) => formatBytes(value)} />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                        <Typography variant="body1">Used: {formatBytes(systemStats.memory_used)}</Typography>
                        <Typography variant="body1">Total: {formatBytes(systemStats.memory_total)}</Typography>
                        <Typography variant="body1">Percentage: {systemStats.memory_percent.toFixed(2)}%</Typography>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={6} lg={4}>
                    <Paper className="system-info-card">
                        <Typography variant="h6" gutterBottom>Swap Usage</Typography>
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={swapData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {swapData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(value) => formatBytes(value)} />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                        <Typography variant="body1">Used: {formatBytes(systemStats.swap_used)}</Typography>
                        <Typography variant="body1">Total: {formatBytes(systemStats.swap_total)}</Typography>
                        <Typography variant="body1">Percentage: {systemStats.swap_percent.toFixed(2)}%</Typography>
                    </Paper>
                </Grid>

                <Grid item xs={12}>
                    <Paper className="system-info-card">
                        <Typography variant="h6" gutterBottom>System Details</Typography>
                        <Typography variant="body1"><strong>OS:</strong> {systemStats.os_name} {systemStats.os_release} ({systemStats.machine})</Typography>
                        <Typography variant="body1"><strong>Shell:</strong> {systemStats.shell}</Typography>
                        <Typography variant="body1"><strong>Boot Time:</strong> {new Date(systemStats.boot_time * 1000).toLocaleString()}</Typography>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default SystemInfo;
