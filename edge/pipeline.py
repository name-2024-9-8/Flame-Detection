"""
边缘端主控管线 - 串联所有边缘模块
- 视频采集 → 预处理 → AI推理 → 定位计算 → 结果输出
- 心跳保活
- 故障检测与上报
- 性能监控
"""
from __future__ import annotations
import time
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

import numpy as np
import cv2

from .video_stream import RTSPStreamReader, CameraConfig, SimulatedCamera
from .preprocessing import ImagePreprocessor, PreprocessConfig
from .inference_engine import YOLOInferenceEngine, InferenceResult, DetectionBox
from .temporal_filter import TemporalFilter, FilterConfig as TemporalFilterConfig
from .output_module import (
    ResultPublisher, AlarmEvent, DeviceHeartbeat,
    DeviceError, encode_frame_base64,
    save_video_clip, extract_clip_frames,
)

# 定位模块 (可选, 需要标定数据)
try:
    from localization.localization_pipeline import LocalizationPipeline, DetectionResult
    from localization.geo_mapper import GeoMapper
    HAS_LOCALIZATION = True
except ImportError:
    HAS_LOCALIZATION = False

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("EdgePipeline")


@dataclass
class EdgeConfig:
    """边缘端配置"""
    # 模型
    model_path: str = "output/export/smoke_detector.onnx"
    conf_threshold: float = 0.25
    iou_threshold: float = 0.5
    img_size: int = 416
    # 视频
    camera: CameraConfig = None
    target_fps: int = 15
    # 预处理
    enable_dehaze: bool = True
    enable_clahe: bool = True
    # 输出
    server_url: str = "http://127.0.0.1:8083"
    api_key: str = ""
    # 心跳
    heartbeat_interval: float = 30.0  # 秒
    # 视频片段
    clip_pre_frames: int = 30   # 报警前2秒
    clip_post_frames: int = 45  # 报警后3秒
    clip_dir: str = "output/clips"
    # 定位
    calib_dir: str = "data/camera_calib"
    enable_localization: bool = True
    # 性能
    latency_target_ms: float = 2000.0  # 时延目标 ≤2s
    # 时域滤波 (消除偶发误报)
    temporal_window_size: int = 5     # 滑动窗口大小
    temporal_vote_threshold: int = 3   # 触发所需检测帧数
    temporal_cooldown_frames: int = 30 # 报警冷却帧数
    # 调试
    show_preview: bool = False
    save_annotated: bool = True


class EdgePipeline:
    """边缘端主控管线"""

    def __init__(self, config: EdgeConfig):
        self.cfg = config
        self.running = False

        # 初始化各模块
        if config.camera is not None:
            self.stream = RTSPStreamReader(config.camera)
        else:
            self.stream = None

        pre_cfg = PreprocessConfig(
            target_size=(config.img_size, config.img_size),
            enable_dehaze=config.enable_dehaze,
            enable_clahe=config.enable_clahe,
        )
        self.preprocessor = ImagePreprocessor(pre_cfg)

        self.engine = YOLOInferenceEngine(
            model_path=config.model_path,
            conf_threshold=config.conf_threshold,
            iou_threshold=config.iou_threshold,
            img_size=config.img_size,
        )

        self.publisher = ResultPublisher(
            server_url=config.server_url,
            api_key=config.api_key,
        )

        # 时域滤波器 (降低误报率: 单帧FPR 19.3% → 5帧3投票 ~0.7%)
        self._temporal_filter = TemporalFilter(TemporalFilterConfig(
            window_size=config.temporal_window_size,
            vote_threshold=config.temporal_vote_threshold,
            cooldown_frames=config.temporal_cooldown_frames,
        ))

        Path(config.clip_dir).mkdir(parents=True, exist_ok=True)

        # 帧缓冲区 (用于视频片段)
        self._frame_buffer: list[np.ndarray] = []
        self._max_buffer_size = config.clip_pre_frames + config.clip_post_frames + 10

        # 定位模块 (按需加载标定)
        self._localization: dict[int, LocalizationPipeline] = {}
        if HAS_LOCALIZATION and config.enable_localization:
            self._init_localization()

        # 状态
        self._last_heartbeat = 0.0
        self._frame_count = 0
        self._detection_count = 0
        self._heartbeat_thread: Optional[threading.Thread] = None

    def _init_localization(self):
        """加载所有可用相机的标定数据"""
        calib_root = Path(self.cfg.calib_dir)
        if not calib_root.exists():
            logger.info(f"标定目录不存在: {calib_root}, 跳过定位模块初始化")
            return
        for f in sorted(calib_root.glob("*.json")):
            try:
                # 从文件名提取 camera_id (如 camera_001_calib.json → camera_001)
                cam_name = f.stem.replace('_calib', '')
                pipeline = LocalizationPipeline(cam_name)
                pipeline.calibrator.load_calibration(str(f))
                pipeline.calibrator.calibrate()
                if pipeline.calibrator.is_calibrated:
                    pipeline.mapper = GeoMapper(pipeline.calibrator)
                    self._localization[cam_name] = pipeline
                    logger.info(f"定位模块已加载: {cam_name} ({f.name})")
            except Exception as e:
                logger.warning(f"加载标定失败 {f.name}: {e}")

    def _calc_location(self, detection_center: tuple,
                       frame_shape: tuple,
                       camera_id) -> tuple:
        """根据检测框中心点计算 GPS 坐标 (供 process_frame 回调使用)"""
        cx, cy = detection_center
        h, w = frame_shape

        # 归一化坐标
        nx = cx / w
        ny = cy / h

        # 查找该摄像头的定位流水线
        cam_key = f"camera_{camera_id:03d}"
        lp = self._localization.get(cam_key) or next(iter(self._localization.values()), None)

        if lp is None:
            return 0.0, 0.0, ""

        try:
            det = DetectionResult(
                bbox_center=(nx, ny),
                bbox_size=(0.1, 0.1),
                confidence=0.5,
            )
            event = lp.process_detection(det)
            if event:
                return event.lng, event.lat, event.location
        except Exception as e:
            logger.warning(f"定位计算失败: {e}")

        return 0.0, 0.0, ""

    def start(self) -> bool:
        """启动管线"""
        if self.stream is not None:
            if not self.stream.connect():
                logger.error("无法连接摄像头")
                return False

        self.running = True

        # 启动心跳线程
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        logger.info("边缘端管线已启动")
        return True

    def stop(self):
        """停止管线"""
        self.running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5.0)
        if self.stream:
            self.stream.close()
        self.publisher.flush_cache()
        logger.info(f"边缘端管线已停止 (检测帧: {self._detection_count}/{self._frame_count})")

    def process_frame(self, frame: np.ndarray,
                       camera_id: int = 0,
                       device_id: int = 0,
                       area_id: int = 0,
                       longitude: float = 0.0,
                       latitude: float = 0.0,
                       location_text: str = "",
                       calc_location_fn: Optional[callable] = None,
                       ) -> Optional[InferenceResult]:
        """处理单帧图像"""
        t_start = time.perf_counter()

        # 1. 预处理
        input_tensor = self.preprocessor.process(frame)

        # 2. AI推理
        outputs = self.engine.infer(input_tensor)

        # 3. 后处理
        detections = self.engine.postprocess_onnx(outputs, frame.shape[:2])

        # 4. 标注图像
        annotated = self.engine.annotate_frame(frame, detections) if detections else frame

        # 5. 计算时延
        elapsed = (time.perf_counter() - t_start) * 1000

        result = InferenceResult(
            camera_id=camera_id,
            timestamp=time.time(),
            detections=detections,
            image_raw=frame,
            image_annotated=annotated,
            inference_time_ms=elapsed,
        )

        # 6. 时域滤波 + 报警
        if result.has_detection:
            self._handle_detection(result, device_id, area_id,
                                    longitude, latitude, location_text,
                                    calc_location_fn)
        else:
            # 无检测帧也更新时域滤波器 (用于滑动窗口投票计数)
            self._temporal_filter.update(has_fire=False, confidence=0.0,
                                         camera_id=result.camera_id)

        self._frame_count += 1
        return result

    def _handle_detection(self, result: InferenceResult,
                           device_id: int, area_id: int,
                           lng: float, lat: float, loc: str,
                           calc_location_fn: Optional[callable]):
        """处理检测事件 (经时域滤波确认后才发送报警)"""
        self._detection_count += 1
        best = max(result.detections, key=lambda d: d.confidence)

        # 时域滤波: 滑动窗口投票确认, 消除偶发误报
        fire_event = self._temporal_filter.update(
            has_fire=True,
            confidence=best.confidence,
            camera_id=result.camera_id,
        )
        if fire_event is None:
            return  # 尚未达到投票阈值, 不发送报警

        # 计算定位 (如果有定位函数)
        final_lng, final_lat, final_loc = lng, lat, loc
        if calc_location_fn:
            try:
                final_lng, final_lat, final_loc = calc_location_fn(
                    best.center, result.image_raw.shape
                )
            except Exception as e:
                logger.warning(f"定位计算失败: {e}")

        # 保存视频片段
        video_path = ""
        if len(self._frame_buffer) >= self.cfg.clip_pre_frames:
            clip_frames = extract_clip_frames(
                self._frame_buffer,
                trigger_idx=-1,
                pre_frames=self.cfg.clip_pre_frames,
                post_frames=self.cfg.clip_post_frames,
            )
            if clip_frames:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_path = str(Path(self.cfg.clip_dir) / f"alarm_{result.camera_id}_{ts}.mp4")
                save_video_clip(clip_frames, video_path, fps=15, duration=5.0)

        # 编码检测帧
        picture_b64 = encode_frame_base64(result.image_annotated)

        # 构建报警事件
        now = datetime.now(timezone.utc).isoformat()
        urgency = "高" if best.confidence > 0.8 else ("中" if best.confidence > 0.5 else "低")

        event = AlarmEvent(
            camera_id=result.camera_id,
            device_id=device_id,
            area_id=area_id,
            timestamp=now,
            longitude=final_lng,
            latitude=final_lat,
            location=final_loc,
            confidence=best.confidence,
            urgency_degree=urgency,
            description=f"检测到火焰/烟尘 (置信度: {best.confidence:.2f})",
            picture_base64=picture_b64,
            video_url=video_path,
            status="1",
            remark=f"推理时延: {result.inference_time_ms:.0f}ms, 滤波窗口: {self._temporal_filter.vote_count}/{self.cfg.temporal_window_size}",
        )

        self.publisher.send_alarm(event)

    def run(self, duration: float = 0, frame_callback: Optional[callable] = None,
            camera_configs: Optional[list] = None, device_info: Optional[dict] = None):
        """
        运行主循环
        duration: 运行秒数 (0=无限)
        frame_callback: 每帧回调函数
        camera_configs: 摄像头配置列表 (含位置信息)
        device_info: 设备信息 (device_id, area_id, longitude, latitude, location)
        """
        if not self.running:
            self.start()

        frame_interval = 1.0 / self.cfg.target_fps
        last_frame_time = 0
        start_time = time.time()

        # 设备/摄像头默认信息
        dev = device_info or {}
        device_id = dev.get('device_id', 0)
        area_id = dev.get('area_id', 0)
        default_lng = dev.get('longitude', 0.0)
        default_lat = dev.get('latitude', 0.0)
        default_loc = dev.get('location', '')

        while self.running:
            if duration > 0 and (time.time() - start_time) >= duration:
                break

            current = time.time()
            if current - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue

            # 读取帧
            if self.stream:
                frame = self.stream.read_frame()
                cam_id = self.stream.camera.camera_id
                cam_lng = self.stream.camera.longitude or default_lng
                cam_lat = self.stream.camera.latitude or default_lat
            else:
                # 测试模式: 生成模拟帧
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                cam_id = 0
                cam_lng = default_lng
                cam_lat = default_lat

            if frame is None:
                continue

            last_frame_time = current

            # 加入帧缓冲区
            self._frame_buffer.append(frame.copy())
            if len(self._frame_buffer) > self._max_buffer_size:
                self._frame_buffer.pop(0)

            # 构建定位回调
            calc_fn = None
            if self._localization:
                _cam_id = cam_id
                calc_fn = lambda center, shape, cid=_cam_id: self._calc_location(center, shape, cid)

            # 处理
            result = self.process_frame(
                frame,
                camera_id=cam_id,
                device_id=device_id,
                area_id=area_id,
                longitude=cam_lng,
                latitude=cam_lat,
                location_text=default_loc,
                calc_location_fn=calc_fn,
            )
            if result is None:
                continue

            if frame_callback:
                frame_callback(result)

            # 预览
            if self.cfg.show_preview and result.image_annotated is not None:
                cv2.imshow("Edge Detection", result.image_annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        if self.cfg.show_preview:
            cv2.destroyAllWindows()

    def _heartbeat_loop(self):
        """心跳保活循环"""
        while self.running:
            time.sleep(self.cfg.heartbeat_interval)
            if not self.running:
                break

            # 获取系统状态
            latency_stats = self.engine.get_latency_stats()
            heartbeat = DeviceHeartbeat(
                device_id=0,
                mac="",
                timestamp=datetime.now(timezone.utc).isoformat(),
                status="online",
            )
            self.publisher.send_heartbeat(heartbeat)

            # 性能告警
            if latency_stats.get("avg_ms", 0) > self.cfg.latency_target_ms:
                logger.warning(f"推理时延超标: avg={latency_stats['avg_ms']:.0f}ms > "
                               f"{self.cfg.latency_target_ms}ms")
                self.publisher.report_device_error(DeviceError(
                    device_id=0, mac="",
                    error_code="latency_high",
                    error_msg=f"推理时延{latency_stats['avg_ms']:.0f}ms超过阈值",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ))

    def get_stats(self) -> dict:
        """获取运行统计"""
        return {
            "frames_processed": self._frame_count,
            "detections": self._detection_count,
            "detection_rate": (self._detection_count / max(self._frame_count, 1)),
            "latency": self.engine.get_latency_stats(),
            "buffer_size": len(self._frame_buffer),
        }
