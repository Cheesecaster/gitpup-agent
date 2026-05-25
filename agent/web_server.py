"""Agent API + SSE server + chat endpoint."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp import web
from agent.config import load_config
from agent.live_status import StatusManager

status_mgr = StatusManager()


async def handle_index(request):
    dist = request.app["web_dir"] / "dist"
    index = dist / "index.html"
    if index.exists():
        return web.FileResponse(index)
    return web.Response(text="Dashboard not built yet. Run 'cd web && npm run build'", status=404)


async def handle_sse(request):
    """SSE endpoint: streams agent status updates."""
    queue = status_mgr.register_client()
    resp = web.StreamResponse(
        status=200, reason="OK",
        headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
    await resp.prepare(request)

    try:
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30)
                event = f"data: {data}\n\n"
                await resp.write(event.encode())
            except asyncio.TimeoutError:
                await resp.write(b":keepalive\n\n")
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        status_mgr.unregister_client(queue)
    return resp


async def handle_chat(request):
    data = await request.json()
    user_message = data.get("message", "")
    if not user_message:
        return web.json_response({"error": "empty message"}, status=400)

    status_mgr.add_chat_message("user", user_message)
    await status_mgr.broadcast({"state": "chatting", "current_task": f"Responding to: {user_message[:50]}...", "mood": "curious"})

    # TODO: Integrate LLM for real responses
    response = f"🌿 I heard you say: '{user_message}'. Still learning to chat properly — my brain is growing! 🧠"

    status_mgr.add_chat_message("assistant", response)
    await status_mgr.broadcast({"state": "sleeping", "current_task": "", "mood": "peaceful"})
    return web.json_response({"response": response})


async def handle_api_status(request):
    return web.json_response(status_mgr._status.to_dict())


async def handle_api_journals(request):
    from agent.journal.journal import Journal
    journal = Journal("data/journal")
    return web.json_response({"entries": journal.get_entries(limit=50), "stats": journal.get_stats()})


async def handle_api_goals(request):
    goals_path = Path("GOALS.md")
    content = goals_path.read_text() if goals_path.exists() else "# No goals yet"
    return web.json_response({"content": content})


async def handle_webhook_gitlawb(request):
    event_type = request.headers.get("X-Gitlab-Event", "unknown")
    status_mgr.add_chat_message("system", f"GitLawb event: {event_type}")
    return web.Response(text="ok")


def create_app(web_dir: str = "web"):
    app = web.Application()
    app["web_dir"] = Path(web_dir)

    app.router.add_get("/api/status", handle_api_status)
    app.router.add_get("/api/journals", handle_api_journals)
    app.router.add_get("/api/goals", handle_api_goals)
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_post("/webhooks/gitlawb", handle_webhook_gitlawb)
    app.router.add_get("/sse", handle_sse)
    app.router.add_get("/", handle_index)
    return app


def main():
    host = os.environ.get("EVO_HOST", "0.0.0.0")
    port = int(os.environ.get("EVO_PORT", "3000"))
    web_dir = os.environ.get("WEB_DIR", "web")
    app = create_app(web_dir)
    print(f"🌱 Evo Garden API running at http://{host}:{port}")
    print(f"🌿 SSE stream: http://{host}:{port}/sse")
    print(f"🌸 Dashboard: http://{host}:{port}/")
    web.run_app(app, host=host, port=port, print=lambda _: None)


if __name__ == "__main__":
    main()
