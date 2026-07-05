import pymysql
from datetime import datetime

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='0201',
                       database='flame_detection', charset='utf8mb4')
cursor = conn.cursor()
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

cameras = [
    ('192.168.1.103', 'CAM:MAC:00:00:03', 'rtsp://192.168.1.103:554/stream1',
     '江北嘴1号摄像头', '106.5720', '29.5750', 1, '摄像头型号A', '王工', 1, '江北嘴金融城监控'),
    ('192.168.1.104', 'CAM:MAC:00:00:04', 'rtsp://192.168.1.104:554/stream1',
     '南滨路1号摄像头', '106.5900', '29.5450', 2, '摄像头型号B', '赵工', 2, '南滨路沿线监控'),
    ('192.168.1.105', 'CAM:MAC:00:00:05', 'rtsp://192.168.1.105:554/stream1',
     '沙坪坝1号摄像头', '106.4550', '29.5600', 1, '摄像头型号A', '王工', 1, '沙坪坝商圈监控'),
]

for cam in cameras:
    ip, mac, url, name, lng, lat, area, ctype, maint, devid, remark = cam
    cursor.execute("""
        INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude,
            AreaId, Type, InstallTime, Maintainer, DeviceId, Remark)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s,%s,%s)
    """, (ip, mac, url, name, lng, lat, area, ctype, maint, devid, remark))
    print(f'Added: {name}')

conn.commit()
cursor.execute('SELECT Id, Name, Longitude, Latitude FROM T_Camera')
for row in cursor.fetchall():
    print(f'  ID={row[0]}, Name={row[1]}, lng={row[2]}, lat={row[3]}')
conn.close()
print('Done!')
