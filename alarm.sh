#!/bin/bash
# トースト通知：Windows 10/11のネイティブ通知

# 引数で通知タイプを指定（デフォルトはnone）
TYPE=${1:-none}
TITLE="from Claude Code"
PWD=$(pwd)
IMG="\\\\wsl.localhost\\Ubuntu-22.04"${PWD//\//\\}"\\imgs\\Claude_AI_symbol.png"

case "$TYPE" in
    stop)
        MESSAGE="タスクが完了しました"
        ;;
    notification)
        MESSAGE="通知が届きました"
        ;;
    *)
        MESSAGE="$TYPE"
        ;;
esac

powershell.exe -Command "New-BurntToastNotification -Text '$TITLE', '$MESSAGE' -AppLogo '$IMG'"
