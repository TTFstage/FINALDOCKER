from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]
    
    if debug_mode:
        app.run(debug=debug_mode)
    else:
        app.run(host='0.0.0.0', port=8080)
