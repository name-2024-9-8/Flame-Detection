<?php
/**
 * 用户模型 — 用户查询、密码管理、角色关联
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-16  融合修复: 新增用户CRUD方法
 * @task      人员B — 阶段2 用户信息库/JWT认证支撑
 */
defined('BASEPATH') OR exit('No direct script access allowed');
class User_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    // ── 原有方法 ──

    /**
     * 根据账号查询用户
     */
    public function get_by_account($account) {
        return $this->db->get_where('T_User', array('Account' => $account))
                        ->row();
    }

    /**
     * 根据 ID 查询用户
     */
    public function get_by_id($id) {
        return $this->db->get_where('T_User', array('Id' => $id))
                        ->row();
    }

    /**
     * 查询用户及其角色
     */
    public function get_with_roles($id) {
        $this->db->select('u.*, ur.RoleId, r.Name as RoleName');
        $this->db->from('T_User u');
        $this->db->join('T_UserRole ur', 'u.Id = ur.UserId', 'left');
        $this->db->join('T_Role r',    'ur.RoleId = r.Id', 'left');
        $this->db->where('u.Id', $id);
        return $this->db->get()->result();
    }

    /**
     * 更新密码（hash 加密）
     */
    public function update_password($id, $password) {
        $hash = password_hash($password, PASSWORD_DEFAULT);
        $this->db->where('Id', $id)
                 ->update('T_User', array('Password' => $hash));
    }

    // ── 新增CRUD方法 ──

    /**
     * 分页查询用户列表（含角色名/部门名）
     */
    public function get_user_list($page = 1, $per_page = 20, $filters = array()) {
        $this->db->select('u.*, r.Name as RoleName, b.Name as BranchName');
        $this->db->from('T_User u');
        $this->db->join('T_UserRole ur', 'u.Id = ur.UserId', 'left');
        $this->db->join('T_Role r',     'ur.RoleId = r.Id', 'left');
        $this->db->join('T_Branch b',   'u.BranchId = b.Id', 'left');
        $this->db->where('u.IsDelete', 0);

        if (!empty($filters['username'])) {
            $this->db->like('u.Account', $filters['username']);
        }
        if (!empty($filters['real_name'])) {
            $this->db->like('u.Name', $filters['real_name']);
        }
        if (!empty($filters['user_type']) && $filters['user_type'] == '1') {
            // 管理员: RoleName=超级管理员
            $this->db->where('r.Name', '超级管理员');
        }

        $total = $this->db->count_all_results('', false);
        $this->db->order_by('u.Id', 'ASC');
        $this->db->limit($per_page, ($page - 1) * $per_page);
        $list = $this->db->get()->result_array();

        return array('total' => $total, 'page' => $page, 'per_page' => $per_page, 'list' => $list);
    }

    /**
     * 根据ID获取用户详情（含角色/部门）
     */
    public function get_user_detail($id) {
        $this->db->select('u.*, ur.RoleId, r.Name as RoleName, b.Name as BranchName');
        $this->db->from('T_User u');
        $this->db->join('T_UserRole ur', 'u.Id = ur.UserId', 'left');
        $this->db->join('T_Role r',     'ur.RoleId = r.Id', 'left');
        $this->db->join('T_Branch b',   'u.BranchId = b.Id', 'left');
        $this->db->where('u.Id', $id);
        return $this->db->get()->row_array();
    }

    /**
     * 创建用户（含角色绑定）
     */
    public function create_user($data) {
        $row = array(
            'Account'    => isset($data['account']) ? $data['account'] : null,
            'Name'       => isset($data['name']) ? $data['name'] : null,
            'Password'   => isset($data['password'])
                            ? password_hash($data['password'], PASSWORD_DEFAULT)
                            : password_hash('123456', PASSWORD_DEFAULT),
            'Email'      => isset($data['email']) ? $data['email'] : null,
            'Phone'      => isset($data['phone']) ? $data['phone'] : null,
            'AreaId'     => isset($data['area_id']) ? intval($data['area_id']) : null,
            'BranchId'   => isset($data['branch_id']) ? intval($data['branch_id']) : null,
            'CreateTime' => date('Y-m-d H:i:s'),
            'CreateBy'   => isset($data['create_by']) ? intval($data['create_by']) : null,
            'IsDelete'   => 0,
            'Remark'     => isset($data['remark']) ? $data['remark'] : null,
        );
        $this->db->insert('T_User', $row);
        $user_id = $this->db->insert_id();

        // 绑定角色
        if (isset($data['role_id']) && $data['role_id']) {
            $this->db->insert('T_UserRole', array(
                'UserId' => $user_id,
                'RoleId' => intval($data['role_id']),
            ));
        }
        return $user_id;
    }

    /**
     * 更新用户信息
     */
    public function update_user($id, $data) {
        $row = array();
        if (isset($data['name']))      $row['Name']     = $data['name'];
        if (isset($data['email']))     $row['Email']    = $data['email'];
        if (isset($data['phone']))     $row['Phone']    = $data['phone'];
        if (isset($data['area_id']))   $row['AreaId']   = intval($data['area_id']);
        if (isset($data['branch_id'])) $row['BranchId'] = intval($data['branch_id']);
        if (isset($data['remark']))    $row['Remark']   = $data['remark'];
        if (isset($data['password']) && $data['password']) {
            $row['Password'] = password_hash($data['password'], PASSWORD_DEFAULT);
        }
        if (!empty($row)) {
            $this->db->where('Id', $id)->update('T_User', $row);
        }

        // 更新角色
        if (isset($data['role_id'])) {
            $this->db->where('UserId', $id)->delete('T_UserRole');
            if ($data['role_id']) {
                $this->db->insert('T_UserRole', array(
                    'UserId' => $id,
                    'RoleId' => intval($data['role_id']),
                ));
            }
        }
        return true;
    }

    /**
     * 软删除用户
     */
    public function delete_user($id) {
        // 不允许删除管理员
        $user = $this->get_by_id($id);
        if (!$user || $user->Account === 'admin') {
            return false;
        }
        $this->db->where('Id', $id)->update('T_User', array('IsDelete' => 1));
        return true;
    }
}
