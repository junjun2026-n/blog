(() => {
  const form = document.getElementById('comment-form');
  if (!form) return;
  const text = form.elements.content;
  const picker = document.getElementById('emoji-picker');
  const toggle = document.getElementById('emoji-toggle');
  const files = document.getElementById('sticker-file');
  const preview = document.getElementById('sticker-preview');
  const status = document.getElementById('comment-status');
  let busy = false;
  const submit = form.querySelector('button:not([type=button])');
  for (const emoji of ['😀','😄','😁','😂','🤣','😊','😍','🥰','😘','😎','🤔','😅','😭','🥺','😮','😡','👍','👎','👏','🙏','🤝','💪','🎉','❤️','💯','🔥','🌹','☕','🐶','🐱','👀','✅']) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = emoji; button.setAttribute('aria-label', '插入表情 ' + emoji);
    button.addEventListener('click', () => {
      const start = text.selectionStart, end = text.selectionEnd;
      if (text.value.length - (end-start) + emoji.length > 3000) return;
      text.setRangeText(emoji, start, end, 'end'); text.focus();
    });
    picker.append(button);
  }
  toggle.addEventListener('click', () => { picker.hidden = !picker.hidden; toggle.setAttribute('aria-expanded', String(!picker.hidden)); });
  async function upload(selected) {
    if (busy) return;
    if (preview.children.length + selected.length > 3) { status.textContent = '每条评论最多添加 3 张表情包。'; files.value = ''; return; }
    busy = true; submit.disabled = true; files.disabled = true;
    try {
      for (const file of selected) {
        if (file.size > 5*1024*1024) throw new Error('单张图片不能超过 5MB。');
        const data = new FormData(); data.append('file',file);
        status.textContent = '正在上传表情包…';
        const response = await fetch('/api/images', {method:'POST', body:data, headers:{'X-CSRFToken':form.elements.csrf_token.value}});
        if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('上传失败，请刷新页面后重试。');
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || '上传失败');
        const item = document.createElement('div'); item.className = 'sticker-item';
        const image = document.createElement('img'); image.src = result.url; image.alt = '待发表表情包';
        const input = document.createElement('input'); input.type='hidden'; input.name='images'; input.value=result.url;
        const remove = document.createElement('button'); remove.type='button'; remove.textContent='×'; remove.setAttribute('aria-label','移除表情包');
        remove.addEventListener('click', () => item.remove());
        item.append(image,input,remove); preview.append(item);
      }
      status.textContent = '表情包已添加，点击发表评论即可发布。';
    } catch (error) { status.textContent = error.message; }
    finally { busy=false; submit.disabled=false; files.disabled=false; files.value=''; }
  }
  files.addEventListener('change', () => upload(Array.from(files.files)));
  text.addEventListener('paste', event => {
    const images=Array.from(event.clipboardData?.files || []).filter(file => file.type.startsWith('image/'));
    if (images.length) { event.preventDefault(); upload(images); }
  });
  form.addEventListener('submit', event => {
    if (busy || (!text.value.trim() && !preview.children.length)) {
      event.preventDefault(); status.textContent = busy ? '请等待表情包上传完成。' : '请输入评论或添加表情包。';
    }
  });
})();
