<?php
/**
 * Branch 部门管理控制器 — 列表/树/详情/创建/更新/删除
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 部门管理API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Branch extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Branch_model');
    }

    // GET /api/branches — 部门列表
    public function index() {
        $this->require_auth();
        $this->log_access();

        $list = $this->Branch_model->get_list();
        $this->success(array('list' => $list));
    }

    // GET /api/branches/tree — 部门树
    public function tree() {
        $this->require_auth();

        $tree = $this->Branch_model->get_tree();
        $this->success(array('list' => $tree));
    }

    // POST /api/branches/create — 创建部门
    public function create() {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data['name'])) $this->error('部门名称不能为空');

        $id = $this->Branch_model->create($data);
        $this->success(array('id' => $id), '部门创建成功', $this->http_created);
    }

    // GET /api/branches/(:num) — 部门详情
    public function detail($id = 0) {
        $this->require_auth();
        $this->log_access();

        $branch = $this->Branch_model->get_detail($id);
        if (!$branch) $this->error('部门不存在', $this->http_not_found);

        $this->success($branch);
    }

    // POST /api/branches/(:num)/update — 更新部门
    public function update($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data)) $this->error('缺少更新数据');

        $result = $this->Branch_model->update($id, $data);
        $this->success(null, $result ? '更新成功' : '无变更');
    }

    // GET /api/branches/(:num)/delete — 删除部门
    public function delete($id = 0) {
        $this->require_admin();
        $this->log_access();

        $result = $this->Branch_model->delete($id);
        if (!$result) $this->error('删除失败（请先移除子部门和部门成员）');

        $this->success(null, '删除成功');
    }
}
