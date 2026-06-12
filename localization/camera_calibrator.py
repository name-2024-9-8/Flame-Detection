"""
相机标定 - 图像坐标 ↔ 地理坐标映射
方法: 选取视野中标志点，拟合单应矩阵 H
输入: 标志点的 (图像坐标, GPS经纬度) + PTZ参数
输出: 映射关系，用于将检测框中心点转为经纬度
"""
import json
from pathlib import Path

import numpy as np


class CameraCalibrator:
    """
    单相机标定器
    对每个摄像头，通过 N>=4 个标志点拟合图像→GPS的单应变换

    映射流程:
      检测框中心 (px, py) --[H]--> 经纬度 (lng, lat)
    """
    def __init__(self, camera_id):
        self.camera_id = camera_id
        # 标志点: [(img_x, img_y, lng, lat), ...]
        self.landmarks = []
        self.H = None        # 单应矩阵 (3x3)
        self.is_calibrated = False

    def add_landmark(self, img_x, img_y, lng, lat):
        """添加一个标志点: 图像坐标 + GPS经纬度"""
        self.landmarks.append((img_x, img_y, lng, lat))
        self.is_calibrated = False

    def add_landmarks_from_file(self, filepath):
        """从JSON文件加载标志点"""
        filepath = Path(filepath)
        if not filepath.exists():
            print(f"[警告] 标定文件不存在: {filepath}")
            return False
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for pt in data.get('landmarks', []):
            self.add_landmark(pt['img_x'], pt['img_y'], pt['lng'], pt['lat'])
        print(f"已加载 {len(self.landmarks)} 个标志点: {filepath.name}")
        return len(self.landmarks) > 0

    def calibrate(self):
        """
        拟合单应矩阵 H，使 [lng, lat, 1]^T ~ H * [x, y, 1]^T
        需要至少4个标志点 (通常需要更多以获得鲁棒性)
        """
        if len(self.landmarks) < 4:
            raise ValueError(f"至少需要4个标志点，当前 {len(self.landmarks)} 个")

        pts_img = np.array([[p[0], p[1]] for p in self.landmarks], dtype=np.float64)
        pts_gps = np.array([[p[2], p[3]] for p in self.landmarks], dtype=np.float64)

        # 使用OpenCV或最小二乘拟合单应
        try:
            import cv2
            self.H, mask = cv2.findHomography(pts_img, pts_gps, cv2.RANSAC, 5.0)
            inliers = np.sum(mask) if mask is not None else len(self.landmarks)
            print(f"RANSAC拟合完成, 内点: {inliers}/{len(self.landmarks)}")
        except ImportError:
            self.H = self._fit_homography_dlt(pts_img, pts_gps)
            print("DLT直接线性变换拟合完成")

        self.is_calibrated = True
        return self._compute_reprojection_error(pts_img, pts_gps)

    def _fit_homography_dlt(self, src, dst):
        """DLT算法拟合单应矩阵 (无需OpenCV)"""
        n = len(src)
        A = []
        for i in range(n):
            x, y = src[i]
            u, v = dst[i]
            A.append([-x, -y, -1, 0, 0, 0, u*x, u*y, u])
            A.append([0, 0, 0, -x, -y, -1, v*x, v*y, v])
        A = np.array(A, dtype=np.float64)

        # SVD分解求最小特征向量
        _, _, Vt = np.linalg.svd(A)
        H = Vt[-1].reshape(3, 3)
        return H / H[2, 2]  # 归一化

    def _compute_reprojection_error(self, pts_img, pts_gps):
        """计算重投影误差 (米)"""
        errors = []
        for (x, y), (lng, lat) in zip(pts_img, pts_gps):
            p = self.H @ np.array([x, y, 1.0])
            lng_pred, lat_pred = p[0] / p[2], p[1] / p[2]
            # 经纬度差转为近似米 (1度经度≈111320m, 1度纬度≈111320*cos(lat)m)
            d_lng = (lng_pred - lng) * 111320 * np.cos(np.radians(lat))
            d_lat = (lat_pred - lat) * 111320
            error = np.sqrt(d_lng**2 + d_lat**2)
            errors.append(error)

        errors = np.array(errors)
        max_err = errors.max()
        mean_err = errors.mean()
        print(f"重投影误差: 均值={mean_err:.1f}m, 最大={max_err:.1f}m")
        return mean_err, max_err

    def image_to_gps(self, img_x, img_y):
        """图像坐标 -> GPS经纬度"""
        if not self.is_calibrated:
            raise RuntimeError("相机未标定，请先调用 calibrate()")
        p = self.H @ np.array([img_x, img_y, 1.0])
        lng = p[0] / p[2]
        lat = p[1] / p[2]
        return lng, lat

    def save_calibration(self, save_path):
        """保存标定结果"""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'camera_id': self.camera_id,
            'landmarks': [
                {'img_x': float(p[0]), 'img_y': float(p[1]),
                 'lng': float(p[2]), 'lat': float(p[3])}
                for p in self.landmarks
            ],
            'H': self.H.tolist() if self.H is not None else None,
            'is_calibrated': self.is_calibrated,
        }
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"标定结果已保存: {save_path}")

    def load_calibration(self, load_path):
        """加载标定结果"""
        load_path = Path(load_path)
        if not load_path.exists():
            print(f"[警告] 标定文件不存在: {load_path}")
            return False
        with open(load_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.camera_id = data['camera_id']
        self.landmarks = [(p['img_x'], p['img_y'], p['lng'], p['lat'])
                          for p in data['landmarks']]
        if data['H'] is not None:
            self.H = np.array(data['H'])
            self.is_calibrated = data['is_calibrated']
        print(f"已加载标定: {load_path.name}")
        return True


def create_sample_calibration(save_path):
    """创建样本标定数据用于测试"""
    calib = CameraCalibrator("camera_001")

    # 模拟视野中的4个标志点 (图像坐标, 经纬度)
    # 假设: 图像416x416, 对应一个约500x500m的区域
    calib.add_landmark(50, 50, 116.391200, 39.907500)
    calib.add_landmark(366, 50, 116.396800, 39.907500)
    calib.add_landmark(50, 366, 116.391200, 39.903100)
    calib.add_landmark(366, 366, 116.396800, 39.903100)
    calib.add_landmark(208, 208, 116.394000, 39.905300)
    calib.add_landmark(100, 300, 116.392500, 39.904200)

    calib.calibrate()
    calib.save_calibration(save_path)
    return calib


if __name__ == "__main__":
    from config import DATA_DIR
    save_path = DATA_DIR / "camera_calib" / "camera_001_calib.json"
    calib = create_sample_calibration(save_path)

    # 测试: 图像中心 -> GPS
    lng, lat = calib.image_to_gps(208, 208)
    print(f"\n图像中心(208,208) -> 经纬度: ({lng:.6f}, {lat:.6f})")
    print(f"预期: (116.394000, 39.905300)")
