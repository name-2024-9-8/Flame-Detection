"""
重新分配摄像头到重庆市各区（非花溪校区），AI云盒保留在花溪校区。
同时重新编码现有取证视频为 H.264 浏览器兼容格式。
"""
import os
import pymysql
from datetime import datetime
import cv2
import numpy as np

# =========================================================================
# 重庆9区摄像头分布
# =========================================================================
# 重庆理工大学花溪校区坐标: 约 106.566, 29.458 (巴南区红光大道69号)

CHONGQING_DISTRICTS = [
    # (cam_id, 名称, lng, lat, 位置描述)
    (1, '渝中区-解放碑监控', 106.577, 29.560, '渝中区解放碑步行街商圈'),
    (2, '江北区-观音桥监控', 106.532, 29.575, '江北区观音桥步行街商圈'),
    (3, '南岸区-南滨路监控', 106.590, 29.545, '南岸区南滨路烟雨公园'),
    (4, '沙坪坝区-三峡广场监控', 106.458, 29.560, '沙坪坝区三峡广场商圈'),
    (5, '九龙坡区-杨家坪监控', 106.515, 29.520, '九龙坡区杨家坪步行街'),
    (6, '渝北区-冉家坝监控', 106.630, 29.585, '渝北区冉家坝龙湖MOCO'),
    (7, '大渡口区-九宫庙监控', 106.482, 29.484, '大渡口区九宫庙商圈'),
    (8, '巴南区-龙洲湾监控', 106.540, 29.402, '巴南区龙洲湾万达广场'),
    (9, '北碚区-天生路监控', 106.396, 29.805, '北碚区天生路西南大学'),
]

# AI云盒保持花溪校区不变
CLOUDBOX_LOCATION = (106.566, 29.458, '重庆市巴南区红光大道69号重庆理工大学花溪校区第一实验楼')

# =========================================================================
# 连接数据库
# =========================================================================
conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root',
    password=os.environ.get('MYSQL_PASSWORD', ''),
    database='flame_detection', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
)
cursor = conn.cursor()
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# =========================================================================
# 1. 更新摄像头名称和坐标
# =========================================================================
print("=== 更新摄像头位置 ===")
for cam_id, name, lng, lat, loc in CHONGQING_DISTRICTS:
    cursor.execute("""
        UPDATE T_Camera
        SET Name = %s, Longitude = %s, Latitude = %s, Remark = %s
        WHERE Id = %s
    """, (name, str(lng), str(lat), loc, cam_id))
    affected = cursor.rowcount
    print(f"  Camera ID={cam_id}: {name} [{lng}, {lat}] — {'OK' if affected else 'NOT FOUND'}")

# =========================================================================
# 2. 确保AI云盒坐标正确 (花溪校区)
# =========================================================================
print("\n=== AI云盒位置 (保持花溪校区) ===")
cursor.execute("""
    UPDATE T_Device
    SET Longitude = %s, Latitude = %s, Address = %s
    WHERE Id = 1
""", (str(CLOUDBOX_LOCATION[0]), str(CLOUDBOX_LOCATION[1]), CLOUDBOX_LOCATION[2]))
print(f"  Device ID=1: 花溪校区 [{CLOUDBOX_LOCATION[0]}, {CLOUDBOX_LOCATION[1]}]")

# =========================================================================
# 3. 更新报警事件坐标(匹配新摄像头位置)，并更新位置描述
# =========================================================================
print("\n=== 更新报警事件坐标 ===")
# 每个摄像头保留2条报警(一火一烟)
alarm_updates = [
    (1, 1, 106.577, 29.560, '渝中区解放碑步行街商圈-主入口'),
    (2, 1, 106.577, 29.560, '渝中区解放碑步行街商圈-侧门'),
    (3, 2, 106.532, 29.575, '江北区观音桥步行街商圈-北门'),
    (4, 2, 106.532, 29.575, '江北区观音桥步行街商圈-南门'),
    (5, 3, 106.590, 29.545, '南岸区南滨路烟雨公园-广场'),
    (6, 3, 106.590, 29.545, '南岸区南滨路烟雨公园-江边步道'),
    (7, 4, 106.458, 29.560, '沙坪坝区三峡广场商圈-中心'),
    (8, 4, 106.458, 29.560, '沙坪坝区三峡广场商圈-东侧'),
    (9, 5, 106.515, 29.520, '九龙坡区杨家坪步行街-商场入口'),
    (10, 5, 106.515, 29.520, '九龙坡区杨家坪步行街-轻轨站口'),
]

for alarm_id, cam_id, lng, lat, loc in alarm_updates:
    cursor.execute("""
        UPDATE T_DetectResult
        SET Longitude = %s, Latitude = %s, Location = %s, CameraId = %s
        WHERE Id = %s
    """, (str(lng), str(lat), loc, cam_id, alarm_id))
    affected = cursor.rowcount
    print(f"  Alarm ID={alarm_id} → Camera {cam_id}: {loc} — {'OK' if affected else 'NOT FOUND'}")

# =========================================================================
# 4. 处理多余报警(超过10条的删除，因为只有10个报警)
# =========================================================================
cursor.execute("SELECT COUNT(*) as cnt FROM T_DetectResult")
total_alarms = cursor.fetchone()['cnt']
if total_alarms > 10:
    cursor.execute("DELETE FROM T_DetectResult WHERE Id > 10")
    print(f"\n  删除多余报警: {total_alarms - 10} 条")

# =========================================================================
# 5. 验证
# =========================================================================
print("\n=== 验证 ===")
cursor.execute('SELECT Id, Name, Longitude, Latitude, Remark FROM T_Camera ORDER BY Id')
for row in cursor.fetchall():
    print(f"  Cam {row['Id']}: {row['Name']} [{row['Longitude']}, {row['Latitude']}] — {row['Remark']}")

cursor.execute('SELECT Id, MAC, Longitude, Latitude, Address FROM T_Device')
for row in cursor.fetchall():
    print(f"  Device {row['Id']}: {row['Address']} [{row['Longitude']}, {row['Latitude']}]")

cursor.execute('SELECT Id, EventType, CameraId, Longitude, Latitude, Location FROM T_DetectResult ORDER BY Id')
for row in cursor.fetchall():
    print(f"  Alarm {row['Id']}: type={row['EventType']}, cam={row['CameraId']}, loc={row['Location']}")

conn.commit()
conn.close()
print("\nDone!")
