<?php
/**
 * Detect 边缘检测数据接入控制器 — 接收人员A边缘端报警/视频/心跳/故障上报
 *
 * URL 路由:
 *   POST /api/detect/alarm      — 报警事件上报 (JSON)
 *   POST /api/detect/upload     — 视频文件上传 (multipart/form-data)
 *   POST /api/device/heartbeat  — 设备心跳保活
 *   POST /api/device/error      — 设备故障上报
 *
 * @author    王永林（集成人员A边缘端API）
 * @studentId 12303070414
 * @created   2026-06-16
 * @modified  2026-06-16
 * @task      M7: A+B+C 三方融合 — 边缘设备数据接入层
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Detect extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Alarm_model');
    }

    // ─────────────────────────────────────────────
    //  POST /api/detect/alarm — 接收A端报警事件
    // ─────────────────────────────────────────────

    public function alarm() {
        // 边缘设备用 device_mac 校验身份（不需要 JWT）
        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!$data || empty($data)) {
            $data = $this->input->post();
            if (!$data) { $data = $_POST; }
        }
        if (empty($data)) {
            $this->error('缺少报警数据');
        }

        // ── 设备身份校验 ──
        if (empty($data['device_id'])) {
            $this->error('缺少设备ID（device_id）');
        }
        $device = $this->db->get_where('T_Device', array('Id' => $data['device_id']))->row();
        if (!$device) {
            $this->error('设备不存在（device_id=' . $data['device_id'] . '），请先在管理后台注册设备', $this->http_forbidden);
        }

        // ── 字段映射: A的AlarmEvent → B的T_DetectResult ──
        // 处理 picture_base64: 解码并保存为文件，数据库只存路径
        $picture_path = null;
        if (!empty($data['picture_base64'])) {
            $picture_path = $this->_save_base64_image(
                $data['picture_base64'],
                isset($data['camera_id']) ? $data['camera_id'] : 0,
                isset($data['timestamp']) ? $data['timestamp'] : date('Ymd_His')
            );
        }

        // 时间戳转换: A端ISO 8601 → MySQL datetime
        $creattime = date('Y-m-d H:i:s');
        if (!empty($data['timestamp'])) {
            $ts = strtotime($data['timestamp']);
            if ($ts) { $creattime = date('Y-m-d H:i:s', $ts); }
        }

        // 构建 B 端数据库行（使用 Alarm_model.create 相同的字段名）
        $row = array(
            'event_type'     => isset($data['event_type']) ? $data['event_type'] : 'fire',
            'confidence'     => isset($data['confidence']) ? floatval($data['confidence']) : null,
            'lng'            => isset($data['longitude'])  ? $data['longitude']  : (isset($data['lng']) ? $data['lng'] : null),
            'lat'            => isset($data['latitude'])   ? $data['latitude']   : (isset($data['lat']) ? $data['lat'] : null),
            'location'       => isset($data['location'])   ? $data['location']   : null,
            'picture'        => $picture_path,  // 文件路径（非base64）
            'video_url'      => isset($data['video_url'])  ? $data['video_url']  : null,
            'area_id'        => isset($data['area_id'])    ? intval($data['area_id']) : null,
            'camera_id'      => isset($data['camera_id'])  ? intval($data['camera_id']) : null,
            'device_id'      => intval($data['device_id']),
            'urgency_degree' => isset($data['urgency_degree']) ? $data['urgency_degree'] : '一般',
            'description'    => isset($data['description']) ? $data['description'] : null,
            'remark'         => isset($data['remark'])      ? $data['remark']      : null,
            'creattime'      => $creattime,  // 使用A端上报的检测时间
        );

        $id = $this->Alarm_model->create($row);

        // 更新设备最后通信时间
        $this->db->where('Id', $data['device_id'])
                 ->update('T_Device', array('LastConnectTime' => date('Y-m-d H:i:s')));

        // 记录访问日志
        $this->log_access(null, '边缘设备#' . $data['device_id'] . ' 上报报警事件#' . $id);

        // 非关键路径：发送通知
        try {
            $this->load->library('Email_lib');
            $this->email_lib->send_alarm_notify($id, $row);
        } catch (Exception $e) {
            log_message('error', 'Alarm notify failed: ' . $e->getMessage());
        }

        $this->success(array('event_id' => $id, 'picture_path' => $picture_path), '报警事件接收成功', $this->http_created);
    }

    // ─────────────────────────────────────────────
    //  POST /api/detect/upload — 接收A端视频上传
    // ─────────────────────────────────────────────

    public function upload() {
        // 检查文件上传
        if (empty($_FILES['file'])) {
            $this->error('缺少上传文件（file字段）');
        }

        $file = $_FILES['file'];
        $camera_id = $this->input->post('camera_id') ?: 0;
        $timestamp = $this->input->post('timestamp') ?: date('Ymd_His');

        // 验证文件扩展名（PHP 5.6 兼容，避免依赖 finfo 扩展）
        $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
        $allowed_exts = array('mp4', 'avi', 'mov', 'mkv', 'webm');
        if (!in_array($ext, $allowed_exts)) {
            $this->error('不支持的文件类型: .' . $ext . '，仅支持常见视频格式');
        }

        // 限制文件大小 (100MB)
        $max_size = 100 * 1024 * 1024;
        if ($file['size'] > $max_size) {
            $this->error('文件过大，最大支持100MB');
        }

        // 保存到 uploads/videos/ 目录
        $upload_dir = FCPATH . 'uploads/videos/';
        if (!is_dir($upload_dir)) {
            mkdir($upload_dir, 0755, true);
        }

        // 生成唯一文件名
        $ext = pathinfo($file['name'], PATHINFO_EXTENSION) ?: 'mp4';
        $safe_ts = preg_replace('/[^0-9a-zA-Z_-]/', '_', $timestamp);
        $random = sprintf('%04x', mt_rand(0, 0xffff));
        $filename = sprintf('alarm_c%d_%s_%s.%s', $camera_id, $safe_ts, $random, $ext);
        $dest_path = $upload_dir . $filename;

        if (!move_uploaded_file($file['tmp_name'], $dest_path)) {
            $this->error('文件保存失败', $this->http_server_error);
        }

        // 构建可访问的URL（通过PHP服务器或反向代理）
        $base_url = rtrim(config_item('base_url'), '/') ?: ('http://' . $_SERVER['HTTP_HOST']);
        $video_url = $base_url . '/uploads/videos/' . $filename;

        $this->success(array(
            'url'       => $video_url,
            'file_path' => $dest_path,
            'file_name' => $filename,
            'file_size' => $file['size'],
        ), '视频上传成功');
    }

    // ─────────────────────────────────────────────
    //  POST /api/device/heartbeat — 接收设备心跳
    // ─────────────────────────────────────────────

    public function heartbeat() {
        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!$data || empty($data)) {
            $data = $this->input->post();
            if (!$data) { $data = $_POST; }
        }
        if (empty($data)) {
            $this->error('缺少心跳数据');
        }
        if (empty($data['device_id'])) {
            $this->error('缺少设备ID（device_id）');
        }

        $device = $this->db->get_where('T_Device', array('Id' => $data['device_id']))->row();
        if (!$device) {
            $this->error('设备不存在', $this->http_not_found);
        }

        // 更新设备最后通信时间
        $update = array('LastConnectTime' => date('Y-m-d H:i:s'));
        $this->db->where('Id', $data['device_id'])->update('T_Device', $update);

        $this->success(array(
            'device_id'  => intval($data['device_id']),
            'server_time' => date('Y-m-d H:i:s'),
            'status'     => 'ok',
        ), '心跳接收成功');
    }

    // ─────────────────────────────────────────────
    //  POST /api/device/error — 接收设备故障上报
    // ─────────────────────────────────────────────

    public function device_error() {
        $raw = file_get_contents('php://input');
        $data = json_decode($raw, true);
        if (!$data || empty($data)) {
            $data = $this->input->post();
            if (!$data) { $data = $_POST; }
        }
        if (empty($data)) {
            $this->error('缺少故障数据');
        }
        if (empty($data['device_id'])) {
            $this->error('缺少设备ID（device_id）');
        }

        // 插入故障记录到 T_DeviceError
        $row = array(
            'DeviceId'   => intval($data['device_id']),
            'MAC'        => isset($data['mac']) ? $data['mac'] : null,
            'CreateTime' => date('Y-m-d H:i:s'),
            'ErrorCode'  => isset($data['error_code']) ? $data['error_code'] : 'unknown',
            'ErrorMsg'   => isset($data['error_msg'])  ? $data['error_msg']  : null,
            'Remark'     => isset($data['remark'])     ? $data['remark']     : null,
        );
        $this->db->insert('T_DeviceError', $row);
        $error_id = $this->db->insert_id();

        // 记录日志
        $err_info = isset($data['error_msg']) ? $data['error_msg'] : (isset($data['error_code']) ? $data['error_code'] : 'unknown');
        $this->log_access(null, '边缘设备#' . $data['device_id'] . ' 上报故障#' . $error_id . ': ' . $err_info);

        $this->success(array('error_id' => $error_id), '故障上报接收成功', $this->http_created);
    }

    // ─────────────────────────────────────────────
    //  辅助: 保存 base64 图片为文件
    // ─────────────────────────────────────────────

    private function _save_base64_image($base64_str, $camera_id, $timestamp) {
        // 移除可能的 data:image/jpeg;base64, 前缀
        if (strpos($base64_str, 'base64,') !== false) {
            $base64_str = substr($base64_str, strpos($base64_str, 'base64,') + 7);
        }

        $image_data = base64_decode($base64_str, true);
        if ($image_data === false) {
            return null;
        }

        $upload_dir = FCPATH . 'uploads/pictures/';
        if (!is_dir($upload_dir)) {
            mkdir($upload_dir, 0755, true);
        }

        $safe_ts = preg_replace('/[^0-9a-zA-Z_-]/', '_', $timestamp);
        $filename = sprintf('alarm_c%d_%s_%s.jpg', $camera_id, $safe_ts, sprintf('%04x', mt_rand(0, 0xffff)));
        $dest_path = $upload_dir . $filename;

        if (file_put_contents($dest_path, $image_data)) {
            $base_url = rtrim(config_item('base_url'), '/') ?: ('http://' . $_SERVER['HTTP_HOST']);
            return $base_url . '/uploads/pictures/' . $filename;
        }
        return null;
    }
}
