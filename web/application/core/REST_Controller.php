<?php
/**
 * REST API 基类控制器 — 提供 JSON 响应封装、JWT 鉴权、频率限制、访问日志等通用功能
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 后端开发与系统集成（RESTful API 基础框架）
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . '../vendor/autoload.php';
use \Firebase\JWT\JWT;
use \Firebase\JWT\Key;
class REST_Controller extends CI_Controller {

    // ── 系统常量 ──
    const ROLE_ADMIN = '超级管理员'; // 管理员角色名（与数据库种子一致）
    const ROLE_USER  = '普通用户';

    // JWT 密钥（生产环境应从环境变量读取）
    protected $jwt_key = 'vai2026_flame_jwt_secret_2026';
    // Token 有效期（秒），默认 24 小时
    protected $jwt_expire = 86400;
    // 当前请求用户ID（登录后填充）
    protected $current_user_id = null;
    // HTTP 状态码
    protected $http_ok            = 200;
    protected $http_created       = 201;
    protected $http_bad_request   = 400;
    protected $http_unauthorized  = 401;
    protected $http_forbidden     = 403;
    protected $http_not_found     = 404;
    protected $http_server_error  = 500;

    public function __construct() {
        parent::__construct();
        header('Content-Type: application/json; charset=UTF-8');
        // CORS: 生产环境应改为具体域名，开发时允许所有
        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type, Authorization');
        header('X-Content-Type-Options: nosniff');
        header('X-Frame-Options: DENY');

        if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
            http_response_code(200);
            exit;
        }
    }

    /**
     * Check if current user is admin (Account=admin or RoleId=1)
     */
    protected function require_admin() {
        $this->require_auth();
        // admin account always has access
        $u = $this->db->get_where('T_User', array('Id' => $this->current_user_id))->row();
        if ($u && $u->Account === 'admin') return;
        // check RoleId=1 (super admin)
        $ur = $this->db->get_where('T_UserRole', array(
            'UserId' => $this->current_user_id,
            'RoleId' => 1,
        ))->row();
        if (!$ur) {
            $this->error('Need admin permission', $this->http_forbidden);
        }
    }


    // ─────────────────────────────────
    //  统一 JSON 响应
    // ─────────────────────────────────

    /**
     * 成功响应
     */
    protected function success($data = null, $message = 'success', $code = null) {
        $code = $code ?: $this->http_ok;
        $this->_json($code, $message, $data);
    }

    /**
     * 失败响应
     */
    protected function error($message = 'error', $code = null, $data = null) {
        $code = $code ?: $this->http_bad_request;
        $this->_json($code, $message, $data);
    }

    private function _json($http_code, $message, $data) {
        http_response_code($http_code);
        $result = array(
            'code'    => $http_code,
            'message' => $message,
            'data'    => $data
        );
        echo json_encode($result, JSON_UNESCAPED_UNICODE);
        exit;
    }

    // ─────────────────────────────────
    //  JWT 鉴权
    // ─────────────────────────────────

    /**
     * 生成 JWT Token
     */
    protected function generate_token($user_id, $account) {
        $payload = array(
            'iss'     => 'flame_detection',       // 签发者
            'iat'     => time(),                   // 签发时间
            'exp'     => time() + $this->jwt_expire, // 过期时间
            'user_id' => $user_id,
            'account' => $account
        );
        return JWT::encode($payload, $this->jwt_key, 'HS256');
    }

    /**
     * 验证 JWT 并返回 payload，失败时直接输出错误并退出
     */
    protected function require_auth() {
        $token = $this->_get_token();
        if (!$token) {
            $this->error('缺少认证 Token，请先登录', $this->http_unauthorized);
        }
        try {
            $decoded = JWT::decode($token, new Key($this->jwt_key, 'HS256'));
            $this->current_user_id = $decoded->user_id;
            return $decoded;
        } catch (\Exception $e) {
            $this->error('Token 无效或已过期，请重新登录', $this->http_unauthorized);
        }
    }

    /**
     * 从请求头中提取 Token
     */
    private function _get_token() {
        $header = $this->input->get_request_header('Authorization');
        if (!$header) {
            return null;
        }
        // 支持 "Bearer <token>" 格式或直接传 token
        if (preg_match('/^Bearer\s+(.+)$/i', $header, $matches)) {
            return $matches[1];
        }
        return $header;
    }

    // ─────────────────────────────────
    //  频率限制（Redis）
    // ─────────────────────────────────

    /**
     * 简单频率限制：同一 key 在 $seconds 秒内最多 $max 次
     */
    protected function rate_limit($key, $max = 60, $seconds = 60) {
        try {
            $redis  = new \Predis\Client();
            $count  = $redis->incr($key);
            if ($count == 1) {
                $redis->expire($key, $seconds);
            }
            if ($count > $max) {
                $this->error('请求过于频繁，请稍后再试', $this->http_bad_request);
            }
        } catch (\Exception $e) {
            // Redis 不可用时跳过限制
        }
    }

    /**
     * 记录访问日志
     */
    protected function log_access($user_id = null, $remark = '') {
        $this->db->insert('T_AccessLog', array(
            'UserId'     => $user_id ?: $this->current_user_id,
            'Url'        => uri_string(),
            'Method'     => $this->input->method(),
            'IP'         => $this->input->ip_address(),
            'UserAgent'  => substr($this->input->user_agent(), 0, 500),
            'CreateTime' => date('Y-m-d H:i:s'),
            'Remark'     => $remark
        ));
    }
}
