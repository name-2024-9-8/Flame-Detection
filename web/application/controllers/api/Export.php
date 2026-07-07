<?php
/**
 * Export 导出控制器 — Office 文档导出（Excel/Word）
 *
 * @author    王永林
 * @studentId 12303070414
 * @created   2026-06-11
 * @modified  2026-06-11
 * @task      王永林 — 阶段3 核心业务后端：Office文档导出模块
 */
defined('BASEPATH') OR exit('No direct script access allowed');

require_once APPPATH . 'core/REST_Controller.php';

class Export extends REST_Controller {

    public function __construct() {
        parent::__construct();
        $this->load->model('Alarm_model');
    }

    // ─────────────────────────────────
    //  GET /api/export/excel — 报警事件导出 Excel
    // ─────────────────────────────────

    public function excel() {
        $this->require_auth();
        $this->log_access();

        $start = $this->input->get('start_time', true);
        $end   = $this->input->get('end_time', true);
        $type  = $this->input->get('type', true);

        // 查询数据（不分页，最多导出1000条）
        $result = $this->Alarm_model->get_list(1, 1000, array(
            'start_time' => $start,
            'end_time'   => $end,
            'event_type' => $type,
        ));

        require_once APPPATH . '../vendor/autoload.php';

        $obj = new PHPExcel();
        $obj->getProperties()
            ->setCreator('视频AI智能识别及预警管理系统')
            ->setTitle('报警事件报表');

        $sheet = $obj->setActiveSheetIndex(0);
        $sheet->setTitle('报警事件');

        // 表头
        $headers = array('编号', '事件类型', '置信度', '经纬度', '位置', '报警时间',
                         '摄像头', 'AI云盒', '状态', '紧急程度', '处理结果');
        $col = 0;
        foreach ($headers as $h) {
            $sheet->setCellValueByColumnAndRow($col, 1, $h);
            $col++;
        }

        // 数据行（防公式注入：以 =、+、-、@ 开头的前缀单引号）
        $row = 2;
        $status_map = array('1'=>'报警', '2'=>'待审核', '3'=>'已审核');
        foreach ($result['list'] as $item) {
            $sheet->setCellValueByColumnAndRow(0, $row, $item['Id']);
            $sheet->setCellValueByColumnAndRow(1, $row, $this->_safe_cell($item['EventType'] == 'fire' ? '火焰' : '烟雾'));
            $sheet->setCellValueByColumnAndRow(2, $row, round($item['Confidence'] * 100, 1) . '%');
            $sheet->setCellValueByColumnAndRow(3, $row, $this->_safe_cell($item['Longitude'] . ',' . $item['Latitude']));
            $sheet->setCellValueByColumnAndRow(4, $row, $this->_safe_cell($item['Location']));
            $sheet->setCellValueByColumnAndRow(5, $row, $item['CreatTime']);
            $sheet->setCellValueByColumnAndRow(6, $row, $this->_safe_cell($item['CameraName']));
            $sheet->setCellValueByColumnAndRow(7, $row, $this->_safe_cell($item['DeviceAddress']));
            $sheet->setCellValueByColumnAndRow(8, $row, isset($status_map[$item['Status']]) ? $status_map[$item['Status']] : $item['Status']);
            $sheet->setCellValueByColumnAndRow(9, $row, $this->_safe_cell($item['UrgencyDegree']));
            $sheet->setCellValueByColumnAndRow(10, $row, $this->_safe_cell($item['OperateResult']));
            $row++;
        }

        // 自动列宽
        for ($c = 0; $c < 10; $c++) {
            $sheet->getColumnDimensionByColumn($c)->setAutoSize(true);
        }

        // 下载
        $filename = 'alarm_events_' . date('Ymd_His') . '.xlsx';
        header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Cache-Control: max-age=0');

        $writer = PHPExcel_IOFactory::createWriter($obj, 'Excel2007');
        $writer->save('php://output');
    }

    // ─────────────────────────────────
    //  GET /api/export/word — 报警事件导出 Word
    // ─────────────────────────────────

    public function word() {
        $this->require_auth();
        $this->log_access();

        $id = intval($this->input->get('id', true));
        if (!$id) {
            $this->error('请指定事件ID');
        }

        $event = $this->Alarm_model->get_detail($id);
        if (!$event) {
            $this->error('报警事件不存在', $this->http_not_found);
        }

        require_once APPPATH . '../vendor/autoload.php';

        $phpWord = new \PhpOffice\PhpWord\PhpWord();

        $section = $phpWord->addSection();
        $section->addTitle('报警事件报告', 1);
        $section->addText('');

        // 基本信息表格
        $table = $section->addTable(array('borderSize' => 1, 'cellMargin' => 80));
        $style = array('bold' => true);

        $rows = array(
            array('事件编号', '# ' . $event['Id']),
            array('事件类型', $event['EventType'] == 'fire' ? '火焰' : '烟雾'),
            array('置信度', round($event['Confidence'] * 100, 1) . '%'),
            array('经度', $event['Longitude']),
            array('纬度', $event['Latitude']),
            array('报警地点', $event['Location']),
            array('报警时间', $event['CreatTime']),
            array('所属摄像头', $event['CameraName']),
            array('所属AI云盒', $event['DeviceAddress']),
            array('事件描述', $event['Description']),
            array('处理状态', $event['Status'] == '1' ? '报警' : ($event['Status'] == '2' ? '待审核' : '已审核')),
            array('事件紧急程度', $event['UrgencyDegree']),
            array('处理人', $event['OperateName']),
            array('处理时间', $event['OperateTime']),
            array('处理结果', $event['OperateResult']),
            array('审核人', $event['AuditName']),
            array('审核时间', $event['AuditTime']),
        );

        foreach ($rows as $r) {
            $table->addRow();
            $table->addCell(3000)->addText($r[0], $style);
            $table->addCell(6000)->addText($r[1] ?: '—');
        }

        $filename = 'alarm_report_' . $id . '_' . date('Ymd_His') . '.docx';
        header('Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Cache-Control: max-age=0');

        $writer = \PhpOffice\PhpWord\IOFactory::createWriter($phpWord, 'Word2007');
        $writer->save('php://output');
    }

    /**
     * 防 Excel 公式注入：首字符为 = + - @ 时前缀单引号
     */
    private function _safe_cell($val) {
        if ($val === null || $val === '') return '';
        $first = mb_substr((string)$val, 0, 1);
        if (in_array($first, array('=', '+', '-', '@'))) {
            return "'" . $val;
        }
        return $val;
    }
}
