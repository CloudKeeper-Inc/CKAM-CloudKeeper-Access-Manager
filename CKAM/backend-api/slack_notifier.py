import os
from slack_sdk import WebClient
from datetime import datetime, timedelta

# The function signature has changed to accept a "target_conversation_id"
def post_slack_approval_request(request_id, user_name, permission, jit_time, reason, access_type, target_conversation_id):
    """
    Posts a formatted approval request message to a target Slack conversation (a channel OR a user).
    """
    try:
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        if not slack_token:
            print("ERROR: SLACK_BOT_TOKEN environment variable is not set.")
            return
        
        # We no longer get the channel from the environment. We use the one passed in.
        if not target_conversation_id:
            print(f"ERROR: No target_conversation_id was provided for request {request_id}.")
            return

        bot_client = WebClient(token=slack_token)

        # The message block generation is unchanged.
        ist = timedelta(hours=5, minutes=30)
        utc_now = datetime.utcnow()
        ist_now = (utc_now + ist).strftime("%Y-%m-%d %H:%M")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*A new access request has been submitted*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Requester's name:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*When:*\n{ist_now}"},
                    {"type": "mrkdwn", "text": f"*Request ID:*\n{request_id}"},
                    {"type": "mrkdwn", "text": f"*Permission:*\n{permission}"},
                    {"type": "mrkdwn", "text": f"*Access type:*\n{access_type}"},
                    {"type": "mrkdwn", "text": f"*JIT time:*\n{jit_time} hrs"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n\"{reason}\""}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "emoji": True, "text": "Approve"},
                        "style": "primary",
                        "value": "approve_request",
                        "action_id": "approve"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "emoji": True, "text": "Deny"},
                        "style": "danger",
                        "value": "deny_request",
                        "action_id": "deny"
                    }
                ]
            }
        ]

        # This command works for both Channel IDs (like C12345) and User IDs (like U12345).
        bot_client.chat_postMessage(
            channel=target_conversation_id,
            blocks=blocks,
            text=f"New access request from {user_name} for {permission}"
        )
        
        print(f"Successfully sent notification for request {request_id} to conversation {target_conversation_id}.")

    except Exception as e:
        print(f"ERROR sending Slack notification: {e}")
