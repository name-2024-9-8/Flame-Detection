<?php
/**
 * User 用户管理控制器 — 列表/详情/创建/更新/删除
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 用户管理API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class User extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('User_model');
    }

    // GET /api/users — 用户列表
    public function index() {
        $this->require_auth();
        $this->log_access();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(100, max(1, intval($this->input->get('per_page', true)) ?: 20));

        $filters = array();
        foreach (array('username', 'real_name', 'user_type') as $k) {
            $v = $this->input->get($k, true);
            if ($v !== null && $v !== '') {
                $filters[$k] = $v;
            }
        }

        $result = $this->User_model->get_user_list($page, $per_page, $filters);
        $this->success($result);
    }

    // POST /api/users/create — 创建用户
    public function create() {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data['account'])) $this->error('账号不能为空');
        if (empty($data['name']))   $this->error('姓名不能为空');

        // 检查账号是否已存在
        $exist = $this->User_model->get_by_account($data['account']);
        if ($exist) $this->error('该账号已存在');

        $id = $this->User_model->create_user($data);
        $this->success(array('id' => $id), '用户创建成功', $this->http_created);
    }

    // GET /api/users/(:num) — 用户详情
    public function detail($id = 0) {
        $this->require_auth();
        $this->log_access();

        $user = $this->User_model->get_user_detail($id);
        if (!$user) $this->error('用户不存在', $this->http_not_found);

        $this->success($user);
    }

    // POST /api/users/(:num)/update — 更新用户
    public function update($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data)) $this->error('缺少更新数据');

        $result = $this->User_model->update_user($id, $data);
        $this->success(null, $result ? '更新成功' : '无变更');
    }

    // GET /api/users/(:num)/delete — 删除用户
    public function delete($id = 0) {
        $this->require_admin();
        $this->log_access();

        $result = $this->User_model->delete_user($id);
        if (!$result) $this->error('删除失败（不允许删除管理员账号）');

        $this->success(null, '删除成功');
    }
}
