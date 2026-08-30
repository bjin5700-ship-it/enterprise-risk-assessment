# 企业风险动态评估系统

Flask + 中文 20 维规则引擎。生产：https://sentinel-risk.cn/erm/

- 评分只走 `risk_engine`，LLM 不打分。
- 登录默认管理员：见服务器 `users.json` / `ERM_ADMIN_USER`（勿提交到仓库）。
- 部署：`powershell -File scripts/deploy-erm-to-vps.ps1`（推送 GitHub 后同步 `sentinel-hk:/opt/enterprise-risk-assessment`）。
