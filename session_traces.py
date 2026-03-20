import argparse
import json

from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()


def fetch_session_traces(session_id: str) -> list[dict]:
    langfuse = get_client()
    session = langfuse.api.sessions.get(session_id)
    traces = [langfuse.api.trace.get(trace_id) for trace_id in session.traces]
    return [trace.model_dump(mode='json') for trace in traces]


def main():
    parser = argparse.ArgumentParser(
        description='Download all traces for a Langfuse session as JSON'
    )
    parser.add_argument('session_id', help='The Langfuse session ID')
    parser.add_argument('output', help='The file to write to')
    args = parser.parse_args()

    traces = fetch_session_traces(args.session_id)
    with open(args.output, 'w') as f:
        json.dump(traces, f, indent=2)


if __name__ == '__main__':
    main()
