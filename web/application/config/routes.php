<?php
/**
 * API 路由配置
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      人员B — 阶段2 RESTful API 路由映射
 */
defined('BASEPATH') OR exit('No direct script access allowed');

/*
| -------------------------------------------------------------------------
| URI ROUTING
| -------------------------------------------------------------------------
| This file lets you re-map URI requests to specific controller functions.
|
| Typically there is a one-to-one relationship between a URL string
| and its corresponding controller class/method. The segments in a
| URL normally follow this pattern:
|
|	example.com/class/method/id/
|
| In some instances, however, you may want to remap this relationship
| so that a different class/function is called than the one
| corresponding to the URL.
|
| Please see the user guide for complete details:
|
|	https://codeigniter.com/userguide3/general/routing.html
|
| -------------------------------------------------------------------------
| RESERVED ROUTES
| -------------------------------------------------------------------------
|
| There are three reserved routes:
|
|	$route['default_controller'] = 'welcome';
|
| This route indicates which controller class should be loaded if the
| URI contains no data. In the above example, the "welcome" class
| would be loaded.
|
|	$route['404_override'] = 'errors/page_missing';
|
| This route will tell the Router which controller/method to use if those
| provided in the URL cannot be matched to a valid route.
|
|	$route['translate_uri_dashes'] = FALSE;
|
| This is not exactly a route, but allows you to automatically route
| controller and method names that contain dashes. '-' isn't a valid
| class or method name character, so it requires translation.
| When you set this option to TRUE, it will replace ALL dashes in the
| controller and method URI segments.
|
| Examples:	my-controller/index	-> my_controller/index
|		my-controller/my-method	-> my_controller/my_method
*/
$route['default_controller'] = 'welcome';
$route['404_override'] = '';
$route['translate_uri_dashes'] = FALSE;

// ── RESTful API 路由 ──
// Auth 认证
$route['api/auth/login']   = 'api/Auth/login';
$route['api/auth/profile'] = 'api/Auth/profile';
$route['api/auth/refresh'] = 'api/Auth/refresh';
$route['api/auth/logout']  = 'api/Auth/logout';

// 报警事件
$route['api/alarm/events']                  = 'api/Alarm/index';
$route['api/alarm/events/create']           = 'api/Alarm/create';
$route['api/alarm/events/(:num)']           = 'api/Alarm/detail/$1';
$route['api/alarm/events/(:num)/update']    = 'api/Alarm/update/$1';

// 设备管理
$route['api/devices']                       = 'api/Device/index';
$route['api/devices/create']                = 'api/Device/create';
$route['api/devices/(:num)/update']         = 'api/Device/update/$1';
$route['api/devices/(:num)/delete']         = 'api/Device/delete/$1';

// 统计分析
$route['api/statistics']                    = 'api/Statistics/index';
$route['api/statistics/health']             = 'api/Statistics/health';

// 文档导出
$route['api/export/excel']                  = 'api/Export/excel';
$route['api/export/word']                   = 'api/Export/word';

// WebService 数据交换
$route['api/webservice/alarm']              = 'api/WebService/alarm';
$route['api/webservice/device/(:num)']      = 'api/WebService/device/$1';
$route['api/webservice/video-frame/(:num)'] = 'api/WebService/video_frame/$1';
$route['api/webservice/report']             = 'api/WebService/report';
