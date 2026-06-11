<?php
/**
 * 前端联调登录页 — 供人员C 测试 JWT 鉴权流程
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 */
?><!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>火焰识别预警系统 — 管理登录</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: linear-gradient(135deg, #1e293b 0%, #334155 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { background: #fff; border-radius: 12px; padding: 40px 36px; width: 380px; box-shadow: 0 20px 60px rgba(0,0,0,.3); }
.card h2 { text-align: center; margin-bottom: 8px; color: #1e293b; }
.card .sub { text-align: center; color: #94a3b8; font-size: 13px; margin-bottom: 28px; }
.form-group { margin-bottom: 18px; }
.form-group label { display: block; font-size: 13px; color: #475569; margin-bottom: 6px; font-weight: 500; }
.form-group input { width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; outline: none; transition: border .2s; }
.form-group input:focus { border-color: #3b82f6; }
.btn { width: 100%; padding: 12px; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; font-weight: 500; transition: opacity .2s; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.result { margin-top: 16px; padding: 12px; border-radius: 6px; font-size: 13px; font-family: monospace; display: none; }
.result.success { background: #f0fdf4; color: #166534; border: 1px solid #86efac; display:block; }
.result.error { background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; display:block; }
.info { margin-top: 20px; padding: 10px 12px; background: #f8fafc; border-radius: 6px; font-size: 12px; color: #64748b; }
.info a { color: #3b82f6; }
</style>
</head>
<body>

<div class="card">
  <h2>🔥 火焰识别预警系统</h2>
  <p class="sub">视频AI智能识别及预警管理系统 v1.0</p>

  <div class="form-group">
    <label>账号</label>
    <input type="text" id="account" placeholder="admin" value="admin">
  </div>
  <div class="form-group">
    <label>密码</label>
    <input type="password" id="password" placeholder="密码" value="123456">
  </div>
  <button class="btn btn-primary" id="loginBtn" onclick="doLogin()">登 录</button>

  <div id="result" class="result"></div>

  <div class="info">
    🧪 联调用 — 登录后获得 JWT Token<br>
    📡 <a href="/index.php/apidoc" target="_blank">查看完整API文档</a>
  </div>
</div>

<script>
function doLogin() {
    var btn = document.getElementById('loginBtn');
    var result = document.getElementById('result');
    btn.disabled = true;
    btn.textContent = '登录中...';
    result.className = 'result';

    var formData = new FormData();
    formData.append('account', document.getElementById('account').value);
    formData.append('password', document.getElementById('password').value);

    fetch('/index.php/api/auth/login', {
        method: 'POST',
        body: formData
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.code === 200) {
            result.className = 'result success';
            result.innerHTML = '✅ 登录成功！<br><br>Token:<br><textarea style="width:100%;height:50px;font-size:11px" readonly>' + data.data.token + '</textarea><br>过期时间: ' + new Date(Date.now() + data.data.expires_in * 1000).toLocaleString() + '<br><br><b>测试命令（curl）:</b><br><code>curl -H "Authorization: Bearer ' + data.data.token.substr(0,25) + '..." http://localhost:8080/index.php/api/auth/profile</code>';
            // 存到 localStorage 方便后续调试
            try { localStorage.setItem('jwt_token', data.data.token); } catch(e) {}
        } else {
            result.className = 'result error';
            result.textContent = '❌ ' + data.message;
        }
    })
    .catch(function(err) {
        result.className = 'result error';
        result.textContent = '❌ 网络错误: ' + err.message;
    })
    .finally(function() {
        btn.disabled = false;
        btn.textContent = '登 录';
    });
}

// 回车登录
document.getElementById('password').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') doLogin();
});
</script>

</body>
</html>
