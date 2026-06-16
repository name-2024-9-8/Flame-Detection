<?php
/**
 * Log 日志查询控制器 — 访问日志 / 操作日志查询
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-12
 * @modified  2026-06-12
 * @task      王永林 — 融合补充：日志查询API
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Log extends REST_Controller {

    public function __construct() {
        parent::__construct();
    }

    // ─────────────────────────────────
    //  GET /api/logs/access — 访问日志
    // ─────────────────────────────────

    public function access() {
        $this->require_auth();
        $this->log_access();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(200, max(1, intval($this->input->get('per_page', true)) ?: 20));

        // COUNT
        $cnt_row = $this->db->query(
            'SELECT COUNT(*) as cnt FROM T_AccessLog a LEFT JOIN T_User u ON a.UserId = u.Id'
        )->row();
        $total = $cnt_row ? $cnt_row->cnt : 0;

        // 分页 + 联表用户姓名
        $list = $this->db->query(
            'SELECT a.*, u.Name as UserName FROM T_AccessLog a
             LEFT JOIN T_User u ON a.UserId = u.Id
             ORDER BY a.CreateTime DESC
             LIMIT ' . intval($per_page) . ' OFFSET ' . intval(($page - 1) * $per_page)
        )->result_array();

        $items = array();
        foreach ($list as $item) {
            $items[] = array(
                'id'              => intval($item['Id']),
                'user_id'         => $item['UserId'] ? intval($item['UserId']) : null,
                'username'        => $item['UserName'] ?: '匿名',
                'ip_address'      => $item['IP'],
                'request_method'  => $item['Method'],
                'request_url'     => $item['Url'],
                'user_agent'      => $item['UserAgent'],
                'request_params'  => $item['Remark'],
                'response_code'   => null,
                'duration_ms'     => null,
                'created_at'      => $item['CreateTime'],
            );
        }

        $this->success(array(
            'items'     => $items,
            'total'     => intval($total),
            'page'      => $page,
            'per_page'  => $per_page,
            'pages'     => ceil($total / $per_page),
        ));
    }

    // ─────────────────────────────────
    //  GET /api/logs/operation — 操作日志
    // ─────────────────────────────────

    public function operation() {
        $this->require_auth();

        $page     = max(1, intval($this->input->get('page', true)) ?: 1);
        $per_page = min(200, max(1, intval($this->input->get('per_page', true)) ?: 20));

        // COUNT
        $total = $this->db->query(
            'SELECT COUNT(*) as cnt FROM T_OperateLog'
        )->row()->cnt;

        // 分页 + 联表用户姓名
        $list = $this->db
            ->select('o.*, u.Name as UserName')
            ->from('T_OperateLog o')
            ->join('T_User u', 'o.UserId = u.Id', 'left')
            ->order_by('o.CreateTime', 'DESC')
            ->limit($per_page, ($page - 1) * $per_page)
            ->get()->result_array();

        $items = array();
        foreach ($list as $item) {
            $items[] = array(
                'id'               => intval($item['Id']),
                'user_id'          => $item['UserId'] ? intval($item['UserId']) : null,
                'username'         => $item['UserName'] ?: '未知',
                'operation_type'   => $item['Type'],
                'operation_module' => $item['MenuName'],
                'operation_desc'   => $item['Type'] . ' — ' . $item['MenuName'],
                'target_table'     => $item['MenuName'],
                'target_id'        => null,
                'old_data'         => $item['ContentOld'],
                'new_data'         => $item['ContentNew'],
                'ip_address'       => null,
                'created_at'       => $item['CreateTime'],
            );
        }

        $this->success(array(
            'items'     => $items,
            'total'     => intval($total),
            'page'      => $page,
            'per_page'  => $per_page,
            'pages'     => ceil($total / $per_page),
        ));
    }
}
