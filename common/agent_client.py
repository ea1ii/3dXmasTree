import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SETTINGS_PATH = Path(__file__).with_name("settings.json")


class AgentError(RuntimeError):
    pass


def load_settings():
    with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
        return json.load(settings_file)


def save_settings(settings):
    temporary_path = SETTINGS_PATH.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)
        settings_file.write("\n")
    os.replace(temporary_path, SETTINGS_PATH)


def _request(agent_name, endpoint, settings, method="GET", payload=None):
    token_env = settings["agents"].get("token_env", "XMAS_AGENT_TOKEN")
    token = os.environ.get(token_env)
    if not token:
        raise AgentError(f"Set {token_env} on the command-center computer first")

    agent = settings["agents"][agent_name]
    url = f"http://{agent['host']}:{agent['port']}{endpoint}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    timeout = settings["agents"].get("timeout_seconds", 5)

    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get_content_type()
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(message).get("error", message)
        except json.JSONDecodeError:
            pass
        raise AgentError(f"{agent_name} agent: {message}") from error
    except (TimeoutError, URLError, OSError) as error:
        raise AgentError(f"Cannot reach {agent_name} agent at {url}: {error}") from error


def request_json(agent_name, endpoint, settings, method="GET", payload=None):
    response, _ = _request(agent_name, endpoint, settings, method, payload)
    return json.loads(response.decode("utf-8"))


def request_image(agent_name, endpoint, settings):
    response, content_type = _request(agent_name, endpoint, settings)
    if not content_type.startswith("image/"):
        raise AgentError(f"{agent_name} agent returned {content_type}, not an image")
    return response