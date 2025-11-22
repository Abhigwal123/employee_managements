"""
Flask Application Entry Point
Run with: python flask_app.py --port 8000
"""
import sys
import os
import argparse
import logging
from app import create_app

# Configure logging for startup messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check Google Sheets service availability at startup
from app.utils.trace_logger import trace_startup
trace_startup("Testing Google Sheets import readiness")

logger.info("Checking Google Sheets service availability...")
try:
    from app.services.google_sheets_import import _try_import_google_sheets
    success, path = _try_import_google_sheets()
    if success:
        logger.info(f"✅ Google Sheets service ready (loaded from: {path})")
        trace_startup(f"Google Sheets ready (loaded from: {path})")
    else:
        logger.warning("⚠️ Google Sheets service not available - some features may be limited")
        trace_startup("Google Sheets not ready, will retry at runtime")
except Exception as e:
    logger.warning(f"⚠️ Could not check Google Sheets service: {e}")
    trace_startup(f"Google Sheets check failed: {e}")

# Create app instance
try:
    app = create_app()
except Exception as e:
    print(f"\n❌ ERROR: Failed to create Flask app: {e}", file=sys.stderr)
    print(f"   Error type: {type(e).__name__}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)


DEFAULT_HOST = os.getenv("FLASK_HOST", "localhost")  # Use 0.0.0.0 in Docker
DEFAULT_PORT = 8000


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Flask Backend Server')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST, help='Host to bind to (default: localhost, use 0.0.0.0 for Docker)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to run the server on (default: 8000)')
    args = parser.parse_args()
    
    try:
        print("\n" + "="*80)
        print("  Flask Backend Server Starting")
        print("="*80)
        bind_address = args.host if args.host != "0.0.0.0" else "0.0.0.0"
        print(f"\n✓ Running on http://{bind_address}:{args.port}")
        print(f"✓ API endpoints available at: http://{bind_address}:{args.port}/api/v1/")
        print("\nPress Ctrl+C to stop\n")
        print("="*80 + "\n")
        
        # In Docker, bind to 0.0.0.0 to accept connections from outside container
        # In local development, bind to localhost for security
        app.run(debug=False, host=args.host, port=args.port, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\n❌ ERROR: Server failed to start: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
