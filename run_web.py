"""Entry point for the web interface."""

from sw_reviewer.config import configure_observability, load_config
from sw_reviewer.pipeline_agent import create_pipeline_agent
from sw_reviewer.interfaces.web import create_web_app

config = load_config()
configure_observability(config)
agent = create_pipeline_agent(config)
app = create_web_app(agent)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=7932)
