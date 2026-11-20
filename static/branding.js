// ============================================================
// 文件名称：branding.js
// 生成日期：2026-11-11
// 修改日期：2026-11-20
// 版本信息：v0.261115
// 作    者：JUN
// 备    注：本程序由AI辅助完成。
//           文件功能：实现 branding 模块相关功能。
//           文件用途：供博客的 BLOG/static/branding.js 模块使用。
//           注意事项：运行前检查依赖与配置；涉及数据或服务变更时先备份并验证。
// ============================================================
(() => {
  const form = document.getElementById('branding-form');
  if (!form) return;
  const fileInput = document.getElementById('logo-file');
  const status = document.getElementById('logo-status');
  const save = document.getElementById('save-branding');
  let busy = false;
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    if (file.size > 5*1024*1024) { status.textContent = 'LOGO 不能超过 5MB。'; fileInput.value=''; return; }
    busy = true; save.disabled = true; fileInput.disabled = true; status.textContent = '正在上传 LOGO…';
    try {
      const body = new FormData(); body.append('file',file);
      const response = await fetch('/api/images', {method:'POST', body, headers:{'X-CSRFToken':form.elements.csrf_token.value}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('上传失败，请刷新后重试。');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '上传失败');
      form.elements.platform_logo.value = data.url;
      form.elements.remove_logo.checked = false;
      const preview = document.getElementById('logo-preview'); preview.src = data.url; preview.hidden = false;
      status.textContent = 'LOGO 已上传，请点击保存设置。';
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; save.disabled = false; fileInput.disabled = false; fileInput.value = ''; }
  });
  form.addEventListener('submit', event => { if (busy) { event.preventDefault(); status.textContent = '请等待上传完成。'; } });
})();
