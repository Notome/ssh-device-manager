try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False

OS_COMMANDS = {
    "cisco_ios": [
        "show version",
        "show ip interface brief",
        "show running-config",
        "show interfaces",
        "show vlan brief",
        "show mac address-table",
        "show ip route",
        "show cdp neighbors",
    ],
    "cisco_nxos": [
        "show version",
        "show ip interface brief",
        "show running-config",
        "show interfaces",
        "show vlan",
        "show mac address-table",
        "show ip route",
        "show cdp neighbors",
    ],
    "mikrotik_routeros": [
        "/system identity print",
        "/ip address print",
        "/interface print",
        "/ip route print",
        "/ip firewall filter print",
        "/system resource print",
        "/log print",
    ],
    "juniper_junos": [
        "show version",
        "show interfaces terse",
        "show route",
        "show configuration",
        "show system uptime",
        "show chassis hardware",
    ],
    "huawei_vrpv8": [
        "display version",
        "display ip interface brief",
        "display interface brief",
        "display ip routing-table",
        "display current-configuration",
        "display cpu-usage",
    ],
    "hp_comware": [
        "display version",
        "display interface brief",
        "display ip routing-table",
        "display current-configuration",
        "display cpu-usage",
    ],
    "linux": [
        "uname -a",
        "ip addr",
        "ip route",
        "df -h",
        "free -h",
        "uptime",
        "ps aux --sort=-%cpu | head -15",
        "netstat -tlnp",
    ],
}

OS_LABELS = {
    "cisco_ios": "Cisco IOS",
    "cisco_nxos": "Cisco NX-OS",
    "mikrotik_routeros": "MikroTik RouterOS",
    "juniper_junos": "Juniper JunOS",
    "huawei_vrpv8": "Huawei VRP",
    "hp_comware": "HP / Aruba",
    "linux": "Linux Server",
}


class NetmikoService:
    @staticmethod
    def execute_command(hostname, username, password, os_type, command, timeout=30):
        if not NETMIKO_AVAILABLE:
            return False, "Библиотека netmiko не установлена.\nУстановите: pip install netmiko"

        if not username or not password:
            return False, "Не указаны учётные данные для подключения"

        device_params = {
            "device_type": os_type,
            "host": hostname,
            "username": username,
            "password": password,
            "timeout": timeout,
            "conn_timeout": 10,
        }

        try:
            with ConnectHandler(**device_params) as conn:
                output = conn.send_command(command, read_timeout=timeout)
            return True, output if output else "✅ Команда выполнена успешно (без вывода)"
        except NetmikoAuthenticationException:
            return False, "Ошибка аутентификации: неверный логин или пароль"
        except NetmikoTimeoutException:
            return False, "Превышено время ожидания подключения"
        except Exception as e:
            return False, f"Ошибка подключения: {str(e)}"

    @staticmethod
    def test_connection(hostname, username, password, os_type):
        if not NETMIKO_AVAILABLE:
            return False, "Netmiko не установлен"
        device_params = {
            "device_type": os_type,
            "host": hostname,
            "username": username,
            "password": password,
            "timeout": 10,
            "conn_timeout": 8,
        }
        try:
            with ConnectHandler(**device_params) as conn:
                pass
            return True, "Подключение успешно"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_quick_commands(os_type):
        return OS_COMMANDS.get(os_type, [])

    @staticmethod
    def get_os_labels():
        return OS_LABELS
