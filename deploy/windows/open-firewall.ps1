# 开放 Windows 防火墙端口（管理员 PowerShell 运行）
# 用法: .\deploy\windows\open-firewall.ps1 -Port 8088

param(
    [int]$Port = 8088,
    [string]$Name = "ERM-Risk-Assessment"
)

$ruleName = "ERM-$Name-$Port"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "规则已存在: $ruleName"
} else {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port
    Write-Host "已放行 TCP $Port"
}
Write-Host "若使用 Nginx/IIS 反代，还需放行 80 和 443"
