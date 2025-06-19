import tkinter as tk
from tkinter import messagebox, simpledialog
import sqlite3
from datetime import datetime
import csv

# -------- Helper functions for table names --------
def get_half_and_year():
    now = datetime.now()
    return ('H1', now.year) if now.month <= 6 else ('H2', now.year)

def get_trade_table_name(half, year):
    return f"trades_{year}_{half}"

def get_current_trade_table():
    half, year = get_half_and_year()
    return get_trade_table_name(half, year)

def get_previous_trade_table():
    half, year = get_half_and_year()
    if half == 'H2':
        return get_trade_table_name('H1', year)
    else:
        return get_trade_table_name('H2', year - 1)

trade_table = get_current_trade_table()
previous_table = get_previous_trade_table()

# -------- Database setup --------
conn = sqlite3.connect("swing_trades.db")
c = conn.cursor()

c.execute(f'''
CREATE TABLE IF NOT EXISTS {trade_table} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_name TEXT,
    current_price REAL,
    target_price REAL,
    stop_loss REAL,
    volume INT,
    confidence INT,
    notes TEXT,
    result TEXT,
    date TEXT
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS completed_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_name TEXT,
    buy_price REAL,
    target_price REAL,
    stop_loss REAL,
    volume INT,
    result TEXT,
    outcome_price REAL,
    pnl REAL,
    date_closed TEXT
)
''')

def migrate_open_trades():
    try:
        c.execute(f"SELECT * FROM {previous_table} LIMIT 1")
    except sqlite3.OperationalError:
        return
    c.execute(f"SELECT * FROM {trade_table} LIMIT 1")
    if c.fetchone(): return
    open_trades = c.execute(f"SELECT stock_name, current_price, target_price, stop_loss, volume, confidence, notes, result, date FROM {previous_table} WHERE result = ''").fetchall()
    for row in open_trades:
        c.execute(f"INSERT INTO {trade_table} (stock_name, current_price, target_price, stop_loss, volume, confidence, notes, result, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
    conn.commit()
    messagebox.showinfo("New Period", f"Migrated {len(open_trades)} open trades to new table: {trade_table}")

migrate_open_trades()

# -------- GUI + App Logic --------
budget = None

def set_budget():
    global budget
    b = simpledialog.askfloat("Budget", "Enter your monthly budget (₹):")
    if b is None or b <= 0:
        messagebox.showerror("Error", "Budget required.")
        root.destroy()
    budget = b
    update_summary()

def reset_budget():
    set_budget()
    messagebox.showinfo("Budget Reset", f"New budget: ₹{budget}")

def calculate_metrics(current, target, stop, volume):
    try:
        risk = current - stop
        reward = target - current
        rr_ratio = round(reward / risk, 2) if risk else 0
        position_size = int((0.01 * budget) / risk) if risk else 0
        breakeven = round((target + stop) / 2, 2)
        cost = round(current * volume, 2)
        expected = round(reward * volume, 2)
        return {
            "Risk/Reward": rr_ratio,
            "1% Position Size": position_size,
            "Breakeven": breakeven,
            "Cost": cost,
            "Expected Return": expected
        }
    except:
        return {}

def submit_trade():
    try:
        data = {
            "stock": stock_entry.get().upper(),
            "current": float(current_entry.get()),
            "target": float(target_entry.get()),
            "stop": float(stop_entry.get()),
            "volume": int(volume_entry.get()),
            "confidence": int(conf_entry.get()),
            "notes": notes_entry.get()
        }
        metrics = calculate_metrics(data["current"], data["target"], data["stop"], data["volume"])
        c.execute(f'''
        INSERT INTO {trade_table} (stock_name, current_price, target_price, stop_loss,
                                   volume, confidence, notes, result, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, '', ?)
        ''', (data["stock"], data["current"], data["target"], data["stop"],
              data["volume"], data["confidence"], data["notes"], datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        result_text.delete("1.0", tk.END)
        for k, v in metrics.items():
            result_text.insert(tk.END, f"{k}: {v}\n")
        update_summary()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def update_summary():
    summary.delete("1.0", tk.END)
    trades = c.execute(f"SELECT * FROM {trade_table}").fetchall()
    total_cap = sum(row[2] * row[5] for row in trades)
    expected = sum((row[3] - row[2]) * row[5] for row in trades)
    summary.insert(tk.END, f"Active Trades: {len(trades)}\nCapital Used: ₹{round(total_cap,2)}\nExpected Return: ₹{round(expected,2)}\n")

def view_active():
    win = tk.Toplevel()
    win.title("Active Trades")
    headers = ["ID", "Stock", "Buy", "Target", "SL", "Vol", "Conf", "Date"]
    for i, h in enumerate(headers):
        tk.Label(win, text=h, relief="ridge", width=12, bg="lightgrey").grid(row=0, column=i)
    rows = c.execute(f"SELECT id, stock_name, current_price, target_price, stop_loss, volume, confidence, date FROM {trade_table}").fetchall()
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            tk.Label(win, text=val, relief="ridge", width=12).grid(row=r_idx, column=c_idx)

def view_closed():
    win = tk.Toplevel()
    win.title("Closed Trades")
    headers = ["ID", "Stock", "Buy", "Target", "SL", "Vol", "Result", "Exit", "P/L", "Closed"]
    for i, h in enumerate(headers):
        tk.Label(win, text=h, relief="ridge", width=10, bg="lightgrey").grid(row=0, column=i)
    rows = c.execute("SELECT * FROM completed_trades ORDER BY id DESC").fetchall()
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            color = "green" if c_idx == 8 and val > 0 else "red" if c_idx == 8 and val < 0 else "white"
            tk.Label(win, text=val, bg=color, width=10).grid(row=r_idx, column=c_idx)

def close_trade():
    trade_id = simpledialog.askinteger("Trade ID", "Enter Trade ID to close:")
    result = simpledialog.askstring("Result", "Type 'goal' or 'stop':")
    if result not in ["goal", "stop"]:
        messagebox.showerror("Error", "Invalid result.")
        return
    row = c.execute(f"SELECT * FROM {trade_table} WHERE id = ?", (trade_id,)).fetchone()
    if not row:
        messagebox.showerror("Error", "Trade ID not found.")
        return
    exit_price = row[3] if result == "goal" else row[4]
    pnl = round((exit_price - row[2]) * row[5], 2)
    c.execute('''INSERT INTO completed_trades (stock_name, buy_price, target_price, stop_loss, volume, result, outcome_price, pnl, date_closed)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (row[1], row[2], row[3], row[4], row[5], result, exit_price, pnl, datetime.now().strftime("%Y-%m-%d %H:%M")))
    c.execute(f"DELETE FROM {trade_table} WHERE id = ?", (trade_id,))
    conn.commit()
    update_summary()
    messagebox.showinfo("Closed", f"Trade closed with P/L: ₹{pnl}")

def export_csv():
    with open("trades_export.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Stock", "Buy", "Target", "SL", "Vol", "Conf", "Notes", "Result", "Date"])
        rows = c.execute(f"SELECT * FROM {trade_table}").fetchall()
        writer.writerows(rows)
    messagebox.showinfo("Exported", "Trades exported to 'trades_export.csv'")

# -------- GUI Layout --------
root = tk.Tk()
root.title("Swing Trading Assistant")

tk.Label(root, text="Stock").grid(row=0, column=0)
stock_entry = tk.Entry(root); stock_entry.grid(row=0, column=1)

tk.Label(root, text="Current Price").grid(row=1, column=0)
current_entry = tk.Entry(root); current_entry.grid(row=1, column=1)

tk.Label(root, text="Target Price").grid(row=2, column=0)
target_entry = tk.Entry(root); target_entry.grid(row=2, column=1)

tk.Label(root, text="Stop Loss").grid(row=3, column=0)
stop_entry = tk.Entry(root); stop_entry.grid(row=3, column=1)

tk.Label(root, text="Volume").grid(row=4, column=0)
volume_entry = tk.Entry(root); volume_entry.grid(row=4, column=1)

tk.Label(root, text="Confidence").grid(row=5, column=0)
conf_entry = tk.Entry(root); conf_entry.grid(row=5, column=1)

tk.Label(root, text="Notes").grid(row=6, column=0)
notes_entry = tk.Entry(root); notes_entry.grid(row=6, column=1)

tk.Button(root, text="Submit Trade", command=submit_trade, bg="lightgreen").grid(row=7, column=0, columnspan=2, pady=4)
tk.Button(root, text="View Active Trades", command=view_active).grid(row=8, column=0, columnspan=2)
tk.Button(root, text="View Closed Trades", command=view_closed).grid(row=9, column=0, columnspan=2)
tk.Button(root, text="Close Trade", command=close_trade, bg="orange").grid(row=10, column=0, columnspan=2)
tk.Button(root, text="Export CSV", command=export_csv).grid(row=11, column=0, columnspan=2)
tk.Button(root, text="Reset Budget", command=reset_budget).grid(row=12, column=0, columnspan=2)

tk.Label(root, text="Trade Metrics").grid(row=13, column=0, columnspan=2)
result_text = tk.Text(root, height=6, width=50); result_text.grid(row=14, column=0, columnspan=2)

tk.Label(root, text="Summary").grid(row=15, column=0, columnspan=2)
summary = tk.Text(root, height=4, width=50); summary.grid(row=16, column=0, columnspan=2)

set_budget()
update_summary()
root.mainloop()
conn.close()
