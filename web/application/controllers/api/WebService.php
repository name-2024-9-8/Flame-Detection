<?php
/**
 * WebService 数据交换控制器 — 跨系统 JSON 数据接口 / 加密传输
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段4 数据交换与系统对接
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class WebService extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Alarm_model');
        $this->load->model('Device_model');
    }

    // ─────────────────────────────────
    //  POST /api/webservice/alarm — 接收外部系统报警数据
    // ─────────────────────────────────

    /**
     * 通用报警数据上报接口（对外标准格式）
     * 请求格式：{"UnitCode":"单位编码","VerifyID":"验证ID","data":{...}}
     * 响应格式：{"code":200,"message":"success","data":{"event_id":123}}
     * 失败重传标记：响应含 error_code 字段
     */
    public function alarm() {
        $this->rate_limit('ws_alarm:' . $this->input->ip_address(), 30, 60);

        $raw  = file_get_contents('php://input');
        $body = json_decode($raw, true);
        if (!$body) $body = $this->input->post();

        $unit_code = isset($body['UnitCode']) ? $body['UnitCode'] : null;
        $verify_id = isset($body['VerifyID']) ? $body['VerifyID'] : null;
        $data = isset($body['data']) ? $body['data'] : $body;

        if (empty($unit_code)) {
            $this->error('缺少 UnitCode（单位编码）');
        }

        // 调用方身份校验（数据库注册单位查询）
        $this->_verify_caller($unit_code, $verify_id);

        if (empty($data['device_id'])) {
            $this->error('缺少 device_id', $this->http_bad_request);
        }

        // 设备 MAC 校验
        if (empty($data['device_mac'])) {
            $this->error('缺少 device_mac', $this->http_forbidden);
        }
        $device = $this->db->get_where('T_Device', array(
            'Id' => $data['device_id'],
            'MAC' => $data['device_mac']
        ))->row();
        if (!$device) {
            $this->error('设备验证失败', $this->http_forbidden);
        }

        try {
            $event_id = $this->Alarm_model->create($data);

            $response = array(
                'event_id'    => $event_id,
                'retry_flag'  => false,
            );
            $this->success($response, '上报成功', $this->http_created);
        } catch (Exception $e) {
            log_message('error', 'WebService alarm failed: ' . $e->getMessage());
            $this->error('数据处理失败，请重试', $this->http_server_error, array(
                'error_code' => 'E001',
                'retry_flag' => true,
            ));
        }
    }

    // ─────────────────────────────────
    //  GET /api/webservice/device/:id — 获取云盒详情（供外部系统查询）
    // ─────────────────────────────────

    public function device($id = 0) {
        $unit_code = $this->input->get('unit_code', true);
        if ($unit_code) {
            // 外部系统：验证 unit_code 注册状态
            $this->_verify_caller($unit_code, null);
        } else {
            $this->require_auth();
        }

        $device = $this->Device_model->get_device_detail($id);
        if (!$device) {
            $this->error('设备不存在', $this->http_not_found);
        }

        $this->success($device);
    }

    // ─────────────────────────────────
    //  GET /api/webservice/video-frame/:event_id — 获取报警视频帧URL
    // ─────────────────────────────────

    public function video_frame($event_id = 0) {
        $unit_code = $this->input->get('unit_code', true);
        if ($unit_code) {
            $this->_verify_caller($unit_code, null);
        } else {
            $this->require_auth();
        }

        $event = $this->Alarm_model->get_detail($event_id);
        if (!$event) {
            $this->error('事件不存在', $this->http_not_found);
        }

        $this->success(array(
            'event_id'   => $event_id,
            'picture_url' => $event['Picture'],
            'video_url'   => $event['VideoUrl'],
            'camera_url'  => $event['CameraIP'] ? 'rtsp://' . $event['CameraIP'] . '/stream' : null,
        ));
    }

    // ─────────────────────────────────
    //  POST /api/webservice/report — 数据汇报（向智慧城市等上级平台推送）
    // ─────────────────────────────────

    /**
     * 数据汇报接口 — 向区智慧城市/市级平台推送统计数据
     * 预留：实际对接时填写目标 URL 和认证信息
     */
    public function report() {
        $this->require_auth();
        $this->log_access();

        $target = $this->input->post('target', true) ?: 'smart_city';
        $start  = $this->input->post('start_time', true);
        $end    = $this->input->post('end_time', true);

        $summary = $this->Alarm_model->summary($start, $end);
        $by_area = $this->Alarm_model->stats_by_area($start, $end);

        $report = array(
            'report_time' => date('Y-m-d H:i:s'),
            'reporter'    => 'flame_detection',
            'period'      => array('start' => $start, 'end' => $end),
            'summary'     => $summary,
            'by_area'     => $by_area,
        );

        // TODO: 向目标平台发起 HTTP POST 推送
        // $target_urls = array(
        //     'smart_city' => 'http://xxx.smartcity.gov/api/receive',
        //     'municipal'  => 'http://xxx.municipal.gov/api/receive',
        // );
        // $this->_post_to_external($target_urls[$target], $report);

        $this->success(array('report' => $report, 'target' => $target), '汇报数据已准备');
    }

    // ─────────────────────────────────
    //  调用方身份校验（预留）
    // ─────────────────────────────────

    private function _verify_caller($unit_code, $verify_id) {
        // 查询数据字典中注册的外部系统单位
        $registered = $this->db
            ->get_where('T_Dictionary', array('Key' => 'UnitCode', 'Value' => $unit_code))
            ->row();
        if (!$registered && !in_array($unit_code, array('SMART_CITY_001', 'VIDEO_MONITOR_001', 'ATMOS_MONITOR_001'))) {
            $this->error('未注册的单位编码：' . $unit_code, $this->http_forbidden);
        }
        return true;
    }
}
