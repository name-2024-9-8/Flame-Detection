<?php
/**
 * Email_lib 邮件通知库 — SMTP 邮件告警 / 微信推送 / 短信通知（预留）
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段3 核心业务后端：快速汇报模块（SMTP/微信/短信）
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class Email_lib {

    protected $CI;

    // SMTP 配置（部署时修改为真实值）
    protected $smtp_host    = 'smtp.qq.com';
    protected $smtp_port    = 587;
    protected $smtp_user    = '';
    protected $smtp_pass    = '';
    protected $smtp_crypto  = 'tls';

    // 通知接收人（管理员邮箱列表）
    protected $alert_emails = array();

    public function __construct() {
        $this->CI =& get_instance();
    }

    // ─────────────────────────────────
    //  报警事件邮件通知
    // ─────────────────────────────────

    /**
     * 发送报警通知邮件给管理员
     */
    public function send_alarm_notify($event_id, $data) {
        if (empty($this->smtp_user)) {
            log_message('info', 'Email not configured, skip alarm notify for event#' . $event_id);
            return false;
        }

        $this->CI->load->library('email');

        $config = array(
            'protocol'  => 'smtp',
            'smtp_host' => $this->smtp_host,
            'smtp_port' => $this->smtp_port,
            'smtp_user' => $this->smtp_user,
            'smtp_pass' => $this->smtp_pass,
            'smtp_crypto' => $this->smtp_crypto,
            'mailtype'  => 'html',
            'charset'   => 'utf-8',
            'newline'   => "\r\n",
        );
        $this->CI->email->initialize($config);

        $type      = isset($data['event_type']) ? $data['event_type'] : '未知';
        $conf      = isset($data['confidence']) ? round($data['confidence'] * 100, 1) . '%' : 'N/A';
        $location  = isset($data['location']) ? $data['location'] : '未知位置';
        $time      = date('Y-m-d H:i:s');

        $subject = "[火情预警] {$type} 报警 — {$location}";
        $message = "
            <h3>🔥 报警事件通知</h3>
            <table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse'>
                <tr><td><b>事件编号</b></td><td>#{$event_id}</td></tr>
                <tr><td><b>事件类型</b></td><td>{$type}</td></tr>
                <tr><td><b>置信度</b></td><td>{$conf}</td></tr>
                <tr><td><b>发生位置</b></td><td>{$location}</td></tr>
                <tr><td><b>报警时间</b></td><td>{$time}</td></tr>
            </table>
            <p>请登录系统进行处理。</p>
        ";

        $this->CI->email->from($this->smtp_user, '火焰识别预警系统');
        $this->CI->email->to($this->alert_emails);
        $this->CI->email->subject($subject);
        $this->CI->email->message($message);

        return $this->CI->email->send();
    }

    // ─────────────────────────────────
    //  微信推送（预留接口）
    // ─────────────────────────────────

    /**
     * 微信企业号/公众号推送（预留）
     */
    public function send_wechat_notify($event_id, $data) {
        // TODO: 接入企业微信/公众号模板消息 API
        log_message('info', 'Wechat notify reserved for event#' . $event_id);
        return true;
    }

    // ─────────────────────────────────
    //  短信通知（预留接口）
    // ─────────────────────────────────

    /**
     * 短信通知（预留，接入阿里云/腾讯云短信 SDK）
     */
    public function send_sms_notify($phone, $event_id, $data) {
        // TODO: 接入阿里云短信 / 腾讯云短信 SDK
        log_message('info', 'SMS notify reserved for event#' . $event_id . ' to ' . $phone);
        return true;
    }
}
