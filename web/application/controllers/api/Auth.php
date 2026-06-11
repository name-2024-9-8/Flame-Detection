<?php
/**
 * Auth 认证控制器 — 登录 / 登出 / Token 刷新 / 用户信息
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段2 RESTful API与JWT鉴权
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';
class Auth extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('User_model');
    }

    // ─────────────────────────────────
    //  POST /api/auth/login
    // ─────────────────────────────────

    public function login() {
        // 频率限制：同一 IP 每分钟最多 10 次登录尝试
        $this->rate_limit('login:' . $this->input->ip_address(), 10, 60);

        $account  = $this->input->post('account', true);
        $password = $this->input->post('password');

        if (empty($account) || empty($password)) {
            $this->error('账号和密码不能为空');
        }

        // 查询用户
        $user = $this->User_model->get_by_account($account);
        if (!$user) {
            $this->error('账号或密码错误');
        }

        // 验证密码（兼容明文和 hash）
        if (password_verify($password, $user->Password)) {
            // hash 验证
        } elseif ($password === $user->Password) {
            // 旧明文密码 → 自动升级为 hash
            $this->User_model->update_password($user->Id, $password);
        } else {
            $this->error('账号或密码错误');
        }

        // 生成 Token
        $token = $this->generate_token($user->Id, $user->Account);

        // 返回
        $data = array(
            'token'      => $token,
            'expires_in' => $this->jwt_expire,
            'user'       => array(
                'id'      => $user->Id,
                'account' => $user->Account,
                'name'    => $user->Name,
                'area_id' => $user->AreaId,
                'branch_id' => $user->BranchId,
            )
        );

        // 记录访问日志
        $this->log_access($user->Id, '登录成功');

        $this->success($data, '登录成功');
    }

    // ─────────────────────────────────
    //  GET /api/auth/profile
    // ─────────────────────────────────

    public function profile() {
        $payload = $this->require_auth();
        $user = $this->User_model->get_by_id($this->current_user_id);

        if (!$user) {
            $this->error('用户不存在', $this->http_not_found);
        }

        $this->success(array(
            'id'        => $user->Id,
            'account'   => $user->Account,
            'name'      => $user->Name,
            'email'     => $user->Email,
            'phone'     => $user->Phone,
            'area_id'   => $user->AreaId,
            'branch_id' => $user->BranchId,
        ));
    }

    // ─────────────────────────────────
    //  POST /api/auth/refresh
    // ─────────────────────────────────

    public function refresh() {
        $payload = $this->require_auth();
        $token = $this->generate_token($payload->user_id, $payload->account);

        $this->success(array(
            'token'      => $token,
            'expires_in' => $this->jwt_expire,
        ), 'Token 刷新成功');
    }

    // ─────────────────────────────────
    //  POST /api/auth/logout
    // ─────────────────────────────────

    public function logout() {
        $this->require_auth();
        $this->log_access($this->current_user_id, '登出');
        // 无状态 JWT 无法服务端销毁，前端丢弃即可
        $this->success(null, '登出成功');
    }
}
