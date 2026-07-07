<?php
/**
 * API 接口文档页 — 供段林川联调使用
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 后端 API 联调文档
 */
?><!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>视频AI预警系统 — API 文档 v1.0</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: #f5f7fa; color: #333; }
.sidebar { position: fixed; top:0; left:0; bottom:0; width:260px; background:#1e293b; color:#cbd5e1; overflow-y:auto; }
.sidebar h2 { padding:20px; font-size:18px; color:#fff; border-bottom:1px solid #334155; }
.sidebar a { display:block; padding:10px 20px; color:#94a3b8; text-decoration:none; font-size:14px; border-left:3px solid transparent; }
.sidebar a:hover { color:#fff; background:#334155; }
.main { margin-left:260px; padding:30px 40px; max-width:1100px; }
h1 { font-size:26px; margin-bottom:8px; }
h2 { font-size:20px; margin:32px 0 12px; padding-bottom:6px; border-bottom:2px solid #e2e8f0; }
h3 { font-size:16px; margin:20px 0 8px; }
.endpoint { background:#fff; border-radius:8px; padding:16px 20px; margin:12px 0; box-shadow:0 1px 3px rgba(0,0,0,.08); }
.method { display:inline-block; padding:2px 10px; border-radius:4px; font-size:12px; font-weight:bold; color:#fff; margin-right:10px; }
.method.get    { background:#22c55e; }
.method.post   { background:#3b82f6; }
.method.put    { background:#f59e0b; }
.method.delete { background:#ef4444; }
.url { font-family: Consolas, monospace; font-size:15px; color:#475569; }
.desc { margin:8px 0; font-size:14px; color:#64748b; }
.field { font-size:13px; color:#475569; margin-top:6px; }
.field b { color:#334155; }
pre { background:#1e293b; color:#e2e8f0; padding:12px 16px; border-radius:6px; font-size:13px; overflow-x:auto; margin-top:8px; }
.tag { display:inline-block; padding:1px 8px; border-radius:3px; font-size:11px; margin-right:6px; }
.tag.auth { background:#fef3c7; color:#92400e; }
.tag.none { background:#f1f5f9; color:#64748b; }
</style>
</head>
<body>

<div class="sidebar">
  <h2>📡 API v1.0</h2>
  <a href="#auth">🔐 Auth 认证</a>
  <a href="#alarm">🔥 Alarm 报警</a>
  <a href="#device">🖥️ Device 设备</a>
  <a href="#stats">📊 Statistics 统计</a>
  <a href="#export">📥 Export 导出</a>
  <a href="#ws">🔗 WebService</a>
  <a href="#health">❤️ Health</a>
</div>

<div class="main">
<h1>视频AI智能识别及预警管理系统</h1>
<p style="color:#64748b;font-size:14px;">王永林 (12303070414) | Base: <code>http://localhost:8080/index.php</code></p>

<!-- Auth -->
<h2 id="auth">🔐 Auth 认证</h2>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/auth/login</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">用户登录，返回JWT Token（24h有效）</p>
  <p class="field"><b>Body:</b> account, password</p>
  <pre>{"code":200,"message":"登录成功","data":{"token":"eyJ...","expires_in":86400,"user":{...}}}</pre>
</div>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/auth/profile</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">获取当前用户信息</p>
  <p class="field"><b>Header:</b> Authorization: Bearer &lt;token&gt;</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/auth/refresh</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">刷新JWT Token</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/auth/logout</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">登出（客户端丢弃Token）</p>
</div>

<!-- Alarm -->
<h2 id="alarm">🔥 Alarm 报警事件</h2>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/alarm/events</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">报警事件列表（分页+筛选）</p>
  <p class="field"><b>Query:</b> page, per_page, status(1/2/3), event_type(fire/smoke), area_id, urgency_degree, device_id, start_time, end_time</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/alarm/events/create</span>
  <span class="tag none">边缘设备</span>
  <p class="desc">边缘AI推理盒上报报警（A→B接口）</p>
  <p class="field"><b>Body:</b> device_id(必填), device_mac, event_type, confidence, lng, lat, location, camera_id, description, picture, video_url</p>
  <pre>{"code":201,"message":"报警事件接收成功","data":{"event_id":7}}</pre>
</div>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/alarm/events/:id</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">报警事件详情（自动标记已读）</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/alarm/events/:id/update</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">处理/审核报警<br><b>Body:</b> action=process|audit, operate_result, description, urgency_degree</p>
</div>

<!-- Device -->
<h2 id="device">🖥️ Device 设备管理</h2>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/devices</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">设备列表<br><b>Query:</b> type=device|camera, area_id, device_id, keyword, page, per_page</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/devices/create</span>
  <span class="tag auth">管理员</span>
  <p class="desc">创建设备（云盒/摄像头）<br><b>Body:</b> type=device|camera, mac, address, name, ip, lng, lat, area_id, camera_url, device_id...</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/devices/:id/update</span>
  <span class="tag auth">管理员</span>
  <p class="desc">更新设备信息</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/devices/:id/delete</span>
  <span class="tag auth">管理员</span>
  <p class="desc">删除设备（先解除摄像头绑定）</p>
</div>

<!-- Statistics -->
<h2 id="stats">📊 Statistics 统计分析</h2>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/statistics</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">统计数据<br><b>Query:</b> dimension=summary|time|area, start_time, end_time</p>
</div>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/statistics/health</span>
  <span class="tag none">免鉴权</span>
  <p class="desc">系统健康检查（DB+Redis）</p>
</div>

<!-- Export -->
<h2 id="export">📥 Export 文档导出</h2>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/export/excel</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">报警事件导出Excel<br><b>Query:</b> start_time, end_time, type</p>
</div>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/export/word?id=:id</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">单条报警导出Word报告</p>
</div>

<!-- WebService -->
<h2 id="ws">🔗 WebService 外部对接</h2>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/webservice/alarm</span>
  <span class="tag none">外部系统</span>
  <p class="desc">外部系统报警上报（标准JSON格式）<br><b>Body:</b> {"UnitCode":"单位编码","VerifyID":"验证ID","data":{...}}</p>
</div>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/webservice/device/:id</span>
  <span class="tag none">外部系统</span>
  <p class="desc">外部系统获取云盒详情</p>
</div>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/webservice/video-frame/:id</span>
  <span class="tag none">外部系统</span>
  <p class="desc">获取报警视频帧URL</p>
</div>

<div class="endpoint">
  <span class="method post">POST</span><span class="url">/api/webservice/report</span>
  <span class="tag auth">需鉴权</span>
  <p class="desc">数据汇报（向智慧城市平台）</p>
</div>

<!-- Health -->
<h2 id="health">❤️ 健康检查</h2>

<div class="endpoint">
  <span class="method get">GET</span><span class="url">/api/statistics/health</span>
  <span class="tag none">免鉴权</span>
  <p class="desc">运维监控健康检查</p>
  <pre>{"status":"ok","timestamp":"2026-06-11 20:00:00","checks":{"database":true,"redis":true}}</pre>
</div>

</div>
</body>
</html>
