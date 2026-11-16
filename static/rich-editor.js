(() => {
  const form = document.querySelector('form.editor');
  if (!form) return;
  const textarea = form.elements.content;
  const format = form.elements.content_format;
  const status = document.getElementById('import-status');
  const imageInput = document.getElementById('image-file');
  const $area = $(textarea);
  let active = false;
  let currentFormat = format.value;
  let uploads = 0;
  const token = () => form.elements.csrf_token.value;

  function sync() { if (active) textarea.value = $area.summernote('isEmpty') ? '' : $area.summernote('code'); }
  function destroy() {
    if (active) {
      sync();
      const content = textarea.value;
      $area.summernote('destroy'); active = false;
      textarea.value = content;
    }
    textarea.required = true;
  }
  function initialize() {
    currentFormat = format.value;
    const supportsImages = ['markdown','html'].includes(format.value);
    imageInput.disabled = !supportsImages;
    document.getElementById('image-upload-label').hidden = !supportsImages;
    if (format.value !== 'html') return;
    textarea.required = false;
    $area.summernote({
      lang: 'zh-CN', height: 460, minHeight: 260, maxHeight: 1000,
      placeholder: '开始写作，可插入图片或直接粘贴文字…',
      dialogsInBody: true,
      toolbar: [
        ['style', ['style']], ['font', ['bold','italic','underline','strikethrough','clear']],
        ['fontsize', ['fontsize']], ['color', ['color']],
        ['para', ['ul','ol','paragraph']], ['insert', ['link','table','uploadImage']],
        ['view', ['fullscreen','undo','redo']]
      ],
      buttons: {
        uploadImage: () => $.summernote.ui.button({contents:'▧ 图片', tooltip:'上传图片', click:() => {
          $area.summernote('saveRange'); imageInput.click();
        }}).render()
      },
      callbacks: {
        onChange: html => { textarea.value = html; },
        onImageUpload: files => uploadImages(files),
        onPaste: event => {
          const clipboard = (event.originalEvent || event).clipboardData;
          if (!clipboard) return;
          const images = Array.from(clipboard.files || []).filter(file => file.type.startsWith('image/'));
          if (images.length) { event.preventDefault(); uploadImages(images); return; }
          // Sanitize pasted HTML through the same server renderer used by published posts.
          const html = clipboard.getData('text/html');
          if (html) {
            event.preventDefault();
            $area.summernote('saveRange');
            const body = new FormData(); body.append('content',html); body.append('content_format','html');
            fetch('/api/preview', {method:'POST', body, headers:{'X-CSRFToken':token()}})
              .then(async response => { if (!response.ok) throw new Error('粘贴失败，请重试。'); return response.json(); })
              .then(data => { $area.summernote('restoreRange'); $area.summernote('pasteHTML',data.html); })
              .catch(error => { status.textContent = error.message; });
          }
        }
      }
    });
    active = true;
  }

  async function uploadImages(files) {
    if (!['markdown','html'].includes(format.value)) { status.textContent = '请切换为富文本或 Markdown 后插入图片。'; return; }
    if (active) $area.summernote('saveRange');
    uploads++;
    try {
      for (const file of Array.from(files)) {
        if (file.size > 5 * 1024 * 1024) throw new Error('每张图片不能超过 5MB。');
        status.textContent = '正在上传图片…';
        const body = new FormData(); body.append('file',file);
        const response = await fetch('/api/images', {method:'POST', body, headers:{'X-CSRFToken':token()}});
        if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('上传失败，请检查登录状态或图片大小。');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '上传失败');
        if (active) {
          $area.summernote('restoreRange');
          $area.summernote('insertImage', data.url, image => { image.attr('alt','文章图片'); image.css('max-width','100%'); });
        } else {
          const start = textarea.selectionStart;
          const snippet = `\n![文章图片](${data.url})\n`;
          textarea.setRangeText(snippet, start, textarea.selectionEnd, 'end');
        }
        status.textContent = '图片已插入，保存文章后生效。';
      }
    } catch (error) { status.textContent = error.message; }
    finally { uploads--; imageInput.value = ''; }
  }

  imageInput.addEventListener('change', () => uploadImages(imageInput.files));
  function plainText(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('script,style').forEach(node => node.remove());
    doc.querySelectorAll('br').forEach(node => node.replaceWith('\n'));
    doc.querySelectorAll('img').forEach(node => node.replaceWith(node.getAttribute('alt') || ''));
    doc.querySelectorAll('p,div,h1,h2,h3,h4,h5,h6,li,blockquote,pre,tr').forEach(node => node.append('\n'));
    doc.querySelectorAll('td,th').forEach(node => node.append('\t'));
    return doc.body.textContent.replace(/\u00a0/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  }
  format.addEventListener('change', async () => {
    const nextFormat = format.value;
    const previous = currentFormat;
    destroy();
    if (nextFormat === 'html' && textarea.value.trim()) {
      format.disabled = true;
      try {
        const body = new FormData(); body.append('content',textarea.value); body.append('content_format',previous);
        const response = await fetch('/api/preview', {method:'POST',body,headers:{'X-CSRFToken':token()}});
        if (!response.ok) throw new Error('格式转换失败。');
        textarea.value = (await response.json()).html;
      } catch (error) { status.textContent=error.message; format.value=previous; }
      finally { format.disabled = false; }
    }
    if (previous === 'html' && ['text','json'].includes(nextFormat)) {
      textarea.value = plainText(textarea.value);
      status.textContent = nextFormat === 'text' ? '已转换为纯文本，HTML 标签已移除，文字与换行已保留。' : '已提取文字，请确保内容为有效 JSON 后保存。';
    } else if (previous === 'html' && nextFormat === 'markdown') {
      textarea.value = new TurndownService({headingStyle:'atx',codeBlockStyle:'fenced'}).turndown(textarea.value);
      status.textContent = '已转换为 Markdown，不保留编辑器的 HTML 标签。';
    } else if (nextFormat === 'html') {
      status.textContent = '已切换为富文本编辑。';
    }
    document.getElementById('content-preview').hidden = true;
    initialize();
  });
  form.addEventListener('submit', event => {
    sync();
    if (uploads || format.disabled) { event.preventDefault(); status.textContent = '请等待图片上传或格式转换完成。'; return; }
    if ((active && $area.summernote('isEmpty')) || !textarea.value.trim() || textarea.value.length > 100000) {
      event.preventDefault(); status.textContent = '正文不能为空，且不能超过 10 万字。';
    }
  });
  window.blogEditor = {sync,destroy,initialize};
  initialize();
})();
