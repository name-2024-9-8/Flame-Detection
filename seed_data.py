"""Seed database with initial data"""
import os
import pymysql

# Connect via TCP
conn = None
for port in [3306, 3307]:
    for pwd in [os.environ.get('MYSQL_PASSWORD', '')]:
        try:
            conn = pymysql.connect(host='127.0.0.1', port=port, user='root',
                                   password=pwd, charset='utf8mb4')
            print(f'Connected: port={port}, password=[{pwd}]')
            break
        except Exception as e:
            pass
    if conn:
        break

if not conn:
    print('Cannot connect to any MySQL instance')
    # Try the D-drive MySQL via the mysql CLI
    import subprocess
    result = subprocess.run([
        'D:/mysql/mysql-8.0.36-winx64/bin/mysql.exe',
        '--socket=D_FLAME_MYSQL',
        'flame_detection',
        '-e', 'SELECT 1'
    ], capture_output=True, text=True)
    print('mysql CLI test:', result.stdout, result.stderr)
    exit(1)

cursor = conn.cursor()
cursor.execute('USE flame_detection')

# Check existing data
cursor.execute('SELECT COUNT(*) FROM T_Role')
if cursor.fetchone()[0] > 0:
    print('Seed data already exists, skipping')
    cursor.execute('SELECT Id, Account, Name FROM T_User')
    print(f'Users: {cursor.fetchall()}')
    conn.close()
    exit(0)

# Insert roles
cursor.execute("INSERT INTO T_Role (Name, Description) VALUES ('超级管理员', '系统最高权限')")
cursor.execute("INSERT INTO T_Role (Name, Description) VALUES ('普通用户', '查看和处理报警事件')")

# Insert users (password = 123456, bcrypt hash)
pwd_hash = '$2y$10$7QnEoGsR8POwiIekEtlIIu/ZGCatuhYt8p1yfFGjMq8nfu34Szikm'
cursor.execute("INSERT INTO T_User (Account, Name, Password) VALUES ('admin', '管理员', %s)", (pwd_hash,))
cursor.execute("INSERT INTO T_UserRole (UserId, RoleId) VALUES (1, 1)")

# Site config
cursor.execute("INSERT INTO T_Site (thresh, width, height, video_times, heartBeat, exception_times) VALUES (0.6, 640, 480, 5, 24, 10)")

# Dictionary
dictionaries = [
    ('EventType', 'fire', None),
    ('EventType', 'smoke', None),
    ('UrgencyDegree', '紧急', None),
    ('UrgencyDegree', '重要', None),
    ('UrgencyDegree', '一般', None),
    ('UrgencyDegree', '提示', None),
    ('DeviceType', '摄像头型号A', None),
    ('DeviceType', '摄像头型号B', None),
]
for key, val, remark in dictionaries:
    cursor.execute("INSERT INTO T_Dictionary (`Key`, `Value`, Remark) VALUES (%s, %s, %s)", (key, val, remark))

# Areas
cursor.execute("INSERT INTO T_Area (Name, Remark) VALUES ('主厂区', '主要生产区域')")
cursor.execute("INSERT INTO T_Area (Name, Remark) VALUES ('仓库区', '仓储物流区域')")

# Departments
from datetime import datetime
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
cursor.execute("INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark) VALUES ('技术部', 0, 1, %s, 1, '负责系统运维与技术管理')", (now,))
cursor.execute("INSERT INTO T_Branch (Name, ParentId, LeaderId, CreateTime, CreateBy, Remark) VALUES ('安保部', 0, 1, %s, 1, '负责安全监控与应急响应')", (now,))

# More users
cursor.execute("INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, Remark) VALUES ('chuli001', '处理员小张', %s, 'chuli@firealarm.com', '13800138001', 1, 1, %s, 1, '技术部员工')", (pwd_hash, now))
cursor.execute("INSERT INTO T_User (Account, Name, Password, Email, Phone, AreaId, BranchId, CreateTime, CreateBy, Remark) VALUES ('zhangsan', '张三', %s, 'zhangsan@example.com', '13800138002', 2, 2, %s, 1, '安保部员工')", (pwd_hash, now))
cursor.execute("INSERT INTO T_UserRole (UserId, RoleId) VALUES (2, 2)")
cursor.execute("INSERT INTO T_UserRole (UserId, RoleId) VALUES (3, 2)")

# Authorities for super admin (RoleId=1)
auths = [
    'system:config', 'system:department', 'system:user', 'system:role', 'system:datadict',
    'device:cloudbox', 'device:camera', 'device:view',
    'alarm:event', 'alarm:review', 'alarm:camera_fault', 'alarm:cloudbox_fault',
    'log:access', 'log:operation',
]
for auth in auths:
    cursor.execute("INSERT INTO T_Authority (RoleId, Authority) VALUES (1, %s)", (auth,))

# Authorities for normal user (RoleId=2)
for auth in ['device:view', 'alarm:event', 'alarm:review']:
    cursor.execute("INSERT INTO T_Authority (RoleId, Authority) VALUES (2, %s)", (auth,))

# Devices (AI cloud boxes)
cursor.execute("INSERT INTO T_Device (MAC, Longitude, Latitude, Address, AreaId, ModelPerson, ModelInfo, Maintainer, CreateTime, StructuralInfo, DetailInfo) VALUES ('AA:BB:CC:DD:EE:01', '116.397428', '39.909204', '主厂区1号监控室', 1, '王工', 'RK3399 Pro D', '王工', %s, 'ARM Cortex-A72 + NPU', '主厂区边缘AI分析盒')", (now,))
cursor.execute("INSERT INTO T_Device (MAC, Longitude, Latitude, Address, AreaId, ModelPerson, ModelInfo, Maintainer, CreateTime, StructuralInfo, DetailInfo) VALUES ('AA:BB:CC:DD:EE:02', '116.398500', '39.908500', '仓库区入口', 2, '赵工', 'RK3399 Pro D', '赵工', %s, 'ARM Cortex-A72 + NPU', '仓库区边缘AI分析盒')", (now,))

# Cameras
cursor.execute("INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude, AreaId, Type, InstallTime, Maintainer, DeviceId, Remark) VALUES ('192.168.1.101', 'CAM:MAC:00:00:01', 'rtsp://192.168.1.101:554/stream1', '主厂区1号摄像头', '116.397428', '39.909204', 1, '摄像头型号A', %s, '王工', 1, '主厂区火焰监控')", (now,))
cursor.execute("INSERT INTO T_Camera (IP, MAC, CameraUrl, Name, Longitude, Latitude, AreaId, Type, InstallTime, Maintainer, DeviceId, Remark) VALUES ('192.168.1.102', 'CAM:MAC:00:00:02', 'rtsp://192.168.1.102:554/stream1', '仓库区1号摄像头', '116.398500', '39.908500', 2, '摄像头型号B', %s, '赵工', 2, '仓库区烟雾监控')", (now,))

# Fault records
cursor.execute("INSERT INTO T_CameraError (CameraId, CameraIP, CreateTime, ErrorCode, ErrorMsg, Remark) VALUES (1, '192.168.1.101', %s, '1', '网络连接超时，摄像头视频流中断', '需检查交换机端口')", (now,))
cursor.execute("INSERT INTO T_CameraError (CameraId, CameraIP, CreateTime, ErrorCode, ErrorMsg, Remark) VALUES (2, '192.168.1.102', %s, '2', '图像质量下降，镜头存在遮挡物', '需现场清理镜头')", (now,))
cursor.execute("INSERT INTO T_DeviceError (DeviceId, MAC, CreateTime, ErrorCode, ErrorMsg, Remark) VALUES (1, 'AA:BB:CC:DD:EE:01', %s, 'HEARTBEAT_LOST', '设备心跳超时，已超过30分钟无响应', '需检查设备供电')", (now,))

# More dictionaries
more_dicts = [
    ('CameraType', '固定摄像头', '固定安装不可转动'),
    ('CameraType', '云台摄像头', '支持PTZ云台控制'),
    ('DeviceType', 'RK3399 Pro D', 'Rockchip AI处理器'),
    ('DeviceType', 'Jetson Nano', 'NVIDIA AI处理器'),
    ('ErrorCode', '1', '网络故障'),
    ('ErrorCode', '2', '图像质量差'),
    ('ErrorCode', 'HEARTBEAT_LOST', '设备心跳丢失'),
    ('UnitCode', 'SMART_CITY_001', '智慧城市平台'),
    ('UnitCode', 'VIDEO_MONITOR_001', '视频监控平台'),
    ('UnitCode', 'ATMOS_MONITOR_001', '大气监测平台'),
]
for key, val, remark in more_dicts:
    cursor.execute("INSERT INTO T_Dictionary (`Key`, `Value`, Remark) VALUES (%s, %s, %s)", (key, val, remark))

conn.commit()
print('All seed data inserted!')

# Verify
cursor.execute('SELECT Id, Account, Name FROM T_User')
print(f'Users: {cursor.fetchall()}')
cursor.execute('SELECT Id, Name FROM T_Role')
print(f'Roles: {cursor.fetchall()}')
cursor.execute('SELECT COUNT(*) FROM T_Authority')
print(f'Authorities: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM T_Device')
print(f'Devices: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM T_Camera')
print(f'Cameras: {cursor.fetchone()[0]}')

conn.close()
print('Done!')
