try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False


class SSHService:
    @staticmethod
    def execute_command(hostname, username, password, command, timeout=15):
        if not PARAMIKO_AVAILABLE:
            return False, "❌ Библиотека paramiko не установлена.\nУстановите: pip install paramiko"
        
        if not username or not password:
            return False, "❌ Не указаны учетные данные для SSH подключения"
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=hostname,
                username=username,
                password=password,
                timeout=5,
                allow_agent=False,
                look_for_keys=False
            )
            
            stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            
            output = stdout.read().decode("utf-8", errors="replace")
            error = stderr.read().decode("utf-8", errors="replace")
            
            ssh.close()
            
            result = ""
            if output:
                result += output
            if error:
                result += "\n" + error if result else error
            
            if not result:
                result = "✅ Команда выполнена успешно (без вывода)"
            
            return True, result
            
        except paramiko.AuthenticationException:
            return False, "❌ Ошибка аутентификации: неверный логин или пароль"
        except paramiko.SSHException as e:
            return False, f"❌ Ошибка SSH: {str(e)}"
        except TimeoutError:
            return False, "❌ Превышено время ожидания подключения"
        except Exception as e:
            return False, f"❌ Неизвестная ошибка: {str(e)}"
    
    @staticmethod
    def test_connection(hostname, username, password):
        if not PARAMIKO_AVAILABLE:
            return False, "Paramiko не установлен"
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=hostname,
                username=username,
                password=password,
                timeout=5,
                allow_agent=False,
                look_for_keys=False
            )
            ssh.close()
            return True, "Подключение успешно"
        except Exception as e:
            return False, str(e)
