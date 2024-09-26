import os
from string import Template

template_dir = "templates"

class TemplateRenderer:
    def __init__(self, template_path):
        with open(template_path, "r", encoding="utf-8") as file:
            self.template = Template(file.read())
      
    def render(self, data):
        return self.template.safe_substitute(data)
        

MarkdownTemplate = TemplateRenderer(
    os.path.join(template_dir, "template.md")
)

HTMLTemplate = TemplateRenderer(
    os.path.join(template_dir, "template.html")
)

