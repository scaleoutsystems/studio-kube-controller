from kubernetes import client, config, watch

import os
import requests
import time

STUDIO_SERVICE_NAME = os.environ.get("STUDIO_SERVICE_NAME", None)
STUDIO_SERVICE_PORT = os.environ.get("STUDIO_SERVICE_PORT", None)
APP_STATUS_ENDPOINT = os.environ.get("APP_STATUS_ENDPOINT", None)
APP_STATUSES_ENDPOINT = os.environ.get("APP_STATUSES_ENDPOINT", None)
TOKEN_ENDPOINT = os.environ.get("TOKEN_ENDPOINT", None)

BASE_URL = f"http://{STUDIO_SERVICE_NAME}:{STUDIO_SERVICE_PORT}"
APP_STATUS_URL = f"{BASE_URL}/{APP_STATUS_ENDPOINT}"
APP_STATUSES_URL = f"{BASE_URL}/{APP_STATUSES_ENDPOINT}"
TOKEN_URL = f"{BASE_URL}/{TOKEN_ENDPOINT}"

USERNAME = os.environ.get("EVENT_LISTENER_USERNAME", None)
PASSWORD = os.environ.get("EVENT_LISTENER_PASSWORD", None)

K8S_STATUS_MAP = {
    "CrashLoopBackOff": "Error",
    "Completed": "Retrying...",
    "ContainerCreating": "Created",
    "PodInitializing": "Pending",
}

token = None

# Number of retries
max_retries = 10

# Time to wait between retries (in seconds)
retry_interval = 10

config.incluster_config.load_incluster_config()

api = client.CoreV1Api()
w = watch.Watch()

label_selector = "type=app"
namespace = "default"

latest_status = {}


def get_token():
    req = {
        "username": USERNAME,
        "password": PASSWORD,
    }

    for retry in range(max_retries):
        print(f"retry: {retry}")

        try:
            res = requests.post(TOKEN_URL, json=req, verify=False)

            if res.status_code == 200:
                resp = res.json()

                if "token" in resp:
                    print("Token retrieved successfully.")
                    global token
                    token = resp["token"]
                    return True
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

    return False


def sync_all_statuses():
    values = ""

    for pod in api.list_namespaced_pod(
        namespace=namespace, label_selector=label_selector
    ).items:
        status = pod.status.phase
        release = pod.metadata.labels["release"]

        values += f"{release}:{status},"

    data = {"values": values}

    print(f"DATA: {data}", flush=True)
    print("Syncing all statuses...", flush=True)

    post(APP_STATUSES_URL, data=data)


def init_event_listener():
    for event in w.stream(
        api.list_namespaced_pod,
        namespace=namespace,
        label_selector=label_selector,
    ):
        pod = event["object"]

        status = get_status(pod)

        print(f"Synchronizing status: {status}", flush=True)

        # status = pod.status.phase
        release = pod.metadata.labels["release"]

        event_type = event["type"]

        if latest_status.get(release) == status:
            print("Status not changed, skipping...")

        latest_status[release] = status

        if event_type != "DELETED":
            print(f"EVENT_TYPE: {event_type}", flush=True)
            print(f"STATUS: {status}", flush=True)

            data = {
                "release": release,
                "status": status,
            }

            post(APP_STATUS_URL, data=data)


def get_status(pod):
    """
    Returns the status of a pod by looping through each container
    and checking the status.
    """
    container_statuses = pod.status.container_statuses

    if container_statuses is not None:
        for container_status in container_statuses:
            state = container_status.state

            if state is not None:
                terminated = state.terminated

                if terminated is not None:
                    reason = terminated.reason
                    return mapped_status(reason)

                waiting = state.waiting

                if waiting is not None:
                    reason = waiting.reason
                    return mapped_status(reason)
        else:
            running = state.running
            ready = container_status.ready
            if running and ready:
                return "Running"
            else:
                return "Pending"

    return pod.status.phase


def mapped_status(reason: str) -> str:
    return K8S_STATUS_MAP.get(reason, reason)


def post(url, data):
    try:
        headers = {"Authorization": f"Token {token}"}

        response = requests.post(url, data=data, headers=headers, verify=False)

        print(f"RESPONSE STATUS CODE: {response.status_code}")
        print(f"RESPONSE TEXT: {response.text}")

    except requests.exceptions.RequestException:
        print("Service did not respond.")


if __name__ == "__main__":
    success = get_token()

    if success:
        sync_all_statuses()
        init_event_listener()
