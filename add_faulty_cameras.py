"""Add 2 faulty cameras in Chongqing with fault records and alarm events"""
import os
import pymysql
from datetime import datetime

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
                       database='flame_detection', charset='utf8mb4')
cursor = conn.cursor()
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# =========================================================================
# Camera ID 6: 杨家坪 (九龙坡区, southwest of Chongqing center)
# =========================================================================
cursor.execute("""
    INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude,
        AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
    VALUES ('192.168.1.106', 'CAM:MAC:00:00:06',
            'rtsp://192.168.1.106:554/stream1',
            '杨家坪1号摄像头', '106.5150', '29.5200',
            1, '摄像头型号A', NOW(), '李工', 1,
            '九龙坡区杨家坪商圈监控')
""")
cam6_id = cursor.lastrowid
print(f'Added Camera ID={cam6_id}: 杨家坪1号摄像头 [106.5150, 29.5200]')

# Fault record
cursor.execute("""
    INSERT INTO T_CameraError (CameraId, CameraIP, CreateTime, ErrorCode, ErrorMsg, Remark)
    VALUES (%s, '192.168.1.106', NOW(), '1',
            '网络连接超时，摄像头视频流中断 — 杨家坪商圈交换机异常',
            '需检查交换机端口及网线连接')
""", (cam6_id,))
print(f'  Fault record added (network timeout)')

# Alarm events (2 records)
cursor.execute("""
    INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location,
        CameraId, DeviceId, Status, CreatTime, UrgencyDegree)
    VALUES
        ('fire', 0.92, '106.5150', '29.5200', '杨家坪商圈主入口',
         %s, 1, '1', DATE_SUB(NOW(), INTERVAL 2 HOUR), '紧急'),
        ('smoke', 0.78, '106.5150', '29.5200', '杨家坪商圈侧门',
         %s, 1, '1', DATE_SUB(NOW(), INTERVAL 1 HOUR), '重要')
""", (cam6_id, cam6_id))
print(f'  2 alarm events added (fire 92%%, smoke 78%%)')

# =========================================================================
# Camera ID 7: 冉家坝 (渝北区, northeast of Chongqing center)
# =========================================================================
cursor.execute("""
    INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude,
        AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
    VALUES ('192.168.1.107', 'CAM:MAC:00:00:07',
            'rtsp://192.168.1.107:554/stream1',
            '冉家坝1号摄像头', '106.6300', '29.5850',
            2, '摄像头型号B', NOW(), '赵工', 2,
            '渝北区冉家坝社区监控')
""")
cam7_id = cursor.lastrowid
print(f'Added Camera ID={cam7_id}: 冉家坝1号摄像头 [106.6300, 29.5850]')

# Fault record
cursor.execute("""
    INSERT INTO T_CameraError (CameraId, CameraIP, CreateTime, ErrorCode, ErrorMsg, Remark)
    VALUES (%s, '192.168.1.107', NOW(), '2',
            '图像质量下降，镜头存在遮挡物 — 冉家坝社区广场',
            '需现场清理镜头并检查防护罩')
""", (cam7_id,))
print(f'  Fault record added (poor image quality)')

# Alarm events (2 records)
cursor.execute("""
    INSERT INTO T_DetectResult (EventType, Confidence, Longitude, Latitude, Location,
        CameraId, DeviceId, Status, CreatTime, UrgencyDegree)
    VALUES
        ('fire', 0.89, '106.6300', '29.5850', '冉家坝社区广场',
         %s, 2, '1', DATE_SUB(NOW(), INTERVAL 3 HOUR), '重要'),
        ('smoke', 0.65, '106.6300', '29.5850', '冉家坝社区北侧',
         %s, 2, '1', DATE_SUB(NOW(), INTERVAL 30 MINUTE), '一般')
""", (cam7_id, cam7_id))
print(f'  2 alarm events added (fire 89%%, smoke 65%%)')

conn.commit()

# =========================================================================
# Verify
# =========================================================================
print('\n=== Verification ===')
cursor.execute('SELECT Id, Name, Longitude, Latitude FROM T_Camera ORDER BY Id')
print('All Cameras:')
for row in cursor.fetchall():
    print(f'  ID={row["Id"]}, Name={row["Name"]}, lng={row["Longitude"]}, lat={row["Latitude"]}')

cursor.execute('SELECT COUNT(*) as cnt FROM T_CameraError')
print(f'Camera faults: {cursor.fetchone()["cnt"]}')

cursor.execute('SELECT COUNT(*) as cnt FROM T_DetectResult')
print(f'Alarm events: {cursor.fetchone()["cnt"]}')

cursor.execute("""
    SELECT CameraId, COUNT(*) as cnt
    FROM T_DetectResult WHERE CameraId IN (%s, %s)
    GROUP BY CameraId
""", (cam6_id, cam7_id))
for row in cursor.fetchall():
    print(f'  Camera ID={row["CameraId"]}: {row["cnt"]} alarm events')

conn.close()
print('Done!')
