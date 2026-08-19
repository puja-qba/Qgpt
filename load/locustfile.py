"""Q-GPT capacity load rig — weighted scenario mix for the doable calculator inputs.

Each task maps to one row of the capacity calculator and is tagged with its
scenario id so it can be run in isolation, e.g.::

    locust -f load/locustfile.py --tags s03      # vector-search only (S03/S12)
    locust -f load/locustfile.py --tags s05      # heavy ingestion only (S05/S16)

With no --tags, users pick tasks by the S12 mix weights in load_config.json.

Coverage (the "doable" load scenarios):
    S01/S08  stateless_prompt      baseline sessions + held stream + output tokens
    S02      conversation_prompt   conversation-history token amplification
    S03/S12  rag_document_query    RAG context tokens + vector-search QPS
    S04      ingest_light          light file ingestion
    S05/S16  ingest_heavy          heavy file ingestion + worker capacity
    S06/S07  agentic_mcp_prompt    MCP calls per prompt + agentic call count

Per-request calculator quantities (tokens, MCP calls, stream hold, ingest time)
are emitted as 'metric:*' rows via support.record_metric — read those in the
Locust stats/CSV. Infra-shaped outputs (S13/S15/S18/S20 knee, burst, autoscaler)
come from the run profile / load shapes in load/shapes.py, not a task.

This file defines behaviour only. It does not start a run; launch with `locust`.
"""

import uuid

from locust import HttpUser, task, tag, between

from load import api, settings, support


class QGPTUser(HttpUser):
    """One synthetic Q-GPT session (S01 baseline session unit)."""

    host = settings.HOST
    wait_time = between(settings.WAIT_MIN, settings.WAIT_MAX)

    def on_start(self):
        """Authenticate once and open a chat session for this user."""
        self.authed = support.authenticate(self.client)
        self.chat_session_id = None
        self.parent_message_id = None
        if self.authed:
            self._open_chat_session()

    # --- session helpers ----------------------------------------------------
    def _open_chat_session(self):
        with self.client.post(
            api.create_chat_session_path(),
            json=api.create_chat_session_payload(),
            name="chat:create-session",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                try:
                    self.chat_session_id = resp.json().get("chat_session_id")
                    resp.success()
                except ValueError:
                    resp.failure("create-session: non-JSON response")
            else:
                resp.failure(f"create-session: HTTP {resp.status_code}")

    def _ready(self):
        return self.authed and self.chat_session_id is not None

    def _send_prompt(self, message, name, use_retrieval=False, file_ids=None):
        """POST a prompt, drain the stream, and record the derived metrics.

        Shared by every prompt-shaped scenario. Records held-stream duration
        (S08), output tokens (S08), and MCP/tool calls (S06/S07) per request.
        """
        if not self._ready():
            return
        payload = api.send_message_payload(
            self.chat_session_id,
            message,
            parent_message_id=self.parent_message_id,
            file_ids=file_ids,
            use_retrieval=use_retrieval,
        )
        with self.client.post(
            api.send_message_path(),
            json=payload,
            name=name,
            stream=True,
            timeout=settings.STREAM_HOLD_TIMEOUT,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"{name}: HTTP {resp.status_code}")
                return
            result = support.consume_stream(resp)
            resp.success()

        support.record_metric("stream_hold_ms", result["hold_seconds"] * 1000)
        support.record_metric("output_tokens", result["output_tokens"])
        if result["first_token_s"] is not None:
            support.record_metric("ttft_ms", result["first_token_s"] * 1000)
        if use_retrieval:
            support.record_metric("rag_prompt_tokens", support.estimate_tokens(message))
        if result["tool_calls"]:
            support.record_metric("mcp_calls", result["tool_calls"])

    def _upload_file(self, size_bytes, tag_name):
        """Upload one synthetic file and return its id, timing the ingestion."""
        import time

        filename, content = support.make_file(size_bytes, tag_name)
        start = time.time()
        with self.client.post(
            api.file_upload_path(),
            files=api.file_upload_files(filename, content),
            name=f"file:upload-{tag_name}",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"upload-{tag_name}: HTTP {resp.status_code}")
                return None
            support.record_metric("ingest_ms", (time.time() - start) * 1000)
            try:
                # TODO CONFIRM the id field in the upload response.
                data = resp.json()
                file_id = data[0]["id"] if isinstance(data, list) else data.get("id")
                resp.success()
                return file_id
            except (ValueError, KeyError, IndexError, TypeError):
                resp.failure(f"upload-{tag_name}: unexpected response shape")
                return None

    # --- Scenarios (weights come from the S12 mix table) --------------------
    @tag("s01", "s08", "generative")
    @task(settings.MIX["stateless_prompt"])
    def stateless_prompt(self):
        """S01/S08 — single-turn generative prompt; baseline session load."""
        self._send_prompt(
            f"Give me a two-paragraph status update. ref={uuid.uuid4().hex[:8]}",
            name="chat:stateless-prompt",
        )

    @tag("s02", "conversation")
    @task(settings.MIX["conversation_prompt"])
    def conversation_prompt(self):
        """S02 — multi-turn conversation amplifying input tokens via history."""
        for turn in range(settings.CONVERSATION_TURNS):
            self._send_prompt(
                f"Continuing our discussion, elaborate on point {turn + 1}.",
                name="chat:conversation-turn",
            )

    @tag("s03", "s12", "rag", "vector")
    @task(settings.MIX["rag_document_query"])
    def rag_document_query(self):
        """S03/S12 — retrieval-augmented prompt; drives vector search + RAG tokens."""
        self._send_prompt(
            "Based on our internal documents, summarise the QA onboarding process.",
            name="chat:rag-query",
            use_retrieval=True,
        )

    @tag("s04", "ingest", "light")
    @task(settings.MIX["ingest_light"])
    def ingest_light(self):
        """S04 — light file upload followed by a prompt about it."""
        file_id = self._upload_file(settings.LIGHT_FILE_BYTES, "light")
        if file_id is not None:
            self._send_prompt(
                "Summarise the attached document.",
                name="chat:prompt-with-light-file",
                file_ids=[file_id],
            )

    @tag("s05", "s16", "ingest", "heavy")
    @task(settings.MIX["ingest_heavy"])
    def ingest_heavy(self):
        """S05/S16 — heavy file upload; stresses ingestion workers + NAT egress."""
        file_id = self._upload_file(settings.HEAVY_FILE_BYTES, "heavy")
        if file_id is not None:
            self._send_prompt(
                "Extract the key findings from the attached document.",
                name="chat:prompt-with-heavy-file",
                file_ids=[file_id],
            )

    @tag("s06", "s07", "agentic", "mcp")
    @task(settings.MIX["agentic_mcp_prompt"])
    def agentic_mcp_prompt(self):
        """S06/S07 — agentic prompt that fans out into MCP/tool calls."""
        self._send_prompt(
            "List my recent Teams chats and summarise the latest one.",
            name="chat:agentic-mcp",
        )
