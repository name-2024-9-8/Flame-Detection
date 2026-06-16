"""
地理映射模块 - 将检测结果转为GPS坐标 + 逆地址解析
支持: 单应映射 + PTZ参数校正 + 坐标解析
"""
import json
from pathlib import Path

import numpy as np


class GeoMapper:
    """
    地理坐标映射器
    将烟尘检测框中心点(图像坐标) 映射为 GPS经纬度 + 文字地址
    """
    def __init__(self, camera_calibrator):
        self.calibrator = camera_calibrator

    def detection_to_gps(self, img_x, img_y, ptz_values=None):
        """
        检测框中心点 -> 经纬度
        可选: 使用PTZ参数对映射进行微调
        """
        # 基础映射
        lng, lat = self.calibrator.image_to_gps(img_x, img_y)

        # PTZ校正: 如果PTZ相对于标定时有变化，调整映射
        if ptz_values is not None:
            lng, lat = self._apply_ptz_correction(lng, lat, ptz_values)

        return lng, lat

    @staticmethod
    def _apply_ptz_correction(lng, lat, ptz_values):
        """
        PTZ偏移校正
        当摄像头转动后，原始映射会偏移，需要根据PTZ差值补偿
        简化模型: P每变化1度 ≈ 经度偏移0.0002 (约20m)
                  T每变化1度 ≈ 纬度偏移0.00015 (约15m)
        """
        p = ptz_values.get('P', 0)
        t = ptz_values.get('T', 0)
        z = ptz_values.get('Z', 1)

        # 以P=0,T=0,Z=1为基准的简化校正
        p_offset = (p - 0) * 0.0002
        t_offset = (t - 0) * 0.00015

        return lng + p_offset, lat + t_offset

    @staticmethod
    def reverse_geocode(lng, lat, api_key=None):
        """
        经纬度 -> 文字地址
        支持: 百度/高德逆地理编码API
        离线: 使用内置地名库近似匹配
        """
        if api_key:
            return GeoMapper._online_reverse_geocode(lng, lat, api_key)
        else:
            return GeoMapper._offline_reverse_geocode(lng, lat)

    @staticmethod
    def _online_reverse_geocode(lng, lat, api_key):
        """在线逆地址解析"""
        import urllib.request
        import urllib.parse

        try:
            # 百度逆地理编码API
            url = (
                f"https://api.map.baidu.com/reverse_geocoding/v3/"
                f"?ak={api_key}&output=json&coordtype=wgs84ll"
                f"&location={lat},{lng}"
            )
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('status') == 0:
                    result = data.get('result', {})
                    return result.get('formatted_address', '未知地址')
        except Exception as e:
            print(f"[逆地址解析错误] {e}")

        return f"{lng:.4f},{lat:.4f}"

    @staticmethod
    def _offline_reverse_geocode(lng, lat):
        """
        离线逆地址解析 (近似)
        通过预定义的区域边界进行匹配
        """
        from config import DATA_DIR
        region_file = DATA_DIR / "camera_calib" / "regions.json"

        if region_file.exists():
            with open(region_file, 'r', encoding='utf-8') as f:
                regions = json.load(f)

            for region in regions:
                if GeoMapper._point_in_polygon(lng, lat, region['boundary']):
                    return region['name']

        # 无匹配时返回坐标字符串
        return f"{lng:.6f},{lat:.6f}"

    @staticmethod
    def _point_in_polygon(lng, lat, polygon):
        """射线法判断点是否在多边形内"""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            yi, xi = polygon[i]
            yj, xj = polygon[j]
            if ((yi > lat) != (yj > lat)) and \
                    (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside


def create_sample_regions(save_path):
    """创建样本地域数据, 用于离线逆地址解析测试"""
    regions = [
        {
            "name": "A区-工业园区",
            "boundary": [
                [116.390, 39.907], [116.398, 39.907],
                [116.398, 39.902], [116.390, 39.902]
            ]
        },
        {
            "name": "B区-居民区",
            "boundary": [
                [116.398, 39.907], [116.406, 39.907],
                [116.406, 39.902], [116.398, 39.902]
            ]
        }
    ]
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(regions, f, ensure_ascii=False, indent=2)
    print(f"区域数据已创建: {save_path}")


if __name__ == "__main__":
    from config import DATA_DIR
    from localization.camera_calibrator import CameraCalibrator

    # 加载标定
    calib = CameraCalibrator("camera_001")
    calib_path = DATA_DIR / "camera_calib" / "camera_001_calib.json"
    calib.load_calibration(calib_path)

    # 创建样例区域
    region_path = DATA_DIR / "camera_calib" / "regions.json"
    create_sample_regions(region_path)

    # 测试映射
    mapper = GeoMapper(calib)
    lng, lat = calib.image_to_gps(208, 208)
    print(f"\n检测中心(208,208) -> 经纬度: ({lng:.6f}, {lat:.6f})")

    address = GeoMapper.reverse_geocode(lng, lat)
    print(f"逆地址解析: {address}")
