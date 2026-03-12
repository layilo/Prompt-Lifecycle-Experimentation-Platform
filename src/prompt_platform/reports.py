from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from jinja2 import Template

from prompt_platform.utils import dump_json, ensure_dir


HTML_TEMPLATE = Template(
    """
    <html>
      <head>
        <title>{{ title }}</title>
        <style>
          body { font-family: Georgia, serif; margin: 2rem; background: linear-gradient(135deg, #f7f1e3, #dff9fb); color: #130f40; }
          table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
          th, td { border: 1px solid #30336b; padding: 0.5rem; text-align: left; }
          th { background: #22a6b3; color: white; }
          pre { background: #f0f3f5; padding: 1rem; }
        </style>
      </head>
      <body>
        <h1>{{ title }}</h1>
        <pre>{{ summary }}</pre>
        {% if rows %}
        <table>
          <thead>
            <tr>{% for key in rows[0].keys() %}<th>{{ key }}</th>{% endfor %}</tr>
          </thead>
          <tbody>
            {% for row in rows %}
            <tr>{% for value in row.values() %}<td>{{ value }}</td>{% endfor %}</tr>
            {% endfor %}
          </tbody>
        </table>
        {% endif %}
      </body>
    </html>
    """
)


class ReportBuilder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = ensure_dir(output_dir)

    def write(self, name: str, payload: dict[str, Any], fmt: str) -> Path:
        path = self.output_dir / f"{name}.{fmt}"
        if fmt == "json":
            dump_json(path, payload)
        elif fmt == "md":
            lines = [f"# {name}", "", "```json", str(payload), "```"]
            path.write_text("\n".join(lines), encoding="utf-8")
        elif fmt == "csv":
            rows = payload.get("leaderboard") or payload.get("snapshots") or []
            with path.open("w", newline="", encoding="utf-8") as handle:
                if rows:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    handle.write("key,value\n")
                    for key, value in payload.items():
                        handle.write(f"{key},{value}\n")
        elif fmt == "html":
            rows = payload.get("leaderboard") or payload.get("snapshots") or []
            path.write_text(HTML_TEMPLATE.render(title=name, summary=payload, rows=rows), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported report format: {fmt}")
        return path

