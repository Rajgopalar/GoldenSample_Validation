# 🏭 Golden Sample Revalidation Tracker

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A professional dashboard for tracking golden sample revalidations with automated email alerts and real-time monitoring.

## 📊 Overview

The Golden Sample Revalidation Tracker is a comprehensive monitoring solution designed for manufacturing and quality control environments. It helps track sample validation dates, sends automated reminders for revalidations, and provides real-time insights into sample status across your organization.

### Key Features

- **📈 Real-time Dashboard** - Interactive visualizations of sample status and urgency levels
- **📧 Automated Email Alerts** - Daily notifications for samples requiring attention
- **🔔 Critical & Urgent Alerts** - Visual indicators for overdue and urgent samples
- **📊 Data Visualization** - Donut and bar charts for status distribution analysis
- **🔍 Advanced Filtering** - Filter by status, urgency, and search by model name
- **📥 Data Export** - Export filtered data to CSV format
- **📱 Responsive Design** - Works seamlessly on desktop and tablet devices

## 🚀 Live Demo

Check out the live application: [Golden Sample Tracker](https://your-app-url.streamlit.app)

## 📸 Screenshots

### Dashboard Overview
![Dashboard Overview](screenshots/dashboard.png)

### Sample Details Table
![Sample Details](screenshots/table.png)

### Email Alert Example
![Email Alert](screenshots/email.png)

## 🛠️ Technology Stack

- **Frontend**: Streamlit
- **Data Processing**: Pandas
- **Visualization**: Plotly
- **Email**: SMTP (Gmail)
- **Date Handling**: Python datetime, dateutil
- **Deployment**: Streamlit Cloud / GitHub

## 📋 Prerequisites

- Python 3.8 or higher
- Gmail account with App Password enabled
- Google Sheets (public access for data source)

## 🔧 Installation

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/golden-sample-tracker.git
cd golden-sample-tracker
