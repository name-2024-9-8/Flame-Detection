<?php
/**
 * Dictionary 数据字典控制器 — 列表/类型/详情/创建/更新/删除
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 数据字典管理API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Dictionary extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Dictionary_model');
    }

    // GET /api/dictionary — 字典列表
    public function index() {
        $this->require_auth();
        $this->log_access();

        $dict_type = $this->input->get('dict_type', true);
        $list = $this->Dictionary_model->get_list($dict_type);
        $this->success(array('list' => $list));
    }

    // GET /api/dictionary/types — 字典类型列表
    public function types() {
        $this->require_auth();
        $types = $this->Dictionary_model->get_types();
        $this->success(array('list' => $types));
    }

    // POST /api/dictionary/create — 创建字典项
    public function create() {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data['key']) || empty($data['value'])) {
            $this->error('字典类型(Key)和值(Value)不能为空');
        }

        $id = $this->Dictionary_model->create($data);
        $this->success(array('id' => $id), '字典项创建成功', $this->http_created);
    }

    // GET /api/dictionary/(:num) — 字典详情
    public function detail($id = 0) {
        $this->require_auth();
        $this->log_access();

        $item = $this->Dictionary_model->get_detail($id);
        if (!$item) $this->error('字典项不存在', $this->http_not_found);

        $this->success($item);
    }

    // POST /api/dictionary/(:num)/update — 更新字典项
    public function update($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data)) $this->error('缺少更新数据');

        $result = $this->Dictionary_model->update($id, $data);
        $this->success(null, $result ? '更新成功' : '无变更');
    }

    // GET /api/dictionary/(:num)/delete — 删除字典项
    public function delete($id = 0) {
        $this->require_admin();
        $this->log_access();

        $this->Dictionary_model->delete($id);
        $this->success(null, '删除成功');
    }
}
