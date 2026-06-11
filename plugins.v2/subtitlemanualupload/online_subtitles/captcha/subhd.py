from __future__ import annotations

from ..common import *  # noqa: F401,F403

class SubHDSvgCaptchaSolver:
    LENGTH_MAP = {
        986: "I", 998: "1", 1068: "I", 1081: "1", 1082: "v", 1130: "Y", 1134: "Y",
        1172: "v", 1224: "Y", 1274: "L", 1298: "V", 1311: "V", 1360: "i", 1380: "L",
        1406: "V", 1473: "i", 1478: "T", 1491: "r", 1598: "N", 1601: "T", 1604: "X",
        1610: "J", 1613: "x", 1614: "N", 1615: "N", 1616: "N", 1617: "N", 1618: "N",
        1634: "k", 1637: "k", 1694: "t", 1706: "K", 1709: "K", 1731: "N", 1744: "J",
        1754: "F", 1770: "k", 1835: "t", 1838: "u", 1840: "A", 1844: "A", 1848: "K",
        1850: "Z", 1853: "Z", 1886: "h", 1900: "F", 1922: "H", 1928: "H", 1960: "P",
        1991: "u", 1993: "A", 1996: "D", 2004: "Z", 2018: "w", 2035: "w", 2042: "7",
        2043: "h", 2080: "j", 2082: "H", 2104: "R", 2107: "R", 2123: "P", 2140: "4",
        2162: "D", 2164: "O", 2183: "w", 2198: "C", 2199: "C", 2200: "C", 2201: "C",
        2202: "C", 2210: "f", 2212: "7", 2246: "E", 2253: "j", 2260: "o", 2272: "d",
        2279: "M", 2282: "M", 2294: "U", 2301: "U", 2310: "W", 2318: "4", 2321: "M",
        2332: "a", 2344: "O", 2345: "W", 2346: "W", 2366: "s", 2380: "b", 2381: "C",
        2382: "0", 2394: "f", 2433: "E", 2448: "o", 2461: "d", 2464: "p", 2466: "M",
        2485: "U", 2498: "c", 2501: "e", 2503: "W", 2512: "q", 2526: "a", 2546: "2",
        2563: "s", 2578: "b", 2580: "0", 2606: "5", 2632: "6", 2669: "p", 2706: "c",
        2709: "e", 2721: "q", 2758: "2", 2800: "9", 2823: "5", 2851: "6", 3033: "9",
        3038: "S", 3054: "B", 3160: "g", 3244: "Q", 3254: "Q", 3266: "G", 3291: "S",
        3308: "B", 3414: "8", 3423: "g", 3514: "Q", 3538: "G", 3663: "m", 3667: "m",
        3698: "8", 3878: "3", 3968: "m", 4201: "3",
    }

    def solve(self, svg_content: str) -> str:
        candidates = []
        for match in re.finditer(r'd=["\']([^"\']+)["\']', svg_content or ""):
            path = match.group(1)
            if len(path) <= 500:
                continue
            x_match = re.search(r"(\d+(?:\.\d*)?)", path)
            candidates.append((float(x_match.group(1)) if x_match else 0.0, path))
        result = []
        for _, path in sorted(candidates, key=lambda item: item[0]):
            result.append(self._resolve_collision(len(path), path) or self.LENGTH_MAP.get(len(path), ""))
        return "".join(result)
    def _resolve_collision(self, length: int, path: str) -> str:
        min_y = self._min_y(path)
        move_y = self._move_y(path)
        width = self._width(path)
        if length in {986, 1068}:
            return "I" if min_y > 13 else "l"
        if length in {1274, 1380}:
            return "y" if move_y > 30 else "L"
        if length in {1610, 1744}:
            return "x" if min_y > 19 else "J"
        if length == 1615:
            return "r" if min_y > 18 else "N"
        if length in {2198, 2381}:
            return "n" if min_y > 19 else "C"
        if length == 2318:
            return "W" if width > 30 else "4"
        if length in {1598, 1731}:
            return "X" if min_y > 13 else "N"
        if length in {1694, 1835}:
            return "z" if min_y > 22 else "t"
        if length == 2279:
            return "R" if min_y > 13 else "M"
        return ""

    @staticmethod
    def _numbers(path: str) -> List[float]:
        return [float(item) for item in re.findall(r"(\d+(?:\.\d*)?)", path or "")]

    def _min_y(self, path: str) -> float:
        values = self._numbers(path)[1::2]
        return min(values) if values else 0.0

    def _move_y(self, path: str) -> float:
        match = re.search(r"M(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)", path or "")
        return float(match.group(2)) if match else 0.0

    def _width(self, path: str) -> float:
        values = self._numbers(path)[0::2]
        return max(values) - min(values) if values else 0.0
