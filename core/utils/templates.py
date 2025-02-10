"""Template rendering utilities."""

import os
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape
from core.config import settings

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(settings.EMAIL_TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render a template with the given context."""
    try:
        template = env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        raise ValueError(f"Error rendering template {template_name}: {str(e)}") 