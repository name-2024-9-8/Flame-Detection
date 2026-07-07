<?php
/**
 * Config 系统配置控制器 — 读取/更新 T_Site
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 系统配置管理API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Config extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Site_model');
    }

    // GET /api/config — 读取系统配置
    public function index() {
        $this->require_admin();
        $this->log_access();

        $config = $this->Site_model->get_config();
        $this->success($config);
    }

    // POST /api/config/update — 更新系统配置
    public function update() {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        if (empty($data)) $this->error('缺少配置数据');

        $result = $this->Site_model->update_config($data);
        $this->success(null, $result ? '配置更新成功' : '无变更');
    }
}
