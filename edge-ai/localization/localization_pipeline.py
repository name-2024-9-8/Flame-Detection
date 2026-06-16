"""
定位流水线 - 将检测结果转为带经纬度的报警事件
完整流程:
  检测框 → 中心点 → 单应映射 → PTZ校正 → 经纬度 → 逆地址解析 → 报警事件
"""
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List

import numpy as np

from localization.camera_calibrator import CameraCalibrator
from localization.ptz_parser import PTZParser
from localization.geo_mapper import GeoMapper


@dataclass
class DetectionResult:
    """单次检测结果"""
    bbox_center: tuple   # (cx, cy) 归一化[0,1]或像素坐标
    bbox_size: tuple     # (w, h)
    confidence: float    # [0, 1]
    is_smoke: bool = True


@dataclass
class AlarmEvent:
    """最终报警事件 - 供后端入库和前端展示"""
    camera_id: str
    timestamp: str = ""
    image_path: str = ""
    video_path: str = ""
    lng: float = 0.0
    lat: float = 0.0
    location: str = ""
    confidence: float = 0.0
    ptz_values: Optional[dict] = None

    def to_dict(self):
        """转dict, 用于JSON序列化传给后端"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self):
        """转JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class LocalizationPipeline:
    """
    烟尘定位流水线
    整合: 检测结果 + PTZ识别 + 坐标映射 + 逆地址解析
    """
    def __init__(self, camera_id, calib_path=None, image_size=416):
        self.camera_id = camera_id
        self.image_size = image_size

        # 初始化各模块
        self.calibrator = CameraCalibrator(camera_id)
        self.ptz_parser = PTZParser()
        self.mapper = None

        # 加载标定
        if calib_path:
            loaded = self.calibrator.load_calibration(calib_path)
            if loaded:
                self.calibrator.calibrate()
                self.mapper = GeoMapper(self.calibrator)

    def init_ocr(self, engine='basic'):
        """初始化OCR"""
        self.ptz_parser.init_ocr(engine)

    def process_detection(self, detection: DetectionResult,
                          camera_image=None, ptz_values=None) -> Optional[AlarmEvent]:
        """
        处理单次检测结果 -> 报警事件
        Args:
            detection: 检测结果
            camera_image: 摄像头图像帧 (用于OCR提取PTZ)
            ptz_values: 也可直接传入PTZ值
        Returns:
            AlarmEvent 或 None
        """
        if self.mapper is None:
            print("[警告] 定位器未标定")
            return None

        # 1. 获取PTZ参数
        if ptz_values is None and camera_image is not None:
            ptz_values = self.ptz_parser.parse_from_image(camera_image)

        # 2. 检测框中心点坐标
        cx, cy = self._get_pixel_coord(detection.bbox_center)

        # 3. 图像坐标 -> GPS
        lng, lat = self.mapper.detection_to_gps(cx, cy, ptz_values)

        # 4. 逆地址解析
        location = GeoMapper.reverse_geocode(lng, lat)

        # 5. 组装报警事件
        event = AlarmEvent(
            camera_id=self.camera_id,
            lng=lng,
            lat=lat,
            location=location,
            confidence=detection.confidence,
            ptz_values=ptz_values,
        )
        return event

    def _get_pixel_coord(self, bbox_center):
        """将归一化坐标或像素坐标转为像素坐标"""
        cx, cy = bbox_center
        if cx < 1.0 and cy < 1.0:  # 归一化坐标
            cx = cx * self.image_size
            cy = cy * self.image_size
        return cx, cy

    def batch_process(self, detections: List[DetectionResult],
                      camera_image=None, ptz_values=None) -> List[AlarmEvent]:
        """批量处理多个检测结果"""
        events = []
        for det in detections:
            event = self.process_detection(det, camera_image, ptz_values)
            if event:
                events.append(event)
        return events

    def verify_accuracy(self, test_points, max_error_m=200):
        """
        验证定位精度
        test_points: [(img_x, img_y, expected_lng, expected_lat), ...]
        max_error_m: 最大允许误差 (默认200m)
        Returns: (平均误差, 最大误差, 是否达标)
        """
        errors = []
        for img_x, img_y, exp_lng, exp_lat in test_points:
            pred_lng, pred_lat = self.calibrator.image_to_gps(img_x, img_y)
            d_lng = (pred_lng - exp_lng) * 111320 * np.cos(np.radians(exp_lat))
            d_lat = (pred_lat - exp_lat) * 111320
            error = np.sqrt(d_lng**2 + d_lat**2)
            errors.append(error)

        errors = np.array(errors)
        mean_err = errors.mean()
        max_err = errors.max()
        passed = max_err <= max_error_m

        print(f"\n=== 定位精度验证 ===")
        print(f"测试点数: {len(test_points)}")
        print(f"平均误差: {mean_err:.1f}m")
        print(f"最大误差: {max_err:.1f}m")
        print(f"允许误差: {max_error_m}m")
        print(f"结果: {'通过' if passed else '不通过'}")

        return mean_err, max_err, passed

    def export_calibration_data(self, save_path):
        """导出标定数据文件 (供其他摄像头参考)"""
        self.calibrator.save_calibration(save_path)


def demo_pipeline():
    """演示完整的定位流水线"""
    from config import DATA_DIR

    calib_path = DATA_DIR / "camera_calib" / "camera_001_calib.json"

    # 初始化流水线
    pipeline = LocalizationPipeline("camera_001", calib_path)

    # 模拟多个检测结果
    detections = [
        DetectionResult(bbox_center=(0.3, 0.4), bbox_size=(0.1, 0.1), confidence=0.92),
        DetectionResult(bbox_center=(0.6, 0.7), bbox_size=(0.08, 0.08), confidence=0.85),
        DetectionResult(bbox_center=(0.5, 0.3), bbox_size=(0.12, 0.12), confidence=0.78),
    ]

    # 模拟PTZ参数
    ptz = {'P': 10, 'T': 5, 'Z': 3}

    print("=== 定位流水线演示 ===")
    events = pipeline.batch_process(detections, ptz_values=ptz)
    for i, event in enumerate(events):
        print(f"\n事件 {i+1}:")
        print(f"  位置: ({event.lng:.6f}, {event.lat:.6f})")
        print(f"  地址: {event.location}")
        print(f"  置信度: {event.confidence:.2f}")
        print(f"  JSON: {event.to_json()[:80]}...")

    # 验证精度
    test_pts = [
        (50, 50, 116.391200, 39.907500),
        (366, 50, 116.396800, 39.907500),
        (208, 208, 116.394000, 39.905300),
    ]
    pipeline.verify_accuracy(test_pts)


if __name__ == "__main__":
    demo_pipeline()
