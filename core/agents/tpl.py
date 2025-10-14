
import os

from jinja2 import Environment, FileSystemLoader, Template


class TemplateManager:
  
  def __init__(self, tpl_dir: str | None = None) -> None:
    if tpl_dir is None:
      tpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    
    self._env = Environment(
      loader=FileSystemLoader(tpl_dir), 
      auto_reload=True
    )
    
  def get_template(self, name) -> Template:
    if not name.endswith(".jinja"):
      name += ".jinja"  
    
    return self._env.get_template(name)
  
  def render(self, name: str, context: dict) -> str:
    tpl = self.get_template(name)
    return tpl.render(context)
