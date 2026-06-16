"""
=============================================================================
认证路由：登录、登出、Token验证 — 融合模式（通过B的PHP API鉴权）
作者：段林川（前端） + 王永林（后端API桥接）
创建时间：2026-06-11
修改时间：2026-06-12  融合：改为调用B的PHP API而非本地SQLite
=============================================================================
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps

auth_bp = Blueprint('auth', __name__)


def _try_restore_session_from_jwt():
    """从请求头的JWT Bearer Token中恢复用户会话（用于API调用）"""
    if 'user_id' in session:
        return True  # 已有有效session
    auth_header = request.headers.get('Authorization', '')
    if not auth_header:
        return False
    # 解析 Bearer token
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    else:
        token = auth_header
    if not token:
        return False
    # 用JWT查询B的PHP API获取用户信息
    try:
        from api_bridge import APIBridge
        APIBridge.set_token(token)
        result = APIBridge.get_profile()
        if result.get('code') == 200:
            user_data = result.get('data', {})
            session['user_id'] = user_data.get('id')
            session['username'] = user_data.get('username', '')
            session['user_type'] = user_data.get('user_type', 2)
            session['real_name'] = user_data.get('real_name', '')
            session['email'] = user_data.get('email', '')
            session['phone'] = user_data.get('phone', '')
            session['jwt_token'] = token
            return True
    except Exception:
        pass
    return False


def login_required(f):
    """登录验证装饰器 — 支持 session cookie 和 JWT Bearer token 双模式"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 先尝试从JWT恢复session（API调用场景）
        _try_restore_session_from_jwt()
        if 'user_id' not in session:
            # API请求返回401 JSON，页面请求重定向到登录页
            if request.path.startswith('/api/'):
                from flask import jsonify
                return jsonify({'code': 401, 'msg': '请先登录', 'data': None}), 401
            flash('请先登录系统', 'warning')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """超级用户验证装饰器 — 支持 session 和 JWT 双模式"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        _try_restore_session_from_jwt()
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                from flask import jsonify
                return jsonify({'code': 401, 'msg': '请先登录', 'data': None}), 401
            flash('请先登录系统', 'warning')
            return redirect(url_for('auth.login_page'))
        if session.get('user_type') != 1:
            if request.path.startswith('/api/'):
                from flask import jsonify
                return jsonify({'code': 403, 'msg': '需要超级用户权限', 'data': None}), 403
            flash('需要超级用户权限', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """获取当前登录用户（从session中获取用户信息字典）"""
    if 'user_id' in session:
        return {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'real_name': session.get('real_name'),
            'user_type': session.get('user_type'),
            'email': session.get('email', ''),
            'phone': session.get('phone', ''),
            'department_id': session.get('department_id'),
            'role_id': session.get('role_id'),
        }
    return None


# =========================================================================
# 页面路由
# =========================================================================

@auth_bp.route('/login', methods=['GET'])
def login_page():
    """登录页面"""
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    """处理登录请求 — 通过B的PHP API鉴权"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    remember = request.form.get('remember') == 'on'

    if not username or not password:
        flash('请输入用户名和密码', 'danger')
        return redirect(url_for('auth.login_page'))

    # ★ 融合模式：调用B的PHP API进行鉴权
    from api_bridge import APIBridge
    result = APIBridge.login(username, password)

    if result.get('code') != 200:
        flash(result.get('msg', '用户名或密码错误'), 'danger')
        return redirect(url_for('auth.login_page'))

    # 登录成功，从API响应中提取用户信息
    user_data = result.get('data', {}).get('user', {})
    jwt_token = result.get('data', {}).get('token', '')

    # 存储到Flask session（保持原有session机制兼容模板）
    session['user_id'] = user_data.get('id')
    session['username'] = user_data.get('username', username)
    session['user_type'] = user_data.get('user_type', 2)
    session['real_name'] = user_data.get('real_name') or username
    session['email'] = user_data.get('email', '')
    session['phone'] = user_data.get('phone', '')
    session['department_id'] = user_data.get('department_id')
    session['role_id'] = user_data.get('role_id')
    session['jwt_token'] = jwt_token   # ★ 保存JWT供bridge使用

    if remember:
        session.permanent = True

    flash('欢迎回来，{}！'.format(session.get('real_name', username)), 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    """登出"""
    from api_bridge import APIBridge
    APIBridge.logout()
    session.clear()
    flash('您已成功退出系统', 'info')
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/profile')
@login_required
def profile():
    """个人资料页面"""
    user = get_current_user()
    return render_template('profile.html', user=user)


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """更新个人资料（融合模式下暂不支持密码修改，需B端扩展API）"""
    user = get_current_user()
    if not user:
        return jsonify({'code': 401, 'msg': '请先登录'}), 401

    # 仅更新session中的显示名称
    new_name = request.form.get('real_name', '')
    if new_name:
        session['real_name'] = new_name

    flash('个人资料更新成功（密码修改需联系管理员）', 'success')
    return redirect(url_for('auth.profile'))
