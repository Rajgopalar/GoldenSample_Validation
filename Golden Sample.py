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

# Auto email settings - ONE EMAIL PER DAY
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
    initial_sidebar_state="collapsed"
)

# Custom CSS for compact layout
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Arial+Narrow:wght@400;700&display=swap');
    
    * {
        font-family: 'Arial Narrow', 'Arial', sans-serif !important;
    }
    
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
        padding: 5px !important;
    }
    
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 8px !important;
        border-radius: 6px;
    }
    
    div[data-testid="stMetric"] label {
        font-size: 0.85rem !important;
        font-weight: bold !important;
    }
    
    div[data-testid="stMetric"] .stMetricValue {
        font-size: 1.5rem !important;
        font-weight: bold !important;
    }
    
    .critical-alert {
        background-color: #f8d7da;
        border-left: 3px solid #dc3545;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 3px 0;
        font-size: 0.8rem;
    }
    
    .urgent-alert {
        background-color: #fff3cd;
        border-left: 3px solid #fd7e14;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 3px 0;
        font-size: 0.8rem;
    }
    
    .good-alert {
        background-color: #d4edda;
        border-left: 3px solid #28a745;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 3px 0;
        font-size: 0.8rem;
    }
    
    .stButton button {
        padding: 0.25rem 0.5rem !important;
        font-size: 0.8rem !important;
    }
    
    .stSelectbox label, .stMultiselect label, .stTextInput label {
        font-size: 0.8rem !important;
        font-weight: bold !important;
    }
    
    h3 {
        font-size: 1.1rem !important;
        margin: 0.5rem 0 !important;
        font-weight: bold !important;
    }
    
    hr {
        margin: 0.3rem 0 !important;
    }
    
    .stDataFrame {
        font-size: 0.85rem !important;
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
#  PERSISTENT STATE
# ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_sent_date": None, "last_sent_time": None}


def _save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _should_send_email_today() -> bool:
    state = _load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    return state.get("last_sent_date") != today


def _mark_email_sent():
    state = _load_state()
    now = datetime.now()
    state["last_sent_date"] = now.strftime("%Y-%m-%d")
    state["last_sent_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
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
            return '🟠 Due Soon'
        return '🟢 On Track'

    df['Alert Status'] = df.apply(get_alert_status, axis=1)
    
    # Clean data - remove rows with empty Model or Status
    df = df.dropna(subset=['Model', 'Staus'])
    df = df[df['Model'].astype(str).str.strip() != '']
    df = df[df['Staus'].astype(str).str.strip() != '']
    
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
    headers = "\\n<table>\\n<thead>\\n<tr>" + "".join(
        f"<th>{h}</th>" for h in
        ["Model", "Validation Date", "Revalidation Due", "Days Left", "Status", "Incharge", "Alert"]
    ) + "</tr>\\n</thead>\\n<tbody>"

    def make_row(row, bg, days_text, badge):
        return (f'<tr style="background-color:{bg};">'
                f'<td style="padding:6px;"><b>{row.get("Model","")}</b></td>'
                f'<td style="padding:6px;">{row.get("Validation Date Display","")}</td>'
                f'<td style="padding:6px;">{row.get("Revalidation Due Display","")}</td>'
                f'<td style="padding:6px;color:#dc3545;font-weight:bold;">{days_text}</td>'
                f'<td style="padding:6px;"><b>{row.get("Staus","")}</b></td>'
                f'<td style="padding:6px;">{row.get("Incharge","")}</td>'
                f'<td style="padding:6px;color:#dc3545;">{badge}</td>'
                f'</tr>')

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
        body{{font-family:'Arial Narrow',Arial,sans-serif;line-height:1.4;margin:0;padding:15px;}}
        .header{{background:linear-gradient(90deg,#1e3c72,#2a5298);color:white;padding:10px;text-align:center;border-radius:6px;}}
        .alert{{background:#f8d7da;border-left:3px solid #dc3545;padding:8px;margin:10px 0;border-radius:4px;font-size:12px;}}
        table{{border-collapse:collapse;width:100%;margin:10px 0;font-size:12px;}}
        th{{background:#2a5298;color:white;padding:6px;text-align:left;}}
        td{{padding:6px;border-bottom:1px solid #ddd;}}
        .footer{{margin-top:15px;padding:8px;background:#f8f9fa;text-align:center;border-radius:4px;font-size:10px;}}
        h3{{margin:8px 0;font-size:14px;}}
    </style>
</head>
<body>
    <div class="header">
        <h3 style="margin:0;">Golden Sample Revalidation Tracker</h3>
        <p style="margin:3px 0 0;font-size:11px;">🚨 URGENT ALERT: Action Required Immediately</p>
    </div>
    <div class="alert">
        <strong>⚠️ CRITICAL ALERT:</strong> {total} sample(s) require immediate attention!<br>
        • {len(overdue_records)} OVERDUE &nbsp;• {len(due_records)} due within 3 days
    </div>
    <h3>🔴 OVERDUE SAMPLES:</h3>
    <table><thead>{headers}</thead><tbody>{over_rows}</tbody></table>
    <h3>⚠️ SAMPLES DUE WITHIN 3 DAYS:</h3>
    <table><thead>{headers}</thead><tbody>{due_rows}</tbody></table>
    <div class="footer">
        <p><i>Automated alert – Golden Sample Tracker System</i><br>Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
    </div>
</body>
</html>"""


def check_and_send_auto_email(df):
    if not AUTO_EMAIL_ENABLED:
        return False, "Auto email disabled"
    
    now = datetime.now()
    if now.hour == AUTO_EMAIL_HOUR and now.minute == AUTO_EMAIL_MINUTE:
        if not _should_send_email_today():
            return False, "Email already sent today"
        
        due = get_due_records(df)
        over = get_overdue_records(df)
        
        if due.empty and over.empty:
            _mark_email_sent()
            return False, "No urgent samples found"
        
        success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
        if success:
            _mark_email_sent()
            return True, f"✅ Auto email sent at {now.strftime('%H:%M:%S')}"
        return False, msg
    
    return False, "Not time yet"


# ─────────────────────────────────────────────────────────────
#  CHARTS (Compressed)
# ─────────────────────────────────────────────────────────────

def create_status_chart(df):
    counts = df['Staus'].value_counts()
    
    # Colors: Dark Red for NG, Green for OK, Orange for Pending
    color_map = {
        'OK': '#28a745',      # Green
        'Pending': '#fd7e14', # Orange
        'NG': '#8B0000'       # Dark Red
    }
    colors = [color_map.get(status, '#6c757d') for status in counts.index]
    
    fig = go.Figure(data=[go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.5,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='outside',
        textfont=dict(family='Arial Narrow', size=12, weight='bold'),
        insidetextfont=dict(size=12, weight='bold'),
        showlegend=False
    )])
    
    fig.update_layout(
        title=dict(text="Status Distribution", font=dict(family='Arial Narrow', size=14, weight='bold')),
        height=280,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    return fig


def create_urgency_chart(df):
    # Filter non-OK samples
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False,
                          font=dict(family='Arial Narrow', size=12))
        fig.update_layout(
            title=dict(text="Samples by Urgency", font=dict(family='Arial Narrow', size=14, weight='bold')),
            height=280,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        return fig

    def cat(d):
        if pd.isna(d):
            return 'Unknown'
        if d < 0:
            return 'Overdue'
        if d <= 3:
            return 'Urgent (0-3)'
        if d <= 7:
            return 'Due Soon (4-7)'
        return 'On Track'

    alert_df['Category'] = alert_df['Days Left'].apply(cat)
    counts = alert_df['Category'].value_counts()
    
    # Colors for urgency
    color_map = {
        'Overdue': '#8B0000',      # Dark Red
        'Urgent (0-3)': '#fd7e14', # Orange
        'Due Soon (4-7)': '#17a2b8', # Blue
        'On Track': '#28a745',     # Green
        'Unknown': '#6c757d'
    }
    
    colors = [color_map.get(cat, '#6c757d') for cat in counts.index]
    
    fig = go.Figure(data=[go.Bar(
        x=counts.index,
        y=counts.values,
        marker_color=colors,
        text=counts.values,
        textposition='auto',
        textfont=dict(family='Arial Narrow', size=12, weight='bold')
    )])
    
    fig.update_layout(
        title=dict(text="Samples by Urgency", font=dict(family='Arial Narrow', size=14, weight='bold')),
        xaxis=dict(title="", tickfont=dict(family='Arial Narrow', size=11)),
        yaxis=dict(title="Count", title_font=dict(family='Arial Narrow', size=11, weight='bold'), 
                   tickfont=dict(family='Arial Narrow', size=11)),
        height=280,
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=30)
    )
    return fig


# ─────────────────────────────────────────────────────────────
#  MAIN (Compressed Layout)
# ─────────────────────────────────────────────────────────────

def main():
    # Compact Header
    st.markdown('<div class="main-header"><h1 style="text-align:center;">📊 Golden Sample Revalidation Tracker</h1></div>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading..."):
        df_raw = fetch_data()
        df = process_data(df_raw)
    
    if df is None or df.empty:
        st.error("No valid data available.")
        st.info("Required: 'Validation Date', 'Staus', 'Model' | Format: DD-MM-YYYY")
        return
    
    st.session_state.df = df
    
    # Check auto email
    auto_sent, auto_msg = check_and_send_auto_email(df)
    if auto_sent:
        st.toast(auto_msg, icon="✅")
    
    # Compact Metrics Row
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
        st.metric("⚠️ Overdue", overdue_count)
    
    # Left: Charts, Right: Table
    col_left, col_right = st.columns([0.4, 0.6])
    
    with col_left:
        # Donut Chart on top
        st.plotly_chart(create_status_chart(df), use_container_width=True, config={'displayModeBar': False})
        # Bar Chart below
        st.plotly_chart(create_urgency_chart(df), use_container_width=True, config={'displayModeBar': False})
    
    with col_right:
        st.markdown("### 📋 Golden Sample Details")
        
        # Compact Filters Row (No Sort option)
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            status_filter = st.multiselect(
                "Status", 
                options=['OK', 'Pending', 'NG'], 
                default=['OK', 'Pending', 'NG'],
                key="status_filter"
            )
        with col_f2:
            urgency_filter = st.selectbox(
                "Urgency",
                options=['All', 'Overdue', 'Urgent (0-3)', 'Due Soon (4-7)', 'On Track'],
                key="urgency_filter"
            )
        with col_f3:
            search_model = st.text_input("🔍 Search Model", placeholder="Enter model name...", key="search_model")
        
        # Apply filters
        filtered_df = df[df['Staus'].isin(status_filter)]
        
        # Apply urgency filter
        if urgency_filter == 'Overdue':
            filtered_df = filtered_df[filtered_df['Days Left'] < 0]
        elif urgency_filter == 'Urgent (0-3)':
            filtered_df = filtered_df[(filtered_df['Days Left'] <= 3) & (filtered_df['Days Left'] >= 0)]
        elif urgency_filter == 'Due Soon (4-7)':
            filtered_df = filtered_df[(filtered_df['Days Left'] <= 7) & (filtered_df['Days Left'] > 3)]
        elif urgency_filter == 'On Track':
            filtered_df = filtered_df[filtered_df['Days Left'] > 7]
        
        if search_model:
            filtered_df = filtered_df[filtered_df['Model'].str.contains(search_model, case=False, na=False)]
        
        # Remove any remaining blank rows
        filtered_df = filtered_df.dropna(subset=['Model', 'Staus'])
        filtered_df = filtered_df[filtered_df['Model'].astype(str).str.strip() != '']
        filtered_df = filtered_df[filtered_df['Staus'].astype(str).str.strip() != '']
        
        # Display table
        display_cols = ['Model', 'Validation Date Display', 'Revalidation Due Display', 
                        'Days Left', 'Staus', 'Incharge', 'Alert Status']
        
        available_cols = [col for col in display_cols if col in filtered_df.columns]
        display_df = filtered_df[available_cols].copy()
        display_df = display_df.fillna('-')
        
        # Format Days Left
        display_df['Days Left'] = display_df['Days Left'].apply(
            lambda x: f"{int(x)}d" if x != '-' and pd.notna(x) and x != '-' else '-'
        )
        
        # Color function for status - Dark Red for NG, Green for OK, Orange for Pending
        def color_status(val):
            if val in ['OK', 'Ok', 'ok']:
                return 'background-color: #28a745; color: white; font-weight: bold'
            elif val in ['Pending', 'pending']:
                return 'background-color: #fd7e14; color: white; font-weight: bold'
            elif val in ['NG', 'Ng', 'ng']:
                return 'background-color: #8B0000; color: white; font-weight: bold'
            return ''
        
        # Apply styling
        styled_df = display_df.style.applymap(color_status, subset=['Staus'])
        
        # Highlight days left
        def highlight_days(val):
            if val != '-' and 'd' in str(val):
                try:
                    days = int(str(val).replace('d', ''))
                    if days < 0:
                        return 'background-color: #8B0000; color: white; font-weight: bold'
                    elif days <= 3:
                        return 'background-color: #fd7e14; color: white; font-weight: bold'
                except:
                    pass
            return ''
        
        styled_df = styled_df.applymap(highlight_days, subset=['Days Left'])
        
        st.dataframe(styled_df, use_container_width=True, height=450)
        
        # Compact Alerts below table
        col_alert1, col_alert2 = st.columns(2)
        with col_alert1:
            if overdue_count > 0:
                st.markdown(f'<div class="critical-alert">🔴 <strong>CRITICAL:</strong> {overdue_count} sample(s) OVERDUE!</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="good-alert">✅ No overdue samples</div>', unsafe_allow_html=True)
        with col_alert2:
            if urgent_count > 0:
                st.markdown(f'<div class="urgent-alert">⚠️ <strong>URGENT:</strong> {urgent_count} sample(s) due within 3 days!</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="good-alert">✅ No urgent samples</div>', unsafe_allow_html=True)
        
        # Action Buttons
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        with col_b1:
            if st.button("📥 Export CSV", use_container_width=True):
                csv = display_df.to_csv(index=False)
                st.download_button("Download", csv, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="dl")
        with col_b2:
            if st.button("📧 Send Alert", use_container_width=True):
                with st.spinner("Sending..."):
                    success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        with col_b3:
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        with col_b4:
            with st.expander("⚙️ Settings"):
                st.text_input("TO Email:", value=st.session_state.primary_recipient, key="to_set")
                st.text_area("CC Emails:", value="\n".join(st.session_state.cc_recipients), height=80, key="cc_set")
                if st.button("Update Recipients"):
                    st.session_state.primary_recipient = st.session_state.to_set
                    st.session_state.cc_recipients = [e.strip() for e in st.session_state.cc_set.split("\n") if e.strip()]
                    st.success("Recipients updated!")

if __name__ == "__main__":
    main()
