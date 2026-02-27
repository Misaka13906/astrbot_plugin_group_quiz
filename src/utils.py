import re

from astrbot.core.message.message_event_result import MessageEventResult


def build_mixed_message(
    text: str, result: MessageEventResult = None
) -> MessageEventResult:
    """
    解析文本中的 Markdown 图片链接，构造混排文本和图片的 MessageEventResult
    支持格式: ![提示字符](网络链接或本地绝对路径)
    """
    if result is None:
        result = MessageEventResult()

    pattern = re.compile(r"!\[.*?\]\((.*?)\)")
    last_idx = 0
    for match in pattern.finditer(text):
        start = match.start()
        end = match.end()
        image_url = match.group(1).strip()

        # 添加图片前面的文本
        if start > last_idx:
            result.message(text[last_idx:start])

        # 添加图片组件
        if image_url.startswith("http://") or image_url.startswith("https://"):
            result.url_image(image_url)
        elif image_url.startswith("base64://"):
            result.base64_image(image_url[9:])
        else:
            # 默认为本地路径
            result.file_image(image_url)

        last_idx = end

    if last_idx < len(text):
        result.message(text[last_idx:])

    return result
