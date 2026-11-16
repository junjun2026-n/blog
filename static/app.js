document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', e => {
  if (!window.confirm(form.dataset.confirm)) e.preventDefault();
}));
document.querySelectorAll('.eye').forEach(button => button.addEventListener('click', () => {
  const input = button.parentElement.querySelector('input');
  input.type = input.type === 'password' ? 'text' : 'password';
  button.setAttribute('aria-label', input.type === 'password' ? '显示密码' : '隐藏密码');
  button.setAttribute('aria-pressed', String(input.type === 'text'));
}));

const documentFile = document.getElementById('document-file');
if (documentFile) {
  const editor = documentFile.closest('form');
  const status = document.getElementById('import-status');
  const preview = document.getElementById('content-preview');
  const token = () => editor.querySelector('[name=csrf_token]').value;
  documentFile.addEventListener('change', async () => {
    const file = documentFile.files[0];
    if (!file) return;
    if (file.size > 1024 * 1024) { status.textContent = '文件不能超过 1MB。'; documentFile.value = ''; return; }
    window.blogEditor?.sync();
    if (editor.elements.content.value.trim() && !confirm('导入会替换当前正文，是否继续？')) { documentFile.value = ''; return; }
    const body = new FormData(); body.append('file', file);
    status.textContent = '正在导入…'; documentFile.disabled = true;
    try {
      const response = await fetch('/api/import', {method:'POST', body, headers:{'X-CSRFToken':token()}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('登录已过期或请求无效，请刷新后重试。');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '导入失败');
      window.blogEditor?.destroy();
      editor.elements.content.value = data.content;
      editor.elements.content_format.value = data.content_format;
      window.blogEditor?.initialize();
      if (!editor.elements.title.value.trim()) editor.elements.title.value = data.title;
      preview.hidden = true;
      status.textContent = data.notice;
    } catch (error) { status.textContent = error.message; }
    finally { documentFile.disabled = false; documentFile.value = ''; }
  });
  document.getElementById('preview-button').addEventListener('click', async () => {
    try {
      window.blogEditor?.sync();
      const body = new FormData();
      body.append('content', editor.elements.content.value);
      body.append('content_format', editor.elements.content_format.value);
      const response = await fetch('/api/preview', {method:'POST', body, headers:{'X-CSRFToken':token()}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('请刷新页面后重试。');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '预览失败');
      preview.innerHTML = data.html; preview.hidden = false;
    } catch (error) { status.textContent = error.message; }
  });
}
