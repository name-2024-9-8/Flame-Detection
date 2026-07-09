/*
=============================================================================
视频AI智能识别及预警管理信息系统 - 火焰识别
前端全局JavaScript
作者：段林川（前端开发与质量保障工程师）
创建时间：2026-06-11
功能描述：全局工具函数、AJAX封装、UI交互增强、响应式适配
=============================================================================
*/

'use strict';

// =========================================================================
// AJAX 全局配置
// =========================================================================

// 为所有AJAX请求添加CSRF保护头和错误处理
$.ajaxSetup({
    beforeSend: function(xhr) {
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    },
    error: function(xhr, status, error) {
        if (xhr.status === 401) {
            // Token/session过期，跳转到登录页
            if (window.location.pathname !== '/login') {
                alert('登录已过期，请重新登录');
                window.location.href = '/login';
            }
        } else if (xhr.status === 403) {
            alert('权限不足，无法执行此操作');
        } else if (xhr.status === 500) {
            console.error('服务器内部错误:', xhr.responseJSON);
        }
    }
});

// =========================================================================
// 工具函数
// =========================================================================

var AppUtils = {
    /**
     * 格式化日期时间
     * @param {string|Date} date - 日期
     * @param {string} fmt - 格式，默认 'YYYY-MM-DD HH:mm:ss'
     */
    formatDate: function(date, fmt) {
        if (!date) return '-';
        fmt = fmt || 'YYYY-MM-DD HH:mm:ss';
        var d = new Date(date);
        if (isNaN(d.getTime())) return date;
        var o = {
            'Y+': d.getFullYear(),
            'M+': d.getMonth() + 1,
            'D+': d.getDate(),
            'H+': d.getHours(),
            'm+': d.getMinutes(),
            's+': d.getSeconds()
        };
        for (var k in o) {
            if (new RegExp('(' + k + ')').test(fmt)) {
                fmt = fmt.replace(RegExp.$1, (RegExp.$1.length === 1) ?
                    o[k] : ('00' + o[k]).substr(('' + o[k]).length));
            }
        }
        return fmt;
    },

    /**
     * Toast提示（使用LayUI）
     */
    toast: function(msg, icon) {
        icon = icon || 1;
        if (typeof layui !== 'undefined' && layui.layer) {
            layui.layer.msg(msg, { icon: icon, time: 2000, shift: 6 });
        } else {
            alert(msg);
        }
    },

    /**
     * 确认对话框
     */
    confirm: function(msg, callback) {
        if (typeof layui !== 'undefined' && layui.layer) {
            layui.layer.confirm(msg, {
                icon: 3,
                title: '提示',
                btn: ['确定', '取消']
            }, function(index) {
                layui.layer.close(index);
                if (callback) callback();
            });
        } else {
            if (confirm(msg) && callback) callback();
        }
    },

    /**
     * Loading遮罩
     */
    showLoading: function(msg) {
        if (typeof layui !== 'undefined' && layui.layer) {
            return layui.layer.load(2, { shade: [0.3, '#000'] });
        }
        return null;
    },

    hideLoading: function(index) {
        if (typeof layui !== 'undefined' && layui.layer && index != null) {
            layui.layer.close(index);
        }
    },

    /**
     * 获取URL参数
     */
    getQueryParam: function(name) {
        var url = window.location.search;
        var params = new URLSearchParams(url);
        return params.get(name);
    },

    /**
     * 防抖函数
     */
    debounce: function(func, wait) {
        var timeout;
        return function() {
            var context = this, args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                func.apply(context, args);
            }, wait);
        };
    },

    /**
     * 节流函数
     */
    throttle: function(func, limit) {
        var inThrottle;
        return function() {
            var args = arguments, context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(function() { inThrottle = false; }, limit);
            }
        };
    }
};

// =========================================================================
// 表格排序增强
// =========================================================================

(function() {
    // 为带有 .sortable 类的表头添加点击排序功能
    $(document).on('click', '.sortable', function() {
        var table = $(this).closest('table');
        var tbody = table.find('tbody');
        var colIndex = $(this).index();
        var rows = tbody.find('tr').toArray();
        var isAsc = !$(this).hasClass('sorted-asc');

        // 移除所有排序标记
        table.find('.sortable').removeClass('sorted-asc sorted-desc');
        $(this).addClass(isAsc ? 'sorted-asc' : 'sorted-desc');

        rows.sort(function(a, b) {
            var aVal = $(a).children('td').eq(colIndex).text().trim();
            var bVal = $(b).children('td').eq(colIndex).text().trim();
            // 尝试数字比较
            var aNum = parseFloat(aVal);
            var bNum = parseFloat(bVal);
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return isAsc ? aNum - bNum : bNum - aNum;
            }
            return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        });

        tbody.empty().append(rows);
    });
})();

// =========================================================================
// 响应式侧边栏适配
// =========================================================================

$(document).ready(function() {
    // 在小屏幕上自动折叠导航栏菜单
    var handleResize = AppUtils.debounce(function() {
        var width = window.innerWidth;
        if (width < 992) {
            $('.navbar-collapse').removeClass('show');
        }
    }, 300);

    $(window).on('resize', handleResize);

    // 点击导航项后在小屏幕上自动收起菜单
    $('.navbar .nav-link').on('click', function() {
        if (window.innerWidth < 992) {
            $('.navbar-collapse').collapse('hide');
        }
    });

    // Flash消息自动消失
    setTimeout(function() {
        $('.alert-dismissible').fadeOut(500, function() {
            $(this).remove();
        });
    }, 5000);

    // 自动为表格添加斑马纹和hover效果
    $('.table').addClass('table-hover');

    // 初始化LayUI
    if (typeof layui !== 'undefined') {
        layui.use(['element', 'layer', 'form'], function() {
            var element = layui.element;
            var form = layui.form;
            // LayUI form渲染
            form.render();
        });
    }
});

// =========================================================================
// 导出功能（通用）
// =========================================================================

window.exportTable = function(tableSelector, filename) {
    var table = $(tableSelector);
    if (!table.length) return;

    var csv = [];
    var rows = table.find('tr');

    rows.each(function() {
        var row = [];
        $(this).find('th, td').each(function() {
            // 获取纯文本（去除HTML标签和徽章）
            var text = $(this).clone().find('.badge,button').remove().end().text().trim();
            // CSV引号转义
            text = '"' + text.replace(/"/g, '""') + '"';
            row.push(text);
        });
        csv.push(row.join(','));
    });

    var csvStr = csv.join('\n');
    var blob = new Blob(['﻿' + csvStr], { type: 'text/csv;charset=utf-8;' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = (filename || 'export') + '.csv';
    link.click();
};

// =========================================================================
// 打印功能
// =========================================================================

window.printPage = function() {
    window.print();
};

// =========================================================================
// 控制台信息
// =========================================================================

console.log('%c🔥 视频AI智能识别及预警管理信息系统 %c v1.1.0',
    'color: #e74c3c; font-size: 16px; font-weight: bold;',
    'color: #888; font-size: 12px;');
console.log('%c基于深度学习的火焰智能检测平台',
    'color: #f39c12; font-size: 12px;');
console.log('%c开发者：段林川（前端开发与质量保障工程师）',
    'color: #3498db; font-size: 11px;');
