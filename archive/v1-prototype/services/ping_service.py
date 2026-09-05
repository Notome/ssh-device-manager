import subprocess
import platform


class PingService:    
    @staticmethod
    def check_device(ip, timeout=3):
        param = "-n" if platform.system().lower() == "windows" else "-c"
        
        try:
            subprocess.check_call(
                ["ping", param, "1", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout
            )
            return "online"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            return "offline"
    
    @staticmethod
    def check_multiple_devices(devices, timeout=3):
        results = {}
        for device in devices:
            status = PingService.check_device(device['ip'], timeout)
            results[device['id']] = status
        return results
