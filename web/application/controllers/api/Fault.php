<?php
/**
 * Fault 故障管理控制器 — 摄像头故障/云盒故障列表与维修
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 故障管理API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Fault extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('CameraError_model');
        $this->load->model('DeviceError_model');
    }

    // ── 摄像头故障 ──

    // GET /api/faults/camera — 列表
    public function camera_faults() {
        $this->require_auth();
        $this->log_access();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(100, max(1, intval($this->input->get('per_page', true)) ?: 20));

        $filters = array();
        if ($this->input->get('camera_id'))  $filters['camera_id']  = $this->input->get('camera_id');
        if ($this->input->get('error_code')) $filters['error_code'] = $this->input->get('error_code');

        $result = $this->CameraError_model->get_list($page, $per_page, $filters);
        $stats  = $this->CameraError_model->get_stats();
        $result['stats'] = $stats;

        $this->success($result);
    }

    // POST /api/faults/camera/(:num)/repair — 维修
    public function camera_repair($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        $remark = isset($data['remark']) ? $data['remark'] : '';
        $result = $this->CameraError_model->repair($id, $remark);

        $this->log_operate('维修摄像头故障#' . $id);
        $this->success(null, $result ? '维修成功' : '维修失败');
    }

    // ── AI云盒故障 ──

    // GET /api/faults/device — 列表
    public function device_faults() {
        $this->require_auth();
        $this->log_access();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(100, max(1, intval($this->input->get('per_page', true)) ?: 20));

        $filters = array();
        if ($this->input->get('device_id'))  $filters['device_id']  = $this->input->get('device_id');
        if ($this->input->get('error_code')) $filters['error_code'] = $this->input->get('error_code');

        $result = $this->DeviceError_model->get_list($page, $per_page, $filters);
        $stats  = $this->DeviceError_model->get_stats();
        $result['stats'] = $stats;

        $this->success($result);
    }

    // POST /api/faults/device/(:num)/repair — 维修
    public function device_repair($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) { $data = $this->input->post(); }

        $remark = isset($data['remark']) ? $data['remark'] : '';
        $result = $this->DeviceError_model->repair($id, $remark);

        $this->log_operate('维修云盒故障#' . $id);
        $this->success(null, $result ? '维修成功' : '维修失败');
    }

    // 操作日志辅助
    private function log_operate($description) {
        $this->db->insert('T_OperateLog', array(
            'MenuName'   => '故障管理',
            'Type'       => '维修',
            'ContentNew' => $description,
            'CreateTime' => date('Y-m-d H:i:s'),
            'UserId'     => $this->current_user_id,
        ));
    }
}
