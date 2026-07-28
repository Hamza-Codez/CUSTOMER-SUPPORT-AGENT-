"""The themed summary email.

Purple / black / zinc, per the platform's look, with everything inlined. Email
clients strip `<style>` blocks and ignore most modern CSS, so this uses inline
styles and table-free block layout rather than anything that would look right in
a browser and collapse in Outlook.

Three jobs, per the intent doc: close the loop for the customer, collect a
satisfaction signal, and carry a quiet "handled by your FTE" footprint.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

# Inlined because clients drop <style>. Kept as constants so the palette is
# stated once rather than smeared through the markup.
INK = "#09090b"        # zinc-950
SURFACE = "#18181b"    # zinc-900
BORDER = "#27272a"     # zinc-800
MUTED = "#a1a1aa"      # zinc-400
TEXT = "#e4e4e7"       # zinc-200
ACCENT = "#a855f7"     # purple-500
ACCENT_DIM = "#7e22ce"  # purple-700


@dataclass
class SummaryContent:
    customer_name: str
    business_name: str
    summary: str
    actions: list[str]
    feedback_url: str


def _rating_links(feedback_url: str) -> str:
    """Five one-click ratings. A link, not a form: a mail client can follow a
    GET, and asking someone to open a browser and type is asking for nothing."""
    cells = []
    for score in range(1, 6):
        cells.append(
            f'<a href="{html.escape(feedback_url)}?rating={score}" '
            f'style="display:inline-block;width:44px;height:44px;line-height:44px;'
            f'margin:0 4px;text-align:center;border-radius:12px;'
            f'background:{SURFACE};border:1px solid {BORDER};color:{TEXT};'
            f'text-decoration:none;font-size:16px;font-weight:600;">{score}</a>'
        )
    return "".join(cells)


def render_summary_email(content: SummaryContent) -> tuple[str, str, str]:
    """Return (subject, html, plain_text)."""
    subject = f"Your conversation with {content.business_name}"

    actions_html = ""
    if content.actions:
        items = "".join(
            f'<li style="margin:0 0 6px 0;color:{TEXT};">{html.escape(a)}</li>'
            for a in content.actions
        )
        actions_html = (
            f'<p style="margin:24px 0 8px 0;color:{MUTED};font-size:13px;'
            f'text-transform:uppercase;letter-spacing:.06em;">What happened</p>'
            f'<ul style="margin:0;padding-left:20px;font-size:15px;line-height:1.6;">{items}</ul>'
        )

    body = f"""
<div style="margin:0;padding:32px 16px;background:{INK};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;background:{SURFACE};border:1px solid {BORDER};border-radius:16px;overflow:hidden;">
    <div style="height:3px;background:linear-gradient(90deg,{ACCENT} 0%,{ACCENT_DIM} 100%);"></div>
    <div style="padding:32px;">
      <p style="margin:0 0 4px 0;color:{MUTED};font-size:13px;">{html.escape(content.business_name)}</p>
      <h1 style="margin:0 0 20px 0;color:#fafafa;font-size:22px;font-weight:650;letter-spacing:-.01em;">
        Thanks, {html.escape(content.customer_name)}
      </h1>
      <p style="margin:0;color:{TEXT};font-size:15px;line-height:1.65;">{html.escape(content.summary)}</p>
      {actions_html}
      <div style="margin:32px 0 0 0;padding:24px 0 0 0;border-top:1px solid {BORDER};">
        <p style="margin:0 0 14px 0;color:#fafafa;font-size:15px;font-weight:600;">How did we do?</p>
        <p style="margin:0 0 16px 0;color:{MUTED};font-size:13px;">Tap a number — 1 is poor, 5 is great.</p>
        <div>{_rating_links(content.feedback_url)}</div>
      </div>
    </div>
    <div style="padding:18px 32px;background:{INK};border-top:1px solid {BORDER};">
      <p style="margin:0;color:{MUTED};font-size:12px;line-height:1.5;">
        Handled by a Digital FTE ·
        <span style="color:{ACCENT};">always-on frontline support</span>
      </p>
    </div>
  </div>
</div>
""".strip()

    action_lines = "\n".join(f"  - {a}" for a in content.actions)
    text = f"""{content.business_name}

Thanks, {content.customer_name}

{content.summary}
{("\nWhat happened:\n" + action_lines) if content.actions else ""}

How did we do? Rate 1-5:
{content.feedback_url}?rating=1  (poor)
{content.feedback_url}?rating=5  (great)

Handled by a Digital FTE — always-on frontline support.
""".strip()

    return subject, body, text


def render_thanks_page(rating: int, already_recorded: bool = False) -> str:
    """What the browser shows after a rating link is clicked."""
    headline = "Thanks for the feedback" if not already_recorded else "Already noted"
    detail = (
        f"You rated this conversation {rating} out of 5."
        if not already_recorded
        else "We had already recorded a rating for this conversation."
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{headline}</title></head>
<body style="margin:0;padding:48px 16px;background:{INK};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:440px;margin:0 auto;background:{SURFACE};border:1px solid {BORDER};border-radius:16px;overflow:hidden;">
    <div style="height:3px;background:linear-gradient(90deg,{ACCENT} 0%,{ACCENT_DIM} 100%);"></div>
    <div style="padding:32px;text-align:center;">
      <h1 style="margin:0 0 10px 0;color:#fafafa;font-size:20px;font-weight:650;">{headline}</h1>
      <p style="margin:0;color:{MUTED};font-size:14px;line-height:1.6;">{detail}</p>
    </div>
  </div>
</body></html>"""
