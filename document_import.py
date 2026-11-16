import io
import json
import zipfile
from pathlib import Path

import mammoth


def import_document(filename, data):
    ext = Path(filename).suffix.lower()
    if len(data) > 1024 * 1024:
        raise ValueError('文件不能超过 1MB。')
    if ext == '.doc':
        raise ValueError('旧版 .doc 请先用 Word 另存为 .docx 后导入。')
    if ext not in ('.md', '.markdown', '.json', '.txt', '.utf8', '.docx'):
        raise ValueError('支持 MD、Markdown、JSON、TXT、UTF8 和 Word DOCX 文件。')
    fmt = 'markdown' if ext in ('.md','.markdown','.docx') else ('json' if ext == '.json' else 'text')
    if ext == '.docx':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 10 * 1024 * 1024 or len(archive.infolist()) > 1000:
                    raise ValueError('Word 文档解压后内容过大。')
            # Convert structure to Markdown without loading or retaining embedded images.
            result = mammoth.convert_to_markdown(io.BytesIO(data), convert_image=mammoth.images.img_element(lambda image: {}))
            content = result.value
        except ValueError:
            raise
        except Exception:
            raise ValueError('无法读取 Word 文件，请确认它是有效的 DOCX 文档。') from None
    else:
        try:
            content = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('文本文件需要使用 UTF-8 编码，请转换编码后导入。') from None
        if '\x00' in content:
            raise ValueError('文件包含二进制内容，请选择 UTF-8 文本文件。')
    if fmt == 'json':
        try:
            content = json.dumps(json.loads(content), ensure_ascii=False, indent=2, allow_nan=False)
        except (ValueError, RecursionError):
            raise ValueError('JSON 格式无效，请检查文件内容。') from None
    if not content.strip() or len(content) > 100000:
        raise ValueError('导入的正文不能为空，且不能超过 10 万字。')
    return {'title': Path(filename.replace('\\','/')).stem[:160], 'content': content, 'content_format': fmt,
            'notice': '已导入 Word 文字与基本结构，图片和复杂版式不保留。' if ext == '.docx' else '文件已导入，可以继续编辑。'}
