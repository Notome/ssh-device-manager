import os
import sqlite3
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "devices.db")


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ip TEXT NOT NULL UNIQUE,
            type TEXT,
            os_type TEXT DEFAULT 'cisco_ios',
            status TEXT DEFAULT 'offline',
            username TEXT,
            password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            user_id INTEGER,
            command TEXT NOT NULL,
            output TEXT,
            success INTEGER DEFAULT 1,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            blocked_ips TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migrations for devices
    cur.execute("PRAGMA table_info(devices)")
    columns = [info[1] for info in cur.fetchall()]
    for col, col_def in [
        ("username", "TEXT"),
        ("password", "TEXT"),
        ("os_type", "TEXT DEFAULT 'cisco_ios'"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]:
        if col not in columns:
            cur.execute(f"ALTER TABLE devices ADD COLUMN {col} {col_def}")

    # Migrations for command_history
    cur.execute("PRAGMA table_info(command_history)")
    ch_columns = [info[1] for info in cur.fetchall()]
    if "user_id" not in ch_columns:
        cur.execute("ALTER TABLE command_history ADD COLUMN user_id INTEGER")

    # Default users
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users (login, password, role) VALUES (?, ?, ?)", ("admin", "1234", "admin"))
        cur.execute("INSERT INTO users (login, password, role) VALUES (?, ?, ?)", ("user", "1234", "user"))

    conn.commit()
    conn.close()


def query(sql, params=(), one=False):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    if sql.strip().upper().startswith("SELECT"):
        rv = cur.fetchall()
    else:
        rv = None
    conn.commit()
    conn.close()
    if one:
        return rv[0] if rv else None
    return rv


# Devices
def add_device(name, ip, device_type, os_type, status, username="", password=""):
    return query(
        "INSERT INTO devices (name, ip, type, os_type, status, username, password) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, ip, device_type, os_type, status, username, password)
    )

def update_device(device_id, name, ip, device_type, os_type, status, username="", password=""):
    return query(
        "UPDATE devices SET name=?, ip=?, type=?, os_type=?, status=?, username=?, password=? WHERE id=?",
        (name, ip, device_type, os_type, status, username, password, device_id)
    )

def delete_device(device_id):
    return query("DELETE FROM devices WHERE id=?", (device_id,))

def get_device(device_id):
    return query("SELECT * FROM devices WHERE id=?", (device_id,), one=True)

def get_all_devices():
    return query("SELECT * FROM devices ORDER BY created_at DESC")

def search_devices(search_term):
    p = f"%{search_term}%"
    return query("SELECT * FROM devices WHERE name LIKE ? OR ip LIKE ? ORDER BY created_at DESC", (p, p))

def filter_devices_by_type(device_type):
    return query("SELECT * FROM devices WHERE type = ? ORDER BY created_at DESC", (device_type,))

def filter_devices_by_status(status):
    return query("SELECT * FROM devices WHERE status = ? ORDER BY created_at DESC", (status,))

def update_device_status(device_id, status):
    return query("UPDATE devices SET status = ? WHERE id = ?", (status, device_id))


# Command History
def add_command_history(device_id, command, output, success=True, user_id=None):
    return query(
        "INSERT INTO command_history (device_id, user_id, command, output, success) VALUES (?, ?, ?, ?, ?)",
        (device_id, user_id, command, output, 1 if success else 0)
    )

def get_command_history(device_id, limit=10):
    return query("SELECT * FROM command_history WHERE device_id=? ORDER BY executed_at DESC LIMIT ?", (device_id, limit))

def get_all_command_history(limit=50):
    return query(
        """SELECT ch.*, d.name as device_name, d.ip as device_ip 
           FROM command_history ch JOIN devices d ON ch.device_id = d.id 
           ORDER BY ch.executed_at DESC LIMIT ?""",
        (limit,)
    )

def get_statistics():
    devices = get_all_devices()
    return {
        "online": len([d for d in devices if d["status"] == "online"]),
        "offline": len([d for d in devices if d["status"] == "offline"]),
        "total": len(devices)
    }


# Users
def get_all_users():
    return query("SELECT * FROM users ORDER BY id")

def get_user_by_id(user_id):
    return query("SELECT * FROM users WHERE id=?", (user_id,), one=True)

def get_user_by_login(login):
    return query("SELECT * FROM users WHERE login=?", (login,), one=True)

def add_user(login, password, role="user", blocked_ips=""):
    return query(
        "INSERT INTO users (login, password, role, blocked_ips) VALUES (?, ?, ?, ?)",
        (login, password, role, blocked_ips)
    )

def update_user(user_id, login, password, role, blocked_ips=""):
    return query(
        "UPDATE users SET login=?, password=?, role=?, blocked_ips=? WHERE id=?",
        (login, password, role, blocked_ips, user_id)
    )

def delete_user(user_id):
    return query("DELETE FROM users WHERE id=?", (user_id,))

def is_ip_blocked_for_user(user_id, ip):
    user = get_user_by_id(user_id)
    if not user:
        return True
    blocked = [x.strip() for x in (user["blocked_ips"] or "").split(",") if x.strip()]
    return ip in blocked
