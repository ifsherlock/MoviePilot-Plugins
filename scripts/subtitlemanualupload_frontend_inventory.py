from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PAGE = REPO_ROOT / "plugins.v2" / "subtitlemanualupload" / "src" / "components" / "AppPage.vue"


SECTION_RE = re.compile(
    r"^<(?P<tag>script|template|style)\b(?P<attrs>[^>]*)>(?P<body>.*?)^</(?P=tag)>",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
STATIC_CLASS_RE = re.compile(r"(?<![:A-Za-z0-9_-])class\s*=\s*(['\"])(?P<value>.*?)(?<!\\)\1", re.DOTALL)
DYNAMIC_CLASS_RE = re.compile(r"(?<![A-Za-z0-9_-]):class\s*=\s*(['\"])(?P<value>.*?)(?<!\\)\1", re.DOTALL)
CSS_CLASS_RE = re.compile(r"(?<![A-Za-z0-9_-])\.([A-Za-z_][A-Za-z0-9_-]*)")
PROP_API_RE = re.compile(
    r"props\.api\.(?P<method>get|post|put|delete|patch)\(\s*`(?P<endpoint>\$\{pluginBase\.value\}[^`]*)`",
)
TEXT_ATTR_RE = re.compile(
    r"(?<![:A-Za-z0-9_-])(?P<name>label|title|placeholder|aria-label|alt)\s*=\s*(['\"])(?P<value>.*?)(?<!\\)\2",
    re.DOTALL,
)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"{{.*?}}", " ", data, flags=re.DOTALL)
        cleaned = _compact_text(cleaned)
        if cleaned:
            self.items.append(cleaned)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _sha256(value: str) -> str:
    return hashlib.sha256(_normalize_newlines(value).encode("utf-8")).hexdigest()


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _parse_sections(source: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    style_sections: list[dict[str, str]] = []
    for match in SECTION_RE.finditer(source):
        tag = match.group("tag").lower()
        item = {
            "attrs": match.group("attrs").strip(),
            "body": match.group("body"),
        }
        if tag == "style":
            style_sections.append(item)
            continue
        if tag in sections:
            raise ValueError(f"expected one <{tag}> section, found multiple")
        sections[tag] = item

    if "script" not in sections:
        raise ValueError("missing <script> section")
    if "template" not in sections:
        raise ValueError("missing <template> section")

    scoped_styles = [item for item in style_sections if re.search(r"\bscoped\b", item["attrs"])]
    if len(scoped_styles) != 1:
        raise ValueError(f"expected one scoped <style> section, found {len(scoped_styles)}")
    sections["style_scoped"] = scoped_styles[0]
    return sections


def _find_matching_brace(source: str, open_index: int) -> int:
    depth = 0
    quote = ""
    escape = False
    line_comment = False
    block_comment = False
    for index in range(open_index, len(source)):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
            continue
        if quote:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "/" and next_char == "/":
            line_comment = True
            continue
        if char == "/" and next_char == "*":
            block_comment = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("could not find matching brace")


def _split_top_level_items(source: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote = ""
    escape = False
    for index, char in enumerate(source):
        if quote:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth -= 1
            continue
        if char == "," and depth == 0:
            item = source[start:index].strip()
            if item:
                items.append(item)
            start = index + 1
    tail = source[start:].strip()
    if tail:
        items.append(tail)
    return items


def _define_expose_keys(script: str) -> list[str]:
    marker = "defineExpose"
    marker_index = script.find(marker)
    if marker_index < 0:
        return []
    open_brace = script.find("{", marker_index)
    if open_brace < 0:
        raise ValueError("defineExpose call has no object literal")
    close_brace = _find_matching_brace(script, open_brace)
    body = script[open_brace + 1 : close_brace]
    keys: list[str] = []
    for item in _split_top_level_items(body):
        if ":" in item:
            key = item.split(":", 1)[0].strip().strip("'\"")
        else:
            key = item.strip()
        if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", key):
            keys.append(key)
    return keys


def _endpoint_inventory(script: str) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for lineno, line in enumerate(script.splitlines(), start=1):
        for match in PROP_API_RE.finditer(line):
            endpoints.append(
                {
                    "method": match.group("method").upper(),
                    "endpoint": match.group("endpoint").replace("${pluginBase.value}", ""),
                    "raw": match.group("endpoint"),
                    "line": lineno,
                }
            )
    return endpoints


def _class_inventory(template: str, style: str) -> dict[str, Any]:
    static_classes: list[str] = []
    for match in STATIC_CLASS_RE.finditer(template):
        static_classes.extend(_compact_text(match.group("value")).split())

    dynamic_keys: list[str] = []
    dynamic_expressions: list[str] = []
    for match in DYNAMIC_CLASS_RE.finditer(template):
        expression = _compact_text(match.group("value"))
        dynamic_expressions.append(expression)
        if expression.startswith("{"):
            dynamic_keys.extend(re.findall(r"([A-Za-z_][A-Za-z0-9_-]*)\s*:", expression))
        for quoted in re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]", expression):
            dynamic_keys.append(quoted)

    style_classes = CSS_CLASS_RE.findall(style)
    template_classes = _unique(static_classes + dynamic_keys)
    style_unique = _unique(style_classes)
    return {
        "template_classes": sorted(template_classes),
        "template_class_count": len(set(template_classes)),
        "static_template_classes": sorted(_unique(static_classes)),
        "dynamic_class_keys": sorted(_unique(dynamic_keys)),
        "dynamic_class_expressions": _unique(dynamic_expressions),
        "style_class_selectors": sorted(style_unique),
        "style_class_selector_count": len(set(style_unique)),
        "style_selectors_not_in_template_inventory": sorted(set(style_unique) - set(template_classes)),
        "template_classes_without_style_selector": sorted(set(template_classes) - set(style_unique)),
    }


def _visible_text_inventory(template: str) -> dict[str, Any]:
    parser = _VisibleTextParser()
    parser.feed(template)

    attr_values: list[dict[str, str]] = []
    for match in TEXT_ATTR_RE.finditer(template):
        value = _compact_text(match.group("value"))
        if value and "{{" not in value:
            attr_values.append({"attr": match.group("name"), "text": value})

    text_nodes = _unique(parser.items)
    static_attr_texts = _unique([item["text"] for item in attr_values])
    all_texts = _unique(text_nodes + static_attr_texts)
    return {
        "text_nodes": text_nodes,
        "static_text_attributes": attr_values,
        "all_static_texts": all_texts,
        "all_static_text_count": len(all_texts),
    }


def build_inventory(*, details: bool = False) -> dict[str, Any]:
    source = APP_PAGE.read_text(encoding="utf-8")
    sections = _parse_sections(source)
    script = sections["script"]["body"]
    template = sections["template"]["body"]
    style = sections["style_scoped"]["body"]
    endpoint_items = _endpoint_inventory(script)
    class_items = _class_inventory(template, style)
    visible_text = _visible_text_inventory(template)

    inventory: dict[str, Any] = {
        "target": _relative(APP_PAGE),
        "line_count": len(source.splitlines()),
        "sections": {
            "script": {
                "attrs": sections["script"]["attrs"],
                "line_count": len(script.splitlines()),
                "sha256": _sha256(script),
            },
            "template": {
                "attrs": sections["template"]["attrs"],
                "line_count": len(template.splitlines()),
                "sha256": _sha256(template),
            },
            "style_scoped": {
                "attrs": sections["style_scoped"]["attrs"],
                "line_count": len(style.splitlines()),
                "sha256": _sha256(style),
            },
        },
        "define_expose_keys": _define_expose_keys(script),
        "endpoint_count": len(endpoint_items),
        "endpoints": endpoint_items if details else [item["endpoint"] for item in endpoint_items],
        "css_class_inventory": class_items,
        "visible_text_inventory": visible_text,
    }
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory SubtitleManualUpload AppPage.vue frontend surface.")
    parser.add_argument("--details", action="store_true", help="include endpoint method and line details")
    args = parser.parse_args()
    print(json.dumps(build_inventory(details=args.details), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
