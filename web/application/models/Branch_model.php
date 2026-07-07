<?php
/**
 * 部门模型 — T_Branch CRUD
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 部门管理数据层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Branch_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    /**
     * 部门列表（含上级部门名和负责人名）
     */
    public function get_list() {
        $this->db->select('b.*, u.Name as LeaderName, p.Name as ParentName');
        $this->db->from('T_Branch b');
        $this->db->join('T_User u', 'b.LeaderId = u.Id', 'left');
        $this->db->join('T_Branch p', 'b.ParentId = p.Id', 'left');
        $this->db->order_by('b.Id', 'ASC');
        return $this->db->get()->result_array();
    }

    /**
     * 部门树（递归嵌套，用于下拉选择父部门）
     */
    public function get_tree() {
        $list = $this->get_list();
        return $this->_build_tree($list, 0);
    }

    private function _build_tree(&$items, $parent_id = 0) {
        $tree = array();
        foreach ($items as &$item) {
            if ($item['ParentId'] == $parent_id) {
                $children = $this->_build_tree($items, $item['Id']);
                if ($children) {
                    $item['children'] = $children;
                }
                $tree[] = $item;
            }
        }
        return $tree;
    }

    /**
     * 单条详情
     */
    public function get_detail($id) {
        $this->db->select('b.*, u.Name as LeaderName, p.Name as ParentName');
        $this->db->from('T_Branch b');
        $this->db->join('T_User u', 'b.LeaderId = u.Id', 'left');
        $this->db->join('T_Branch p', 'b.ParentId = p.Id', 'left');
        $this->db->where('b.Id', $id);
        return $this->db->get()->row_array();
    }

    /**
     * 创建部门
     */
    public function create($data) {
        $row = array(
            'Name'       => isset($data['name']) ? $data['name'] : null,
            'ParentId'   => isset($data['parent_id']) ? intval($data['parent_id']) : 0,
            'LeaderId'   => isset($data['leader_id']) ? intval($data['leader_id']) : null,
            'CreateTime' => date('Y-m-d H:i:s'),
            'CreateBy'   => isset($data['create_by']) ? intval($data['create_by']) : null,
            'Remark'     => isset($data['remark']) ? $data['remark'] : null,
        );
        $this->db->insert('T_Branch', $row);
        return $this->db->insert_id();
    }

    /**
     * 更新部门
     */
    public function update($id, $data) {
        $allowed = array('Name', 'ParentId', 'LeaderId', 'Remark');
        $map = array(
            'name' => 'Name', 'parent_id' => 'ParentId',
            'leader_id' => 'LeaderId', 'remark' => 'Remark',
        );
        $row = array();
        foreach ($map as $field => $col) {
            if (isset($data[$field])) {
                $row[$col] = $data[$field];
            }
        }
        if (empty($row)) return false;
        $this->db->where('Id', $id);
        return $this->db->update('T_Branch', $row);
    }

    /**
     * 删除部门（检查无子部门和无用户后才删除）
     */
    public function delete($id) {
        $children = $this->db->where('ParentId', $id)->count_all_results('T_Branch');
        if ($children > 0) return false;
        $users = $this->db->where('BranchId', $id)->count_all_results('T_User');
        if ($users > 0) return false;
        $this->db->where('Id', $id);
        return $this->db->delete('T_Branch');
    }
}
