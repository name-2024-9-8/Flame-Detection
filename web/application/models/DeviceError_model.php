<?php
/**
 * AI云盒故障模型 — T_DeviceError 查询/维修
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 云盒故障管理数据层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class DeviceError_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    /**
     * 分页查询故障列表
     */
    public function get_list($page = 1, $per_page = 20, $filters = array()) {
        $this->db->select('de.*, d.Address as DeviceAddress, d.MAC as DeviceMAC, d.Longitude, d.Latitude');
        $this->db->from('T_DeviceError de');
        $this->db->join('T_Device d', 'de.DeviceId = d.Id', 'left');

        if (!empty($filters['device_id'])) {
            $this->db->where('de.DeviceId', $filters['device_id']);
        }
        if (!empty($filters['error_code'])) {
            $this->db->where('de.ErrorCode', $filters['error_code']);
        }

        $total = $this->db->count_all_results('', false);
        $this->db->order_by('de.CreateTime', 'DESC');
        $this->db->limit($per_page, ($page - 1) * $per_page);
        $list = $this->db->get()->result_array();

        return array('total' => $total, 'page' => $page, 'per_page' => $per_page, 'list' => $list);
    }

    /**
     * 单条详情
     */
    public function get_detail($id) {
        $this->db->select('de.*, d.Address as DeviceAddress, d.MAC as DeviceMAC, d.Longitude, d.Latitude');
        $this->db->from('T_DeviceError de');
        $this->db->join('T_Device d', 'de.DeviceId = d.Id', 'left');
        $this->db->where('de.Id', $id);
        return $this->db->get()->row_array();
    }

    /**
     * 创建故障记录
     */
    public function create($data) {
        $row = array(
            'DeviceId'   => isset($data['device_id']) ? intval($data['device_id']) : null,
            'MAC'        => isset($data['mac']) ? $data['mac'] : null,
            'CreateTime' => isset($data['create_time']) ? $data['create_time'] : date('Y-m-d H:i:s'),
            'ErrorCode'  => isset($data['error_code']) ? $data['error_code'] : 'unknown',
            'ErrorMsg'   => isset($data['error_msg']) ? $data['error_msg'] : null,
            'Remark'     => isset($data['remark']) ? $data['remark'] : null,
        );
        $this->db->insert('T_DeviceError', $row);
        return $this->db->insert_id();
    }

    /**
     * 维修（标记已修复）
     */
    public function repair($id, $remark = '') {
        $remark_text = '已修复' . ($remark ? ': ' . $remark : '');
        $this->db->where('Id', $id);
        return $this->db->update('T_DeviceError', array('Remark' => $remark_text));
    }

    /**
     * 故障统计
     */
    public function get_stats() {
        $today_start = date('Y-m-d 00:00:00');
        $week_start  = date('Y-m-d 00:00:00', strtotime('-6 days'));
        $month_start = date('Y-m-01 00:00:00');
        $year_start  = date('Y-01-01 00:00:00');

        return array(
            'today' => $this->_count_since($today_start),
            'week'  => $this->_count_since($week_start),
            'month' => $this->_count_since($month_start),
            'year'  => $this->_count_since($year_start),
        );
    }

    private function _count_since($since) {
        return $this->db->where('CreateTime >=', $since)
                        ->count_all_results('T_DeviceError');
    }
}
