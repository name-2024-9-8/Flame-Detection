<?php
/**
 * Statistics 统计分析控制器 — 按时间/区域/设备统计报警数据
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 阶段3 核心业务后端：智能分析模块
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Statistics extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Alarm_model');
    }

    // ─────────────────────────────────
    //  GET /api/statistics
    // ─────────────────────────────────

    public function index() {
        $this->require_auth();
        $this->log_access();

        $dimension = $this->input->get('dimension', true) ?: 'summary';  // summary / time / area
        $start     = $this->input->get('start_time', true);
        $end       = $this->input->get('end_time', true);

        $result = array();

        switch ($dimension) {
            case 'summary':
                // 总览数据
                $result = $this->Alarm_model->summary($start, $end);
                break;

            case 'time':
                // 按日统计
                $granularity = $this->input->get('granularity', true) ?: 'day';
                $result = $this->Alarm_model->stats_by_time($granularity, $start, $end);
                break;

            case 'area':
                // 按区域统计
                $result = $this->Alarm_model->stats_by_area($start, $end);
                break;

            default:
                $this->error('无效的统计维度，可选值：summary / time / area');
        }

        $this->success($result);
    }

    // ─────────────────────────────────
    //  GET /api/statistics/health — 系统健康检查
    // ─────────────────────────────────

    public function health() {
        // 不需要鉴权，供运维监控使用
        $status = array(
            'status'    => 'ok',
            'timestamp' => date('Y-m-d H:i:s'),
            'checks'    => array(
                'database' => $this->_check_db(),
                'redis'    => $this->_check_redis(),
            )
        );

        $all_ok = true;
        foreach ($status['checks'] as $check) {
            if (!$check) $all_ok = false;
        }
        $status['status'] = $all_ok ? 'ok' : 'degraded';

        $http_code = $all_ok ? 200 : 503;
        http_response_code($http_code);
        echo json_encode($status, JSON_UNESCAPED_UNICODE);
    }

    private function _check_db() {
        try {
            $this->db->query('SELECT 1');
            return true;
        } catch (Exception $e) {
            return false;
        }
    }

    private function _check_redis() {
        try {
            $redis = new Predis\Client();
            return $redis->ping() === 'PONG';
        } catch (Exception $e) {
            return false;
        }
    }
}
