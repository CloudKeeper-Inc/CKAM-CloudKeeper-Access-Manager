import re
from flask import current_app
from app import slack_app  # Import the slack_app instance from our main app.py


# Use the slack_app instance to register the action handlers
@slack_app.action("approve")
def handle_approve_action(ack, body, logger):
    ack()
    logger.info("Approve button clicked")

    # Get user who clicked the button
    user_id = body['user']['id']
    user_info = current_app.slack_bot_client.users_info(user=user_id)
    approver_name = user_info['user']['real_name']

    # Extract request_id from the original message blocks
    try:
        request_id_field = body['message']['blocks'][1]['fields'][2]['text']
        request_id = re.search(r'\b\d+\.\d+\b', request_id_field).group(0)
    except (IndexError, AttributeError):
        logger.error("Could not parse request_id from message")
        return

    dynamo_client = current_app.dynamo_client
    request_table = current_app.config['REQUEST_TABLE_NAME']

    # --- Database Logic (Adapted from your original bot) ---
    response = dynamo_client.get_item(
        TableName=request_table,
        Key={'requestId': {'S': request_id}},
        ProjectionExpression='requestStatus, approver'
    )
    current_status = response.get('Item', {}).get('requestStatus', {}).get('S')

    if current_status == 'Pending':
        # Update status to Approved
        dynamo_client.update_item(
            TableName=request_table,
            Key={'requestId': {'S': request_id}},
            UpdateExpression='SET #RS = :status, #AP = :approver',
            ExpressionAttributeNames={'#RS': 'requestStatus', '#AP': 'approver'},
            ExpressionAttributeValues={
                ':status': {'S': 'Approved'},
                ':approver': {'S': approver_name}
            }
        )

        # Update the original Slack message to show it was approved
        original_blocks = body['message']['blocks']
        original_blocks.pop()  # Remove the old buttons
        original_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":white_check_mark: Request *Approved* by <@{user_id}>"
            }
        })
        current_app.slack_bot_client.chat_update(
            channel=body['channel']['id'],
            ts=body['message']['ts'],
            blocks=original_blocks
        )
    else:
        # Request was already handled
        approver = response.get('Item', {}).get('approver', {}).get('S', 'someone')
        current_app.slack_bot_client.chat_postEphemeral(
            channel=body['channel']['id'],
            user=user_id,
            text=f"This request has already been `{current_status}` by {approver}."
        )


@slack_app.action("deny")
def handle_deny_action(ack, body, logger):
    ack()
    logger.info("Deny button clicked")

    user_id = body['user']['id']
    user_info = current_app.slack_bot_client.users_info(user=user_id)
    approver_name = user_info['user']['real_name']

    try:
        request_id_field = body['message']['blocks'][1]['fields'][2]['text']
        request_id = re.search(r'\b\d+\.\d+\b', request_id_field).group(0)
    except (IndexError, AttributeError):
        logger.error("Could not parse request_id from message")
        return

    dynamo_client = current_app.dynamo_client
    request_table = current_app.config['REQUEST_TABLE_NAME']

    response = dynamo_client.get_item(
        TableName=request_table,
        Key={'requestId': {'S': request_id}},
        ProjectionExpression='requestStatus, approver'
    )
    current_status = response.get('Item', {}).get('requestStatus', {}).get('S')

    if current_status == 'Pending':
        dynamo_client.update_item(
            TableName=request_table,
            Key={'requestId': {'S': request_id}},
            UpdateExpression='SET #RS = :status, #AP = :approver',
            ExpressionAttributeNames={'#RS': 'requestStatus', '#AP': 'approver'},
            ExpressionAttributeValues={
                ':status': {'S': 'Rejected'},
                ':approver': {'S': approver_name}
            }
        )

        original_blocks = body['message']['blocks']
        original_blocks.pop()  # Remove the old buttons
        original_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":x: Request *Denied* by <@{user_id}>"
            }
        })
        current_app.slack_bot_client.chat_update(
            channel=body['channel']['id'],
            ts=body['message']['ts'],
            blocks=original_blocks
        )
    else:
        approver = response.get('Item', {}).get('approver', {}).get('S', 'someone')
        current_app.slack_bot_client.chat_postEphemeral(
            channel=body['channel']['id'],
            user=user_id,
            text=f"This request has already been `{current_status}` by {approver}."
        )
