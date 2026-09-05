import subprocess
import shlex
from datetime import datetime


class LocalCmdService:
    @staticmethod
    def execute_command(command: str, timeout: int = 30):
        try:
            if subprocess.os.name == 'nt':
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding='utf-8',
                    errors='replace'
                )
            else:
                args = shlex.split(command)
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding='utf-8',
                    errors='replace'
                )

            output = result.stdout
            if result.stderr:
                output += "\n[STDERR]\n" + result.stderr

            success = result.returncode == 0

            if not output.strip():
                output = "Команда выполнена успешно (вывод пустой)"

            return success, output

        except subprocess.TimeoutExpired:
            return False, f"❌ Команда превысила время выполнения ({timeout} сек)"
        except FileNotFoundError:
            return False, f"❌ Команда не найдена: {command}"
        except Exception as e:
            return False, f"❌ Ошибка выполнения: {str(e)}"


local_cmd = LocalCmdService()