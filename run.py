import tkinter as tk
from tkinter import messagebox
import sqlite3
from datetime import datetime
import csv

# --- Database Setup ---
conn = sqlite3.connect("swing_trades.db")
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_name TEXT,
    current_price REAL,
    target_price REAL,
    stop_loss REAL,
    volume INT,
    budget REAL,
    confidence INT,
    trade_type TEXT,
    notes TEXT,
    tags TEXT,
    reminder TEXT,
    date TEXT
)
''')
conn.commit()

# --- Calculation Logic ---
def calculate_metrics(current, target, stop, volume, budget):
    try:
        risk_per_share = current - stop
        reward_per_share = target - current
        total_risk = risk_per_share * volume
        total_reward = reward_per_share * volume
        risk_reward_ratio = round(reward_per_share / risk_per_share, 2) if risk_per_share else 0

        rec_vol = int((0.01 * budget) / risk_per_share) if risk_per_share else 0
        max_shares = int(budget / current)
        break_even = round((current + stop) / 2, 2)
        total_cost = round(current * volume, 2)
        expected_return = round((target - current) * volume, 2)
        stop_pct = round((current - stop) / current * 100, 2)
        reward_pct = round((target - current) / current * 100, 2)

        tag = "high-risk" if risk_reward_ratio < 1 else ("conservative" if risk_reward_ratio >= 2 else "neutral")
        alert = "⚠️ Risk exceeds 2% of capital!" if total_risk > 0.02 * budget else ""

        return {
            "Risk/Share": round(risk_per_share, 2),
            "Reward/Share": round(reward_per_share, 2),
            "Risk/Reward": risk_reward_ratio,
            "Total Risk": round(total_risk, 2),
            "Total Reward": round(total_reward, 2),
            "Break-Even": break_even,
            "Total Cost": total_cost,
            "Expected Return": expected_return,
            "Stop %": stop_pct,
            "Reward %": reward_pct,
            "1% Risk Volume": rec_vol,
            "Max Shares": max_shares,
            "Auto Tag": tag,
            "Alert": alert
        }
    except:
        return {}

# --- Submit Handler ---
def submit():
    try:
        data = {
            "stock_name": stock_name.get().upper(),
            "current_price": float(current_price.get()),
            "target_price": float(target_price.get()),
            "stop_loss": float(stop_loss.get()),
            "volume": int(volume.get()),
            "budget": float(budget.get()),
            "confidence": int(confidence.get()),
            "trade_type": trade_type.get(),
            "notes": notes.get(),
            "tags": tags.get(),
            "reminder": reminder.get()
        }

        metrics = calculate_metrics(
            data["current_price"], data["target_price"],
            data["stop_loss"], data["volume"], data["budget"]
        )

        # Save to DB
        full_tags = data["tags"] + ", " + metrics["Auto Tag"]
        c.execute('''
        INSERT INTO trades (stock_name, current_price, target_price, stop_loss, volume, budget,
                            confidence, trade_type, notes, tags, reminder, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data["stock_name"], data["current_price"], data["target_price"], data["stop_loss"],
              data["volume"], data["budget"], data["confidence"], data["trade_type"],
              data["notes"], full_tags, data["reminder"],
              datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()

        # Show metrics
        result_text.delete("1.0", tk.END)
        for k, v in metrics.items():
            result_text.insert(tk.END, f"{k}: {v}\n")

    except Exception as e:
        messagebox.showerror("Error", f"Invalid input: {e}")

# --- CSV Export ---
def export_csv():
    with open("trades_export.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Stock", "Current", "Target", "SL", "Volume", "Budget", "Confidence",
                         "Type", "Notes", "Tags", "Reminder", "Date"])
        for row in c.execute("SELECT * FROM trades"):
            writer.writerow(row)
    messagebox.showinfo("Export", "CSV exported as 'trades_export.csv'.")

# --- GUI Setup ---
root = tk.Tk()
root.title("Swing Trading Assistant")

fields = [
    ("Stock Name", "stock_name"),
    ("Current Price", "current_price"),
    ("Target Price", "target_price"),
    ("Stop Loss", "stop_loss"),
    ("Volume", "volume"),
    ("Total Budget", "budget"),
    ("Confidence (0-10)", "confidence"),
    ("Trade Type", "trade_type"),
    ("Notes", "notes"),
    ("Tags", "tags"),
    ("Reminder Date (YYYY-MM-DD)", "reminder")
]

entries = {}

for i, (label_text, var_name) in enumerate(fields):
    label = tk.Label(root, text=label_text)
    label.grid(row=i, column=0, sticky="e", padx=5, pady=3)
    entry = tk.Entry(root, width=40)
    entry.grid(row=i, column=1, padx=5, pady=3)
    entries[var_name] = entry

# Bind entries to variables
stock_name = entries["stock_name"]
current_price = entries["current_price"]
target_price = entries["target_price"]
stop_loss = entries["stop_loss"]
volume = entries["volume"]
budget = entries["budget"]
confidence = entries["confidence"]
trade_type = entries["trade_type"]
notes = entries["notes"]
tags = entries["tags"]
reminder = entries["reminder"]

submit_btn = tk.Button(root, text="Submit Trade", command=submit, bg="lightgreen")
submit_btn.grid(row=len(fields), column=0, pady=10)

export_btn = tk.Button(root, text="Export to CSV", command=export_csv, bg="lightblue")
export_btn.grid(row=len(fields), column=1, pady=10)

result_text = tk.Text(root, height=15, width=60)
result_text.grid(row=len(fields)+1, column=0, columnspan=2, padx=10, pady=10)

root.mainloop()
conn.close()
