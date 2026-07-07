<?php
/**
 * 数据字典模型 — T_Dictionary CRUD
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 数据字典管理数据层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Dictionary_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    /**
     * 字典列表（可选按Key过滤）
     */
    public function get_list($dict_type = null) {
        if ($dict_type) {
            $this->db->where('`Key`', $dict_type);
        }
        $this->db->order_by('`Key`', 'ASC');
        $this->db->order_by('Id', 'ASC');
        return $this->db->get('T_Dictionary')->result_array();
    }

    /**
     * 获取所有字典类型（去重Key）
     */
    public function get_types() {
        $this->db->distinct();
        $this->db->select('`Key`');
        $this->db->order_by('`Key`', 'ASC');
        $result = $this->db->get('T_Dictionary')->result_array();
        $types = array();
        foreach ($result as $row) {
            $types[] = $row['Key'];
        }
        return $types;
    }

    /**
     * 单条详情
     */
    public function get_detail($id) {
        return $this->db->get_where('T_Dictionary', array('Id' => $id))->row_array();
    }

    /**
     * 创建
     */
    public function create($data) {
        $row = array(
            '`Key`'  => isset($data['key']) ? $data['key'] : null,
            '`Value`' => isset($data['value']) ? $data['value'] : null,
            'Remark'  => isset($data['remark']) ? $data['remark'] : null,
        );
        $this->db->insert('T_Dictionary', $row);
        return $this->db->insert_id();
    }

    /**
     * 更新
     */
    public function update($id, $data) {
        $row = array();
        if (isset($data['key']))    $row['`Key`']   = $data['key'];
        if (isset($data['value']))  $row['`Value`'] = $data['value'];
        if (isset($data['remark'])) $row['Remark']  = $data['remark'];
        if (empty($row)) return false;
        $this->db->where('Id', $id);
        return $this->db->update('T_Dictionary', $row);
    }

    /**
     * 删除
     */
    public function delete($id) {
        $this->db->where('Id', $id);
        return $this->db->delete('T_Dictionary');
    }
}
