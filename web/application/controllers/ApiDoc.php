<?php
/**
 * ApiDoc 控制器 — 内嵌 API 文档页 + 简单登录页
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 前端联调支撑：API 文档 + 登录页
 */
defined('BASEPATH') OR exit('No direct script access allowed');

class ApiDoc extends CI_Controller {

    public function index() {
        $this->load->view('api_doc');
    }

    public function login() {
        $this->load->view('login_page');
    }
}
