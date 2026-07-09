"""边缘视频接收 + 检测服务
接收香橙派传来的原始视频 → 火焰检测 → 报警推送 → 返回标注视频
"""
import sys, os, uuid, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory
from flame_alarm import FlameAlarmDetector

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("VideoServer")

app = Flask(__name__)

DETECTED_DIR = Path(__file__).parent.parent / "output" / "detected"
DETECTED_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR = Path(__file__).parent.parent / "output" / "alarm_clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG = {
    'model_path': os.environ.get('MODEL_PATH', 'output/dfire_train/weights/best.onnx'),
    'conf': float(os.environ.get('CONF', '0.25')),
    'server_url': os.environ.get('SERVER_URL', 'http://127.0.0.1:8080'),
    'device_id': int(os.environ.get('DEVICE_ID', '1')),
    'area_id': int(os.environ.get('AREA_ID', '1')),
    'longitude': float(os.environ.get('LNG', '106.528')),
    'latitude': float(os.environ.get('LAT', '29.453')),
    'location': os.environ.get('LOCATION', '重庆理工大学-花溪校区'),
}

def get_detector():
    return FlameAlarmDetector(
        model_path=CONFIG['model_path'],
        conf=CONFIG['conf'],
        server_url=CONFIG['server_url'],
        offline=False,
        device_id=CONFIG['device_id'],
        area_id=CONFIG['area_id'],
        longitude=CONFIG['longitude'],
        latitude=CONFIG['latitude'],
        location=CONFIG['location'],
        filter_window=2,      # 2帧窗口
        filter_votes=1,       # 1票即触发（降低滤波门槛）
        cooldown_frames=5,    # 5帧冷却（捕获更多独立事件）
    )


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('video')
    if not file:
        return jsonify({'code': 400, 'message': '缺少video文件'}), 400

    video_id = uuid.uuid4().hex[:12]
    video_name = f"{video_id}.mp4"
    video_path = DETECTED_DIR / video_name
    file.save(str(video_path))
    logger.info(f"视频已接收: {video_name}")

    try:
        # 记录检测前已有的clips
        clips_before = set(CLIPS_DIR.glob("*.mp4"))

        det = get_detector()
        result = det.process_video(
            str(video_path),
            display=False,
            save_video=True,
            output_dir=str(DETECTED_DIR),
        )

        # 新生成的报警片段
        clips_after = set(CLIPS_DIR.glob("*.mp4"))
        new_clips = sorted(clips_after - clips_before)
        clip_urls = [f'/clips/{p.name}' for p in new_clips]

        logger.info(f"检测完成: {result.get('frames',0)}帧, "
                     f"火焰{result.get('fire_frames',0)}帧, "
                     f"报警{result.get('alarms',0)}次, "
                     f"片段{len(clip_urls)}个")

        # 标注视频路径
        out_video = result.get('output_video', '')
        out_name = Path(out_video).name if out_video else ''

        return jsonify({
            'code': 200,
            'message': '检测完成',
            'data': {
                'video_id': video_id,
                'frames': result.get('frames', 0),
                'fire_frames': result.get('fire_frames', 0),
                'alarms': result.get('alarms', 0),
                'detected_video': f'/detected/{out_name}' if out_name else '',
                'clips': clip_urls,
            }
        })
    except Exception as e:
        logger.error(f"检测失败: {e}")
        return jsonify({'code': 500, 'message': str(e)}), 500


@app.route('/detected/<path:filename>')
def serve_video(filename):
    return send_from_directory(str(DETECTED_DIR), filename)


@app.route('/clips/<path:filename>')
def serve_clip(filename):
    return send_from_directory(str(CLIPS_DIR), filename)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print("=" * 50)
    print(" 视频接收 + 火焰检测服务")
    print(f" 模型: {CONFIG['model_path']}")
    print(f" 服务端: {CONFIG['server_url']}")
    print(f" 上传接口: http://0.0.0.0:9998/upload")
    print(f" 标注视频: http://127.0.0.1:9998/detected/xxx.mp4")
    print("=" * 50)
    app.run(host='0.0.0.0', port=9998)
