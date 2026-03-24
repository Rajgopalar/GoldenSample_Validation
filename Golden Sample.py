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

# Email recipients - Add multiple email addresses here
# Format: ["email1@domain.com", "email2@domain.com", "email3@domain.com"]
DEFAULT_RECIPIENT_EMAILS = [
    "emurugesan.padget@dixoninfo.com",
    "rajgopal.padget@dixoninfo.com",  # Keep old for backup if needed
    # Add more email addresses here
    # "recipient3@dixoninfo.com",
    # "recipient4@dixoninfo.com",
]

# Auto email settings
AUTO_EMAIL_HOUR = 12  # Set to 12 PM
AUTO_EMAIL_MINUTE = 16  # Set to 00 minutes
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
    .recipient-list {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        margin-top: 10px;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_auto_email_date' not in st.session_state:
    st.session_state.last_auto_email_date = None
if 'auto_email_sent_today' not in st.session_state:
    st.session_state.auto_email_sent_today = False
if 'recipient_emails' not in st.session_state:
    st.session_state.recipient_emails = DEFAULT_RECIPIENT_EMAILS.copy()

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
                    # Check if it's DD-MM-YYYY format
                    day, month, year = parts
                    # Validate parts are numbers
                    if day.isdigit() and month.isdigit() and year.isdigit():
                        # Ensure 4-digit year
                        if len(year) == 2:
                            year = '20' + year
                        return datetime(int(year), int(month), int(day))
        
        # Try pandas parser as last resort
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
    
    # Standardize column names
    df.columns = df.columns.str.strip()
    
    # Check if required columns exist
    required_columns = ['Validation Date', 'Staus', 'Model']
    for col in required_columns:
        if col not in df.columns:
            st.error(f"Missing required column: '{col}'")
            st.write("Available columns:", df.columns.tolist())
            return None
    
    # Parse validation dates
    df['Validation Date Parsed'] = df['Validation Date'].apply(parse_date_safe)
    
    # Drop rows with invalid dates
    initial_count = len(df)
    df = df.dropna(subset=['Validation Date Parsed'])
    
    if len(df) < initial_count and initial_count > 0:
        st.warning(f"⚠️ Dropped {initial_count - len(df)} rows with invalid date format")
    
    if df.empty:
        st.error("No valid dates found. Please check date format (should be DD-MM-YYYY)")
        return None
    
    # Convert to datetime series
    validation_dates = pd.Series(df['Validation Date Parsed'])
    
    # Calculate dates using timedelta
    revalidation_dates = validation_dates + pd.Timedelta(days=10)
    reminder_dates = revalidation_dates - pd.Timedelta(days=3)
    
    # Calculate days left
    today = datetime.now().date()
    
    # Create a list of days left
    days_left_list = []
    for reval_date in revalidation_dates:
        if pd.notna(reval_date):
            days_diff = (reval_date.date() - today).days
            days_left_list.append(days_diff)
        else:
            days_left_list.append(None)
    
    df['Days Left'] = days_left_list
    
    # Add calculated columns
    df['Validation Date'] = validation_dates
    df['Revalidation Due'] = revalidation_dates
    df['Reminder Date'] = reminder_dates
    
    # Format dates for display
    df['Validation Date Display'] = validation_dates.dt.strftime('%d-%m-%Y')
    df['Revalidation Due Display'] = revalidation_dates.dt.strftime('%d-%m-%Y')
    df['Reminder Date Display'] = reminder_dates.dt.strftime('%d-%m-%Y')
    
    # Determine alert status
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
    
    # Condition: Days Left <= 3 and Days Left >= 0 and status not OK
    mask = (df['Days Left'] <= 3) & (df['Days Left'] >= 0) & (df['Staus'].str.lower() != 'ok')
    
    return df[mask]

def get_overdue_records(df):
    """Get overdue records"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    mask = (df['Days Left'] < 0) & (df['Staus'].str.lower() != 'ok')
    return df[mask]

def send_email_alert(df, recipient_emails, alert_type="manual"):
    """Send email alert for due records to multiple recipients"""
    due_records = get_due_records(df)
    overdue_records = get_overdue_records(df)
    
    if due_records.empty and overdue_records.empty:
        return False, "No records requiring immediate attention"
    
    # Ensure recipient_emails is a list
    if isinstance(recipient_emails, str):
        recipient_list = [recipient_emails]
    else:
        recipient_list = recipient_emails
    
    # Remove any empty strings or None values
    recipient_list = [r for r in recipient_list if r and r.strip()]
    
    if not recipient_list:
        return False, "No valid recipient email addresses provided"
    
    try:
        # Create email body
        email_body = generate_email_html(df, due_records, overdue_records, alert_type)
        
        success_count = 0
        failed_recipients = []
        
        for recipient in recipient_list:
            try:
                msg = MIMEMultipart()
                msg['From'] = SENDER_EMAIL
                msg['To'] = recipient
                total_urgent = len(due_records) + len(overdue_records)
                msg['Subject'] = f"🚨 GOLDEN SAMPLE ALERT: {total_urgent} {'Samples' if total_urgent > 1 else 'Sample'} Need Immediate Attention"
                msg['CC'] = SENDER_EMAIL  # Send a copy to sender for tracking
                
                msg.attach(MIMEText(email_body, 'html'))
                
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.send_message(msg)
                
                success_count += 1
                
            except Exception as e:
                failed_recipients.append(f"{recipient}: {str(e)}")
                print(f"Failed to send to {recipient}: {e}")
        
        if success_count > 0:
            message = f"Alert sent to {success_count} of {len(recipient_list)} recipient(s)"
            if failed_recipients:
                message += f"\nFailed: {', '.join(failed_recipients)}"
            return True, message
        else:
            return False, f"Failed to send to all recipients: {', '.join(failed_recipients)}"
    
    except Exception as e:
        return False, f"Email failed: {e}"

def generate_email_html(df, due_records, overdue_records, alert_type="manual"):
    """Generate HTML for email body"""
    
    # Generate due records table
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
    
    # Generate overdue records table
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
                <tr>
                    <th>Model</th>
                    <th>Validation Date</th>
                    <th>Revalidation Due</th>
                    <th>Status</th>
                    <th>Current Status</th>
                    <th>Incharge</th>
                    <th>Alert</th>
                </tr>
            </thead>
            <tbody>
                {overdue_rows if overdue_rows else '<tr><td colspan="7" style="text-align:center;">No overdue samples</td></tr>'}
            </tbody>
        </table>
        
        <h3>⚠️ SAMPLES DUE WITHIN 3 DAYS:</h3>
        <table>
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Validation Date</th>
                    <th>Revalidation Due</th>
                    <th>Days Left</th>
                    <th>Current Status</th>
                    <th>Incharge</th>
                    <th>Alert</th>
                </tr>
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
        return
    
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # Check if it's time to send email
    if current_hour == AUTO_EMAIL_HOUR and current_minute == AUTO_EMAIL_MINUTE:
        # Check if email hasn't been sent today
        if not st.session_state.auto_email_sent_today:
            with st.spinner("Sending auto email..."):
                if 'df' in st.session_state and st.session_state.df is not None:
                    df = st.session_state.df
                    due_records = get_due_records(df)
                    overdue_records = get_overdue_records(df)
                    
                    if not due_records.empty or not overdue_records.empty:
                        # Use the current recipient list from session state
                        success, message = send_email_alert(df, st.session_state.recipient_emails, alert_type="auto")
                        if success:
                            st.session_state.last_auto_email_date = now
                            st.session_state.auto_email_sent_today = True
                            st.success(f"✅ Auto email sent successfully at {now.strftime('%H:%M:%S')} to {len(st.session_state.recipient_emails)} recipient(s)")
                        else:
                            st.error(f"❌ Auto email failed: {message}")
                    else:
                        st.info("No urgent samples found, skipping auto email")
    
    # Reset the flag at midnight (new day)
    if current_hour == 0 and current_minute == 0:
        st.session_state.auto_email_sent_today = False

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
    
    fig.update_layout(
        title="Status Distribution",
        height=400,
        showlegend=True
    )
    
    return fig

def create_urgency_chart(df):
    """Create bar chart for urgency levels"""
    if df.empty:
        return go.Figure()
    
    # Filter non-OK samples
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    
    if alert_df.empty:
        # Create empty figure with message
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="Samples by Urgency Level", height=400)
        return fig
    
    # Categorize urgency
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
    
    # Define color order
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
        
        # Auto-refresh option
        auto_refresh = st.checkbox("🔄 Auto-refresh data", value=False)
        if auto_refresh:
            refresh_rate = st.slider("Refresh rate (seconds)", 30, 300, 60)
            st.info(f"Data will refresh every {refresh_rate} seconds")
        
        st.markdown("---")
        
        # Email section
        st.header("📧 Email Notifications")
        st.info(f"📨 Auto emails scheduled daily at {AUTO_EMAIL_HOUR:02d}:{AUTO_EMAIL_MINUTE:02d}")
        
        if st.session_state.last_auto_email_date:
            st.success(f"Last auto email: {st.session_state.last_auto_email_date.strftime('%d-%m-%Y %H:%M:%S')}")
        else:
            st.info("No auto email sent yet today")
        
        # Show status of today's auto email
        if st.session_state.auto_email_sent_today:
            st.success("✅ Auto email already sent today")
        else:
            st.info("⏰ Waiting for scheduled time...")
        
        st.markdown("---")
        
        # Recipient Management
        st.subheader("👥 Email Recipients")
        st.markdown("Manage recipients for both manual and auto alerts:")
        
        # Display current recipients
        st.markdown("**Current Recipients:**")
        for i, email in enumerate(st.session_state.recipient_emails):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"{i+1}. {email}")
            with col2:
                if st.button(f"❌", key=f"remove_{i}"):
                    st.session_state.recipient_emails.pop(i)
                    st.rerun()
        
        # Add new recipient
        st.markdown("**Add New Recipient:**")
        new_recipient = st.text_input("Email address", key="new_recipient")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add Recipient", use_container_width=True):
                if new_recipient and new_recipient.strip():
                    if new_recipient not in st.session_state.recipient_emails:
                        st.session_state.recipient_emails.append(new_recipient.strip())
                        st.success(f"Added {new_recipient}")
                        st.rerun()
                    else:
                        st.warning("Email already in list")
                else:
                    st.warning("Please enter a valid email")
        
        with col2:
            if st.button("🔄 Reset to Default", use_container_width=True):
                st.session_state.recipient_emails = DEFAULT_RECIPIENT_EMAILS.copy()
                st.success("Reset to default recipients")
                st.rerun()
        
        # Show recipient count
        st.caption(f"Total recipients: {len(st.session_state.recipient_emails)}")
        
        st.markdown("---")
        
        # Manual email
        st.subheader("📧 Manual Email Alert")
        
        # Option to send to all or specific recipients
        send_to_all = st.checkbox("Send to all recipients", value=True)
        
        if not send_to_all:
            # Allow selecting specific recipients
            selected_recipients = st.multiselect(
                "Select recipients",
                options=st.session_state.recipient_emails,
                default=st.session_state.recipient_emails[:1] if st.session_state.recipient_emails else []
            )
        else:
            selected_recipients = st.session_state.recipient_emails
        
        # Display selected recipients
        if selected_recipients:
            st.info(f"Will send to: {', '.join(selected_recipients)}")
        else:
            st.warning("No recipients selected")
        
        col1, col2 = st.columns(2)
        with col1:
            send_email = st.button("🚨 Send Alert Now", type="primary", use_container_width=True, disabled=not selected_recipients)
        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        if send_email and selected_recipients:
            with st.spinner(f"Sending alert to {len(selected_recipients)} recipient(s)..."):
                if 'df' in st.session_state and st.session_state.df is not None:
                    success, message = send_email_alert(st.session_state.df, selected_recipients, alert_type="manual")
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.error("No data available to send alerts")
        
        st.markdown("---")
        
        # Debug option
        debug_mode = st.checkbox("🔧 Show debug info", value=False)
    
    # Check for auto email (run this check periodically)
    check_and_send_auto_email()
    
    # Main content
    try:
        # Fetch and process data
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
        
        # Store in session state
        st.session_state.df = df
        
        # Debug info
        if debug_mode:
            with st.expander("Debug Information"):
                st.write("DataFrame Info:")
                st.write(f"Total rows: {len(df)}")
                st.write(f"Columns: {df.columns.tolist()}")
                st.write("Sample data (first 3 rows):")
                st.dataframe(df.head(3))
                st.write("Data types:")
                st.write(df.dtypes)
                st.write("Recipients in session state:")
                st.write(st.session_state.recipient_emails)
        
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
        
        # Alert banners for urgent items
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
        
        # Filter options
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
        
        # Apply filters
        filtered_df = df[df['Staus'].isin(status_filter)]
        
        # Apply urgency filter
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
        
        # Sort
        if sort_by in filtered_df.columns:
            if sort_by == 'Days Left':
                filtered_df = filtered_df.sort_values(sort_by, ascending=True)
            else:
                filtered_df = filtered_df.sort_values(sort_by, ascending=True)
        
        # Display dataframe with styling
        display_columns = ['Model', 'Validation Date Display', 'Revalidation Due Display', 
                          'Days Left', 'Staus', 'Incharge', 'Alert Status']
        
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        display_df = filtered_df[available_columns].copy()
        
        # Replace NaN values
        display_df = display_df.fillna('-')
        
        # Format Days Left for better display
        display_df['Days Left'] = display_df['Days Left'].apply(
            lambda x: f"{int(x)} days" if x != '-' and pd.notna(x) and x != '-' else '-'
        )
        
        # Color code the entire row based on urgency
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
        
        # Export and email buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export to CSV", use_container_width=True):
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"golden_sample_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_csv"
                )
        
        with col2:
            if st.button("📧 Send Alert to All", use_container_width=True):
                with st.spinner(f"Sending alerts to {len(st.session_state.recipient_emails)} recipient(s)..."):
                    success, message = send_email_alert(df, st.session_state.recipient_emails, alert_type="manual")
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        
        # Auto-refresh logic
        if auto_refresh:
            time.sleep(refresh_rate)
            st.rerun()
            
    except Exception as e:
        st.error(f"An error occurred: {e}")
        if debug_mode:
            st.exception(e)

if __name__ == "__main__":
    main()
