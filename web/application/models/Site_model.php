<?php
/**
 * 系统配置模型 — T_Site 读写
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: 融合修复 — 系统配置管理数据层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Site_model extends CI_Model {

    public function __construct() {
        parent::__construct();
        $this->load->database();
    }

    /**
     * 获取系统配置（第一行）
     */
    public function get_config() {
        $site = $this->db->get('T_Site')->row_array();
        if (!$site) {
            // 返回默认值
            return array(
                'thresh'          => 0.6,
                'width'           => 640,
                'height'          => 480,
                'video_times'     => 5,
                'heartBeat'       => 24,
                'exception_times' => 10,
            );
        }
        return $site;
    }

    /**
     * 更新系统配置
     */
    public function update_config($data) {
        $allowed = array('thresh', 'width', 'height', 'video_times', 'heartBeat', 'exception_times');
        $row = array();
        foreach ($allowed as $col) {
            if (isset($data[$col])) {
                $row[$col] = $data[$col];
            }
        }
        if (empty($row)) {
            return false;
        }

        $exists = $this->db->get('T_Site')->row();
        if ($exists) {
            $this->db->where('Id', $exists->Id);
            return $this->db->update('T_Site', $row);
        } else {
            return $this->db->insert('T_Site', $row);
        }
    }
}
