from flask import Flask, request, Response, stream_with_context, jsonify
import requests
import random
import os
from functools import wraps

app = Flask(__name__)
# Target API base URL
TARGET_API = "https://openrouter.ai"

# Path mappings
PATH_MAPPINGS = {
    "/api/v1/chat": "/api/v1/chat",
    "/api/v1/models": "/api/v1/models"
}

# Get API keys from environment variable
def get_api_keys():
    api_keys_str = os.environ.get('API_KEYS', '')
    if not api_keys_str:
        return []
    return [key.strip() for key in api_keys_str.split(',') if key.strip()]

# Get authentication token from environment variable
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '666')

# Authentication decorator for POST requests
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            auth_header = request.headers.get('Authorization')
            if not auth_header or auth_header != f"Bearer {AUTH_TOKEN}":
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route('/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    # Construct the full path
    full_path = f"/{path}"

    # Apply path mapping if matches
    for original_path, new_path in PATH_MAPPINGS.items():
        if full_path.startswith(original_path):
            full_path = full_path.replace(original_path, new_path, 1)
            break

    # Construct target URL
    target_url = f"{TARGET_API}{full_path}"

    # Forward the request to the target API
    headers = {key: value for key, value in request.headers if key != 'Host'}

    # Get API keys and select a random one if available
    api_keys = get_api_keys()
    if api_keys:
        random_key = random.choice(api_keys)
        headers['Authorization'] = f"Bearer {random_key}"

    # Handle POST requests with streaming
    if request.method == 'POST':
        response = requests.post(
            target_url,
            headers=headers,
            json=request.get_json(silent=True),
            params=request.args,
            stream=True
        )

        # Create a streaming response for POST
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk

        # Create flask streaming response
        proxy_response = Response(
            stream_with_context(generate()),
            status=response.status_code
        )

    # Handle GET requests without streaming
    elif request.method == 'GET':
        response = requests.get(
            target_url,
            headers=headers,
            params=request.args
        )

        # Create a regular response for GET
        proxy_response = Response(
            response.content,
            status=response.status_code,
            mimetype=response.headers.get('Content-Type')
        )
        return proxy_response

    # Forward response headers
    for key, value in response.headers.items():
        if key.lower() not in ('content-length', 'transfer-encoding', 'connection'):
            proxy_response.headers[key] = value

    return proxy_response


@app.route('/', methods=['GET'])
def index():
    return "Service is running."


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=True)
