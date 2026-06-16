<?php
/**
 * API 路由配置
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-16  融合: 新增边缘检测数据接入路由（/api/detect/*, /api/device/*）
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

// 日志查询（融合联调新增）
$route['api/logs/access']                   = 'api/Log/access';
$route['api/logs/operation']                = 'api/Log/operation';

// 边缘检测数据接入（人员A → 人员B 接口，M7融合新增）
$route['api/detect/alarm']                  = 'api/Detect/alarm';
$route['api/detect/upload']                 = 'api/Detect/upload';
$route['api/device/heartbeat']              = 'api/Detect/heartbeat';
$route['api/device/error']                  = 'api/Detect/device_error';

// 用户管理 CRUD（M7融合修复新增）
$route['api/users']                         = 'api/User/index';
$route['api/users/create']                  = 'api/User/create';
$route['api/users/(:num)']                  = 'api/User/detail/$1';
$route['api/users/(:num)/update']           = 'api/User/update/$1';
$route['api/users/(:num)/delete']           = 'api/User/delete/$1';

// 角色管理 CRUD（M7融合修复新增）
$route['api/roles']                         = 'api/Role/index';
$route['api/roles/create']                  = 'api/Role/create';
$route['api/roles/(:num)']                  = 'api/Role/detail/$1';
$route['api/roles/(:num)/update']           = 'api/Role/update/$1';
$route['api/roles/(:num)/delete']           = 'api/Role/delete/$1';

// 部门管理 CRUD（M7融合修复新增）
$route['api/branches']                      = 'api/Branch/index';
$route['api/branches/tree']                 = 'api/Branch/tree';
$route['api/branches/create']               = 'api/Branch/create';
$route['api/branches/(:num)']               = 'api/Branch/detail/$1';
$route['api/branches/(:num)/update']        = 'api/Branch/update/$1';
$route['api/branches/(:num)/delete']        = 'api/Branch/delete/$1';

// 数据字典 CRUD（M7融合修复新增）
$route['api/dictionary']                    = 'api/Dictionary/index';
$route['api/dictionary/types']              = 'api/Dictionary/types';
$route['api/dictionary/create']             = 'api/Dictionary/create';
$route['api/dictionary/(:num)']             = 'api/Dictionary/detail/$1';
$route['api/dictionary/(:num)/update']      = 'api/Dictionary/update/$1';
$route['api/dictionary/(:num)/delete']      = 'api/Dictionary/delete/$1';

// 故障管理（M7融合修复新增）
$route['api/faults/camera']                 = 'api/Fault/camera_faults';
$route['api/faults/camera/(:num)/repair']   = 'api/Fault/camera_repair/$1';
$route['api/faults/device']                 = 'api/Fault/device_faults';
$route['api/faults/device/(:num)/repair']   = 'api/Fault/device_repair/$1';

// 系统配置（M7融合修复新增）
$route['api/config']                        = 'api/Config/index';
$route['api/config/update']                 = 'api/Config/update';

// WebService 数据交换
$route['api/webservice/alarm']              = 'api/WebService/alarm';
$route['api/webservice/device/(:num)']      = 'api/WebService/device/$1';
$route['api/webservice/video-frame/(:num)'] = 'api/WebService/video_frame/$1';
$route['api/webservice/report']             = 'api/WebService/report';
