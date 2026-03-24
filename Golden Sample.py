import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import http.server
import socketserver
import webbrowser

# ========== CONFIGURATION ==========
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSG42OXWxsoLV7wNqqDAdryfmDYU4IGBv1gEJm8-8bP_qh6vCe2NWAx7_vM3DYQqxCPFX3jv-TimRgV/pub?output=csv"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SENDER_EMAIL = "rajgopalr.padget@dixoninfo.com"
SENDER_PASSWORD = "gzxzuolbmqkdhcst"  # App Password (no spaces)

WEB_PORT = 8000

# 🔁 TEST MODE (set False for production)
TEST_MODE = True
# ===================================


def fetch_data():
    try:
        df = pd.read_csv(CSV_URL)
        print(f"✓ Loaded {len(df)} records")
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def parse_date(date_str):
    if pd.isna(date_str):
        return None
    return pd.to_datetime(date_str, dayfirst=True, errors='coerce')


def process_data(df):
    if df is None:
        return None

    df = df.copy()

    if 'Validation Date' not in df.columns:
        print("Missing 'Validation Date' column")
        return None

    df['Validation Date'] = df['Validation Date'].apply(parse_date)
    df = df.dropna(subset=['Validation Date'])

    df['Revalidation Due'] = df['Validation Date'] + timedelta(days=10)
    df['Reminder Date'] = df['Revalidation Due'] - timedelta(days=3)

    today = datetime.now().date()
    df['Days Left'] = (df['Revalidation Due'] - pd.Timestamp(today)).dt.days

    df['Validation Date Display'] = df['Validation Date'].dt.strftime('%d-%m-%Y')
    df['Revalidation Due Display'] = df['Revalidation Due'].dt.strftime('%d-%m-%Y')
    df['Reminder Date Display'] = df['Reminder Date'].dt.strftime('%d-%m-%Y')

    return df


def get_due_records(df):
    today = datetime.now().date()

    # Condition 1: 3 days before revalidation
    cond1 = df['Reminder Date'].dt.date == today

    # Condition 2: Pending → daily trigger
    cond2 = df['Staus'].str.lower() == 'pending'

    # Combine
    return df[cond1 | cond2]


def generate_html_dashboard(df):
    total = len(df)
    ok = len(df[df['Staus'].str.lower() == 'ok'])
    pending = len(df[df['Staus'].str.lower() == 'pending'])
    ng = len(df[df['Staus'].str.lower() == 'ng'])

    # Generate table rows
    html_rows = ""
    for _, row in df.iterrows():
        status = str(row.get('Staus', '')).lower()

        if status == 'pending':
            color = "#fff3cd"
        elif status == 'ng':
            color = "#f8d7da"
        elif status == 'ok':
            color = "#d4edda"
        else:
            color = "white"

        # Hide days for NG
        days_left = "-" if status == "ng" else row.get('Days Left', '')

        html_rows += f"""
        <tr style="background:{color}">
            <td>{row.get('Model','')}</td>
            <td>{row.get('Validation Date Display','')}</td>
            <td>{row.get('Revalidation Due Display','')}</td>
            <td>{days_left}</td>
            <td><b>{row.get('Staus','')}</b></td>
            <td>{row.get('Incharge','')}</td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <title>Golden Sample Revalidation Tracker</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                background: #f5f7fb;
                margin: 0;
            }}

            .header {{
                background: linear-gradient(90deg,#1e3c72,#2a5298);
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 28px;
                font-weight: bold;
            }}

            .cards {{
                display: flex;
                justify-content: space-around;
                padding: 20px;
                gap: 20px;
            }}

            .card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                width: 200px;
                text-align: center;
                box-shadow: 0 8px 20px rgba(0,0,0,0.15);
                transition: transform 0.2s;
            }}

            .card:hover {{
                transform: translateY(-5px);
            }}

            .card h2 {{
                margin: 0;
                font-size: 30px;
                color: #2a5298;
            }}

            .container {{
                display: flex;
                gap: 20px;
                padding: 20px;
            }}

            .chart {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                width: 35%;
                box-shadow: 0 8px 20px rgba(0,0,0,0.15);
            }}

            .table-container {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                width: 65%;
                box-shadow: 0 8px 20px rgba(0,0,0,0.15);
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
            }}

            th {{
                background: #2a5298;
                color: white;
                padding: 10px;
            }}

            td {{
                padding: 10px;
                text-align: center;
                border-bottom: 1px solid #ddd;
            }}

            tr:hover {{
                background: #f1f1f1;
            }}

            h3 {{
                text-align: center;
                margin-bottom: 10px;
            }}
        </style>
    </head>

    <body>

        <div class="header">
            Golden Sample Revalidation Tracker
        </div>

        <div class="cards">
            <div class="card">
                <h2>{total}</h2>
                <p>Total Samples</p>
            </div>

            <div class="card">
                <h2>{ok}</h2>
                <p>OK</p>
            </div>

            <div class="card">
                <h2>{pending}</h2>
                <p>Pending</p>
            </div>

            <div class="card">
                <h2>{ng}</h2>
                <p>NG</p>
            </div>
        </div>

        <div class="container">

            <div class="chart">
                <h3>Revalidation Status Distribution</h3>
                <canvas id="statusChart"></canvas>
            </div>

            <div class="table-container">
                <h3>Golden Sample Details</h3>
                <table>
                    <tr>
                        <th>Model</th>
                        <th>Validation</th>
                        <th>Revalidation</th>
                        <th>Days Left</th>
                        <th>Status</th>
                        <th>Incharge</th>
                    </tr>
                    {html_rows}
                </table>
            </div>

        </div>

        <script>
            const total = {total};

            const centerText = {{
                id: 'centerText',
                beforeDraw(chart) {{
                    const {{width}} = chart;
                    const {{height}} = chart;
                    const ctx = chart.ctx;

                    ctx.restore();
                    ctx.font = "bold 20px Arial";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";

                    ctx.fillText("Total", width / 2, height / 2 - 10);
                    ctx.fillText(total, width / 2, height / 2 + 15);

                    ctx.save();
                }}
            }};

            new Chart(document.getElementById('statusChart'), {{
                type: 'doughnut',
                data: {{
                    labels: ['OK', 'Pending', 'NG'],
                    datasets: [{{
                        data: [{ok}, {pending}, {ng}],
                        backgroundColor: ['#28a745','#ffc107','#dc3545']
                    }}]
                }},
                options: {{
                    cutout: '65%',
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }}
                    }}
                }},
                plugins: [centerText]
            }});
        </script>

    </body>
    </html>
    """

    return html

def generate_email_table(df):
    rows = ""

    for _, row in df.iterrows():
        status = str(row.get('Staus', '')).lower()

        if status == 'pending':
            color = "#fff3cd"   # yellow
        elif status == 'ng':
            color = "#f8d7da"   # red
        elif status == 'ok':
            color = "#d4edda"   # green
        else:
            color = "white"

        rows += f"""
        <tr style="background-color:{color};">
            <td>{row.get('Model','')}</td>
            <td>{row.get('Validation Date Display','')}</td>
            <td>{row.get('Revalidation Due Display','')}</td>
            <td>{row.get('Days Left','')}</td>
            <td><b>{row.get('Staus','')}</b></td>
            <td>{row.get('Incharge','')}</td>
        </tr>
        """

    html = f"""
    <html>
    <body style="font-family: Arial;">
        <h2>🚨 Golden Sample Alert</h2>
        <p>This is an automated reminder for validation tracking.</p>

        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width:100%;">
            <tr style="background-color:#343a40; color:white;">
                <th>Model</th>
                <th>Validation Date</th>
                <th>Revalidation Due</th>
                <th>Days Left</th>
                <th>Status</th>
                <th>Incharge</th>
            </tr>
            {rows}
        </table>

        <br>
        <p><b>Legend:</b></p>
        <p>
        🟨 Pending (Needs Action)<br>
        🟥 NG (Issue Found)<br>
        🟩 OK (Completed)
        </p>

        <br>
        <p>Regards,<br>Golden Sample Tracker</p>
    </body>
    </html>
    """

    return html


def send_all_reminders(df):
    reminders = get_due_records(df)

    if reminders.empty:
        print("No reminders to send today.")
        return 0

    print(f"\n📧 Sending alert for {len(reminders)} records...")

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = SENDER_EMAIL   # self for testing
        msg['Subject'] = "🚨 Golden Sample Daily Alert"

        html_body = generate_email_table(reminders)
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully")
        return 1

    except Exception as e:
        print(f"❌ Email failed: {e}")
        return 0


def start_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", WEB_PORT), handler) as httpd:
        print(f"🌐 Server running: http://localhost:{WEB_PORT}")
        httpd.serve_forever()


def main():
    print("🚀 Golden Sample Tracker Started")

    df = fetch_data()
    df = process_data(df)

    if df is None or df.empty:
        print("No valid data")
        return

    # Save dashboard
    html = generate_html_dashboard(df)
    file_name = "dashboard.html"

    with open(file_name, "w", encoding="utf-8") as f:
        f.write(html)

    abs_path = os.path.abspath(file_name)
    webbrowser.open(f"file:///{abs_path}")

    # Send emails
    sent = send_all_reminders(df)

    print(f"\n📊 Emails sent: {sent}")
    print(f"📁 Dashboard: {abs_path}")

    # Optional server
    choice = input("Start web server? (y/n): ")
    if choice.lower() == 'y':
        start_server()


if __name__ == "__main__":
    main()
