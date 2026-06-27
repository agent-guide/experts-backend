from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app


HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _schema_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _format_schema(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "-"
    if "$ref" in schema:
        return _schema_name(str(schema["$ref"]))
    if "type" in schema:
        schema_type = str(schema["type"])
        if schema_type == "array":
            return f"array[{_format_schema(schema.get('items'))}]"
        return schema_type
    if "allOf" in schema:
        return " | ".join(_format_schema(item) for item in schema["allOf"])
    if "anyOf" in schema:
        return " | ".join(_format_schema(item) for item in schema["anyOf"])
    return json.dumps(schema, ensure_ascii=False)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        safe_row = [cell.replace("\n", "<br>").replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(safe_row) + " |")
    return lines


def _request_body(operation: dict[str, Any]) -> list[list[str]]:
    body = operation.get("requestBody")
    if not body:
        return []

    rows: list[list[str]] = []
    required = "yes" if body.get("required") else "no"
    for content_type, content in body.get("content", {}).items():
        rows.append(
            [
                "body",
                content_type,
                required,
                _format_schema(content.get("schema")),
                body.get("description", "-"),
            ]
        )
    return rows


def _parameters(operation: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for parameter in operation.get("parameters", []):
        rows.append(
            [
                parameter.get("in", "-"),
                parameter.get("name", "-"),
                "yes" if parameter.get("required") else "no",
                _format_schema(parameter.get("schema")),
                parameter.get("description", "-"),
            ]
        )
    rows.extend(_request_body(operation))
    return rows


def _responses(operation: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for status_code, response in operation.get("responses", {}).items():
        content = response.get("content", {})
        if not content:
            rows.append([status_code, "-", response.get("description", "-")])
            continue
        for content_type, payload in content.items():
            rows.append(
                [
                    status_code,
                    content_type,
                    _format_schema(payload.get("schema")),
                ]
            )
    return rows


def build_markdown(schema: dict[str, Any]) -> str:
    title = schema.get("info", {}).get("title", "API Reference")
    version = schema.get("info", {}).get("version", "-")
    grouped: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}

    for path, path_item in schema.get("paths", {}).items():
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not operation:
                continue
            tag = operation.get("tags", ["Other"])[0]
            grouped.setdefault(tag, []).append((method.upper(), path, operation))

    lines = [
        f"# {title}",
        "",
        f"Version: `{version}`",
        "",
        "This document is generated from the FastAPI OpenAPI schema.",
        "",
    ]

    for tag in sorted(grouped):
        lines.extend([f"## {tag}", ""])
        for method, path, operation in sorted(grouped[tag], key=lambda item: (item[1], item[0])):
            summary = operation.get("summary") or operation.get("operationId") or "-"
            description = operation.get("description")
            lines.extend(
                [
                    f"### {method} `{path}`",
                    "",
                    f"- Summary: {summary}",
                ]
            )
            if description:
                lines.append(f"- Description: {description}")
            lines.append("")

            input_rows = _parameters(operation)
            lines.extend(["#### Input Parameters", ""])
            if input_rows:
                lines.extend(
                    _markdown_table(
                        ["Location", "Name", "Required", "Type", "Description"],
                        input_rows,
                    )
                )
            else:
                lines.append("No input parameters.")
            lines.append("")

            response_rows = _responses(operation)
            lines.extend(["#### Response", ""])
            if response_rows:
                lines.extend(_markdown_table(["Status", "Content Type", "Schema"], response_rows))
            else:
                lines.append("No response schema.")
            lines.append("")

    components = schema.get("components", {}).get("schemas", {})
    if components:
        lines.extend(["## Schemas", ""])
        for name in sorted(components):
            lines.extend([f"### `{name}`", ""])
            component = components[name]
            properties = component.get("properties", {})
            required = set(component.get("required", []))
            if properties:
                rows = []
                for prop_name, prop_schema in properties.items():
                    rows.append(
                        [
                            prop_name,
                            "yes" if prop_name in required else "no",
                            _format_schema(prop_schema),
                            prop_schema.get("description", "-"),
                        ]
                    )
                lines.extend(_markdown_table(["Field", "Required", "Type", "Description"], rows))
            else:
                lines.append(f"`{json.dumps(component, ensure_ascii=False)}`")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export FastAPI OpenAPI schema.")
    parser.add_argument(
        "--output",
        default="docs/api/API_REFERENCE.md",
        help="Markdown output path.",
    )
    parser.add_argument(
        "--json-output",
        default="docs/api/openapi.json",
        help="OpenAPI JSON output path.",
    )
    args = parser.parse_args()

    schema = app.openapi()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(schema), encoding="utf-8")
    print(f"Wrote {output}")

    json_output = Path(args.json_output)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {json_output}")


if __name__ == "__main__":
    main()
