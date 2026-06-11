<?php
/**
 * Alarm 报警事件控制器 — 边缘设备数据接入 / 报警查询 / 处理审核
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段3 核心业务后端：报警事件CRUD API（A↔B关键接口）
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Alarm extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Alarm_model');
        $this->load->model('User_model');
    }

    // ─────────────────────────────────
    //  GET /api/alarm/events — 分页列表
    // ─────────────────────────────────

    public function index() {
        $this->require_auth();
        $this->log_access();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(100, max(1, intval($this->input->get('per_page', true)) ?: 20));

        $filters = array();
        $allowed = array('status', 'event_type', 'area_id', 'urgency_degree',
                         'device_id', 'camera_id', 'start_time', 'end_time');
        foreach ($allowed as $key) {
            $val = $this->input->get($key, true);
            if ($val !== null && $val !== '') {
                $filters[$key] = $val;
            }
        }

        $result = $this->Alarm_model->get_list($page, $per_page, $filters);
        $this->success($result);
    }

    // ─────────────────────────────────
    //  POST /api/alarm/events — 边缘设备上报（A→B 接口）
    // ─────────────────────────────────

    public function create() {
        // 边缘设备的请求可能不含 JWT Token，因此不强制鉴权
        // 但用设备 MAC 校验（可选的增强方案）

        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!$data || empty($data)) {
            // 兼容 form-data 或 CI3 已消费 php://input
            $data = $this->input->post();
            if (!$data) {
                $data = $_POST;
            }
        }

        if (empty($data)) {
            $this->error('缺少报警数据');
        }

        // 必填字段校验
        if (empty($data['device_id'])) {
            $this->error('缺少设备ID（device_id）');
        }

        $id = $this->Alarm_model->create($data);

        // 记录日志
        $this->log_access(null, '设备#' . $data['device_id'] . ' 上报报警事件#' . $id);

        // 发送通知（非关键路径，失败不影响主流程）
        try {
            $this->load->library('Email_lib');
            $this->email_lib->send_alarm_notify($id, $data);
        } catch (Exception $e) {
            log_message('error', 'Alarm notify failed: ' . $e->getMessage());
        }

        $this->success(array('event_id' => $id), '报警事件接收成功', $this->http_created);
    }

    // ─────────────────────────────────
    //  GET /api/alarm/events/(:num) — 详情
    // ─────────────────────────────────

    public function detail($id = 0) {
        $this->require_auth();
        $this->log_access();

        // 标记为已读
        $this->db->where('Id', $id)->update('T_DetectResult', array('IsRead' => 1));

        $event = $this->Alarm_model->get_detail($id);
        if (!$event) {
            $this->error('报警事件不存在', $this->http_not_found);
        }

        $this->success($event);
    }

    // ─────────────────────────────────
    //  POST /api/alarm/events/(:num)/update — 处理 + 审核
    // ─────────────────────────────────

    public function update($id = 0) {
        $this->require_auth();
        $this->log_access();

        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!$data || empty($data)) {
            $data = $this->input->post();
            if (!$data) {
                $data = $_POST;
            }
        }
        if (empty($data)) {
            $this->error('缺少更新数据');
        }

        $event = $this->Alarm_model->get_detail($id);
        if (!$event) {
            $this->error('报警事件不存在', $this->http_not_found);
        }

        $action = isset($data['action']) ? $data['action'] : 'process';

        switch ($action) {
            case 'process':
                // 处理：人员操作后变为"待审核"
                if ($event['Status'] != '1') {
                    $this->error('该事件当前状态不允许处理');
                }
                $this->Alarm_model->process($id, $this->current_user_id, $data);
                $this->log_operate('处理报警事件#' . $id, $event, $data);
                $this->success(null, '处理成功');

            case 'audit':
                // 审核：管理员审核通过
                if ($event['Status'] != '2') {
                    $this->error('该事件当前状态不允许审核');
                }
                $this->Alarm_model->audit($id, $this->current_user_id, $data);
                $this->log_operate('审核报警事件#' . $id, $event, $data);
                $this->success(null, '审核成功');

            default:
                $this->error('无效的操作类型，可选值：process / audit');
        }
    }

    // ─────────────────────────────────
    //  操作日志辅助
    // ─────────────────────────────────

    private function log_operate($menu, $old_data, $new_data) {
        $this->db->insert('T_OperateLog', array(
            'MenuName'   => '报警事件管理',
            'Type'       => $menu,
            'ContentOld' => json_encode($old_data, JSON_UNESCAPED_UNICODE),
            'ContentNew' => json_encode($new_data, JSON_UNESCAPED_UNICODE),
            'CreateTime' => date('Y-m-d H:i:s'),
            'UserId'     => $this->current_user_id,
        ));
    }
}
