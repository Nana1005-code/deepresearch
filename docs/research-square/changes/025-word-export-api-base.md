# 025 Word 导出使用动态后端地址

## 问题

`ReportExport.vue` 将 Word 导出接口硬编码为 `http://127.0.0.1:8000/export/word`。当整合版使用备用后端端口（例如 8011）时，页面其他 API 会读取 `VITE_API_BASE_URL` 并正常工作，只有 Word 导出请求仍发往 8000，浏览器因此显示 `Failed to fetch`。

## 修复

- Word 导出与其他前端接口统一读取 `import.meta.env.VITE_API_BASE_URL`。
- 未配置时仍回退到 `http://localhost:8000`。
- 清理末尾斜杠，避免生成双斜杠 URL。

这项修改只调整导出请求地址，不改变 DOCX 生成逻辑。
