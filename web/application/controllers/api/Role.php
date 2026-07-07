<?php
/**
 * Role 角色管理控制器 — 列表/详情/创建/更新/删除
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 角色管理API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Role extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Role_model');
    }

    // GET /api/roles — 角色列表
    public function index() {
        $this->require_auth();
        $this->log_access();

        $list = $this->Role_model->get_list();
        $this->success(array('list' => $list));
    }

    // POST /api/roles/create — 创建角色
    public function create() {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data['name'])) $this->error('角色名称不能为空');

        $id = $this->Role_model->create($data);
        $this->success(array('id' => $id), '角色创建成功', $this->http_created);
    }

    // GET /api/roles/(:num) — 角色详情
    public function detail($id = 0) {
        $this->require_auth();
        $this->log_access();

        $role = $this->Role_model->get_detail($id);
        if (!$role) $this->error('角色不存在', $this->http_not_found);

        $this->success($role);
    }

    // POST /api/roles/(:num)/update — 更新角色
    public function update($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data)) $this->error('缺少更新数据');

        $result = $this->Role_model->update($id, $data);
        $this->success(null, $result ? '更新成功' : '无变更');
    }

    // GET /api/roles/(:num)/delete — 删除角色
    public function delete($id = 0) {
        $this->require_admin();
        $this->log_access();

        $this->Role_model->delete($id);
        $this->success(null, '删除成功');
    }
}
