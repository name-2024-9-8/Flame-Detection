<?php
/**
 * Device 设备管理控制器 — AI云盒 / 摄像头 CRUD
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 阶段3 核心业务后端：设备资源信息管理
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Device extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Device_model');
    }

    // ─────────────────────────────────
    //  GET /api/devices?type=device|camera
    // ─────────────────────────────────

    public function index() {
        $this->require_auth();
        $this->log_access();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(100, max(1, intval($this->input->get('per_page', true)) ?: 20));
        $type     = $this->input->get('type', true) ?: 'device';

        $filters = array(
            'area_id'   => $this->input->get('area_id', true),
            'device_id' => $this->input->get('device_id', true),
            'keyword'   => $this->input->get('keyword', true),
        );

        if ($type === 'camera') {
            $result = $this->Device_model->get_camera_list($page, $per_page, $filters);
        } else {
            $result = $this->Device_model->get_device_list($page, $per_page, $filters);
        }

        $this->success($result);
    }

    // ─────────────────────────────────
    //  POST /api/devices/create
    // ─────────────────────────────────

    public function create() {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) $data = $this->input->post();

        $type = isset($data['type']) ? $data['type'] : 'device';

        if ($type === 'camera') {
            if (empty($data['name'])) $this->error('摄像头名称不能为空');
            $id = $this->Device_model->create_camera($data);
        } else {
            if (empty($data['mac'])) $this->error('MAC地址不能为空');
            $id = $this->Device_model->create_device($data);
        }

        $this->success(array('id' => $id), '创建成功', $this->http_created);
    }

    // ─────────────────────────────────
    //  PUT /api/devices/(:num)/update
    // ─────────────────────────────────

    public function update($id = 0) {
        $this->require_admin();
        $this->log_access();

        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        if (!$data) $data = $this->input->post();

        $type = isset($data['type']) ? $data['type'] : 'device';

        if ($type === 'camera') {
            $result = $this->Device_model->update_camera($id, $data);
        } else {
            $result = $this->Device_model->update_device($id, $data);
        }

        $this->success(null, $result ? '更新成功' : '无变更');
    }

    // ─────────────────────────────────
    //  DELETE /api/devices/(:num)/delete
    // ─────────────────────────────────

    public function delete($id = 0) {
        $this->require_admin();
        $this->log_access();

        $type = $this->input->get('type', true) ?: 'device';

        if ($type === 'camera') {
            $result = $this->Device_model->delete_camera($id);
        } else {
            $result = $this->Device_model->delete_device($id);
        }

        $this->success(null, $result ? '删除成功' : '删除失败');
    }
}
