<?php
/**
 * 用户模型 — 用户查询、密码管理、角色关联
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段2 用户信息库/JWT认证支撑
 */
defined('BASEPATH') OR exit('No direct script access allowed');
class User_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

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
}
