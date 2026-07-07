"""
边缘端AI推理引擎
- 加载 ONNX/RKNN 模型进行推理
- 后处理: NMS + 坐标解码
- 性能监控: 时延统计
- 支持 YOLO 格式输出
"""
from __future__ import annotations
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import cv2

logger = logging.getLogger(__name__)


@dataclass
class DetectionBox:
    """检测框"""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str = ""

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1


@dataclass
class InferenceResult:
    """单帧推理结果"""
    camera_id: int
    timestamp: float
    detections: list[DetectionBox] = field(default_factory=list)
    image_raw: Optional[np.ndarray] = None
    image_annotated: Optional[np.ndarray] = None
    inference_time_ms: float = 0.0

    @property
    def has_detection(self) -> bool:
        return len(self.detections) > 0

    @property
    def max_confidence(self) -> float:
        if not self.detections:
            return 0.0
        return max(d.confidence for d in self.detections)


class YOLOInferenceEngine:
    """
    YOLO 推理引擎
    - ONNX Runtime 推理
    - YOLO 输出解码 + NMS
    - 帧标注
    """

    CLASS_NAMES = {0: "fire", 1: "smoke"}

    def __init__(self, model_path: str, conf_threshold: float = 0.25,
                 iou_threshold: float = 0.5, img_size: int = 416):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.img_size = img_size

        self._session = None
        self._backend = self._detect_backend()
        self._load_model()

        # 时延统计
        self._latency_samples: list[float] = []

    def _detect_backend(self) -> str:
        """检测可用的推理后端"""
        ext = Path(self.model_path).suffix.lower()
        if ext == '.rknn':
            return 'rknn'
        elif ext == '.onnx':
            return 'onnx'
        elif ext in {'.pt', '.pth', '.torchscript'}:
            return 'pytorch'
        else:
            raise ValueError(f"不支持的模型格式: {ext}")

    def _load_model(self):
        """加载模型"""
        if self._backend == 'onnx':
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(
                    self.model_path,
                    providers=['CPUExecutionProvider']
                )
                self._input_name = self._session.get_inputs()[0].name
                self._output_names = [o.name for o in self._session.get_outputs()]
                logger.info(f"ONNX模型已加载: {self.model_path} (provider=CPU)")
            except ImportError:
                raise ImportError("请安装 onnxruntime: pip install onnxruntime")

        elif self._backend == 'rknn':
            try:
                from rknnlite.api import RKNNLite
                self._session = RKNNLite()
                ret = self._session.load_rknn(self.model_path)
                if ret != 0:
                    raise RuntimeError(f"RKNN模型加载失败: {ret}")
                # RK3588 NPU 有 3 个核心:
                #   NPU_CORE_0 = 1  (大核0)
                #   NPU_CORE_1 = 2  (大核1)
                #   NPU_CORE_2 = 4  (小核)
                #   NPU_CORE_AUTO = 0  (自动分配, 推荐)
                #   NPU_CORE_ALL = 7  (全部3核, 最大性能)
                core_mask = getattr(RKNNLite, 'NPU_CORE_AUTO', 0)
                ret = self._session.init_runtime(core_mask=core_mask)
                if ret != 0:
                    raise RuntimeError(f"RKNN runtime初始化失败 (core_mask={core_mask}): {ret}")
                logger.info(f"RKNN模型已加载 (RK3588 NPU, core_mask={core_mask}): {self.model_path}")
            except ImportError:
                raise ImportError("请安装 RKNN Toolkit Lite 2: pip install rknn-toolkit-lite2")

        elif self._backend == 'pytorch':
            import torch
            self._device = torch.device('cpu')
            self._model = torch.jit.load(self.model_path, map_location='cpu')
            self._model.eval()
            logger.info(f"PyTorch模型已加载: {self.model_path}")

    def infer(self, image_batch: np.ndarray) -> list[np.ndarray]:
        """
        模型推理
        image_batch: (B, 3, H, W) float32 [0,1]
        返回: 模型原始输出列表
        """
        start = time.perf_counter()

        if self._backend == 'onnx':
            outputs = self._session.run(
                self._output_names,
                {self._input_name: image_batch}
            )
        elif self._backend == 'rknn':
            outputs = self._session.inference(inputs=[image_batch])
        elif self._backend == 'pytorch':
            import torch
            with torch.no_grad():
                tensor = torch.from_numpy(image_batch).to(self._device)
                outputs = self._model(tensor)
                outputs = [o.cpu().numpy() if isinstance(o, torch.Tensor) else o for o in outputs]

        elapsed = (time.perf_counter() - start) * 1000
        self._latency_samples.append(elapsed)
        return outputs

    def postprocess_onnx(self, outputs: list[np.ndarray],
                          orig_shape: tuple) -> list[DetectionBox]:
        """
        YOLO ONNX输出后处理
        假设输出格式: (1, 5+nc, num_proposals) 或标准YOLO输出
        """
        detections = []

        # Ultralytics YOLO ONNX 输出格式: (1, 84, 8400)
        if len(outputs) == 1 and outputs[0].ndim == 3:
            pred = outputs[0][0]  # (84, 8400)
            pred = np.transpose(pred)  # (8400, 84)

            # 提取置信度和类别
            cls_scores = pred[:, 4:]
            cls_ids = np.argmax(cls_scores, axis=1)
            confidences = np.max(cls_scores, axis=1) * pred[:, 4]

            for i in range(len(pred)):
                if confidences[i] < self.conf_threshold:
                    continue
                cx, cy, w, h = pred[i, :4]
                x1 = (cx - w / 2) * orig_shape[1] / self.img_size
                y1 = (cy - h / 2) * orig_shape[0] / self.img_size
                x2 = (cx + w / 2) * orig_shape[1] / self.img_size
                y2 = (cy + h / 2) * orig_shape[0] / self.img_size

                detections.append(DetectionBox(
                    x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2),
                    confidence=float(confidences[i]),
                    class_id=int(cls_ids[i]),
                    class_name=self.CLASS_NAMES.get(int(cls_ids[i]), "unknown")
                ))

        # 多尺度YOLO输出: 3个尺度的特征图 (自定义模型格式, 已弃用)
        elif len(outputs) == 3:
            raise NotImplementedError(
                "3输出多尺度YOLO格式已不再支持。"
                "请使用YOLO11单输出格式: model.export(format='onnx', opset=12)"
            )

        return detections

    def _nms(self, boxes: list[DetectionBox]) -> list[DetectionBox]:
        """非极大值抑制"""
        if len(boxes) <= 1:
            return boxes

        boxes = sorted(boxes, key=lambda b: b.confidence, reverse=True)
        keep = []

        while boxes:
            keep.append(boxes[0])
            if len(boxes) == 1:
                break
            remaining = []
            for b in boxes[1:]:
                iou = self._compute_iou(keep[-1], b)
                if iou < self.iou_threshold:
                    remaining.append(b)
            boxes = remaining

        return keep

    @staticmethod
    def _compute_iou(box1: DetectionBox, box2: DetectionBox) -> float:
        x1 = max(box1.x1, box2.x1)
        y1 = max(box1.y1, box2.y1)
        x2 = min(box1.x2, box2.x2)
        y2 = min(box1.y2, box2.y2)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1.x2 - box1.x1) * (box1.y2 - box1.y1)
        area2 = (box2.x2 - box2.x1) * (box2.y2 - box2.y1)
        union = area1 + area2 - inter
        return inter / (union + 1e-7)

    def annotate_frame(self, frame: np.ndarray,
                        detections: list[DetectionBox]) -> np.ndarray:
        """在帧上绘制检测框"""
        annotated = frame.copy()
        for det in detections:
            color = (0, 0, 255)  # 红色
            cv2.rectangle(annotated,
                          (int(det.x1), int(det.y1)),
                          (int(det.x2), int(det.y2)),
                          color, 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            cv2.putText(annotated, label,
                        (int(det.x1), int(det.y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return annotated

    def get_latency_stats(self) -> dict:
        """获取推理时延统计"""
        if not self._latency_samples:
            return {"avg_ms": 0, "max_ms": 0, "min_ms": 0, "count": 0}
        arr = np.array(self._latency_samples)
        return {
            "avg_ms": float(np.mean(arr)),
            "max_ms": float(np.max(arr)),
            "min_ms": float(np.min(arr)),
            "p99_ms": float(np.percentile(arr, 99)),
            "count": len(arr),
        }
