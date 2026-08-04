"""The embeddable widget.

This is the file the integrations page has been telling sellers to paste. It did
not exist, which made the whole page a screenshot of an integration — the fair
version of the complaint that the mechanisms "don't look practically functional".

Three decisions worth knowing:

**Shadow DOM.** Everything renders inside a closed-ish shadow root with its own
styles. A support widget that inherits a storefront's CSS is a widget that looks
broken on every third site, and one that leaks its own CSS is worse.

**No build step and no dependencies.** It is hand-written ES5-compatible-ish JS
served as one file. A widget that needs a bundler is a widget that goes stale;
this one is auditable by the seller pasting it, which matters when you are asking
them to run your script on their checkout page.

**The key is public and does nothing on its own.** It identifies the tenant and
authorises exactly one endpoint, `/chat/public`. Origin checking happens server
side; nothing here is a security control, and nothing here should be trusted to
be one.
"""

from __future__ import annotations

from app.core.config import get_settings

# Kept in one string rather than a static file so the API base can be baked in at
# request time — a seller pasting a snippet should not also have to configure a
# URL, and a mismatch between the two is a silent failure that looks like the
# agent is down.
_TEMPLATE = r"""
/* Digital FTE widget. Served by the API; safe to read before you paste it. */
(function () {
  "use strict";

  var API = "__API_BASE__";

  /* The key comes off our own <script> tag. Reading it from the DOM rather than
     asking the seller to call an init function means the snippet is one line and
     has no ordering requirements. */
  var script =
    document.currentScript ||
    (function () {
      var all = document.getElementsByTagName("script");
      for (var i = all.length - 1; i >= 0; i--) {
        if (all[i].getAttribute("data-fte-key")) return all[i];
      }
      return null;
    })();

  if (!script) return;
  var KEY = script.getAttribute("data-fte-key");
  if (!KEY) return;
  if (window.__fteWidgetMounted) return;
  window.__fteWidgetMounted = true;

  var LAUNCHER_LABEL = script.getAttribute("data-fte-label") || "Support";
  /* A session id per browser tab. Persisted so a refresh mid-conversation does
     not lose the identity the customer already proved. */
  var SESSION_KEY = "fte.widget.session";
  var session;
  try {
    session = sessionStorage.getItem(SESSION_KEY);
  } catch (e) {
    session = null;
  }
  if (!session) {
    session = "w-" + Math.random().toString(36).slice(2, 10);
    try {
      sessionStorage.setItem(SESSION_KEY, session);
    } catch (e) {}
  }

  var host = document.createElement("div");
  host.setAttribute("data-fte-widget", "");
  host.style.cssText = "position:fixed;z-index:2147483000;right:0;bottom:0;";
  document.body.appendChild(host);
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  var style = document.createElement("style");
  style.textContent = [
    ":host,*{box-sizing:border-box}",
    ".launcher{position:fixed;right:20px;bottom:20px;height:52px;min-width:52px;",
    "padding:0 18px;border:0;border-radius:8px;cursor:pointer;color:#fff;",
    "font:500 14px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;",
    "background:linear-gradient(180deg,#870775,#4d0342);",
    "box-shadow:0 6px 18px -6px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.12)}",
    ".launcher:hover{background:linear-gradient(180deg,#96087f,#870775)}",
    ".panel{position:fixed;right:20px;bottom:84px;width:370px;max-width:calc(100vw - 32px);",
    "height:520px;max-height:calc(100vh - 120px);display:flex;flex-direction:column;",
    "background:#0f0f12;border:1px solid #26262c;border-radius:10px;overflow:hidden;",
    "box-shadow:0 20px 48px -20px rgba(0,0,0,.85);",
    "font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#d6d6db}",
    ".hd{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #26262c;",
    "background:linear-gradient(180deg,#1c1c21,#16161a)}",
    ".hd b{font-size:13px;color:#fafafa;font-weight:600}",
    ".hd small{color:#6b6b75;font-size:11px}",
    ".x{margin-left:auto;background:0;border:0;color:#9d9da6;cursor:pointer;font-size:18px;line-height:1}",
    ".log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}",
    ".m{max-width:85%;padding:8px 11px;border-radius:8px;font-size:13.5px;white-space:pre-wrap;word-wrap:break-word}",
    ".me{align-self:flex-end;background:rgba(135,7,117,.22);border:1px solid rgba(135,7,117,.45);color:#fafafa}",
    ".it{align-self:flex-start;background:#16161a;border:1px solid #26262c}",
    ".er{align-self:flex-start;background:rgba(251,113,133,.08);border:1px solid rgba(251,113,133,.3);color:#fb7185}",
    ".chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px;align-self:flex-start}",
    ".chip{font-size:10.5px;padding:2px 6px;border-radius:4px;border:1px solid #26262c;color:#9d9da6}",
    ".ft{display:flex;gap:6px;padding:10px;border-top:1px solid #26262c;background:#0f0f12}",
    ".ft input{flex:1;min-width:0;background:#16161a;border:1px solid #26262c;border-radius:8px;",
    "padding:9px 11px;color:#fafafa;font-size:13.5px;outline:0}",
    ".ft input:focus{border-color:#870775}",
    ".ft button{border:0;border-radius:8px;padding:0 14px;color:#fff;cursor:pointer;font-size:13px;",
    "background:linear-gradient(180deg,#870775,#4d0342)}",
    ".ft button:disabled{opacity:.45;cursor:default}",
    ".by{padding:0 12px 9px;font-size:10px;color:#4b4b55;text-align:center}",
    "@media (max-width:420px){.panel{right:8px;left:8px;width:auto;bottom:76px}}",
  ].join("");
  root.appendChild(style);

  var launcher = document.createElement("button");
  launcher.className = "launcher";
  launcher.type = "button";
  launcher.textContent = LAUNCHER_LABEL;
  root.appendChild(launcher);

  var panel = null;
  var log = null;
  var input = null;
  var sendBtn = null;
  var busy = false;

  function text(el, value) {
    el.appendChild(document.createTextNode(value));
  }

  /* textContent throughout, never innerHTML. The reply is model output rendered
     on someone else's page; treating it as markup would be handing an injection
     vector a paintbrush. */
  function bubble(cls, value) {
    var el = document.createElement("div");
    el.className = "m " + cls;
    text(el, value);
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function chips(actions) {
    if (!actions || !actions.length) return;
    var wrap = document.createElement("div");
    wrap.className = "chips";
    for (var i = 0; i < actions.length; i++) {
      var c = document.createElement("span");
      c.className = "chip";
      text(c, actions[i].label);
      wrap.appendChild(c);
    }
    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;
  }

  function send(value) {
    if (busy || !value) return;
    busy = true;
    sendBtn.disabled = true;
    bubble("me", value);
    input.value = "";
    var pending = bubble("it", "Working…");

    var controller = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () {
      if (controller) controller.abort();
    }, 45000);

    var contextData = null;
    try {
      var raw = localStorage.getItem("fte.widget.context");
      if (raw) contextData = JSON.parse(raw);
    } catch (e) {}

    fetch(API + "/chat/public", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-FTE-Site-Key": KEY },
      body: JSON.stringify({ message: value, session_id: session, ephemeral_context: contextData }),
      signal: controller ? controller.signal : undefined,
    })
      .then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) throw new Error(body.detail || "Something went wrong.");
          return body;
        });
      })
      .then(function (body) {
        pending.className = "m it";
        pending.textContent = "";
        text(pending, body.reply);
        chips(body.actions);
      })
      .catch(function (err) {
        pending.className = "m er";
        pending.textContent = "";
        text(
          pending,
          err && err.name === "AbortError"
            ? "That took too long. Please try again."
            : (err && err.message) || "Something went wrong."
        );
      })
      .then(function () {
        clearTimeout(timer);
        busy = false;
        sendBtn.disabled = false;
        input.focus();
      });
  }

  function build() {
    panel = document.createElement("div");
    panel.className = "panel";

    var hd = document.createElement("div");
    hd.className = "hd";
    var title = document.createElement("b");
    /* Starts generic and is corrected the moment the store identifies itself.
       This file is one static script served to every tenant, so a name compiled
       into it is necessarily the wrong name for all but one of them — which is
       exactly what happened: every seller's widget was headed "Aeron Home
       Goods", the demo store. Only the key knows whose site this is. */
    text(title, "Support");
    var sub = document.createElement("small");

    fetch(API + "/widget/config", { headers: { "X-FTE-Site-Key": KEY } })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (cfg) {
        if (cfg && cfg.business_name) {
          title.textContent = "";
          text(title, cfg.business_name);
          sub.textContent = "";
          text(sub, "Support");
        }
      })
      .catch(function () {
        /* The header is cosmetic. A store that cannot be named still answers
           questions, so this must never block the conversation. */
      });
    var close = document.createElement("button");
    close.className = "x";
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    text(close, "×");
    close.onclick = toggle;
    hd.appendChild(title);
    hd.appendChild(sub);
    hd.appendChild(close);

    log = document.createElement("div");
    log.className = "log";

    var ft = document.createElement("form");
    ft.className = "ft";
    input = document.createElement("input");
    input.setAttribute("placeholder", "Ask about an order, a refund, a product…");
    input.setAttribute("aria-label", "Message");
    sendBtn = document.createElement("button");
    sendBtn.type = "submit";
    text(sendBtn, "Send");
    ft.appendChild(input);
    ft.appendChild(sendBtn);
    ft.onsubmit = function (e) {
      e.preventDefault();
      send(input.value.trim());
    };

    var by = document.createElement("div");
    by.className = "by";
    text(by, "AI support · a person reviews anything that moves money");

    panel.appendChild(hd);
    panel.appendChild(log);
    panel.appendChild(ft);
    panel.appendChild(by);
    root.appendChild(panel);

    send("hi");
  }

  function toggle() {
    if (!panel) {
      build();
    } else {
      panel.style.display = panel.style.display === "none" ? "flex" : "none";
    }
    if (input) input.focus();
  }

  launcher.onclick = toggle;
})();
"""


def render_widget_js() -> str:
    """The widget source, with this deployment's API base baked in.

    The API base is the only thing substituted, and it is the only thing that
    *can* be: this response is identical for every tenant, so anything
    store-specific has to be fetched at runtime against the key.
    """
    return _TEMPLATE.replace(
        "__API_BASE__", get_settings().public_base_url.rstrip("/")
    )
