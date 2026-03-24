import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import plotly.graph_objects as go
import warnings
import time
import threading
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

# Auto email settings
AUTO_EMAIL_HOUR = 09
AUTO_EMAIL_MINUTE = 00
# Fires if current time is within +/- this many minutes of target (handles restarts)
AUTO_EMAIL_WINDOW_MINUTES = 10
AUTO_EMAIL_ENABLED = True

# Persistent state file — survives thread/process restarts on Streamlit Cloud
STATE_FILE = "/tmp/golden_sample_email_state.json"
SENT_FLAG_FILE = "/tmp/golden_sample_sent_flag.json"
# ===================================

st.set_page_config(
    page_title="Golden Sample Revalidation Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72, #2a5298);
        padding: 1rem; border-radius: 10px; margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
#  PERSISTENT STATE WITH DEDUPLICATION
# ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load persistent state with deduplication tracking"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "last_sent_date": None, 
        "last_sent_time": None, 
        "last_result": "",
        "sent_emails": []  # Track sent emails with timestamps
    }


def _save_state(state: dict):
    """Save persistent state"""
    try:
        # Keep only last 10 sent emails for tracking
        if "sent_emails" in state and len(state["sent_emails"]) > 10:
            state["sent_emails"] = state["sent_emails"][-10:]
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _get_email_hash(df) -> str:
    """Create a unique hash for the current data to prevent duplicate sends"""
    due_records = get_due_records(df)
    overdue_records = get_overdue_records(df)
    
    # Create a hash based on the records that need attention
    if due_records.empty and overdue_records.empty:
        return None
    
    # Combine the data into a string for hashing
    data_string = ""
    for _, row in due_records.iterrows():
        data_string += f"{row.get('Model', '')}_{row.get('Days Left', 0)}_{row.get('Staus', '')}"
    for _, row in overdue_records.iterrows():
        data_string += f"{row.get('Model', '')}_{row.get('Days Left', 0)}_{row.get('Staus', '')}"
    
    return hashlib.md5(data_string.encode()).hexdigest()


def _already_sent_for_data(df) -> bool:
    """Check if email with same data has already been sent today"""
    state = _load_state()
    current_hash = _get_email_hash(df)
    
    if not current_hash:
        return False
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if this hash was sent today
    for sent in state.get("sent_emails", []):
        if (sent.get("hash") == current_hash and 
            sent.get("date") == today):
            return True
    
    return False


def _mark_email_sent(df, success: bool, message: str):
    """Mark that an email has been sent for the current data"""
    state = _load_state()
    current_hash = _get_email_hash(df)
    
    if not current_hash:
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Add to sent emails list
    if "sent_emails" not in state:
        state["sent_emails"] = []
    
    # Check if already exists (prevent duplicates)
    existing = False
    for sent in state["sent_emails"]:
        if sent.get("hash") == current_hash and sent.get("date") == today:
            existing = True
            break
    
    if not existing:
        state["sent_emails"].append({
            "hash": current_hash,
            "date": today,
            "time": now_str,
            "success": success,
            "message": message
        })
    
    # Update last sent info
    state["last_sent_date"] = today
    state["last_sent_time"] = now_str
    state["last_result"] = f"{'✅' if success else '❌'} Auto email sent at {now_str}" if success else f"❌ Failed: {message}"
    
    _save_state(state)


def _is_in_send_window() -> bool:
    """True if current time is within AUTO_EMAIL_WINDOW_MINUTES of target time."""
    now = datetime.now()
    target = now.replace(
        hour=AUTO_EMAIL_HOUR, minute=AUTO_EMAIL_MINUTE,
        second=0, microsecond=0
    )
    diff_minutes = abs((now - target).total_seconds() / 60)
    return diff_minutes <= AUTO_EMAIL_WINDOW_MINUTES


def _already_sent_today() -> bool:
    """Check if any email was sent today (regardless of data)"""
    state = _load_state()
    last_sent_date = state.get("last_sent_date")
    if not last_sent_date:
        return False
    try:
        return datetime.strptime(last_sent_date, "%Y-%m-%d").date() == datetime.now().date()
    except Exception:
        return False


def check_and_trigger_auto_email(df):
    """
    Called on EVERY page load/rerun.
    Sends auto email if: enabled + in time window + not sent for current data.
    Returns (sent: bool, message: str)
    """
    if not AUTO_EMAIL_ENABLED:
        return False, ""
    if not _is_in_send_window():
        return False, ""
    
    # Check if already sent for this data
    if _already_sent_for_data(df):
        return False, "Already sent for current data"
    
    due = get_due_records(df)
    over = get_overdue_records(df)

    if due.empty and over.empty:
        # No urgent samples, mark as sent to avoid repeated checks
        _mark_email_sent(df, False, "No urgent samples")
        return False, "No urgent samples"

    # Send email
    success, msg = _send_email(df, PRIMARY_RECIPIENT, CC_RECIPIENTS, "auto")
    
    # Mark as sent
    _mark_email_sent(df, success, msg)
    
    return success, msg


# ─────────────────────────────────────────────────────────────
#  BACKGROUND THREAD (with deduplication)
# ─────────────────────────────────────────────────────────────

_thread_started = {"value": False}
_last_thread_check = {"timestamp": None}


def _background_scheduler():
    """Background thread with deduplication to prevent multiple sends"""
    while True:
        try:
            if AUTO_EMAIL_ENABLED and _is_in_send_window():
                # Check if we already processed recently (within last 2 minutes)
                current_time = time.time()
                if _last_thread_check["timestamp"] and (current_time - _last_thread_check["timestamp"]) < 120:
                    time.sleep(60)
                    continue
                
                _last_thread_check["timestamp"] = current_time
                
                # Fetch fresh data
                df_raw = pd.read_csv(CSV_URL)
                df_proc = process_data(df_raw)
                
                if df_proc is not None:
                    # Check if already sent for this data
                    if not _already_sent_for_data(df_proc):
                        due = get_due_records(df_proc)
                        over = get_overdue_records(df_proc)
                        
                        if not due.empty or not over.empty:
                            success, msg = _send_email(df_proc, PRIMARY_RECIPIENT, CC_RECIPIENTS, "auto")
                            _mark_email_sent(df_proc, success, msg)
                        else:
                            # No urgent samples, mark as sent to avoid repeated checks
                            _mark_email_sent(df_proc, False, "No urgent samples")
        except Exception as e:
            # Log error but don't crash
            print(f"Thread error: {e}")
        
        # Wait longer to reduce frequency (5 minutes instead of 1)
        time.sleep(300)  # Check every 5 minutes during window

def _ensure_scheduler_running():
    if not _thread_started["value"]:
        t = threading.Thread(target=_background_scheduler, daemon=True, name="AutoEmailScheduler")
        t.start()
        _thread_started["value"] = True


# ─────────────────────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────────────────────

def _init_session_state():
    if "primary_recipient" not in st.session_state:
        st.session_state.primary_recipient = PRIMARY_RECIPIENT
    if "cc_recipients" not in st.session_state:
        st.session_state.cc_recipients = CC_RECIPIENTS.copy()
    if "df" not in st.session_state:
        st.session_state.df = None
    if "last_email_sent" not in st.session_state:
        st.session_state.last_email_sent = None


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
    reminder_dates = revalidation_dates - pd.Timedelta(days=3)
    today = datetime.now().date()

    df['Days Left'] = [
        (r.date() - today).days if pd.notna(r) else None for r in revalidation_dates
    ]
    df['Validation Date'] = validation_dates
    df['Revalidation Due'] = revalidation_dates
    df['Reminder Date'] = reminder_dates
    df['Validation Date Display'] = validation_dates.dt.strftime('%d-%m-%Y')
    df['Revalidation Due Display'] = revalidation_dates.dt.strftime('%d-%m-%Y')
    df['Reminder Date Display'] = reminder_dates.dt.strftime('%d-%m-%Y')

    def get_alert_status(row):
        d = row['Days Left']
        s = str(row.get('Staus', '')).lower()
        if pd.isna(d):   return '⚪ Unknown'
        if s == 'ok':    return '✅ Completed'
        if d < 0:        return '🔴 OVERDUE'
        if d <= 3:       return '🔴 URGENT (≤3 days)'
        if d <= 7:       return '🟡 Due Soon (4-7 days)'
        return '🟢 On Track (>7 days)'

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

def _send_email(df, primary_recipient, cc_recipients, alert_type="manual"):
    due_records = get_due_records(df)
    overdue_records = get_overdue_records(df)

    if due_records.empty and overdue_records.empty:
        return False, "No records requiring immediate attention"

    cc_list = [e for e in cc_recipients if e and e.strip()]

    try:
        email_body = _generate_email_html(due_records, overdue_records)
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


def send_single_email_alert(df, primary_recipient, cc_recipients, alert_type="manual"):
    return _send_email(df, primary_recipient, cc_recipients, alert_type)


def _generate_email_html(due_records, overdue_records):
    headers = "<table" + "".join(
        f"<th>{h}</th>" for h in
        ["Model", "Validation Date", "Revalidation Due", "Days Left", "Current Status", "Incharge", "Alert"]
    ) + "</tr>"

    def make_row(row, bg, days_text, badge):
        return (f'<tr style="background-color:{bg};">'
                f'<td><b>{row.get("Model","")}</b></td>'
                f'<td>{row.get("Validation Date Display","")}</td>'
                f'<td>{row.get("Revalidation Due Display","")}</td>'
                f'<td style="color:#dc3545;font-weight:bold;">{days_text}</td>'
                f'<td><b>{row.get("Staus","")}</b></td>'
                f'<td>{row.get("Incharge","")}</td>'
                f'<td style="color:#dc3545;">{badge}</td></tr>')

    over_rows = "".join(
        make_row(r, "#f8d7da", f"{abs(int(r['Days Left']))} days overdue", "🔴 OVERDUE")
        for _, r in overdue_records.iterrows()
    ) if not overdue_records.empty else '<tr><td colspan="7" style="text-align:center;">None</td></tr>'

    due_rows = "".join(
        make_row(r, "#fff3cd", f"{int(r['Days Left'])} days", "⚠️ URGENT")
        for _, r in due_records.iterrows()
    ) if not due_records.empty else '<tr><td colspan="7" style="text-align:center;">None</td></tr>'

    total = len(due_records) + len(overdue_records)

    return f"""<html><head><style>
        body{{font-family:Arial,sans-serif;line-height:1.6;}}
        .hdr{{background:linear-gradient(90deg,#1e3c72,#2a5298);color:white;padding:20px;text-align:center;}}
        .alert{{background:#f8d7da;border-left:4px solid #dc3545;padding:15px;margin:20px 0;}}
        table{{border-collapse:collapse;width:100%;margin:20px 0;}}
        th{{background:#2a5298;color:white;padding:12px;text-align:left;}}
        td{{padding:10px;border-bottom:1px solid #ddd;}}
        .footer{{margin-top:30px;padding:20px;background:#f8f9fa;text-align:center;}}
    </style></head><body>
    <div class="hdr"><h2>Golden Sample Revalidation Tracker</h2>
    <p>🚨 URGENT ALERT: Action Required Immediately</p></div>
    <div class="alert"><strong>⚠️ CRITICAL ALERT:</strong> {total} sample(s) require immediate attention!<br>
    • {len(overdue_records)} OVERDUE &nbsp;• {len(due_records)} due within 3 days<br>
    Please take necessary action immediately.</div>
    <h3>🔴 OVERDUE SAMPLES:</h3>
    <table><thead>{headers}</thead><tbody>{over_rows}</tbody></table>
    <h3>⚠️ SAMPLES DUE WITHIN 3 DAYS:</h3>
    <table><thead>{headers}</thead><tbody>{due_rows}</tbody></table>
    <div class="footer">
    <p>🔴 OVERDUE: Past revalidation date – Immediate action<br>
    ⚠️ URGENT: Due within 3 days &nbsp; 🟡 Due Soon: Within 7 days</p>
    <p><i>Automated alert – Golden Sample Tracker System</i></p>
    <p>Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
    </div></body></html>"""


# ─────────────────────────────────────────────────────────────
#  CHARTS
# ─────────────────────────────────────────────────────────────

def create_status_chart(df):
    counts = df['Staus'].value_counts()
    fig = go.Figure(data=[go.Pie(
        labels=counts.index, values=counts.values, hole=0.6,
        marker_colors=['#28a745', '#ffc107', '#dc3545'],
        textinfo='label+percent', textposition='outside'
    )])
    fig.update_layout(title="Status Distribution", height=400)
    return fig


def create_urgency_chart(df):
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="Samples by Urgency Level", height=400)
        return fig

    def cat(d):
        if pd.isna(d): return 'Unknown'
        if d < 0: return 'Overdue'
        if d <= 3: return 'Urgent (0-3 days)'
        if d <= 7: return 'Due Soon (4-7 days)'
        return 'On Track (>7 days)'

    alert_df['Cat'] = alert_df['Days Left'].apply(cat)
    counts = alert_df['Cat'].value_counts()
    cmap = {'Overdue': '#dc3545', 'Urgent (0-3 days)': '#ff6b6b',
            'Due Soon (4-7 days)': '#ffc107', 'On Track (>7 days)': '#28a745', 'Unknown': '#6c757d'}
    fig = go.Figure(data=[go.Bar(
        x=counts.index, y=counts.values,
        marker_color=[cmap.get(c, '#6c757d') for c in counts.index],
        text=counts.values, textposition='auto'
    )])
    fig.update_layout(title="Samples by Urgency Level",
                      xaxis_title="Urgency Level", yaxis_title="Count", height=400)
    return fig


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    _init_session_state()
    _ensure_scheduler_running()

    st.markdown(
        '<div class="main-header"><h1 style="color:white;text-align:center;">'
        '📊 Golden Sample Revalidation Tracker</h1></div>',
        unsafe_allow_html=True
    )

    # ── Load data FIRST — needed by auto-email check ─────────
    with st.spinner("Loading data..."):
        df_raw = fetch_data()
        df = process_data(df_raw)

    auto_sent, auto_msg = False, ""
    if df is not None:
        st.session_state.df = df
        # Runs on every rerun — fires email if inside time window and not sent for current data
        auto_sent, auto_msg = check_and_trigger_auto_email(df)

    # ── Sidebar ──────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Controls")
        auto_refresh = st.checkbox("🔄 Auto-refresh data", value=True)
        if auto_refresh:
            refresh_rate = st.slider("Refresh rate (seconds)", 30, 300, 60)
            st.info(f"Page refreshes every {refresh_rate} seconds")

        st.markdown("---")
        st.header("📧 Email Notifications")
        st.subheader("🤖 Auto Email Settings")

        now = datetime.now()
        w_start = (now.replace(hour=AUTO_EMAIL_HOUR, minute=AUTO_EMAIL_MINUTE, second=0)
                   - timedelta(minutes=AUTO_EMAIL_WINDOW_MINUTES)).strftime("%H:%M")
        w_end   = (now.replace(hour=AUTO_EMAIL_HOUR, minute=AUTO_EMAIL_MINUTE, second=0)
                   + timedelta(minutes=AUTO_EMAIL_WINDOW_MINUTES)).strftime("%H:%M")

        st.info(f"📨 Daily send window: **{w_start} – {w_end}**")
        st.caption(f"Current time: {now.strftime('%H:%M:%S')}")

        pstate = _load_state()
        if pstate.get("last_sent_time"):
            st.success(f"✅ Last auto email: {pstate['last_sent_time']}")
        if pstate.get("last_result"):
            r = pstate["last_result"]
            if r.startswith("✅"):   st.success(r)
            elif r.startswith("❌"): st.error(r)
            else:                    st.info(r)

        if _already_sent_today():
            st.success("✅ Auto email already sent today")
        else:
            if _is_in_send_window():
                st.warning("🟡 INSIDE send window — will fire once on next refresh if data has changed")
            else:
                target = now.replace(
                    hour=AUTO_EMAIL_HOUR, minute=AUTO_EMAIL_MINUTE,
                    second=0, microsecond=0
                ) - timedelta(minutes=AUTO_EMAIL_WINDOW_MINUTES)
                if target <= now:
                    target += timedelta(days=1)
                diff = target - now
                h = diff.seconds // 3600
                m = (diff.seconds % 3600) // 60
                st.info(f"⏰ Window opens in: {h}h {m}m")

        if auto_sent:
            st.success("🚀 Auto email sent this session!")

        # ── Test button ──────────────────────────────────────
        st.markdown("---")
        st.subheader("🧪 Test Auto Email")
        st.caption("Fires immediately, bypasses schedule.")
        if st.button("🔬 Send Test Auto Email Now", use_container_width=True):
            with st.spinner("Sending..."):
                if st.session_state.df is not None:
                    ok, msg = _send_email(
                        st.session_state.df,
                        st.session_state.primary_recipient,
                        st.session_state.cc_recipients,
                        "test"
                    )
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Data not loaded yet.")

        st.markdown("---")

        # ── Recipients ───────────────────────────────────────
        st.subheader("👥 Email Recipients")
        st.markdown("**Primary Recipient (TO):**")
        new_primary = st.text_input("TO Email", value=st.session_state.primary_recipient)
        if new_primary != st.session_state.primary_recipient:
            st.session_state.primary_recipient = new_primary

        st.markdown("**CC Recipients:**")
        for i, email in enumerate(st.session_state.cc_recipients):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.text(f"{i+1}. {email}")
            with c2:
                if st.button("❌", key=f"rm_{i}"):
                    st.session_state.cc_recipients.pop(i)
                    st.rerun()

        new_cc = st.text_input("CC Email", key="new_cc")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ Add CC", use_container_width=True):
                if new_cc and new_cc.strip() and new_cc not in st.session_state.cc_recipients:
                    st.session_state.cc_recipients.append(new_cc.strip())
                    st.rerun()
        with c2:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.primary_recipient = PRIMARY_RECIPIENT
                st.session_state.cc_recipients = CC_RECIPIENTS.copy()
                st.rerun()

        st.caption(f"📧 TO: {st.session_state.primary_recipient}")
        st.caption(f"👥 CC: {len(st.session_state.cc_recipients)} recipient(s)")
        st.markdown("---")

        # ── Manual email ─────────────────────────────────────
        st.subheader("📧 Manual Email Alert")
        c1, c2 = st.columns(2)
        with c1:
            send_now = st.button("🚨 Send Alert Now", type="primary", use_container_width=True)
        with c2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        if send_now:
            with st.spinner("Sending..."):
                if st.session_state.df is not None:
                    ok, msg = send_single_email_alert(
                        st.session_state.df,
                        st.session_state.primary_recipient,
                        st.session_state.cc_recipients
                    )
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.error("No data available")

        st.markdown("---")
        debug_mode = st.checkbox("🔧 Debug info", value=False)
        if debug_mode:
            with st.expander("Debug"):
                st.write("**Persistent state:**", _load_state())
                st.write("**In send window:**", _is_in_send_window())
                st.write("**Sent today:**", _already_sent_today())
                st.write("**Sent for current data:**", _already_sent_for_data(df) if df is not None else False)
                st.write("**Thread running:**", _thread_started["value"])
                st.write(f"**Window:** {w_start} – {w_end}")
                if df is not None:
                    st.write(f"**Rows:** {len(df)}")
                    st.write(f"**Urgent samples:** {len(get_due_records(df))}")
                    st.write(f"**Overdue samples:** {len(get_overdue_records(df))}")
                    st.dataframe(df.head(3))

    # ── Main content ─────────────────────────────────────────
    if df is None or df.empty:
        st.error("No valid data available.")
        st.info("Required columns: 'Validation Date', 'Staus', 'Model' | Date format: DD-MM-YYYY")
        return

    # Metrics
    cols = st.columns(5)
    total        = len(df)
    ok_count     = len(df[df['Staus'].str.lower() == 'ok'])
    pend_count   = len(df[df['Staus'].str.lower() == 'pending'])
    ng_count     = len(df[df['Staus'].str.lower() == 'ng'])
    urgent_count = len(get_due_records(df))
    over_count   = len(get_overdue_records(df))

    cols[0].metric("Total Samples", total)
    cols[1].metric("✅ OK", ok_count)
    cols[2].metric("⏳ Pending", pend_count)
    cols[3].metric("❌ NG", ng_count)
    cols[4].metric("🔴 Urgent", urgent_count + over_count,
                   delta=f"{over_count} overdue" if over_count > 0 else None,
                   delta_color="inverse" if (urgent_count + over_count) > 0 else "normal")

    if over_count > 0:
        st.error(f"🔴 **CRITICAL:** {over_count} sample(s) OVERDUE — Immediate action required!")
    if urgent_count > 0:
        st.warning(f"⚠️ **URGENT:** {urgent_count} sample(s) due within 3 days!")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(create_status_chart(df), use_container_width=True)
    with c2:
        st.plotly_chart(create_urgency_chart(df), use_container_width=True)

    st.markdown("### 📋 Golden Sample Details")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sf = st.multiselect("Filter by Status", ['OK', 'Pending', 'NG'], default=['OK', 'Pending', 'NG'])
    with c2:
        uf = st.selectbox("Filter by Urgency",
                          ['All', 'Overdue', 'Urgent (≤3 days)', 'Due Soon (4-7 days)', 'On Track (>7 days)'])
    with c3:
        sm = st.text_input("🔍 Search Model", placeholder="Model name...")
    with c4:
        sb = st.selectbox("Sort by", ['Days Left', 'Validation Date', 'Revalidation Due', 'Model'])

    fdf = df[df['Staus'].isin(sf)]
    if uf == 'Overdue':
        fdf = fdf[fdf['Days Left'] < 0]
    elif uf == 'Urgent (≤3 days)':
        fdf = fdf[(fdf['Days Left'] <= 3) & (fdf['Days Left'] >= 0)]
    elif uf == 'Due Soon (4-7 days)':
        fdf = fdf[(fdf['Days Left'] <= 7) & (fdf['Days Left'] > 3)]
    elif uf == 'On Track (>7 days)':
        fdf = fdf[fdf['Days Left'] > 7]
    if sm:
        fdf = fdf[fdf['Model'].str.contains(sm, case=False, na=False)]
    if sb in fdf.columns:
        fdf = fdf.sort_values(sb, ascending=True)

    disp_cols = ['Model', 'Validation Date Display', 'Revalidation Due Display',
                 'Days Left', 'Staus', 'Incharge', 'Alert Status']
    disp_df = fdf[[c for c in disp_cols if c in fdf.columns]].copy().fillna('-')
    disp_df['Days Left'] = disp_df['Days Left'].apply(
        lambda x: f"{int(x)} days" if x != '-' and pd.notna(x) else '-'
    )

    def highlight_row(row):
        try:
            if row.get('Days Left', '-') != '-':
                d = int(str(row['Days Left']).split()[0])
                if d < 0:  return ['background-color:#f8d7da'] * len(row)
                if d <= 3: return ['background-color:#fff3cd'] * len(row)
        except Exception:
            pass
        return [''] * len(row)

    st.dataframe(disp_df.style.apply(highlight_row, axis=1), use_container_width=True, height=500)

    if st.button("📥 Export to CSV", use_container_width=True):
        st.download_button(
            "Download CSV", disp_df.to_csv(index=False),
            file_name=f"golden_sample_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv", key="dl_csv"
        )

    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()


if __name__ == "__main__":
    main()
