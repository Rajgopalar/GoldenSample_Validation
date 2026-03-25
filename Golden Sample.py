import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import plotly.graph_objects as go
import warnings
import time
import os
import json
import hashlib

warnings.filterwarnings('ignore')

# ========== CONFIGURATION ==========
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSG42OXWxsoLV7wNqqDAdryfmDYU4IGBv1gEJm8-8bP_qh6vCe2NWAx7_vM3DYQqxCPFX3jv-TimRgV/pub?output=csv"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "rajgopalr.padget@dixoninfo.com"
SENDER_PASSWORD = "gzxzuolbmqkdhcst"

PRIMARY_RECIPIENT = "emurugesan.padget@dixoninfo.com"
CC_RECIPIENTS = [
    "chauhandeesingh@gmail.com",
    "rajgopal.padget@dixoninfo.com",
]

# Auto email settings - ONE EMAIL PER DAY AT 9 AM
AUTO_EMAIL_HOUR = 9
AUTO_EMAIL_MINUTE = 0
AUTO_EMAIL_ENABLED = True

# Persistent state file
STATE_FILE = "/tmp/golden_sample_email_state.json"
# ===================================

st.set_page_config(
    page_title="Golden Sample Revalidation Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"  # Collapsed sidebar to save space
)

# Custom CSS for compact layout
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72, #2a5298);
        padding: 0.5rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    .main-header h1 {
        font-size: 1.5rem !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 8px;
        border-radius: 8px;
    }
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 8px;
        border-radius: 8px;
    }
    .stButton button {
        padding: 0.25rem 0.5rem;
        font-size: 0.8rem;
    }
    .compact-table {
        font-size: 0.8rem;
    }
    .status-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: bold;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'email_sent_today' not in st.session_state:
    st.session_state.email_sent_today = False
if 'last_email_date' not in st.session_state:
    st.session_state.last_email_date = None
if 'primary_recipient' not in st.session_state:
    st.session_state.primary_recipient = PRIMARY_RECIPIENT
if 'cc_recipients' not in st.session_state:
    st.session_state.cc_recipients = CC_RECIPIENTS.copy()
if 'df' not in st.session_state:
    st.session_state.df = None

# ─────────────────────────────────────────────────────────────
#  PERSISTENT STATE (SINGLE EMAIL PER DAY)
# ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load persistent state"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "last_sent_date": None,
        "last_sent_time": None,
        "email_sent_today": False
    }


def _save_state(state: dict):
    """Save persistent state"""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _should_send_email_today() -> bool:
    """Check if email should be sent today"""
    state = _load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    return state.get("last_sent_date") != today


def _mark_email_sent():
    """Mark that email has been sent today"""
    state = _load_state()
    now = datetime.now()
    state["last_sent_date"] = now.strftime("%Y-%m-%d")
    state["last_sent_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
    state["email_sent_today"] = True
    _save_state(state)
    st.session_state.email_sent_today = True
    st.session_state.last_email_date = now


# ─────────────────────────────────────────────────────────────
#  DATA HELPERS
# ─────────────────────────────────────────────────────────────

def parse_date_safe(date_str):
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    try:
        date_str = str(date_str).strip()
        for sep in ['-', '/', '.']:
            if sep in date_str:
                parts = date_str.split(sep)
                if len(parts) == 3:
                    day, month, year = parts
                    if day.isdigit() and month.isdigit() and year.isdigit():
                        if len(year) == 2:
                            year = '20' + year
                        return datetime(int(year), int(month), int(day))
        return pd.to_datetime(date_str, dayfirst=True, errors='coerce')
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_data():
    try:
        return pd.read_csv(CSV_URL)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None


def process_data(df):
    if df is None:
        return None
    df = df.copy()
    df.columns = df.columns.str.strip()

    for col in ['Validation Date', 'Staus', 'Model']:
        if col not in df.columns:
            return None

    df['Validation Date Parsed'] = df['Validation Date'].apply(parse_date_safe)
    df = df.dropna(subset=['Validation Date Parsed'])
    if df.empty:
        return None

    validation_dates = pd.Series(df['Validation Date Parsed'])
    revalidation_dates = validation_dates + pd.Timedelta(days=10)
    today = datetime.now().date()

    df['Days Left'] = [
        (r.date() - today).days if pd.notna(r) else None for r in revalidation_dates
    ]
    df['Validation Date Display'] = validation_dates.dt.strftime('%d-%m-%Y')
    df['Revalidation Due Display'] = revalidation_dates.dt.strftime('%d-%m-%Y')

    def get_alert_status(row):
        d = row['Days Left']
        s = str(row.get('Staus', '')).lower()
        if pd.isna(d):
            return '⚪ Unknown'
        if s == 'ok':
            return '✅ Completed'
        if d < 0:
            return '🔴 OVERDUE'
        if d <= 3:
            return '🔴 URGENT'
        if d <= 7:
            return '🟡 Due Soon'
        return '🟢 On Track'

    df['Alert Status'] = df.apply(get_alert_status, axis=1)
    return df


def get_due_records(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df['Days Left'] <= 3) & (df['Days Left'] >= 0) & (df['Staus'].str.lower() != 'ok')]


def get_overdue_records(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df['Days Left'] < 0) & (df['Staus'].str.lower() != 'ok')]


# ─────────────────────────────────────────────────────────────
#  EMAIL
# ─────────────────────────────────────────────────────────────

def send_email_alert(df, primary_recipient, cc_recipients):
    """Send a single email with primary in TO and others in CC"""
    due_records = get_due_records(df)
    overdue_records = get_overdue_records(df)

    if due_records.empty and overdue_records.empty:
        return False, "No records requiring immediate attention"

    cc_list = [e for e in cc_recipients if e and e.strip()]

    try:
        email_body = generate_email_html(due_records, overdue_records)
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = primary_recipient
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)

        total = len(due_records) + len(overdue_records)
        msg['Subject'] = (
            f"🚨 GOLDEN SAMPLE ALERT: {total} "
            f"{'Samples' if total > 1 else 'Sample'} Need Immediate Attention"
        )
        msg.attach(MIMEText(email_body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        return True, f"Alert sent to {primary_recipient} and {len(cc_list)} CC recipient(s)"
    except Exception as e:
        return False, f"Email failed: {e}"


def generate_email_html(due_records, overdue_records):
    headers = "<tr>" + "".join(
        f"<th>{h}</th>" for h in
        ["Model", "Validation Date", "Revalidation Due", "Days Left", "Status", "Incharge", "Alert"]
    ) + "</tr>"

    def make_row(row, bg, days_text, badge):
        return (f'<tr style="background-color:{bg};">'
                f'<td style="padding:8px;"><b>{row.get("Model","")}</b></td>'
                f'<td style="padding:8px;">{row.get("Validation Date Display","")}</td>'
                f'<td style="padding:8px;">{row.get("Revalidation Due Display","")}</td>'
                f'<td style="padding:8px;color:#dc3545;font-weight:bold;">{days_text}</td>'
                f'<td style="padding:8px;"><b>{row.get("Staus","")}</b></td>'
                f'<td style="padding:8px;">{row.get("Incharge","")}</td>'
                f'<td style="padding:8px;color:#dc3545;">{badge}</td></tr>')

    over_rows = "".join(
        make_row(r, "#f8d7da", f"{abs(int(r['Days Left']))} days overdue", "🔴 OVERDUE")
        for _, r in overdue_records.iterrows()
    ) if not overdue_records.empty else '<tr><td colspan="7" style="text-align:center;">None</td></tr>'

    due_rows = "".join(
        make_row(r, "#fff3cd", f"{int(r['Days Left'])} days", "⚠️ URGENT")
        for _, r in due_records.iterrows()
    ) if not due_records.empty else '<tr><td colspan="7" style="text-align:center;">None</td></tr>'

    total = len(due_records) + len(overdue_records)

    return f"""<html>
<head>
    <style>
        body{{font-family:Arial,sans-serif;line-height:1.6;margin:0;padding:20px;}}
        .header{{background:linear-gradient(90deg,#1e3c72,#2a5298);color:white;padding:15px;text-align:center;border-radius:8px;}}
        .alert{{background:#f8d7da;border-left:4px solid #dc3545;padding:12px;margin:15px 0;border-radius:4px;}}
        table{{border-collapse:collapse;width:100%;margin:15px 0;}}
        th{{background:#2a5298;color:white;padding:10px;text-align:left;}}
        td{{padding:8px;border-bottom:1px solid #ddd;}}
        .footer{{margin-top:20px;padding:12px;background:#f8f9fa;text-align:center;border-radius:4px;font-size:12px;}}
        h3{{margin:10px 0;font-size:16px;}}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">Golden Sample Revalidation Tracker</h2>
        <p style="margin:5px 0 0;">🚨 URGENT ALERT: Action Required Immediately</p>
    </div>
    <div class="alert">
        <strong>⚠️ CRITICAL ALERT:</strong> {total} sample(s) require immediate attention!<br>
        • {len(overdue_records)} OVERDUE &nbsp;• {len(due_records)} due within 3 days<br>
        Please take necessary action immediately.
    </div>
    <h3>🔴 OVERDUE SAMPLES:</h3>
    <table><thead>{headers}</thead><tbody>{over_rows}</tbody></table>
    <h3>⚠️ SAMPLES DUE WITHIN 3 DAYS:</h3>
    <table><thead>{headers}</thead><tbody>{due_rows}</tbody></table>
    <div class="footer">
        <p><i>Automated alert – Golden Sample Tracker System</i></p>
        <p>Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
    </div>
</body>
</html>"""


def check_and_send_auto_email(df):
    """Check if it's 9 AM and send email (ONCE PER DAY)"""
    if not AUTO_EMAIL_ENABLED:
        return False, "Auto email disabled"
    
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # Check if it's exactly 9:00 AM
    if current_hour == AUTO_EMAIL_HOUR and current_minute == AUTO_EMAIL_MINUTE:
        # Check if email already sent today
        if not _should_send_email_today():
            return False, "Email already sent today"
        
        due = get_due_records(df)
        over = get_overdue_records(df)
        
        if due.empty and over.empty:
            # No urgent samples - still mark as sent to avoid repeated checks
            _mark_email_sent()
            return False, "No urgent samples found"
        
        # Send email
        success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
        
        if success:
            _mark_email_sent()
            return True, f"✅ Auto email sent at {now.strftime('%H:%M:%S')}"
        else:
            return False, msg
    
    return False, "Not time yet"


# ─────────────────────────────────────────────────────────────
#  CHARTS (Compact)
# ─────────────────────────────────────────────────────────────

def create_status_chart(df):
    counts = df['Staus'].value_counts()
    fig = go.Figure(data=[go.Pie(
        labels=counts.index, values=counts.values, hole=0.5,
        marker_colors=['#28a745', '#ffc107', '#dc3545'],
        textinfo='label+percent', textposition='outside'
    )])
    fig.update_layout(title="Status Distribution", height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def create_urgency_chart(df):
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="Samples by Urgency", height=300, margin=dict(l=20, r=20, t=40, b=20))
        return fig

    def cat(d):
        if pd.isna(d): return 'Unknown'
        if d < 0: return 'Overdue'
        if d <= 3: return 'Urgent (0-3)'
        if d <= 7: return 'Due Soon (4-7)'
        return 'On Track'

    alert_df['Cat'] = alert_df['Days Left'].apply(cat)
    counts = alert_df['Cat'].value_counts()
    cmap = {'Overdue': '#dc3545', 'Urgent (0-3)': '#ff6b6b', 'Due Soon (4-7)': '#ffc107', 'On Track': '#28a745'}
    
    fig = go.Figure(data=[go.Bar(
        x=counts.index, y=counts.values,
        marker_color=[cmap.get(c, '#6c757d') for c in counts.index],
        text=counts.values, textposition='auto'
    )])
    fig.update_layout(title="Samples by Urgency", xaxis_title="Urgency Level", 
                      yaxis_title="Count", height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig


# ─────────────────────────────────────────────────────────────
#  MAIN (Compact Dashboard)
# ─────────────────────────────────────────────────────────────

def main():
    # Compact Header
    st.markdown('<div class="main-header"><h1 style="color:white;text-align:center;">📊 Golden Sample Revalidation Tracker</h1></div>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading..."):
        df_raw = fetch_data()
        df = process_data(df_raw)
    
    if df is None or df.empty:
        st.error("No valid data available. Check: 'Validation Date', 'Staus', 'Model' | Format: DD-MM-YYYY")
        return
    
    st.session_state.df = df
    
    # Check and send auto email (ONCE PER DAY at 9 AM)
    auto_sent, auto_msg = check_and_send_auto_email(df)
    
    # ── Compact Metrics Row ──────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    total = len(df)
    ok_count = len(df[df['Staus'].str.lower() == 'ok'])
    pending_count = len(df[df['Staus'].str.lower() == 'pending'])
    ng_count = len(df[df['Staus'].str.lower() == 'ng'])
    urgent_count = len(get_due_records(df))
    overdue_count = len(get_overdue_records(df))
    
    with col1:
        st.metric("Total", total)
    with col2:
        st.metric("✅ OK", ok_count)
    with col3:
        st.metric("⏳ Pending", pending_count)
    with col4:
        st.metric("❌ NG", ng_count)
    with col5:
        st.metric("🔴 Urgent", urgent_count)
    with col6:
        st.metric("⚠️ Overdue", overdue_count, delta="ACTION!" if overdue_count > 0 else None)
    
    # Alert banners (compact)
    if overdue_count > 0:
        st.error(f"🔴 **CRITICAL:** {overdue_count} sample(s) OVERDUE!")
    if urgent_count > 0:
        st.warning(f"⚠️ **URGENT:** {urgent_count} sample(s) due within 3 days!")
    
    # ── Charts Row (Compact) ─────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(create_status_chart(df), use_container_width=True, config={'displayModeBar': False})
    with c2:
        st.plotly_chart(create_urgency_chart(df), use_container_width=True, config={'displayModeBar': False})
    
    # ── Compact Table with Filters ───────────────────────────
    st.markdown("### 📋 Details")
    
    # Filters in a single row
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        status_filter = st.multiselect("Status", ['OK', 'Pending', 'NG'], default=['OK', 'Pending', 'NG'], label_visibility="collapsed", placeholder="Status")
    with filter_col2:
        urgency_filter = st.selectbox("Urgency", ['All', 'Overdue', 'Urgent (≤3)', 'Due Soon (4-7)', 'On Track'], label_visibility="collapsed")
    with filter_col3:
        search_model = st.text_input("🔍", placeholder="Search Model...", label_visibility="collapsed")
    with filter_col4:
        sort_by = st.selectbox("Sort", ['Days Left', 'Validation Date', 'Revalidation Due', 'Model'], label_visibility="collapsed")
    
    # Apply filters
    filtered_df = df[df['Staus'].isin(status_filter)]
    if urgency_filter == 'Overdue':
        filtered_df = filtered_df[filtered_df['Days Left'] < 0]
    elif urgency_filter == 'Urgent (≤3)':
        filtered_df = filtered_df[(filtered_df['Days Left'] <= 3) & (filtered_df['Days Left'] >= 0)]
    elif urgency_filter == 'Due Soon (4-7)':
        filtered_df = filtered_df[(filtered_df['Days Left'] <= 7) & (filtered_df['Days Left'] > 3)]
    elif urgency_filter == 'On Track':
        filtered_df = filtered_df[filtered_df['Days Left'] > 7]
    
    if search_model:
        filtered_df = filtered_df[filtered_df['Model'].str.contains(search_model, case=False, na=False)]
    if sort_by in filtered_df.columns:
        filtered_df = filtered_df.sort_values(sort_by, ascending=True)
    
    # Display compact table
    display_cols = ['Model', 'Validation Date Display', 'Revalidation Due Display', 'Days Left', 'Staus', 'Incharge', 'Alert Status']
    display_df = filtered_df[[c for c in display_cols if c in filtered_df.columns]].copy().fillna('-')
    display_df['Days Left'] = display_df['Days Left'].apply(lambda x: f"{int(x)}d" if x != '-' and pd.notna(x) else '-')
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    # ── Compact Controls ─────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📥 Export CSV", use_container_width=True):
            csv = display_df.to_csv(index=False)
            st.download_button("Download", csv, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="dl")
    with col2:
        if st.button("📧 Send Alert Now", use_container_width=True):
            with st.spinner("Sending..."):
                success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
                st.success(msg) if success else st.error(msg)
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col4:
        with st.expander("⚙️ Settings"):
            st.text_input("TO:", value=st.session_state.primary_recipient, key="to_email")
            st.text_area("CC:", value="\n".join(st.session_state.cc_recipients), height=80, key="cc_emails")
            if st.button("Update Recipients"):
                st.session_state.primary_recipient = st.session_state.to_email
                st.session_state.cc_recipients = [e.strip() for e in st.session_state.cc_emails.split("\n") if e.strip()]
                st.success("Recipients updated!")
    
    # Auto-refresh
    if st.checkbox("Auto-refresh", value=True):
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
