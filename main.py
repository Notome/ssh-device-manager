from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from functools import wraps
import json
import zipfile
import io
import threading
from db import (
    init_db, get_all_devices, get_device, add_device, update_device,
    delete_device, update_device_status, get_statistics, search_devices,
    filter_devices_by_type, filter_devices_by_status, add_command_history,
    get_command_history, get_all_command_history,
    get_all_users, get_user_by_id, get_user_by_login, add_user, update_user, delete_user,
    is_ip_blocked_for_user
)
from services.netmiko_service import NetmikoService, OS_LABELS

app = Flask(__name__)
app.secret_key = 'ssh_manager_secret_key_2026'

netmiko_service = NetmikoService()


def row_to_dict(row):
    return dict(row) if row else None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash("Доступ запрещён. Требуются права администратора.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password_val = request.form.get("password", "")
        user = row_to_dict(get_user_by_login(login_val))
        if user and user["password"] == password_val:
            session['user_id'] = user['id']
            session['login'] = user['login']
            session['role'] = user['role']
            flash(f"Добро пожаловать, {user['login']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Неверный логин или пароль", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/")
@login_required
def dashboard():
    search_query = request.args.get('search', '').strip()
    filter_type = request.args.get('type', '').strip()
    filter_status = request.args.get('status', '').strip()

    if search_query:
        devices = search_devices(search_query)
    elif filter_type:
        devices = filter_devices_by_type(filter_type)
    elif filter_status:
        devices = filter_devices_by_status(filter_status)
    else:
        devices = get_all_devices()

    user_id = session['user_id']
    devices_list = []
    for d in devices:
        d_dict = row_to_dict(d)
        d_dict['blocked'] = is_ip_blocked_for_user(user_id, d_dict['ip'])
        devices_list.append(d_dict)

    stats = get_statistics()
    all_devices = get_all_devices()
    device_types = sorted({d['type'] for d in all_devices if d['type']})

    return render_template(
        "dashboard.html",
        devices=devices_list,
        stats=stats,
        device_types=device_types,
        current_search=search_query,
        current_type=filter_type,
        current_status=filter_status
    )

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_device_route():
    if request.method == "POST":
        try:
            add_device(
                name=request.form["name"],
                ip=request.form["ip"],
                device_type=request.form.get("type", ""),
                os_type=request.form.get("os_type", "cisco_ios"),
                status=request.form.get("status", "offline"),
                username=request.form.get("username", ""),
                password=request.form.get("password", "")
            )
            flash(f"Устройство '{request.form['name']}' успешно добавлено!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Ошибка при добавлении: {str(e)}", "error")
    return render_template("add_device.html", os_labels=OS_LABELS)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_device_route(id):
    device = row_to_dict(get_device(id))
    if not device:
        flash("Устройство не найдено", "error")
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        try:
            update_device(
                device_id=id,
                name=request.form["name"],
                ip=request.form["ip"],
                device_type=request.form.get("type", ""),
                os_type=request.form.get("os_type", "cisco_ios"),
                status=request.form.get("status", "offline"),
                username=request.form.get("username", ""),
                password=request.form.get("password", "")
            )
            flash(f"Устройство '{request.form['name']}' успешно обновлено!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Ошибка при обновлении: {str(e)}", "error")

    return render_template("edit_device.html", device=device, os_labels=OS_LABELS)


@app.route("/delete/<int:id>")
@login_required
def delete_device_route(id):
    device = row_to_dict(get_device(id))
    if device:
        delete_device(id)
        flash(f"Устройство '{device['name']}' успешно удалено!", "success")
    else:
        flash("Устройство не найдено", "error")
    return redirect(url_for('dashboard'))


@app.route("/refresh_status")
@login_required
def refresh_status():
    devices = get_all_devices()
    updated_count = 0
    for device in devices:
        new_status = ping_service.check_device(device["ip"])
        if new_status != device["status"]:
            update_device_status(device["id"], new_status)
            updated_count += 1
    flash(f"Статусы обновлены! Изменено устройств: {updated_count}", "success")
    return redirect(url_for('dashboard'))

@app.route("/device/<int:id>", methods=["GET", "POST"])
@login_required
def device_detail(id):
    device = row_to_dict(get_device(id))
    if not device:
        flash("Устройство не найдено", "error")
        return redirect(url_for('dashboard'))

    user_id = session['user_id']

    if is_ip_blocked_for_user(user_id, device['ip']):
        flash(f"Access Denied: у вас нет доступа к устройству {device['ip']}", "error")
        return redirect(url_for('dashboard'))

    output = None
    command_used = None
    os_type = device.get('os_type') or 'cisco_ios'
    quick_commands = NetmikoService.get_quick_commands(os_type)

    if request.method == "POST":
        command = request.form.get("command", "").strip()
        if command:
            success, output = netmiko_service.execute_command(
                hostname=device['ip'],
                username=device['username'],
                password=device['password'],
                os_type=os_type,
                command=command
            )
            add_command_history(
                device_id=id,
                command=command,
                output=output,
                success=success,
                user_id=user_id
            )
            command_used = command
            if success:
                flash("Команда успешно выполнена", "success")
            else:
                flash("Ошибка выполнения команды", "error")

    history = get_command_history(id, limit=10)

    return render_template(
        "device.html",
        device=device,
        output=output,
        command_used=command_used,
        history=history,
        quick_commands=quick_commands,
        os_labels=OS_LABELS
    )

@app.route("/history")
@login_required
def command_history_page():
    history = get_all_command_history(limit=100)
    return render_template("history.html", history=history)

@app.route("/users")
@admin_required
def users_list():
    users = get_all_users()
    return render_template("users.html", users=users)


@app.route("/users/add", methods=["GET", "POST"])
@admin_required
def add_user_route():
    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password_val = request.form.get("password", "")
        role = request.form.get("role", "user")
        blocked_ips = request.form.get("blocked_ips", "").strip()
        if not login_val or not password_val:
            flash("Логин и пароль обязательны", "error")
        else:
            try:
                add_user(login_val, password_val, role, blocked_ips)
                flash(f"Пользователь '{login_val}' создан", "success")
                return redirect(url_for('users_list'))
            except Exception as e:
                flash(f"Ошибка: {str(e)}", "error")
    return render_template("user_form.html", user=None, action="add")


@app.route("/users/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_user_route(id):
    user = row_to_dict(get_user_by_id(id))
    if not user:
        flash("Пользователь не найден", "error")
        return redirect(url_for('users_list'))

    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        password_val = request.form.get("password", "")
        role = request.form.get("role", "user")
        blocked_ips = request.form.get("blocked_ips", "").strip()
        try:
            update_user(id, login_val, password_val, role, blocked_ips)
            flash(f"Пользователь '{login_val}' обновлён", "success")
            return redirect(url_for('users_list'))
        except Exception as e:
            flash(f"Ошибка: {str(e)}", "error")

    return render_template("user_form.html", user=user, action="edit")


@app.route("/users/delete/<int:id>")
@admin_required
def delete_user_route(id):
    if id == session.get('user_id'):
        flash("Нельзя удалить самого себя", "error")
        return redirect(url_for('users_list'))
    user = row_to_dict(get_user_by_id(id))
    if user:
        delete_user(id)
        flash(f"Пользователь '{user['login']}' удалён", "success")
    return redirect(url_for('users_list'))


@app.route("/bulk", methods=["GET", "POST"])
@login_required
def bulk_operations():
    """Массовая отправка команды на несколько устройств"""
    all_devices = get_all_devices()
    user_id = session['user_id']
    devices_list = []
    for d in all_devices:
        d_dict = row_to_dict(d)
        d_dict['blocked'] = is_ip_blocked_for_user(user_id, d_dict['ip'])
        devices_list.append(d_dict)

    results = None
    command_used = None

    if request.method == "POST":
        selected_ids = request.form.getlist("device_ids")
        command = request.form.get("command", "").strip()

        if not selected_ids:
            flash("Выберите хотя бы одно устройство", "error")
            return render_template("bulk.html", devices=devices_list, results=None, command_used=None, os_labels=OS_LABELS)

        if not command:
            flash("Введите команду для отправки", "error")
            return render_template("bulk.html", devices=devices_list, results=None, command_used=None, os_labels=OS_LABELS)

        results = []
        for dev_id in selected_ids:
            device = row_to_dict(get_device(int(dev_id)))
            if not device or is_ip_blocked_for_user(user_id, device['ip']):
                results.append({"ip": "—", "name": dev_id, "success": False, "output": "Нет доступа"})
                continue
            success, output = netmiko_service.execute_command(
                hostname=device['ip'],
                username=device['username'],
                password=device['password'],
                os_type=device.get('os_type') or 'cisco_ios',
                command=command
            )
            add_command_history(device_id=device['id'], command=command, output=output, success=success, user_id=user_id)
            results.append({"ip": device['ip'], "name": device['name'], "success": success, "output": output})

        command_used = command
        ok = sum(1 for r in results if r['success'])
        flash(f"Команда отправлена: {ok}/{len(results)} успешно", "success" if ok else "error")

    return render_template("bulk.html", devices=devices_list, results=results, command_used=command_used, os_labels=OS_LABELS)


@app.route("/bulk/export", methods=["POST"])
@login_required
def bulk_export():
    """Выгрузка конфигурации с нескольких устройств — ZIP-архив"""
    from flask import Response
    import zipfile, io

    selected_ids = request.form.getlist("device_ids")
    user_id = session['user_id']

    if not selected_ids:
        flash("Выберите хотя бы одно устройство", "error")
        return redirect(url_for('bulk_operations'))

    CONFIG_COMMANDS = {
        "cisco_ios":         "show running-config",
        "cisco_nxos":        "show running-config",
        "mikrotik_routeros": "/export compact",
        "juniper_junos":     "show configuration",
        "huawei_vrpv8":      "display current-configuration",
        "hp_comware":        "display current-configuration",
        "linux":             "ip addr show",
    }

    zip_buffer = io.BytesIO()
    collected = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for dev_id in selected_ids:
            device = row_to_dict(get_device(int(dev_id)))
            if not device or is_ip_blocked_for_user(user_id, device['ip']):
                continue
            os_type = device.get('os_type') or 'cisco_ios'
            cmd = CONFIG_COMMANDS.get(os_type, "show running-config")
            success, output = netmiko_service.execute_command(
                hostname=device['ip'],
                username=device['username'],
                password=device['password'],
                os_type=os_type,
                command=cmd
            )
            safe_name = device['name'].replace('/', '_').replace(' ', '_')
            filename = f"{safe_name}_{device['ip']}.txt"
            content = output if success else f"ОШИБКА: {output}"
            zf.writestr(filename, content)
            add_command_history(device_id=device['id'], command=cmd, output=output, success=success, user_id=user_id)
            collected += 1

    if collected == 0:
        flash("Не удалось получить конфиги ни с одного устройства", "error")
        return redirect(url_for('bulk_operations'))

    zip_buffer.seek(0)
    return Response(
        zip_buffer.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=configs_export.zip"}
    )


@app.route("/scan_network")
@login_required
def scan_network():
    flash("Функция сканирования сети пока в разработке", "info")
    return redirect(url_for('dashboard'))


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == "__main__":
    init_db()
    print("=" * 70)
    print("SSH Manager запущен")
    print("http://127.0.0.1:5000")
    print("=" * 70)
    app.run(debug=True, host='0.0.0.0', port=5000)
