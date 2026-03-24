import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import plotly.graph_objects as go
import warnings
import time
warnings.filterwarnings('ignore')

# ========== CONFIGURATION ==========
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSG42OXWxsoLV7wNqqDAdryfmDYU4IGBv1gEJm8-8bP_qh6vCe2NWAx7_vM3DYQqxCPFX3jv-TimRgV/pub?output=csv"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SENDER_EMAIL = "rajgopalr.padget@dixoninfo.com"
SENDER_PASSWORD = "gzxzuolbmqkdhcst"  # App Password

# Email recipients configuration
PRIMARY_RECIPIENT = "emurugesan.padget@dixoninfo.com"  # Main recipient (To field)
CC_RECIPIENTS = [
    "chauhandeesingh@gmail.com",
    "rajgopal.padget@dixoninfo.com",
]

# Auto email settings
AUTO_EMAIL_HOUR = 12  # Set to 12 PM
AUTO_EMAIL_MINUTE = 46  # Set to 26 minutes
AUTO_EMAIL_ENABLED = True

# ===================================

# Page configuration
st.set_page_config(
    page_title="Golden Sample Revalidation Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72, #2a5298);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .status-ok { background-color: #d4edda; color: #155724; }
    .status-pending { background-color: #fff3cd; color: #856404; }
    .status-ng { background-color: #f8d7da; color: #721c24; }
    .urgent-alert {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .auto-email-status {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_auto_email_date' not in st.session_state:
    st.session_state.last_auto_email_date = None
if 'auto_email_sent_today' not in st.session_state:
    st.session_state.auto_email_sent_today = False
if 'primary_recipient' not in st.session_state:
    st.session_state.primary_recipient = PRIMARY_RECIPIENT
if 'cc_recipients' not in st.session_state:
    st.session_state.cc_recipients = CC_RECIPIENTS.copy()
if 'auto_email_log' not in st.session_state:
    st.session_state.auto_email_log = []

def parse_date_safe(date_str):
    """Safely parse date from various formats"""
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    
    try:
        date_str = str(date_str).strip()
        
        # Handle different separators
        separators = ['-', '/', '.']
        for sep in separators:
            if sep in date_str:
                parts = date_str.split(sep)
                if len(parts) == 3:
                    day, month, year = parts
                    if day.isdigit() and month.isdigit() and year.isdigit():
                        if len(year) == 2:
                            year = '20' + year
                        return datetime(int(year), int(month), int(day))
        
        return pd.to_datetime(date_str, dayfirst=True, errors='coerce')
        
    except Exception as e:
        return None

@st.cache_data(ttl=300)
def fetch_data():
    """Fetch data from Google Sheets"""
    try:
        df = pd.read_csv(CSV_URL)
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

def process_data(df):
    """Process and enrich the dataframe"""
    if df is None:
        return None

    df = df.copy()
    df.columns = df.columns.str.strip()
    
    required_columns = ['Validation Date', 'Staus', 'Model']
    for col in required_columns:
        if col not in df.columns:
            st.error(f"Missing required column: '{col}'")
            st.write("Available columns:", df.columns.tolist())
            return None
    
    df['Validation Date Parsed'] = df['Validation Date'].apply(parse_date_safe)
    initial_count = len(df)
    df = df.dropna(subset=['Validation Date Parsed'])
    
    if len(df) < initial_count and initial_count > 0:
        st.warning(f"⚠️ Dropped {initial_count - len(df)} rows with invalid date format")
    
    if df.empty:
        st.error("No valid dates found. Please check date format (should be DD-MM-YYYY)")
        return None
    
    validation_dates = pd.Series(df['Validation Date Parsed'])
    revalidation_dates = validation_dates + pd.Timedelta(days=10)
    
    today = datetime.now().date()
    days_left_list = []
    for reval_date in revalidation_dates:
        if pd.notna(reval_date):
            days_diff = (reval_date.date() - today).days
            days_left_list.append(days_diff)
        else:
            days_left_list.append(None)
    
    df['Days Left'] = days_left_list
    df['Validation Date'] = validation_dates
    df['Revalidation Due'] = revalidation_dates
    df['Validation Date Display'] = validation_dates.dt.strftime('%d-%m-%Y')
    df['Revalidation Due Display'] = revalidation_dates.dt.strftime('%d-%m-%Y')
    
    def get_alert_status(row):
        days_left = row['Days Left']
        status = str(row.get('Staus', '')).lower()
        
        if pd.isna(days_left):
            return '⚪ Unknown'
        if status == 'ok':
            return '✅ Completed'
        elif days_left < 0:
            return '🔴 OVERDUE'
        elif days_left <= 3:
            return '🔴 URGENT (≤3 days)'
        elif days_left <= 7:
            return '🟡 Due Soon (4-7 days)'
        else:
            return '🟢 On Track (>7 days)'
    
    df['Alert Status'] = df.apply(get_alert_status, axis=1)
    
    return df

def get_due_records(df):
    """Get records that need reminders (within 3 days of revalidation)"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    mask = (df['Days Left'] <= 3) & (df['Days Left'] >= 0) & (df['Staus'].str.lower() != 'ok')
    return df[mask]

def get_overdue_records(df):
    """Get overdue records"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    mask = (df['Days Left'] < 0) & (df['Staus'].str.lower() != 'ok')
    return df[mask]

def send_single_email_alert(df, primary_recipient, cc_recipients, alert_type="manual"):
    """Send a single email with primary in TO and others in CC"""
    due_records = get_due_records(df)
    overdue_records = get_overdue_records(df)
    
    if due_records.empty and overdue_records.empty:
        return False, "No records requiring immediate attention"
    
    cc_list = [email for email in cc_recipients if email and email.strip()]
    
    try:
        email_body = generate_email_html(df, due_records, overdue_records, alert_type)
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = primary_recipient
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)
        
        total_urgent = len(due_records) + len(overdue_records)
        msg['Subject'] = f"🚨 GOLDEN SAMPLE ALERT: {total_urgent} {'Samples' if total_urgent > 1 else 'Sample'} Need Immediate Attention"
        
        msg.attach(MIMEText(email_body, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        return True, f"Alert sent to {primary_recipient} (To) and {len(cc_list)} CC recipient(s)"
    
    except Exception as e:
        return False, f"Email failed: {e}"

def generate_email_html(df, due_records, overdue_records, alert_type="manual"):
    """Generate HTML for email body"""
    
    due_rows = ""
    if not due_records.empty:
        for _, row in due_records.iterrows():
            days_left = row.get('Days Left', 0)
            due_rows += f"""
            <tr style="background-color:#fff3cd;">
                <td><b>{row.get('Model', '')}</b></td>
                <td>{row.get('Validation Date Display', '')}</td>
                <td>{row.get('Revalidation Due Display', '')}</td>
                <td style="color:#dc3545; font-weight:bold;">{days_left} days</td>
                <td><b>{row.get('Staus', '')}</b></td>
                <td>{row.get('Incharge', '')}</td>
                <td style="color:#dc3545;">⚠️ URGENT</td>
              </tr>
            """
    
    overdue_rows = ""
    if not overdue_records.empty:
        for _, row in overdue_records.iterrows():
            days_left = row.get('Days Left', 0)
            overdue_rows += f"""
            <tr style="background-color:#f8d7da;">
                <td><b>{row.get('Model', '')}</b></td>
                <td>{row.get('Validation Date Display', '')}</td>
                <td>{row.get('Revalidation Due Display', '')}</td>
                <td style="color:#dc3545; font-weight:bold;">{abs(days_left)} days overdue</td>
                <td><b>{row.get('Staus', '')}</b></td>
                <td>{row.get('Incharge', '')}</td>
                <td style="color:#dc3545;">🔴 OVERDUE</td>
              </tr>
            """
    
    total_urgent = len(due_records) + len(overdue_records)
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .header {{ background: linear-gradient(90deg, #1e3c72, #2a5298); color: white; padding: 20px; text-align: center; }}
            .alert {{ background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th {{ background-color: #2a5298; color: white; padding: 12px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            .footer {{ margin-top: 30px; padding: 20px; background-color: #f8f9fa; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>Golden Sample Revalidation Tracker</h2>
            <p>🚨 URGENT ALERT: Action Required Immediately</p>
        </div>
        
        <div class="alert">
            <strong>⚠️ CRITICAL ALERT:</strong> {total_urgent} sample(s) require immediate attention!
            <br>• {len(overdue_records)} sample(s) are OVERDUE
            <br>• {len(due_records)} sample(s) are due within 3 days
            <br><br>Please take necessary action immediately.
        </div>
        
        <h3>🔴 OVERDUE SAMPLES:</h3>
        <table>
            <thead>
                <tr><th>Model</th><th>Validation Date</th><th>Revalidation Due</th><th>Status</th><th>Current Status</th><th>Incharge</th><th>Alert</th></tr>
            </thead>
            <tbody>
                {overdue_rows if overdue_rows else '<tr><td colspan="7" style="text-align:center;">No overdue samples</td></tr>'}
            </tbody>
        </table>
        
        <h3>⚠️ SAMPLES DUE WITHIN 3 DAYS:</h3>
        <table>
            <thead>
                <tr><th>Model</th><th>Validation Date</th><th>Revalidation Due</th><th>Days Left</th><th>Current Status</th><th>Incharge</th><th>Alert</th></tr>
            </thead>
            <tbody>
                {due_rows if due_rows else '<tr><td colspan="7" style="text-align:center;">No samples due within 3 days</td></tr>'}
            </tbody>
        </table>
        
        <div class="footer">
            <p><strong>Summary:</strong></p>
            <p>🔴 OVERDUE: Revalidation date has passed - Immediate action required<br>
            ⚠️ URGENT: Due within 3 days - Action required soon<br>
            🟡 Due Soon: Due within 7 days - Plan accordingly</p>
            <p><i>This is an automated alert from Golden Sample Tracker System.</i></p>
            <p>Report generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    
    return html

def check_and_send_auto_email():
    """Check if auto email should be sent and send it"""
    if not AUTO_EMAIL_ENABLED:
        return False, "Auto email disabled", None
    
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_date = now.date()
    
    # Debug log
    log_entry = {
        "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "current_time": f"{current_hour:02d}:{current_minute:02d}",
        "scheduled_time": f"{AUTO_EMAIL_HOUR:02d}:{AUTO_EMAIL_MINUTE:02d}",
        "last_sent_date": str(st.session_state.last_auto_email_date),
        "auto_email_sent_today": st.session_state.auto_email_sent_today
    }
    
    # Check if it's time to send email
    time_match = (current_hour == AUTO_EMAIL_HOUR and current_minute == AUTO_EMAIL_MINUTE)
    
    # Check if not sent today
    not_sent_today = (st.session_state.last_auto_email_date is None or 
                     st.session_state.last_auto_email_date.date() != current_date)
    
    log_entry["time_match"] = time_match
    log_entry["not_sent_today"] = not_sent_today
    
    if time_match and not_sent_today:
        log_entry["action"] = "Time matched, attempting to send email"
        
        if 'df' in st.session_state and st.session_state.df is not None:
            df = st.session_state.df
            due_records = get_due_records(df)
            overdue_records = get_overdue_records(df)
            
            log_entry["due_records_count"] = len(due_records)
            log_entry["overdue_records_count"] = len(overdue_records)
            
            if not due_records.empty or not overdue_records.empty:
                success, message = send_single_email_alert(
                    df, 
                    st.session_state.primary_recipient, 
                    st.session_state.cc_recipients, 
                    alert_type="auto"
                )
                if success:
                    st.session_state.last_auto_email_date = now
                    st.session_state.auto_email_sent_today = True
                    log_entry["status"] = "SUCCESS"
                    log_entry["message"] = message
                    st.session_state.auto_email_log.append(log_entry)
                    return True, message, log_entry
                else:
                    log_entry["status"] = "FAILED"
                    log_entry["message"] = message
                    st.session_state.auto_email_log.append(log_entry)
                    return False, message, log_entry
            else:
                log_entry["status"] = "SKIPPED"
                log_entry["message"] = "No urgent samples found"
                st.session_state.auto_email_log.append(log_entry)
                return False, "No urgent samples found, skipping auto email", log_entry
        else:
            log_entry["status"] = "ERROR"
            log_entry["message"] = "No data available"
            st.session_state.auto_email_log.append(log_entry)
            return False, "No data available", log_entry
    
    # Reset sent flag at midnight if needed (handled by not_sent_today check above)
    
    return False, "Not time yet", log_entry

def create_status_chart(df):
    """Create donut chart for status distribution"""
    if df.empty:
        return go.Figure()
    
    status_counts = df['Staus'].value_counts()
    
    fig = go.Figure(data=[go.Pie(
        labels=status_counts.index,
        values=status_counts.values,
        hole=0.6,
        marker_colors=['#28a745', '#ffc107', '#dc3545'],
        textinfo='label+percent',
        textposition='outside'
    )])
    
    fig.update_layout(title="Status Distribution", height=400, showlegend=True)
    return fig

def create_urgency_chart(df):
    """Create bar chart for urgency levels"""
    if df.empty:
        return go.Figure()
    
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="Samples by Urgency Level", height=400)
        return fig
    
    def categorize_urgency(days):
        if pd.isna(days):
            return 'Unknown'
        if days < 0:
            return 'Overdue'
        elif days <= 3:
            return 'Urgent (0-3 days)'
        elif days <= 7:
            return 'Due Soon (4-7 days)'
        else:
            return 'On Track (>7 days)'
    
    alert_df['Urgency Category'] = alert_df['Days Left'].apply(categorize_urgency)
    urgency_counts = alert_df['Urgency Category'].value_counts()
    
    color_map = {
        'Overdue': '#dc3545',
        'Urgent (0-3 days)': '#ff6b6b',
        'Due Soon (4-7 days)': '#ffc107',
        'On Track (>7 days)': '#28a745',
        'Unknown': '#6c757d'
    }
    
    colors = [color_map.get(cat, '#6c757d') for cat in urgency_counts.index]
    
    fig = go.Figure(data=[go.Bar(
        x=urgency_counts.index,
        y=urgency_counts.values,
        marker_color=colors,
        text=urgency_counts.values,
        textposition='auto'
    )])
    
    fig.update_layout(
        title="Samples by Urgency Level",
        xaxis_title="Urgency Level",
        yaxis_title="Number of Samples",
        height=400,
        showlegend=False
    )
    
    return fig

def main():
    # Header
    st.markdown('<div class="main-header"><h1 style="color:white; text-align:center;">📊 Golden Sample Revalidation Tracker</h1></div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Controls")
        
        auto_refresh = st.checkbox("🔄 Auto-refresh data", value=True)
        if auto_refresh:
            refresh_rate = st.slider("Refresh rate (seconds)", 30, 300, 60, value=60)
            st.info(f"Data will refresh every {refresh_rate} seconds")
        
        st.markdown("---")
        
        # Email section
        st.header("📧 Email Notifications")
        
        st.subheader("🤖 Auto Email Settings")
        st.info(f"📨 Auto emails scheduled daily at {AUTO_EMAIL_HOUR:02d}:{AUTO_EMAIL_MINUTE:02d}")
        
        current_time = datetime.now()
        st.caption(f"Current time: {current_time.strftime('%H:%M:%S')}")
        
        # Check and send auto email on each page load
        auto_email_sent, auto_email_message, auto_email_log = check_and_send_auto_email()
        
        # Show auto email status
        if st.session_state.last_auto_email_date:
            st.success(f"✅ Last auto email: {st.session_state.last_auto_email_date.strftime('%d-%m-%Y %H:%M:%S')}")
        
        if st.session_state.auto_email_sent_today:
            st.success("✅ Auto email already sent today")
        else:
            next_time = datetime.now().replace(hour=AUTO_EMAIL_HOUR, minute=AUTO_EMAIL_MINUTE, second=0)
            if next_time < datetime.now():
                next_time += timedelta(days=1)
            time_until = next_time - datetime.now()
            hours = time_until.seconds // 3600
            minutes = (time_until.seconds % 3600) // 60
            st.info(f"⏰ Next auto email in: {hours}h {minutes}m")
        
        # Show auto email result
        if auto_email_sent:
            st.success(auto_email_message)
        elif auto_email_message and auto_email_message not in ["Not time yet", "Auto email disabled"]:
            st.warning(auto_email_message)
        
        # Debug: Show auto email log
        with st.expander("📋 Auto Email Log (Debug)"):
            if st.session_state.auto_email_log:
                for log in st.session_state.auto_email_log[-10:]:  # Show last 10 entries
                    st.text(f"{log['timestamp']}: {log.get('status', 'Check')} - {log.get('message', '')}")
                    if 'current_time' in log:
                        st.text(f"  Time: {log['current_time']} vs {log['scheduled_time']}")
            else:
                st.text("No auto email attempts logged yet")
        
        st.markdown("---")
        
        # Recipient Management
        st.subheader("👥 Email Recipients")
        
        st.markdown("**Primary Recipient (TO):**")
        new_primary = st.text_input("TO Email", value=st.session_state.primary_recipient)
        if new_primary != st.session_state.primary_recipient:
            st.session_state.primary_recipient = new_primary
        
        st.markdown("**CC Recipients:**")
        
        for i, email in enumerate(st.session_state.cc_recipients):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"{i+1}. {email}")
            with col2:
                if st.button(f"❌", key=f"remove_cc_{i}"):
                    st.session_state.cc_recipients.pop(i)
                    st.rerun()
        
        st.markdown("**Add CC Recipient:**")
        new_cc = st.text_input("CC Email", key="new_cc_recipient")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add CC Recipient", use_container_width=True):
                if new_cc and new_cc.strip():
                    if new_cc not in st.session_state.cc_recipients:
                        st.session_state.cc_recipients.append(new_cc.strip())
                        st.success(f"Added {new_cc} to CC list")
                        st.rerun()
                    else:
                        st.warning("Email already in CC list")
                else:
                    st.warning("Please enter a valid email")
        
        with col2:
            if st.button("🔄 Reset to Default", use_container_width=True):
                st.session_state.primary_recipient = PRIMARY_RECIPIENT
                st.session_state.cc_recipients = CC_RECIPIENTS.copy()
                st.success("Reset to default recipients")
                st.rerun()
        
        st.markdown("---")
        st.markdown("**Recipient Summary:**")
        st.caption(f"📧 TO: {st.session_state.primary_recipient}")
        st.caption(f"👥 CC: {len(st.session_state.cc_recipients)} recipient(s)")
        
        st.markdown("---")
        
        # Manual email
        st.subheader("📧 Manual Email Alert")
        
        col1, col2 = st.columns(2)
        with col1:
            send_email = st.button("🚨 Send Alert Now", type="primary", use_container_width=True)
        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        if send_email:
            with st.spinner("Sending alert..."):
                if 'df' in st.session_state and st.session_state.df is not None:
                    success, message = send_single_email_alert(
                        st.session_state.df,
                        st.session_state.primary_recipient,
                        st.session_state.cc_recipients,
                        alert_type="manual"
                    )
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.error("No data available to send alerts")
        
        st.markdown("---")
        debug_mode = st.checkbox("🔧 Show debug info", value=False)
    
    # Main content
    try:
        with st.spinner("Loading data..."):
            df = fetch_data()
            df = process_data(df)
        
        if df is None or df.empty:
            st.error("No valid data available. Please check:")
            st.info("""
            📋 **Data Requirements:**
            1. Google Sheet must be publicly accessible
            2. Required columns: 'Validation Date', 'Staus', 'Model'
            3. Date format: DD-MM-YYYY (e.g., 23-03-2026)
            """)
            return
        
        st.session_state.df = df
        
        if debug_mode:
            with st.expander("Debug Information"):
                st.write("DataFrame Info:")
                st.write(f"Total rows: {len(df)}")
                st.write(f"Columns: {df.columns.tolist()}")
                st.write("Sample data (first 3 rows):")
                st.dataframe(df.head(3))
                st.write("Data types:")
                st.write(df.dtypes)
                st.write("Email Configuration:")
                st.write(f"Primary (TO): {st.session_state.primary_recipient}")
                st.write(f"CC Recipients: {st.session_state.cc_recipients}")
                st.write(f"Auto email sent today: {st.session_state.auto_email_sent_today}")
                st.write(f"Last auto email date: {st.session_state.last_auto_email_date}")
                st.write(f"Auto email enabled: {AUTO_EMAIL_ENABLED}")
                st.write(f"Scheduled time: {AUTO_EMAIL_HOUR:02d}:{AUTO_EMAIL_MINUTE:02d}")
        
        # Metrics Row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total = len(df)
        ok_count = len(df[df['Staus'].str.lower() == 'ok'])
        pending_count = len(df[df['Staus'].str.lower() == 'pending'])
        ng_count = len(df[df['Staus'].str.lower() == 'ng'])
        urgent_count = len(get_due_records(df))
        overdue_count = len(get_overdue_records(df))
        
        with col1:
            st.metric("Total Samples", total)
        with col2:
            st.metric("✅ OK", ok_count)
        with col3:
            st.metric("⏳ Pending", pending_count)
        with col4:
            st.metric("❌ NG", ng_count)
        with col5:
            st.metric("🔴 Urgent", urgent_count + overdue_count, 
                     delta=f"{overdue_count} overdue" if overdue_count > 0 else None,
                     delta_color="inverse" if (urgent_count + overdue_count) > 0 else "normal")
        
        if overdue_count > 0:
            st.error(f"🔴 **CRITICAL ALERT:** {overdue_count} sample(s) are OVERDUE for revalidation! Immediate action required!")
        
        if urgent_count > 0:
            st.warning(f"⚠️ **URGENT ALERT:** {urgent_count} sample(s) require revalidation within 3 days! Please check the table below.")
        
        # Charts Row
        col1, col2 = st.columns(2)
        
        with col1:
            status_chart = create_status_chart(df)
            st.plotly_chart(status_chart, use_container_width=True)
        
        with col2:
            urgency_chart = create_urgency_chart(df)
            st.plotly_chart(urgency_chart, use_container_width=True)
        
        # Data Table with filters
        st.markdown("### 📋 Golden Sample Details")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=['OK', 'Pending', 'NG'],
                default=['OK', 'Pending', 'NG']
            )
        with col2:
            urgency_filter = st.selectbox(
                "Filter by Urgency",
                options=['All', 'Overdue', 'Urgent (≤3 days)', 'Due Soon (4-7 days)', 'On Track (>7 days)']
            )
        with col3:
            search_model = st.text_input("🔍 Search Model", placeholder="Enter model name...")
        with col4:
            sort_by = st.selectbox("Sort by", ['Days Left', 'Validation Date', 'Revalidation Due', 'Model'])
        
        filtered_df = df[df['Staus'].isin(status_filter)]
        
        if urgency_filter != 'All':
            if urgency_filter == 'Overdue':
                filtered_df = filtered_df[filtered_df['Days Left'] < 0]
            elif urgency_filter == 'Urgent (≤3 days)':
                filtered_df = filtered_df[(filtered_df['Days Left'] <= 3) & (filtered_df['Days Left'] >= 0)]
            elif urgency_filter == 'Due Soon (4-7 days)':
                filtered_df = filtered_df[(filtered_df['Days Left'] <= 7) & (filtered_df['Days Left'] > 3)]
            elif urgency_filter == 'On Track (>7 days)':
                filtered_df = filtered_df[filtered_df['Days Left'] > 7]
        
        if search_model:
            filtered_df = filtered_df[filtered_df['Model'].str.contains(search_model, case=False, na=False)]
        
        if sort_by in filtered_df.columns:
            filtered_df = filtered_df.sort_values(sort_by, ascending=True)
        
        display_columns = ['Model', 'Validation Date Display', 'Revalidation Due Display', 
                          'Days Left', 'Staus', 'Incharge', 'Alert Status']
        
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        display_df = filtered_df[available_columns].copy()
        display_df = display_df.fillna('-')
        
        display_df['Days Left'] = display_df['Days Left'].apply(
            lambda x: f"{int(x)} days" if x != '-' and pd.notna(x) and x != '-' else '-'
        )
        
        def highlight_row(row):
            if 'Days Left' in row and row['Days Left'] != '-':
                try:
                    days = int(row['Days Left'].split()[0])
                    if days < 0:
                        return ['background-color: #f8d7da'] * len(row)
                    elif days <= 3:
                        return ['background-color: #fff3cd'] * len(row)
                except:
                    pass
            return [''] * len(row)
        
        styled_df = display_df.style.apply(highlight_row, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=500)
        
        if st.button("📥 Export to CSV", use_container_width=True):
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"golden_sample_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_csv"
            )
        
        if auto_refresh:
            time.sleep(refresh_rate)
            st.rerun()
            
    except Exception as e:
        st.error(f"An error occurred: {e}")
        if debug_mode:
            st.exception(e)

if __name__ == "__main__":
    main()
