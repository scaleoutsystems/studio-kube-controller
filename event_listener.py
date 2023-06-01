from kubernetes import client, config, watch

import requests
import time

STUDIO_SERVICE_NAME = "studio-studio"
STUDIO_SERVICE_PORT = "8080"
APP_STATUS_ENDPOINT = "api/app/status"
TOKEN_ENDPOINT = "api/token-auth"

BASE_URL = f"http://{STUDIO_SERVICE_NAME}:{STUDIO_SERVICE_PORT}"
APP_STATUS_URL = f"{BASE_URL}/{APP_STATUS_ENDPOINT}"
TOKEN_URL = f"{BASE_URL}/{TOKEN_ENDPOINT}/"

USERNAME = "admin"
PASSWORD = "hejjagarettpassword123"


token = None

# Number of retries
max_retries = 10

# Time to wait between retries (in seconds)
retry_interval = 10


def get_token():
    print("get_token")

    req = {
        "username": USERNAME,
        "password": PASSWORD,
    }

    for retry in range(max_retries):
        print(f"retry: {retry}")

        try:
            res = requests.post(TOKEN_URL, json=req, verify=False)

            print(f"TOKEN_URL: {TOKEN_URL}")
            print(f"res.status_code: {res.status_code}")

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
        print(f"EVENT_TYPE: {event['type']}", flush=True)
        print(f"STATUS: {status}", flush=True)
        send_status_to_rest_api(release, status)


def send_status_to_rest_api(release, status):
    """
    TODO: Send the updated status phase to studio REST-API endpoint
    """
    print(f"UPDATE: {release} to {status}", flush=True)

    headers = {"Authorization": f"Token {token}"}

    data = {
        "release": release,
        "status": status,
    }

    response = requests.post(
        APP_STATUS_URL, data=data, headers=headers, verify=False
    )

    print(f"response.status_code: {response.status_code}")
    print(f"POST TO: {APP_STATUS_URL}")


if __name__ == "__main__":
    get_token()
    init_event_listener()
