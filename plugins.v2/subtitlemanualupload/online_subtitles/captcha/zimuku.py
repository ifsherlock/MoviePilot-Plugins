from __future__ import annotations

from ..common import *  # noqa: F401,F403

class ZimukuBmpCaptchaSolver:
    IMG_WIDTH = 100
    IMG_HEIGHT = 27
    CHAR_WIDTH = 20
    NUM_CHARS = 5
    PIXEL_DATA_OFFSET = 54
    SAMPLE_POINTS = [(10, 7), (7, 8), (12, 8), (10, 13), (7, 19), (12, 19), (10, 20), (6, 13), (14, 13)]
    TEMPLATES = {
        "0": [1, 1, 1, 1, 1, 1, 1, 1, 0],
        "1": [0, 1, 0, 0, 0, 0, 1, 0, 0],
        "2": [1, 0, 1, 0, 1, 0, 1, 0, 0],
        "3": [1, 0, 1, 1, 0, 1, 1, 0, 0],
        "4": [0, 0, 1, 0, 0, 1, 0, 0, 0],
        "5": [1, 1, 0, 0, 0, 1, 1, 0, 0],
        "6": [1, 0, 1, 1, 1, 1, 1, 1, 0],
        "7": [1, 0, 1, 0, 0, 0, 0, 0, 0],
        "8": [1, 1, 1, 1, 1, 1, 1, 0, 0],
        "9": [1, 1, 1, 0, 1, 0, 1, 0, 0],
    }

    def __init__(self, b64_string: str):
        self._data = base64.b64decode(b64_string)
        if len(self._data) < self.PIXEL_DATA_OFFSET or self._data[:2] != b"BM":
            raise ValueError("Zimuku 验证码不是 BMP 数据")
        width = struct.unpack_from("<i", self._data, 18)[0]
        height = struct.unpack_from("<i", self._data, 22)[0]
        if (width, height) != (self.IMG_WIDTH, self.IMG_HEIGHT):
            raise ValueError("Zimuku 验证码尺寸不匹配")
        self._stride = (self.IMG_WIDTH * 3 + 3) & ~3

    @classmethod
    def from_html(cls, text: str) -> str:
        match = re.search(r"data:image/bmp;base64,([^\"']+)", text or "")
        if not match:
            return ""
        try:
            return cls(match.group(1)).recognize()
        except Exception as exc:
            logger.warning("[SubtitleManualUpload] Zimuku 验证码识别失败: %s", exc)
            return ""

    def recognize(self) -> str:
        result = []
        one_offset = 0
        for index in range(self.NUM_CHARS):
            char_x = index * self.CHAR_WIDTH
            features = [1 if self._is_foreground(char_x + px - one_offset, py) else 0 for px, py in self.SAMPLE_POINTS]
            digit = self._match_digit(features)
            if digit == "1":
                one_offset += 1
            elif digit == "4":
                one_offset -= 1
            result.append(digit)
        return "".join(result)
    def _is_foreground(self, x: int, y: int, threshold: int = 70) -> bool:
        bmp_y = self.IMG_HEIGHT - 1 - y
        offset = self.PIXEL_DATA_OFFSET + bmp_y * self._stride + x * 3
        b, g, r = self._data[offset], self._data[offset + 1], self._data[offset + 2]
        return (r + g + b) / 3 < threshold

    def _match_digit(self, features: List[int]) -> str:
        best = "?"
        min_diff = 999
        for digit, template in self.TEMPLATES.items():
            diff = sum(left != right for left, right in zip(features, template))
            if diff < min_diff:
                min_diff = diff
                best = digit
        return best
