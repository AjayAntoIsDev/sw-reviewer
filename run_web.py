"""Entry point for the web interface."""

from sw_reviewer.config import configure_observability, load_config
from sw_reviewer.agent import create_agent
from sw_reviewer.interfaces.web import create_web_app

config = load_config()
configure_observability(config)
agent = create_agent(config)
app = create_web_app(agent)
