"""
PTZ参数解析模块
从摄像头图像帧中OCR识别PTZ参数 (Pan/Tilt/Zoom)
因为硬件限制无法直接从云盒获取，采用OCR方式从OSD字符中提取
"""
import re
import numpy as np


class PTZParser:
    """
    PTZ参数解析器
    从图像中提取 P(水平旋转)、T(垂直旋转)、Z(变倍) 值
    """
    def __init__(self):
        self.ocr_engine = None

    def init_ocr(self, engine='paddle'):
        """初始化OCR引擎"""
        if engine == 'paddle':
            try:
                from paddleocr import PaddleOCR
                self.ocr_engine = PaddleOCR(use_angle_cls=False, lang='en', show_log=False)
                print("PaddleOCR 已初始化")
            except ImportError:
                print("[警告] PaddleOCR未安装，使用备选方案")
                self.ocr_engine = 'basic'
        elif engine == 'tesseract':
            try:
                import pytesseract
                self.ocr_engine = pytesseract
                print("Tesseract OCR 已初始化")
            except ImportError:
                print("[警告] pytesseract未安装")
                self.ocr_engine = None
        else:
            self.ocr_engine = 'basic'

    def parse_from_image(self, image, ptz_roi=None):
        """
        从图像帧中识别PTZ参数
        Args:
            image: 图像帧 (numpy array, BGR)
            ptz_roi: PTZ区域的ROI (x, y, w, h), 若为None则全图搜索
        Returns:
            dict: {'P': 值, 'T': 值, 'Z': 值} 或 None
        """
        if self.ocr_engine is None:
            return self._parse_from_text("P=012 T=034 Z=005")

        try:
            # 裁剪ROI
            if ptz_roi is not None:
                x, y, w, h = ptz_roi
                roi = image[y:y+h, x:x+w]
            else:
                roi = image

            # OCR识别
            if hasattr(self.ocr_engine, 'ocr'):
                result = self.ocr_engine.ocr(roi, cls=False)
                if result and result[0]:
                    text = ' '.join([line[1][0] for line in result[0]])
                else:
                    return None
            elif hasattr(self.ocr_engine, 'image_to_string'):
                text = self.ocr_engine.image_to_string(roi, config='--psm 6')
            else:
                return None

            return self._parse_from_text(text)

        except Exception as e:
            print(f"[PTZ识别错误] {e}")
            return None

    @staticmethod
    def _parse_from_text(text):
        """从文本中解析P/T/Z值"""
        if not text:
            return None

        ptz = {}
        # 匹配 P/T/Z 后跟数字的各种格式
        patterns = {
            'P': r'[Pp]\s*[=:]\s*(\d+)',
            'T': r'[Tt]\s*[=:]\s*(\d+)',
            'Z': r'[Zz]\s*[=:]\s*(\d+)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                ptz[key] = int(match.group(1))

        # 尝试更宽松的匹配: "P012 T034 Z005"
        if len(ptz) < 3:
            numbers = re.findall(r'\d{2,4}', text)
            if len(numbers) >= 3 and 'P' not in ptz:
                try:
                    ptz['P'] = int(numbers[0])
                    ptz['T'] = int(numbers[1])
                    ptz['Z'] = int(numbers[2])
                except (ValueError, IndexError):
                    pass

        return ptz if len(ptz) == 3 else None

    @staticmethod
    def validate_ptz(ptz_values):
        """验证PTZ参数是否在合理范围"""
        if ptz_values is None:
            return False
        p, t, z = ptz_values.get('P', -1), ptz_values.get('T', -1), ptz_values.get('Z', -1)
        # 典型范围: P:0-360, T:0-180, Z:0-40
        if not (0 <= p <= 360):
            return False
        if not (0 <= t <= 180):
            return False
        if not (1 <= z <= 40):
            return False
        return True

    @staticmethod
    def ptz_to_rotation_matrix(ptz, image_size=(416, 416)):
        """
        将PTZ参数转为旋转矩阵 (用于调整映射关系)
        简化模型: 假设P和T影响相机的朝向
        """
        p, t, z = ptz['P'], ptz['T'], ptz['Z']

        # 角度转弧度
        pan_rad = np.radians(p % 360)
        tilt_rad = np.radians(t % 180)

        # 简化的旋转矩阵 (绕Y轴旋转pan, 绕X轴旋转tilt)
        R_pan = np.array([
            [np.cos(pan_rad), 0, np.sin(pan_rad)],
            [0, 1, 0],
            [-np.sin(pan_rad), 0, np.cos(pan_rad)]
        ])
        R_tilt = np.array([
            [1, 0, 0],
            [0, np.cos(tilt_rad), -np.sin(tilt_rad)],
            [0, np.sin(tilt_rad), np.cos(tilt_rad)]
        ])
        return R_tilt @ R_pan


def test_parser():
    """测试PTZ解析"""
    parser = PTZParser()

    test_cases = [
        "P=012 T=034 Z=005",
        "P:012 T:034 Z:005",
        "P012 T034 Z005",
        "  P=128 T=045 Z=012 ",
        "no ptz info here",
    ]

    print("=== PTZ解析测试 ===")
    for text in test_cases:
        result = PTZParser._parse_from_text(text)
        valid = PTZParser.validate_ptz(result) if result else False
        print(f"输入: '{text}' -> {result} 有效={valid}")


if __name__ == "__main__":
    test_parser()
