"""The Q-GPT / Onyx API contract used by the load rig — one place to confirm.

Every function here builds a request path or payload for the backend. They are
modelled on the Onyx (formerly Danswer) default REST API, since the SPA uses
``onyx-*`` test IDs, but the staging deployment may have customised them.

>>> HOW TO CONFIRM (≈5 minutes, before the first real run):
    1. Log in to staging in a browser, open DevTools → Network (preserve log).
    2. Send one chat prompt          -> confirm send_message path + JSON body + stream format.
    3. Upload one file in chat       -> confirm file_upload path + multipart field name + response id.
    4. Run one document/RAG query    -> confirm how retrieval is triggered (send_message flag vs. search endpoint).
    5. Note the auth request         -> confirm login path + whether a cookie or bearer token is returned.
    Update load/load_config.json (endpoints/auth) and the payload builders below to match.

Nothing here performs I/O; builders return data for the caller to send.
"""

from load import settings


# --- Paths ------------------------------------------------------------------
def create_chat_session_path():
    return settings.EP["create_chat_session"]


def send_message_path():
    return settings.EP["send_message"]


def file_upload_path():
    return settings.EP["file_upload"]


def document_search_path():
    return settings.EP["document_search"]


# --- Payload builders (TODO CONFIRM shapes) ---------------------------------
def create_chat_session_payload():
    """Body for opening a fresh chat session.

    Onyx default: persona_id 0 is the built-in default assistant.
    """
    return {
        "persona_id": 0,
        "description": "locust-load",
    }


def _model_override():
    """Field(s) that pin the request to the stub or real model.

    TODO CONFIRM: staging may take the model via a payload field like this,
    or via a header, or via the persona. Kept in one helper so the whole rig
    switches in one place.
    """
    return {
        "llm_override": {
            "model_provider": "loadtest",
            "model_version": settings.MODEL_NAME,
        }
    }


def send_message_payload(
    chat_session_id,
    message,
    parent_message_id=None,
    file_ids=None,
    use_retrieval=False,
    top_k=None,
):
    """Body for POST send-message.

    ``use_retrieval`` toggles the RAG/vector path (S03). ``file_ids`` attaches
    previously uploaded documents (S04/S05 ingestion). Onyx streams the reply
    as newline-delimited JSON; see load/support.py for parsing.
    """
    payload = {
        "chat_session_id": chat_session_id,
        "message": message,
        "parent_message_id": parent_message_id,
        "file_descriptors": [{"id": fid} for fid in (file_ids or [])],
        "prompt_id": None,
        "search_doc_ids": None,
        "retrieval_options": (
            {
                "run_search": "always",
                "real_time": True,
                "top_k": top_k or settings.RAG_TOP_K,
            }
            if use_retrieval
            else {"run_search": "never"}
        ),
        "stream_response": True,
    }
    payload.update(_model_override())
    return payload


def file_upload_files(filename, content, content_type="application/octet-stream"):
    """multipart 'files' argument for the upload endpoint.

    TODO CONFIRM the form field name — Onyx has historically used both 'files'
    and 'file'. Returns a structure suitable for requests' ``files=`` kwarg.
    """
    return {"files": (filename, content, content_type)}


def document_search_payload(query, top_k=None):
    """Body for a standalone vector/document search (S03 isolated).

    Used when measuring vector-search QPS per vCPU without generation. If
    staging has no standalone search endpoint, drive S03 through send-message
    with use_retrieval=True instead.
    """
    return {
        "query": query,
        "filters": {},
        "recency_bias_multiplier": 1.0,
        "num_hits": top_k or settings.RAG_TOP_K,
    }
