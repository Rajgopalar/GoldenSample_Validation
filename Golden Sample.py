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
        padding: 1rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        font-size: 1.8rem !important;
        margin: 0 !important;
        padding: 0 !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px;
    }
    
    /* Metric Cards */
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        transition: all 0.2s;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Filter Section */
    .filter-section {
        background: #f8f9fa;
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid #e9ecef;
    }
    
    /* Alert Banners */
    .alert-critical {
        background: linear-gradient(135deg, #fef3f2 0%, #fff5f5 100%);
        border-left: 4px solid #dc2626;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .alert-urgent {
        background: linear-gradient(135deg, #fffbeb 0%, #fff9e6 100%);
        border-left: 4px solid #f59e0b;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .alert-success {
        background: linear-gradient(135deg, #f0fdf4 0%, #f3fef7 100%);
        border-left: 4px solid #10b981;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.4rem 1rem !important;
        transition: all 0.2s !important;
    }
    
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    /* Table Styling */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e9ecef;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-align: center;
    }
    
    /* Chart Containers */
    .chart-container {
        background: white;
        padding: 0.75rem;
        border-radius: 12px;
        border: 1px solid #e9ecef;
        margin-bottom: 1rem;
    }
    
    /* Divider */
    hr {
        margin: 1rem 0;
        border-color: #e9ecef;
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
    headers = "<tr>" + "".join(f"<th style='padding:10px;background:#667eea;color:white;'>{h}</th>" for h in
        ["Model", "Validation Date", "Revalidation Due", "Days Left", "Status", "Incharge", "Alert"]) + "</tr>"

    def make_row(row, bg, days_text, badge):
        return f'<tr style="background-color:{bg};">' + ''.join([
            f'<td style="padding:8px;"><b>{row.get("Model","")}</b></td>',
            f'<td style="padding:8px;">{row.get("Validation Date Display","")}</td>',
            f'<td style="padding:8px;">{row.get("Revalidation Due Display","")}</td>',
            f'<td style="padding:8px;color:#dc3545;">{days_text}</td>',
            f'<td style="padding:8px;"><b>{row.get("Staus","")}</b></td>',
            f'<td style="padding:8px;">{row.get("Incharge","")}</td>',
            f'<td style="padding:8px;color:#dc3545;">{badge}</td>',
        ]) + '</tr>'

    over_rows = "".join(make_row(r, "#fef3f2", f"{abs(int(r['Days Left']))}d overdue", "🔴 OVERDUE") 
                        for _, r in overdue_records.iterrows()) if not overdue_records.empty else '<tr><td colspan="7">None</td></tr>'
    due_rows = "".join(make_row(r, "#fffbeb", f"{int(r['Days Left'])}d", "⚠️ URGENT") 
                       for _, r in due_records.iterrows()) if not due_records.empty else '<tr><td colspan="7">None</td></tr>'

    total = len(due_records) + len(overdue_records)

    return f"""<html>
<head><style>
    body{{font-family:'Inter',sans-serif;margin:0;padding:20px;background:#f8fafc;}}
    .header{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px;text-align:center;border-radius:12px;}}
    .alert{{background:#fef3f2;border-left:4px solid #dc2626;padding:12px;margin:15px 0;border-radius:8px;}}
    table{{border-collapse:collapse;width:100%;margin:15px 0;border-radius:8px;overflow:hidden;}}
    th{{background:#667eea;color:white;padding:10px;}}
    td{{padding:8px;border-bottom:1px solid #e2e8f0;}}
    .footer{{margin-top:20px;padding:12px;background:#f1f5f9;text-align:center;border-radius:8px;}}
</style></head>
<body>
    <div class="header"><h2>Golden Sample Tracker</h2><p>🚨 Urgent Action Required</p></div>
    <div class="alert"><strong>⚠️ Alert:</strong> {total} sample(s) need attention!<br>• {len(overdue_records)} Overdue • {len(due_records)} Due within 3 days</div>
    <h3>🔴 Overdue Samples</h3><table><thead>{headers}</thead><tbody>{over_rows}</tbody></table>
    <h3>⚠️ Samples Due Within 3 Days</h3><table><thead>{headers}</thead><tbody>{due_rows}</tbody></table>
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
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
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
        textfont=dict(family='Inter', size=11),
        hoverinfo='label+value'
    )])
    
    fig.update_layout(
        title=dict(text="Status Distribution", font=dict(family='Inter', size=14, weight='bold')),
        height=280,
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def create_urgency_chart(df):
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False,
                          font=dict(family='Inter', size=12))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
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
        textfont=dict(family='Inter', size=11)
    )])
    
    fig.update_layout(
        title=dict(text="Samples by Urgency", font=dict(family='Inter', size=14, weight='bold')),
        xaxis=dict(title="", tickfont=dict(family='Inter', size=10)),
        yaxis=dict(title="Count", title_font=dict(family='Inter', size=11), tickfont=dict(family='Inter', size=10)),
        height=280,
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=30),
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
    
    # Metrics Row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    total = len(df)
    ok_count = len(df[df['Staus'].str.lower() == 'ok'])
    pending_count = len(df[df['Staus'].str.lower() == 'pending'])
    ng_count = len(df[df['Staus'].str.lower() == 'ng'])
    urgent_count = len(get_due_records(df))
    overdue_count = len(get_overdue_records(df))
    
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Total Samples</div></div>', unsafe_allow_html=True)
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
    
    # Alerts
    if overdue_count > 0:
        st.markdown(f'<div class="alert-critical">🔴 <strong>Critical Alert:</strong> {overdue_count} sample(s) are OVERDUE for revalidation!</div>', unsafe_allow_html=True)
    if urgent_count > 0:
        st.markdown(f'<div class="alert-urgent">⚠️ <strong>Urgent Alert:</strong> {urgent_count} sample(s) require revalidation within 3 days!</div>', unsafe_allow_html=True)
    
    # Charts Row
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        with st.container():
            st.plotly_chart(create_status_chart(df), use_container_width=True, config={'displayModeBar': False})
    with col_chart2:
        with st.container():
            st.plotly_chart(create_urgency_chart(df), use_container_width=True, config={'displayModeBar': False})
    
    # Table Section with Minimized Filters
    st.markdown("### 📋 Sample Details")
    
    # Compact Filter Bar - Minimized Status Filter
    filter_cols = st.columns([2, 2, 2, 1, 1, 1])
    
    with filter_cols[0]:
        status_filter = st.multiselect(
            "Status",
            options=['Ok', 'Pending', 'Ng'],
            default=['Ok', 'Pending', 'Ng'],
            key="status_filter"
        )
    
    with filter_cols[1]:
        urgency_filter = st.selectbox(
            "Urgency",
            options=['All', 'Overdue', 'Urgent', 'Due Soon', 'On Track'],
            key="urgency_filter"
        )
    
    with filter_cols[2]:
        search_model = st.text_input("🔍 Search", placeholder="Model...", key="search_model")
    
    with filter_cols[3]:
        if st.button("📥 Export", use_container_width=True):
            csv = df.to_csv(index=False)
            st.download_button("Download", csv, f"report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", key="dl")
    
    with filter_cols[4]:
        if st.button("📧 Alert", use_container_width=True):
            with st.spinner("Sending..."):
                success, msg = send_email_alert(df, st.session_state.primary_recipient, st.session_state.cc_recipients)
                st.success(msg) if success else st.error(msg)
    
    with filter_cols[5]:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Apply filters
    filtered_df = df[df['Staus'].isin(status_filter)]
    
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
    
    # Display table
    display_df = filtered_df[['Model', 'Validation Date Display', 'Revalidation Due Display', 'Days Left', 'Staus', 'Incharge', 'Alert Status']].copy()
    display_df = display_df.fillna('-')
    display_df['Days Left'] = display_df['Days Left'].apply(lambda x: f"{int(x)}d" if x != '-' and pd.notna(x) else '-')
    
    # Styling function
    def style_status(val):
        if val.lower() == 'ok':
            return 'background-color: #d1fae5; color: #065f46; font-weight: 600; border-radius: 20px; padding: 2px 8px;'
        elif val.lower() == 'pending':
            return 'background-color: #fed7aa; color: #92400e; font-weight: 600; border-radius: 20px; padding: 2px 8px;'
        elif val.lower() == 'ng':
            return 'background-color: #fee2e2; color: #991b1b; font-weight: 600; border-radius: 20px; padding: 2px 8px;'
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
    
    styled_df = display_df.style.applymap(style_status, subset=['Staus'])
    styled_df = styled_df.applymap(style_days, subset=['Days Left'])
    
    st.dataframe(styled_df, use_container_width=True, height=400)
    
    # Settings Expander
    with st.expander("⚙️ Email Settings"):
        col_set1, col_set2 = st.columns(2)
        with col_set1:
            new_primary = st.text_input("Primary Recipient (TO)", value=st.session_state.primary_recipient)
            if new_primary != st.session_state.primary_recipient:
                st.session_state.primary_recipient = new_primary
        with col_set2:
            cc_text = st.text_area("CC Recipients", value="\n".join(st.session_state.cc_recipients), height=80)
            if st.button("💾 Save Settings"):
                st.session_state.cc_recipients = [e.strip() for e in cc_text.split("\n") if e.strip()]
                st.success("Settings saved!")

if __name__ == "__main__":
    main()
