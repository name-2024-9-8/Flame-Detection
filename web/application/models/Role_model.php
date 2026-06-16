<?php
/**
 * 角色模型 — T_Role + T_Authority CRUD
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 角色管理数据层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Role_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    /**
     * 角色列表
     */
    public function get_list() {
        $this->db->where('IsDelete', 0);
        $list = $this->db->get('T_Role')->result_array();

        // 关联权限数
        foreach ($list as &$item) {
            $item['authority_count'] = $this->db
                ->where('RoleId', $item['Id'])
                ->count_all_results('T_Authority');
            $item['user_count'] = $this->db
                ->where('RoleId', $item['Id'])
                ->count_all_results('T_UserRole');
        }
        return $list;
    }

    /**
     * 单条详情（含权限列表）
     */
    public function get_detail($id) {
        $role = $this->db->get_where('T_Role', array('Id' => $id))->row_array();
        if ($role) {
            $role['authorities'] = $this->db
                ->where('RoleId', $id)
                ->get('T_Authority')->result_array();
        }
        return $role;
    }

    /**
     * 创建角色（含权限）
     */
    public function create($data) {
        $row = array(
            'Name'        => isset($data['name']) ? $data['name'] : null,
            'Description' => isset($data['description']) ? $data['description'] : null,
            'IsDelete'    => 0,
        );
        $this->db->insert('T_Role', $row);
        $role_id = $this->db->insert_id();

        // 批量插入权限
        if (isset($data['authorities']) && is_array($data['authorities'])) {
            foreach ($data['authorities'] as $auth) {
                $this->db->insert('T_Authority', array(
                    'RoleId'    => $role_id,
                    'Authority' => is_string($auth) ? $auth : (isset($auth['authority']) ? $auth['authority'] : ''),
                ));
            }
        }
        return $role_id;
    }

    /**
     * 更新角色名称/描述 + 重建权限
     */
    public function update($id, $data) {
        $row = array();
        if (isset($data['name']))        $row['Name']        = $data['name'];
        if (isset($data['description'])) $row['Description'] = $data['description'];
        if (!empty($row)) {
            $this->db->where('Id', $id)->update('T_Role', $row);
        }

        // 重建权限：先删后插
        if (isset($data['authorities']) && is_array($data['authorities'])) {
            $this->db->where('RoleId', $id)->delete('T_Authority');
            foreach ($data['authorities'] as $auth) {
                $this->db->insert('T_Authority', array(
                    'RoleId'    => $id,
                    'Authority' => is_string($auth) ? $auth : (isset($auth['authority']) ? $auth['authority'] : ''),
                ));
            }
        }
        return true;
    }

    /**
     * 软删除
     */
    public function delete($id) {
        $this->db->where('Id', $id)->update('T_Role', array('IsDelete' => 1));
        return true;
    }
}
