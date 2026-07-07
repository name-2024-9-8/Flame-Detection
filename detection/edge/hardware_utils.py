"""Orange Pi 5 (RK3588S) 硬件工具类 — NPU温度、GPIO、IP检测"""
import socket


class OrangePi5Utils:
    """Orange Pi 5 硬件工具类"""

    @staticmethod
    def get_npu_temp() -> float:
        """读取 NPU 温度"""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception:
            return 0.0

    @staticmethod
    def get_cpu_temp() -> float:
        """读取 CPU 温度"""
        try:
            with open("/sys/class/thermal/thermal_zone1/temp", "r") as f:
                return float(f.read().strip()) / 1000.0
        except Exception:
            return 0.0

    @staticmethod
    def get_npu_usage() -> float:
        """获取 NPU 使用率 (需要 rknn-server 支持)"""
        try:
            with open("/sys/kernel/debug/rknpu/load", "r") as f:
                parts = f.read().strip().split()
                if len(parts) >= 3:
                    return float(parts[2].rstrip('%'))
        except Exception:
            pass
        return 0.0

    @staticmethod
    def set_gpio_led(state: bool):
        """控制 GPIO LED 指示灯"""
        try:
            gpio_path = "/sys/class/gpio/gpio7"
            with open(f"{gpio_path}/value", "w") as f:
                f.write("1" if state else "0")
        except Exception:
            pass

    @staticmethod
    def get_ip_address() -> str:
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def check_npu_ready() -> bool:
        """检查 NPU 是否就绪"""
        try:
            from rknnlite.api import RKNNLite
            return True
        except ImportError:
            return False
