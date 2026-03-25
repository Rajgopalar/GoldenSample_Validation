# 🏭 Golden Sample Revalidation Tracker

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A professional dashboard for tracking golden sample revalidations with automated email alerts and real-time monitoring.

## 📊 Overview

The **Golden Sample Revalidation Tracker** is a comprehensive monitoring solution designed for manufacturing and quality control environments. It helps track sample validation dates, sends automated reminders for revalidations, and provides real-time insights into sample status across your organization.

### 🎯 Use Cases
- **Manufacturing Quality Control**: Track sample revalidation cycles
- **Laboratory Management**: Monitor test sample expiration dates
- **Asset Management**: Track equipment calibration schedules
- **Compliance Tracking**: Ensure regulatory compliance for sample validation

## ✨ Key Features

### Core Functionality
- **📈 Real-time Dashboard** - Interactive visualizations with 6 key metrics
- **📧 Automated Email Alerts** - Daily notifications at 9:00 AM
- **🔔 Critical & Urgent Alerts** - Visual indicators for immediate attention
- **📊 Data Visualization** - Interactive donut and bar charts
- **🔍 Advanced Filtering** - Filter by status, urgency, and model search
- **📥 Data Export** - Export filtered data to CSV format
- **📱 Responsive Design** - Works on desktop, tablet, and mobile

### Technical Highlights
- **Smart Deduplication** - Prevents duplicate email alerts
- **Persistent State** - Maintains email history across sessions
- **Auto-Refresh** - Configurable data refresh (30-300 seconds)
- **Error Handling** - Graceful failure handling with user feedback
- **Real-time Calculations** - Automatic day calculations for revalidations

## 🚀 Live Demo

Experience the application live: [Golden Sample Tracker](https://your-app-url.streamlit.app)

*Demo credentials available upon request*

## 📸 Screenshots

### Dashboard Overview
![Dashboard Overview](screenshots/dashboard.png)
*Main dashboard showing metrics, charts, and controls*

### Sample Details Table
![Sample Details](screenshots/table.png)
*Filterable table with color-coded status indicators*

### Email Alert Example
![Email Alert](screenshots/email.png)
*Automated email notification with sample details*

## 🛠️ Technology Stack

| Category | Technology | Purpose |
|----------|------------|---------|
| **Frontend** | Streamlit 1.35.0 | Interactive web interface |
| **Data Processing** | Pandas 2.2.2 | Data manipulation and analysis |
| **Visualization** | Plotly 5.24.1 | Interactive charts and graphs |
| **Email** | SMTP + Gmail | Automated email notifications |
| **Date Handling** | Python datetime, dateutil | Date parsing and calculations |
| **Deployment** | Streamlit Cloud | Cloud hosting |

## 🚀 Quick Start

### Prerequisites
- Python 3.13
- Gmail account with App Password enabled
- Git (for cloning)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/golden-sample-tracker.git
cd golden-sample-tracker
