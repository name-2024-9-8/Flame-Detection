<?php
/**
 * 报警事件模型 — 污染检测结果 CRUD / 统计查询
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段3 核心业务后端：报警事件数据层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Alarm_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    // ─────────────────────────────────
    //  创建
    // ─────────────────────────────────

    /**
     * 接收边缘设备报警事件（A→B 接口）
     */
    public function create($data) {
        $row = array(
            'EventType'     => isset($data['event_type'])     ? $data['event_type']     : 'smoke',
            'Confidence'    => isset($data['confidence'])     ? floatval($data['confidence']) : null,
            'Longitude'     => isset($data['lng'])            ? $data['lng']            : null,
            'Latitude'      => isset($data['lat'])            ? $data['lat']            : null,
            'Location'      => isset($data['location'])       ? $data['location']       : null,
            'Picture'       => isset($data['picture'])        ? $data['picture']        : null,
            'VideoUrl'      => isset($data['video_url'])      ? $data['video_url']      : null,
            'AreaId'        => isset($data['area_id'])        ? intval($data['area_id']) : null,
            'CreatTime'     => isset($data['creattime'])      ? $data['creattime']      : date('Y-m-d H:i:s'),
            'CameraId'      => isset($data['camera_id'])      ? intval($data['camera_id']) : null,
            'DeviceId'      => isset($data['device_id'])      ? intval($data['device_id']) : null,
            'Status'        => '1',  // 1=报警
            'UrgencyDegree' => isset($data['urgency_degree']) ? $data['urgency_degree'] : '一般',
            'Description'   => isset($data['description'])    ? $data['description']    : null,
            'IsRead'        => 0,
            'Remark'        => isset($data['remark'])         ? $data['remark']         : null,
        );
        $this->db->insert('T_DetectResult', $row);
        return $this->db->insert_id();
    }

    // ─────────────────────────────────
    //  查询
    // ─────────────────────────────────

    /**
     * 分页查询报警事件列表
     */
    public function get_list($page = 1, $per_page = 20, $filters = array()) {
        $this->db->select('d.*, c.Name as CameraName, dev.Address as DeviceAddress');
        $this->db->from('T_DetectResult d');
        $this->db->join('T_Camera c', 'd.CameraId = c.Id', 'left');
        $this->db->join('T_Device dev', 'd.DeviceId = dev.Id', 'left');

        // 筛选
        if (!empty($filters['status'])) {
            $this->db->where('d.Status', $filters['status']);
        }
        if (!empty($filters['event_type'])) {
            $this->db->where('d.EventType', $filters['event_type']);
        }
        if (!empty($filters['area_id'])) {
            $this->db->where('d.AreaId', $filters['area_id']);
        }
        if (!empty($filters['urgency_degree'])) {
            $this->db->where('d.UrgencyDegree', $filters['urgency_degree']);
        }
        if (!empty($filters['device_id'])) {
            $this->db->where('d.DeviceId', $filters['device_id']);
        }
        if (!empty($filters['camera_id'])) {
            $this->db->where('d.CameraId', $filters['camera_id']);
        }
        // 时间范围
        if (!empty($filters['start_time'])) {
            $this->db->where('d.CreatTime >=', $filters['start_time']);
        }
        if (!empty($filters['end_time'])) {
            $this->db->where('d.CreatTime <=', $filters['end_time']);
        }

        // 总数
        $total = $this->db->count_all_results('', false);

        // 分页 + 排序
        $this->db->order_by('d.CreatTime', 'DESC');
        $this->db->limit($per_page, ($page - 1) * $per_page);
        $list = $this->db->get()->result_array();

        return array(
            'total'     => $total,
            'page'      => $page,
            'per_page'  => $per_page,
            'list'      => $list
        );
    }

    /**
     * 单条详情
     */
    public function get_detail($id) {
        $this->db->select('d.*, c.Name as CameraName, c.IP as CameraIP,
                          dev.Address as DeviceAddress, dev.MAC as DeviceMAC,
                          u.Name as OperateName, u2.Name as AuditName');
        $this->db->from('T_DetectResult d');
        $this->db->join('T_Camera c', 'd.CameraId = c.Id', 'left');
        $this->db->join('T_Device dev', 'd.DeviceId = dev.Id', 'left');
        $this->db->join('T_User u', 'd.OperateUserId = u.Id', 'left');
        $this->db->join('T_User u2', 'd.AuditUserId = u2.Id', 'left');
        $this->db->where('d.Id', $id);
        return $this->db->get()->row_array();
    }

    // ─────────────────────────────────
    //  更新
    // ─────────────────────────────────

    /**
     * 处理报警事件（工作人员操作）
     */
    public function process($id, $user_id, $data) {
        $row = array(
            'Status'          => '2',  // 2=待审核
            'OperateUserId'   => $user_id,
            'OperateTime'     => date('Y-m-d H:i:s'),
            'OperateResult'   => isset($data['operate_result']) ? $data['operate_result'] : null,
            'Description'     => isset($data['description'])   ? $data['description']   : null,
        );
        $this->db->where('Id', $id);
        return $this->db->update('T_DetectResult', $row);
    }

    /**
     * 审核报警事件（管理员操作）
     */
    public function audit($id, $user_id, $data) {
        $row = array(
            'Status'          => '3',  // 3=已审核
            'AuditUserId'     => $user_id,
            'AuditTime'       => date('Y-m-d H:i:s'),
            'UrgencyDegree'   => isset($data['urgency_degree']) ? $data['urgency_degree'] : null,
        );
        $this->db->where('Id', $id);
        return $this->db->update('T_DetectResult', $row);
    }

    // ─────────────────────────────────
    //  统计
    // ─────────────────────────────────

    /**
     * 按时间维度统计（日/周/月/年）
     */
    public function stats_by_time($granularity = 'day', $start = null, $end = null) {
        $format = ($granularity === 'month') ? '%Y-%m'    :
                  ($granularity === 'year')  ? '%Y'       : '%Y-%m-%d';
        $this->db->select("DATE_FORMAT(CreatTime, '$format') as time_label,
                           COUNT(*) as total,
                           SUM(CASE WHEN EventType='fire' THEN 1 ELSE 0 END) as fire_count,
                           SUM(CASE WHEN EventType='smoke' THEN 1 ELSE 0 END) as smoke_count");
        $this->db->from('T_DetectResult');
        if ($start) $this->db->where('CreatTime >=', $start);
        if ($end)   $this->db->where('CreatTime <=', $end);
        $this->db->group_by('time_label');
        $this->db->order_by('time_label', 'ASC');
        return $this->db->get()->result_array();
    }

    /**
     * 按区域维度统计
     */
    public function stats_by_area($start = null, $end = null) {
        $this->db->select('a.Name as area_name, COUNT(*) as total,
                           SUM(CASE WHEN d.EventType="fire" THEN 1 ELSE 0 END) as fire_count,
                           SUM(CASE WHEN d.EventType="smoke" THEN 1 ELSE 0 END) as smoke_count');
        $this->db->from('T_DetectResult d');
        $this->db->join('T_Area a', 'd.AreaId = a.Id', 'left');
        if ($start) $this->db->where('d.CreatTime >=', $start);
        if ($end)   $this->db->where('d.CreatTime <=', $end);
        $this->db->group_by('d.AreaId');
        $this->db->order_by('total', 'DESC');
        return $this->db->get()->result_array();
    }

    /**
     * 指定时间段内事件总量/火焰量/烟雾量汇总
     */
    public function summary($start = null, $end = null) {
        $this->db->select('COUNT(*) as total,
                           SUM(CASE WHEN EventType="fire" THEN 1 ELSE 0 END) as fire_count,
                           SUM(CASE WHEN EventType="smoke" THEN 1 ELSE 0 END) as smoke_count,
                           SUM(CASE WHEN Status="1" THEN 1 ELSE 0 END) as pending_count,
                           SUM(CASE WHEN Status="3" THEN 1 ELSE 0 END) as reviewed_count');
        $this->db->from('T_DetectResult');
        if ($start) $this->db->where('CreatTime >=', $start);
        if ($end)   $this->db->where('CreatTime <=', $end);
        return $this->db->get()->row_array();
    }
}
