from kubernetes import client, config, watch

import requests

STUDIO_SERVICE_NAME = "studio-studio"
STUDIO_SERVICE_PORT = "8080"
ENDPOINT = "api/app/status"

URL = f"http://{STUDIO_SERVICE_NAME}:{STUDIO_SERVICE_PORT}/{ENDPOINT}"

print(URL)


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

    headers = {
        "Authorization": "Token 2a493c77bc06b9d7f65f5135b6790bf6afa8ad02"
    }

    data = {
        "release": release,
        "status": status,
    }

    print("now with POST!!!")

    response = requests.post(URL, data=data, headers=headers, verify=False)

    print(f"response.status_code: {response.status_code}")
    print(f"POST TO: {URL}")


if __name__ == "__main__":
    init_event_listener()
