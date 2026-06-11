"""
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
认证路由：登录、登出、Token验证
作者：人员C（前端开发与质量保障工程师）
创建时间：2026-06-11
=============================================================================
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from models import db, User, OperationLog

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录系统', 'warning')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """超级用户验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录系统', 'warning')
            return redirect(url_for('auth.login_page'))
        if session.get('user_type') != 1:
            flash('需要超级用户权限', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """获取当前登录用户"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
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
    """处理登录请求"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    remember = request.form.get('remember') == 'on'

    if not username or not password:
        flash('请输入用户名和密码', 'danger')
        return redirect(url_for('auth.login_page'))

    user = User.query.filter_by(username=username).first()

    if user is None or not user.check_password(password):
        flash('用户名或密码错误', 'danger')
        # 记录登录失败日志
        _log_operation(user, 'LOGIN', 'auth', f'用户 {username} 登录失败', request)
        return redirect(url_for('auth.login_page'))

    if user.status == 0:
        flash('该账户已被禁用，请联系管理员', 'danger')
        return redirect(url_for('auth.login_page'))

    # 登录成功，设置session
    session['user_id'] = user.id
    session['username'] = user.username
    session['user_type'] = user.user_type
    session['real_name'] = user.real_name or user.username
    if remember:
        session.permanent = True

    # 更新用户登录信息
    user.last_login_at = datetime.now()
    user.last_login_ip = request.remote_addr
    user.login_count = (user.login_count or 0) + 1
    db.session.commit()

    # 记录登录成功日志
    _log_operation(user, 'LOGIN', 'auth', f'用户 {username} 登录成功', request)

    flash(f'欢迎回来，{user.real_name or user.username}！', 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    """登出"""
    if 'user_id' in session:
        user = get_current_user()
        if user:
            _log_operation(user, 'LOGOUT', 'auth', f'用户 {user.username} 登出系统', request)

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
    """更新个人资料"""
    user = get_current_user()
    if not user:
        return jsonify({'code': 401, 'msg': '请先登录'}), 401

    user.real_name = request.form.get('real_name', user.real_name)
    user.email = request.form.get('email', user.email)
    user.phone = request.form.get('phone', user.phone)

    new_password = request.form.get('new_password', '')
    if new_password:
        if len(new_password) < 6:
            return jsonify({'code': 400, 'msg': '密码长度不能少于6位'}), 400
        user.set_password(new_password)

    db.session.commit()
    session['real_name'] = user.real_name or user.username

    _log_operation(user, 'UPDATE', 'profile', '更新个人资料', request)
    flash('个人资料更新成功', 'success')
    return redirect(url_for('auth.profile'))


# =========================================================================
# 辅助函数
# =========================================================================

def _log_operation(user, op_type, module, desc, request_obj, target_table=None,
                   target_id=None, old_data=None, new_data=None):
    """记录操作日志的辅助函数"""
    try:
        log = OperationLog(
            user_id=user.id if user else None,
            username=user.username if user else 'anonymous',
            operation_type=op_type,
            operation_module=module,
            operation_desc=desc,
            target_table=target_table,
            target_id=target_id,
            old_data=old_data,
            new_data=new_data,
            ip_address=request_obj.remote_addr if request_obj else '',
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass  # 日志记录失败不影响主流程
