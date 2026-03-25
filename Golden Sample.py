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

# Auto email settings
AUTO_EMAIL_HOUR = 9
AUTO_EMAIL_MINUTE = 0
AUTO_EMAIL_ENABLED = True

# Persistent state file
STATE_FILE = "/tmp/golden_sample_email_state.json"
# ===================================

st.set_page_config(
    page_title="Golden Sample Tracker",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Professional CSS Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0.8rem 2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        font-size: 1.5rem !important;
        margin: 0 !important;
        padding: 0 !important;
        font-weight: 600 !important;
    }
    
    /* Metric Cards - Compact */
    .metric-card {
        background: white;
        padding: 0.6rem;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        text-align: center;
        transition: all 0.2s;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }
    
    .metric-label {
        font-size: 0.7rem;
        color: #6c757d;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    
    .alert-success {
        background: linear-gradient(135deg, #f0fdf4 0%, #f3fef7 100%);
        border-left: 3px solid #10b981;
        padding: 0.5rem 0.8rem;
        border-radius: 6px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* Control Bar */
    .control-bar {
        background: #f8f9fa;
        padding: 0.8rem 1rem;
        border-radius: 10px;
        margin: 0.5rem 0 1rem 0;
        border: 1px solid #e9ecef;
    }
    
    .stButton button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.8rem !important;
        transition: all 0.2s !important;
    }
    
    .stSelectbox label, .stTextInput label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.2rem !important;
    }
    
    .stSelectbox, .stTextInput {
        font-size: 0.85rem !important;
    }
    
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e9ecef;
        margin-top: 0.5rem;
    }
    
    .chart-container {
        background: white;
        padding: 0.5rem;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 0.5rem;
    }
    
    hr {
        margin: 0.5rem 0;
        border-color: #e9ecef;
    }
    
    /* Section Title */
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0.5rem 0;
        color: #1f2937;
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
        df = pd.read_csv(CSV_URL)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None


def process_data(df):
    if df is None:
        return None
    df = df.copy()
    df.columns = df.columns.str.strip()

    required_cols = ['Validation Date', 'Staus', 'Model']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            return None

    # Parse dates
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
        s = str(row.get('Staus', '')).lower().strip()
        
        if pd.isna(d):
            return 'Unknown'
        if s == 'ok':
            return 'Completed'
        if d < 0:
            return 'Overdue'
        if d <= 3:
            return 'Urgent'
        if d <= 7:
            return 'Due Soon'
        return 'On Track'

    df['Alert Status'] = df.apply(get_alert_status, axis=1)
    
    # Clean data
    df = df.dropna(subset=['Model', 'Staus', 'Validation Date Display'])
    df = df[df['Model'].astype(str).str.strip() != '']
    df = df[df['Staus'].astype(str).str.strip() != '']
    
    # Standardize status
    df['Staus'] = df['Staus'].astype(str).str.strip().str.capitalize()
    
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
        msg['Subject'] = f"🚨 Golden Sample Alert: {total} Sample(s) Need Attention"
        msg.attach(MIMEText(email_body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        return True, f"Alert sent to {primary_recipient} and {len(cc_list)} CC(s)"
    except Exception as e:
        return False, f"Email failed: {e}"


def generate_email_html(due_records, overdue_records):
    headers = "\\n<table>\\n<thead>\\n<tr>" + "".join(f"<th style='padding:8px;background:#667eea;color:white;'>{h}</th>" for h in
        ["Model", "Validation Date", "Revalidation Due", "Days Left", "Status", "Incharge", "Alert"]) + "</tr>\\n</thead>\\n<tbody>"

    def make_row(row, bg, days_text, badge):
        return f'<tr style="background-color:{bg};">' + ''.join([
            f'<td style="padding:6px;"><b>{row.get("Model","")}</b>\\n</td>',
            f'<td style="padding:6px;">{row.get("Validation Date Display","")}\\n</td>',
            f'<td style="padding:6px;">{row.get("Revalidation Due Display","")}\\n</td>',
            f'<td style="padding:6px;color:#dc3545;">{days_text}\\n</td>',
            f'<td style="padding:6px;"><b>{row.get("Staus","")}</b>\\n</td>',
            f'<td style="padding:6px;">{row.get("Incharge","")}\\n</td>',
            f'<td style="padding:6px;color:#dc3545;">{badge}\\n</td>',
        ]) + '</tr>'

    over_rows = "".join(make_row(r, "#fef3f2", f"{abs(int(r['Days Left']))}d overdue", "🔴 OVERDUE") 
                        for _, r in overdue_records.iterrows()) if not overdue_records.empty else '<tr><td colspan="7">None</td></tr>'
    due_rows = "".join(make_row(r, "#fffbeb", f"{int(r['Days Left'])}d", "⚠️ URGENT") 
                       for _, r in due_records.iterrows()) if not due_records.empty else '<tr><td colspan="7">None</td></tr>'

    total = len(due_records) + len(overdue_records)

    return f"""<html>
<head><style>
    body{{font-family:'Inter',sans-serif;margin:0;padding:15px;background:#f8fafc;}}
    .header{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:12px;text-align:center;border-radius:10px;}}
    .alert{{background:#fef3f2;border-left:3px solid #dc2626;padding:8px;margin:10px 0;border-radius:6px;font-size:12px;}}
    table{{border-collapse:collapse;width:100%;margin:10px 0;border-radius:8px;overflow:hidden;}}
    th{{background:#667eea;color:white;padding:8px;}}
    td{{padding:6px;border-bottom:1px solid #e2e8f0;font-size:12px;}}
    .footer{{margin-top:12px;padding:8px;background:#f1f5f9;text-align:center;border-radius:6px;font-size:10px;}}
</style></head>
<body>
    <div class="header"><h3>Golden Sample Tracker</h3><p>🚨 Urgent Action Required</p></div>
    <div class="alert"><strong>⚠️ Alert:</strong> {total} sample(s) need attention!<br>• {len(overdue_records)} Overdue • {len(due_records)} Due within 3 days</div>
    <h3>🔴 Overdue Samples</h3>{headers}{over_rows}</tbody></table>
    <h3>⚠️ Samples Due Within 3 Days</h3>{headers}{due_rows}</tbody></table>
    <div class="footer"><p>Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p></div>
</body></html>"""


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
            return False, "No urgent samples"
        
        success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
        if success:
            _mark_email_sent()
            return True, f"✅ Auto email sent"
        return False, msg
    
    return False, ""


# ─────────────────────────────────────────────────────────────
#  CHARTS
# ─────────────────────────────────────────────────────────────

def create_status_chart(df):
    if df.empty:
        fig = go.Figure()
        fig.update_layout(height=240, margin=dict(l=10, r=10, t=30, b=10))
        return fig
    
    counts = df['Staus'].value_counts()
    
    colors = []
    for status in counts.index:
        if status.lower() == 'ok':
            colors.append('#10b981')
        elif status.lower() == 'pending':
            colors.append('#f59e0b')
        elif status.lower() == 'ng':
            colors.append('#ef4444')
        else:
            colors.append('#6b7280')
    
    fig = go.Figure(data=[go.Pie(
        labels=counts.index.tolist(),
        values=counts.values.tolist(),
        hole=0.55,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='outside',
        textfont=dict(family='Inter', size=10),
        hoverinfo='label+value'
    )])
    
    fig.update_layout(
        title=dict(text="Status Distribution", font=dict(family='Inter', size=12, weight='bold')),
        height=240,
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def create_urgency_chart(df):
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False,
                          font=dict(family='Inter', size=10))
        fig.update_layout(height=240, margin=dict(l=10, r=10, t=30, b=10))
        return fig

    def cat(d):
        if pd.isna(d): return 'Unknown'
        if d < 0: return 'Overdue'
        if d <= 3: return 'Urgent (0-3)'
        if d <= 7: return 'Due Soon (4-7)'
        return 'On Track'

    alert_df['Category'] = alert_df['Days Left'].apply(cat)
    counts = alert_df['Category'].value_counts()
    
    colors = {'Overdue': '#ef4444', 'Urgent (0-3)': '#f59e0b', 
              'Due Soon (4-7)': '#3b82f6', 'On Track': '#10b981'}
    
    fig = go.Figure(data=[go.Bar(
        x=counts.index.tolist(),
        y=counts.values.tolist(),
        marker_color=[colors.get(cat, '#6b7280') for cat in counts.index],
        text=counts.values.tolist(),
        textposition='auto',
        textfont=dict(family='Inter', size=10)
    )])
    
    fig.update_layout(
        title=dict(text="Samples by Urgency", font=dict(family='Inter', size=12, weight='bold')),
        xaxis=dict(title="", tickfont=dict(family='Inter', size=9)),
        yaxis=dict(title="Count", title_font=dict(family='Inter', size=10), tickfont=dict(family='Inter', size=9)),
        height=240,
        showlegend=False,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    # Header
    st.markdown('<div class="main-header"><h1 style="color:white;">🏭 Golden Sample Revalidation Tracker</h1></div>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading data..."):
        df_raw = fetch_data()
        df = process_data(df_raw)
    
    if df is None or df.empty:
        st.error("No valid data available.")
        st.info("Required: 'Validation Date', 'Staus', 'Model' | Format: DD-MM-YYYY")
        return
    
    st.session_state.df = df
    
    # Auto email check
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
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Total</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#10b981;">{ok_count}</div><div class="metric-label">✅ OK</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f59e0b;">{pending_count}</div><div class="metric-label">⏳ Pending</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#ef4444;">{ng_count}</div><div class="metric-label">❌ NG</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#ef4444;">{urgent_count}</div><div class="metric-label">🔴 Urgent</div></div>', unsafe_allow_html=True)
    with col6:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#dc2626;">{overdue_count}</div><div class="metric-label">⚠️ Overdue</div></div>', unsafe_allow_html=True)
    
    # Charts Row (Compact)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.plotly_chart(create_status_chart(df), use_container_width=True, config={'displayModeBar': False})
    with col_chart2:
        st.plotly_chart(create_urgency_chart(df), use_container_width=True, config={'displayModeBar': False})
    
    # Control Bar - Filters, Search, Export on Top
    st.markdown("### 📋 Sample Details")
    
    # Control Row (Top)
    control_cols = st.columns([1.5, 1.5, 2, 1, 1, 1])
    
    with control_cols[0]:
        # Changed from multiselect to selectbox (dropdown)
        status_filter = st.selectbox(
            "Status",
            options=['All', 'Ok', 'Pending', 'Ng'],
            index=0,
            key="status_filter"
        )
    
    with control_cols[1]:
        urgency_filter = st.selectbox(
            "Urgency",
            options=['All', 'Overdue', 'Urgent', 'Due Soon', 'On Track'],
            key="urgency_filter"
        )
    
    with control_cols[2]:
        search_model = st.text_input("🔍 Search Model", placeholder="Enter model name...", key="search_model")
    
    with control_cols[3]:
        if st.button("📥 Export CSV", use_container_width=True, key="export_btn"):
            csv = df.to_csv(index=False)
            st.download_button("Download", csv, f"report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", key="download_btn")
    
    with control_cols[4]:
        if st.button("📧 Send Alert", use_container_width=True, key="alert_btn"):
            with st.spinner("Sending..."):
                success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
    
    with control_cols[5]:
        if st.button("🔄 Refresh", use_container_width=True, key="refresh_btn"):
            st.cache_data.clear()
            st.rerun()
  
    # Apply filters
    if status_filter == 'All':
        filtered_df = df.copy()
    else:
        filtered_df = df[df['Staus'] == status_filter]
    
    if urgency_filter == 'Overdue':
        filtered_df = filtered_df[filtered_df['Days Left'] < 0]
    elif urgency_filter == 'Urgent':
        filtered_df = filtered_df[(filtered_df['Days Left'] <= 3) & (filtered_df['Days Left'] >= 0)]
    elif urgency_filter == 'Due Soon':
        filtered_df = filtered_df[(filtered_df['Days Left'] <= 7) & (filtered_df['Days Left'] > 3)]
    elif urgency_filter == 'On Track':
        filtered_df = filtered_df[filtered_df['Days Left'] > 7]
    
    if search_model:
        filtered_df = filtered_df[filtered_df['Model'].str.contains(search_model, case=False, na=False)]
    
    # Clean data
    filtered_df = filtered_df.dropna(subset=['Model', 'Staus'])
    filtered_df = filtered_df[filtered_df['Model'].astype(str).str.strip() != '']
    
    # Display table with NG showing blank for Days Left
    display_df = filtered_df[['Model', 'Validation Date Display', 'Revalidation Due Display', 'Days Left', 'Staus', 'Incharge', 'Alert Status']].copy()
    display_df = display_df.fillna('-')
    
    # For NG status, set Days Left to blank
    def format_days_left(row):
        if row['Staus'].lower() == 'ng':
            return '-'
        elif row['Days Left'] != '-' and pd.notna(row['Days Left']):
            return f"{int(row['Days Left'])}d"
        return '-'
    
    display_df['Days Left'] = display_df.apply(format_days_left, axis=1)
    
    # Styling function
    def style_status(val):
        if val.lower() == 'ok':
            return 'background-color: #d1fae5; color: #065f46; font-weight: 600; border-radius: 20px; padding: 2px 8px; display: inline-block;'
        elif val.lower() == 'pending':
            return 'background-color: #fed7aa; color: #92400e; font-weight: 600; border-radius: 20px; padding: 2px 8px; display: inline-block;'
        elif val.lower() == 'ng':
            return 'background-color: #fee2e2; color: #991b1b; font-weight: 600; border-radius: 20px; padding: 2px 8px; display: inline-block;'
        return ''
    
    def style_days(val):
        if val != '-':
            try:
                days = int(val.replace('d', ''))
                if days < 0:
                    return 'background-color: #fee2e2; color: #991b1b; font-weight: 600;'
                elif days <= 3:
                    return 'background-color: #fed7aa; color: #92400e; font-weight: 600;'
            except:
                pass
        return ''
    
    # Apply styling
    styled_df = display_df.style.applymap(style_status, subset=['Staus'])
    styled_df = styled_df.applymap(style_days, subset=['Days Left'])
    
    # Table with shortened height
    st.dataframe(styled_df, use_container_width=True, height=400)
    
    # Settings Expander
    with st.expander("⚙️ Email Settings"):
        col_set1, col_set2 = st.columns(2)
        with col_set1:
            new_primary = st.text_input("Primary Recipient (TO)", value=st.session_state.primary_recipient)
            if new_primary != st.session_state.primary_recipient:
                st.session_state.primary_recipient = new_primary
        with col_set2:
            cc_text = st.text_area("CC Recipients (one per line)", value="\n".join(st.session_state.cc_recipients), height=80)
            if st.button("💾 Save Settings"):
                st.session_state.cc_recipients = [e.strip() for e in cc_text.split("\n") if e.strip()]
                st.success("Settings saved!")

if __name__ == "__main__":
    main()
