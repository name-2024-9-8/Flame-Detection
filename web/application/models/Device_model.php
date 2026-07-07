<?php
/**
 * 设备模型 — AI分析盒 和 摄像头 CRUD
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 阶段3 核心业务后端：设备信息管理
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Device_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    // ─────────────────────────────────
    //  AI 分析盒
    // ─────────────────────────────────

    public function get_device_list($page = 1, $per_page = 20, $filters = array()) {
        $this->db->from('T_Device');
        if (!empty($filters['area_id'])) {
            $this->db->where('AreaId', $filters['area_id']);
        }
        if (!empty($filters['keyword'])) {
            $this->db->group_start()
                     ->like('MAC', $filters['keyword'])
                     ->or_like('Address', $filters['keyword'])
                     ->or_like('ModelInfo', $filters['keyword'])
                     ->group_end();
        }

        $total = $this->db->count_all_results('', false);
        $this->db->order_by('Id', 'DESC');
        $this->db->limit($per_page, ($page - 1) * $per_page);
        $list = $this->db->get()->result_array();

        // 关联摄像头数量
        foreach ($list as &$item) {
            $item['camera_count'] = $this->db->where('DeviceId', $item['Id'])
                                             ->count_all_results('T_Camera');
        }

        return array('total' => $total, 'page' => $page, 'per_page' => $per_page, 'list' => $list);
    }

    public function get_device_detail($id) {
        $device = $this->db->get_where('T_Device', array('Id' => $id))->row_array();
        if ($device) {
            $device['cameras'] = $this->db->get_where('T_Camera', array('DeviceId' => $id))->result_array();
        }
        return $device;
    }

    public function create_device($data) {
        $row = array(
            'MAC'             => isset($data['mac']) ? $data['mac'] : null,
            'Longitude'       => isset($data['lng']) ? $data['lng'] : null,
            'Latitude'        => isset($data['lat']) ? $data['lat'] : null,
            'Address'         => isset($data['address']) ? $data['address'] : null,
            'AreaId'          => isset($data['area_id']) ? intval($data['area_id']) : null,
            'ModelPerson'     => isset($data['model_person']) ? $data['model_person'] : null,
            'ModelInfo'       => isset($data['model_info']) ? $data['model_info'] : null,
            'Maintainer'      => isset($data['maintainer']) ? $data['maintainer'] : null,
            'CreateTime'      => date('Y-m-d H:i:s'),
            'StructuralInfo'  => isset($data['structural_info']) ? $data['structural_info'] : null,
            'DetailInfo'      => isset($data['detail_info']) ? $data['detail_info'] : null,
            'Remark'          => isset($data['remark']) ? $data['remark'] : null,
        );
        $this->db->insert('T_Device', $row);
        return $this->db->insert_id();
    }

    public function update_device($id, $data) {
        $allowed = array('Longitude','Latitude','Address','AreaId','ModelPerson','ModelInfo',
                         'Maintainer','StructuralInfo','DetailInfo','Remark');
        $row = array();
        foreach ($allowed as $key) {
            $map = array(
                'Longitude'=>'lng', 'Latitude'=>'lat', 'Address'=>'address', 'AreaId'=>'area_id',
                'ModelPerson'=>'model_person', 'ModelInfo'=>'model_info', 'Maintainer'=>'maintainer',
                'StructuralInfo'=>'structural_info', 'DetailInfo'=>'detail_info', 'Remark'=>'remark'
            );
            $field = isset($map[$key]) ? $map[$key] : strtolower($key);
            if (isset($data[$field])) {
                $row[$key] = $data[$field];
            }
        }
        if (empty($row)) return false;
        $this->db->where('Id', $id);
        return $this->db->update('T_Device', $row);
    }

    public function delete_device($id) {
        // 先解除摄像头绑定
        $this->db->where('DeviceId', $id)->update('T_Camera', array('DeviceId' => null));
        $this->db->where('Id', $id);
        return $this->db->delete('T_Device');
    }

    // ─────────────────────────────────
    //  摄像头
    // ─────────────────────────────────

    public function get_camera_list($page = 1, $per_page = 20, $filters = array()) {
        $this->db->select('c.*, dev.Address as DeviceAddress, a.Name as AreaName');
        $this->db->from('T_Camera c');
        $this->db->join('T_Device dev', 'c.DeviceId = dev.Id', 'left');
        $this->db->join('T_Area a', 'c.AreaId = a.Id', 'left');

        if (!empty($filters['device_id'])) {
            $this->db->where('c.DeviceId', $filters['device_id']);
        }
        if (!empty($filters['area_id'])) {
            $this->db->where('c.AreaId', $filters['area_id']);
        }
        if (!empty($filters['keyword'])) {
            $this->db->group_start()
                     ->like('c.Name', $filters['keyword'])
                     ->or_like('c.IP', $filters['keyword'])
                     ->group_end();
        }

        $total = $this->db->count_all_results('', false);
        $this->db->order_by('c.Id', 'DESC');
        $this->db->limit($per_page, ($page - 1) * $per_page);
        $list = $this->db->get()->result_array();

        return array('total' => $total, 'page' => $page, 'per_page' => $per_page, 'list' => $list);
    }

    public function get_camera_detail($id) {
        $this->db->select('c.*, dev.Address as DeviceAddress, a.Name as AreaName');
        $this->db->from('T_Camera c');
        $this->db->join('T_Device dev', 'c.DeviceId = dev.Id', 'left');
        $this->db->join('T_Area a', 'c.AreaId = a.Id', 'left');
        $this->db->where('c.Id', $id);
        return $this->db->get()->row_array();
    }

    public function create_camera($data) {
        $row = array(
            'IP'          => isset($data['ip']) ? $data['ip'] : null,
            'MAC'         => isset($data['mac']) ? $data['mac'] : null,
            'CameraUrl'   => isset($data['camera_url']) ? $data['camera_url'] : null,
            'Name'        => isset($data['name']) ? $data['name'] : null,
            'Longitude'   => isset($data['lng']) ? $data['lng'] : null,
            'Latitude'    => isset($data['lat']) ? $data['lat'] : null,
            'AreaId'      => isset($data['area_id']) ? intval($data['area_id']) : null,
            'Type'        => isset($data['type']) ? $data['type'] : null,
            'InstallTime' => isset($data['install_time']) ? $data['install_time'] : date('Y-m-d H:i:s'),
            'BandWidth'   => isset($data['bandwidth']) ? floatval($data['bandwidth']) : null,
            'Maintainer'  => isset($data['maintainer']) ? $data['maintainer'] : null,
            'DeviceId'    => isset($data['device_id']) ? intval($data['device_id']) : null,
            'Remark'      => isset($data['remark']) ? $data['remark'] : null,
        );
        $this->db->insert('T_Camera', $row);
        return $this->db->insert_id();
    }

    public function update_camera($id, $data) {
        $allowed = array('IP'=>'ip','Name'=>'name','Longitude'=>'lng','Latitude'=>'lat',
                         'AreaId'=>'area_id','Type'=>'type','Maintainer'=>'maintainer',
                         'DeviceId'=>'device_id','CameraUrl'=>'camera_url','Remark'=>'remark');
        $row = array();
        foreach ($allowed as $col => $field) {
            if (isset($data[$field])) {
                $row[$col] = $data[$field];
            }
        }
        if (empty($row)) return false;
        $this->db->where('Id', $id);
        return $this->db->update('T_Camera', $row);
    }

    public function delete_camera($id) {
        $this->db->where('Id', $id);
        return $this->db->delete('T_Camera');
    }
}
