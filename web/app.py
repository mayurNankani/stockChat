"""
Stock Market Agent Web Application
Refactored architecture with clean separation of concerns
"""

import os
import sys
import traceback
from flask import Flask
from config import Config
from repositories import StockRepository
from services import LLMService, StockAnalysisService, FormattingService
from services.agent_tools import ToolExecutor
from services.agent_service import AgentService
from routes.stock_routes import init_stock_routes
from routes.api_routes import (
    init_api_routes,
    start_market_overview_refresh_worker,
    warm_market_overview_cache,
)


def create_app(config_object=None):
    """
    Application factory pattern
    
    Args:
        config_object: Configuration object (default: Config())
        
    Returns:
        Configured Flask application
    """
    # Initialize Flask app (serve frontend files from the web/ folder at /static/)
    web_dir = os.path.abspath(os.path.dirname(__file__))
    app = Flask(__name__, static_folder=web_dir, static_url_path='/static')
    
    # Load configuration
    if config_object is None:
        config_object = Config()

    # Validate configuration early — warn at startup, not mid-request
    if not config_object.validate():
        print("[WARN] Configuration validation failed — check API keys in .env")

    app.secret_key = config_object.SECRET_KEY
    
    # Initialize repository layer
    repository = StockRepository()
    
    # Initialize service layer
    llm_service = LLMService(config_object)
    formatting_service = FormattingService()
    stock_service = StockAnalysisService(repository=repository)
    tool_executor = ToolExecutor(repository=repository, stock_service=stock_service, formatting_service=formatting_service)
    agent_service = AgentService(
        llm_service=llm_service,
        tool_executor=tool_executor,
        formatting_service=formatting_service,
    )

    # Initialize and register blueprints
    stock_bp = init_stock_routes(agent_service)
    api_bp = init_api_routes(stock_service)
    
    app.register_blueprint(stock_bp)
    app.register_blueprint(api_bp)

    if config_object.MARKET_OVERVIEW_PRELOAD:
        should_start_background_worker = (
            not config_object.DEBUG or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        )
        if should_start_background_worker:
            warm_market_overview_cache(
                stock_service,
                cache_seconds=config_object.MARKET_OVERVIEW_CACHE_SECONDS,
            )
            started = start_market_overview_refresh_worker(
                stock_service,
                cache_seconds=config_object.MARKET_OVERVIEW_CACHE_SECONDS,
                refresh_interval_seconds=config_object.MARKET_OVERVIEW_REFRESH_SECONDS,
            )
            if started:
                print(
                    "[INFO] Market overview background refresh started "
                    f"(every {config_object.MARKET_OVERVIEW_REFRESH_SECONDS}s)."
                )
    
    return app


# Create application instance
try:
    print("Initializing application...")
    app = create_app()
    print("Application initialized successfully!")
except Exception as e:
    print(f"ERROR during app initialization: {e}")
    traceback.print_exc()
    sys.exit(1)


if __name__ == '__main__':
    try:
        print("=" * 60)
        print("Stock Market Analysis Agent")
        print("=" * 60)
        print(f"LLM Provider: {Config.LLM_PROVIDER}")
        if Config.LLM_PROVIDER == 'ollama':
            print(f"Ollama URL: {Config.OLLAMA_URL}")
            print(f"Available Models: {list(Config.MODEL_MAP.values())}")
        else:
            print("Using Gemini API")
        print("=" * 60)
        print("\nStarting server at http://127.0.0.1:5001")
        print("Press CTRL+C to stop\n")
        
        app.run(host='0.0.0.0', port=5001, debug=True)
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR: Failed to start application")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print(f"\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)
