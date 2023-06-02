from kubernetes import client, config, watch

import os
import requests
import time

STUDIO_SERVICE_NAME = os.environ.get("STUDIO_SERVICE_NAME", None)
STUDIO_SERVICE_PORT = os.environ.get("STUDIO_SERVICE_PORT", None)
APP_STATUS_ENDPOINT = os.environ.get("APP_STATUS_ENDPOINT", None)
TOKEN_ENDPOINT = os.environ.get("TOKEN_ENDPOINT", None)

BASE_URL = f"http://{STUDIO_SERVICE_NAME}:{STUDIO_SERVICE_PORT}"
APP_STATUS_URL = f"{BASE_URL}/{APP_STATUS_ENDPOINT}"
TOKEN_URL = f"{BASE_URL}/{TOKEN_ENDPOINT}"

USERNAME = os.environ.get("EVENT_LISTENER_USERNAME", None)
PASSWORD = os.environ.get("EVENT_LISTENER_PASSWORD", None)

print(f"APP_STATUS_URL: {APP_STATUS_URL}")
print(f"TOKEN_URL: {TOKEN_URL}")

token = None

# Number of retries
max_retries = 10

# Time to wait between retries (in seconds)
retry_interval = 10


def get_token():
    req = {
        "username": USERNAME,
        "password": PASSWORD,
    }

    for retry in range(max_retries):
        print(f"retry: {retry}")

        try:
            res = requests.post(TOKEN_URL, json=req, verify=False)

            print(f"Get token res.status_code: {res.status_code}")

            if res.status_code == 200:
                resp = res.json()

                if "token" in resp:
                    print("Token retrieved successfully.")
                    global token
                    token = resp["token"]
                    break
                else:
                    print("Failed to fetch token.")
                    print(res.text)

        except requests.exceptions.RequestException:
            # An exception occurred, service is not responding
            if retry == max_retries - 1:
                # Maximum retries reached, handle the failure
                print("Service did not respond.")
                break

            # Wait for the specified interval before retrying
            time.sleep(retry_interval)


def init_event_listener():
    config.incluster_config.load_incluster_config()

    api = client.CoreV1Api()
    w = watch.Watch()

    label_selector = "type=app"
    namespace = "default"

    for event in w.stream(
        api.list_namespaced_pod,
        namespace=namespace,
        label_selector=label_selector,
    ):
        pod = event["object"]
        status = pod.status.phase
        release = pod.metadata.labels["release"]

        event_type = event["type"]

        print(f"EVENT_TYPE: {event_type}", flush=True)

        if event_type != "DELETED":
            print(f"STATUS: {status}", flush=True)
            send_status_to_rest_api(release, status)


def send_status_to_rest_api(release, status):
    print(f"UPDATE: {release} to {status}", flush=True)

    headers = {"Authorization": f"Token {token}"}

    data = {
        "release": release,
        "status": status,
    }

    response = requests.post(
        APP_STATUS_URL, data=data, headers=headers, verify=False
    )

    print(f"RESPONSE STATUS CODE: {response.status_code}")


if __name__ == "__main__":
    get_token()
    init_event_listener()
