#!/bin/bash
# データセット品質チェックレポート表示スクリプト
# 使用方法: ./view_report.sh [report.json]

set -e

REPORT_FILE="${1:-report.json}"

if [ ! -f "$REPORT_FILE" ]; then
    echo "エラー: レポートファイルが見つかりません: $REPORT_FILE"
    echo "使用方法: $0 [report.json]"
    exit 1
fi

REPORT_FILE="$REPORT_FILE" python3 -c "
import json
import os
import sys

report_file = os.environ['REPORT_FILE']
with open(report_file) as f:
    report = json.load(f)

print('=' * 60)
print('CPT Dataset Quality Report')
print('=' * 60)
print(f\"Dataset: {report.get('dataset_id', 'N/A')}\")
print(f\"Split: {report.get('split', 'N/A')}\")
print(f\"Total Rows: {report.get('total_rows', 'N/A')}\")
print(f\"Text Field: {report.get('text_field', 'N/A')}\")
print()

summary = report.get('summary', {})
print(f\"Total Issues: {summary.get('total_issues', 0)}\")
print(f\"  Errors: {summary.get('errors', 0)}\")
print(f\"  Warnings: {summary.get('warnings', 0)}\")
print()

for result in report.get('results', []):
    checker = result.get('checker', 'unknown')
    issues = result.get('issues', [])
    if issues:
        print(f'--- {checker} ---')
        for issue in issues:
            severity = issue.get('severity', 'info').upper()
            msg = issue.get('message', '')
            affected = issue.get('affected_rows', 0)
            print(f'  [{severity}] {msg} (affected: {affected} rows)')
        print()

print('=' * 60)
"
