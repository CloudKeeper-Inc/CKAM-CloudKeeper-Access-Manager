import os
import re
import threading
from flask import Flask, request, jsonify, g # <--- Make sure 'g' is imported
from flask_cors import CORS
from slack_bolt import App as SlackApp
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient # <--- Import WebClient for the thread
from config import Config
import boto3

# --- 1. INITIALIZATION ---
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# --- 2. THE PERMANENT FIX for CREDENTIAL EXPIRATION ---
@app.before_request
def get_db_client():
    """
    This function runs before EACH API request to ensure we always have a fresh
    DynamoDB client with valid, non-expired credentials.
    """
    # The 'g' object is a special Flask context that is unique for each request.
    # We use it to store our client for the duration of this single request.
    if 'dynamo_client' not in g:
        cross_account_role_arn = os.environ.get("CROSS_ACCOUNT_ROLE_ARN")
        
        if app.config.get('LOCALSTACK_ENDPOINT'):
            # Logic for local development (unchanged)
            g.dynamo_client = boto3.client(
                'dynamodb',
                region_name=app.config.get('AWS_REGION'),
                endpoint_url=app.config.get('LOCALSTACK_ENDPOINT')
            )
        elif cross_account_role_arn:
            # This logic will now run for each request, getting fresh credentials every time.
            try:
                sts_client = boto3.client('sts', region_name=app.config.get('AWS_REGION'))
                assumed_role_object = sts_client.assume_role(
                    RoleArn=cross_account_role_arn,
                    RoleSessionName="CKAM-API-Request-Session"
                )
                credentials = assumed_role_object['Credentials']
                g.dynamo_client = boto3.client(
                    'dynamodb',
                    region_name=app.config.get('AWS_REGION'),
                    aws_access_key_id=credentials['AccessKeyId'],
                    aws_secret_access_key=credentials['SecretAccessKey'],
                    aws_session_token=credentials['SessionToken'],
                )
                print("Successfully assumed role and created fresh DynamoDB client for API request.")
            except Exception as e:
                print(f"FATAL: Could not assume role during API request. Error: {e}")
                return jsonify({"error": "Could not establish a secure connection to the database."}), 503
        else:
            raise ValueError("Database is not configured. Set LOCALSTACK_ENDPOINT or CROSS_ACCOUNT_ROLE_ARN.")

# --- 3. SLACK APP INITIALIZATION ---
slack_app = SlackApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)
slack_handler = SlackRequestHandler(slack_app)

# --- 4. REGISTER BLUEPRINTS ---
from routes.access_requests import access_requests_bp
app.register_blueprint(access_requests_bp, url_prefix='/api/access')


# --- 5. HELPER FUNCTION FOR SLACK ACTIONS (Thread-Safe Version) ---
def process_action(body, logger, new_status, app_config):
    """
    Processes the 'approve' or 'deny' action in a background thread.
    This version is thread-safe as it creates its own AWS and Slack clients.
    """
    action_word = "Approval" if new_status == "Approved" else "Denial"
    logger.info(f"Processing {action_word} in background thread.")
    
    user_id = body['user']['id']
    approver_name = body['user']['name']
    channel_id = body['channel']['id']
    message_ts = body['message']['ts']
    request_id = None

    try:
        for field in body['message']['blocks'][1]['fields']:
            if field['text'].startswith("*Request ID:*"):
                request_id = field['text'].splitlines()[1]
                break
        if not request_id:
            raise ValueError("Request ID field not found")
    except (IndexError, AttributeError, ValueError) as e:
        logger.error(f"FATAL: Could not parse request_id from Slack message: {e}")
        return

    try:
        sts_client = boto3.client('sts', region_name=app_config['AWS_REGION'])
        assumed_role_object = sts_client.assume_role(
            RoleArn=app_config['CROSS_ACCOUNT_ROLE_ARN'],
            RoleSessionName="CKAM-Action-Processor-Session"
        )
        credentials = assumed_role_object['Credentials']
        dynamo_client = boto3.client(
            'dynamodb',
            region_name=app_config['AWS_REGION'],
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )
        slack_client = WebClient(token=app_config['SLACK_BOT_TOKEN'])
        request_table = app_config['REQUEST_TABLE_NAME']
    except Exception as e:
        logger.error(f"FATAL: Could not create clients in thread. Error: {e}")
        return
    
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
                ':status': {'S': new_status},
                ':approver': {'S': approver_name}
            }
        )
        
        original_blocks = body['message']['blocks']
        original_blocks.pop()
        
        final_text = (f":white_check_mark: Request *Approved* by <@{user_id}>" if new_status == "Approved"
                      else f":x: Request *Denied* by <@{user_id}>")

        original_blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": final_text}})
        slack_client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=original_blocks,
            text=f"Request {request_id} was {new_status}"
        )
    else:
        approver = response.get('Item', {}).get('approver', {}).get('S', 'someone')
        slack_client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"This request has already been handled (`{current_status}`) by {approver}."
        )

# --- 6. SLACK ACTION HANDLERS ---
@slack_app.action("approve")
def handle_approve_action(ack, body, logger):
    ack()
    config_for_thread = {
        'AWS_REGION': app.config['AWS_REGION'],
        'CROSS_ACCOUNT_ROLE_ARN': os.environ.get("CROSS_ACCOUNT_ROLE_ARN"),
        'SLACK_BOT_TOKEN': os.environ.get("SLACK_BOT_TOKEN"),
        'REQUEST_TABLE_NAME': app.config['REQUEST_TABLE_NAME'],
    }
    thread = threading.Thread(target=process_action, args=(body, logger, "Approved", config_for_thread))
    thread.start()

@slack_app.action("deny")
def handle_deny_action(ack, body, logger):
    ack()
    config_for_thread = {
        'AWS_REGION': app.config['AWS_REGION'],
        'CROSS_ACCOUNT_ROLE_ARN': os.environ.get("CROSS_ACCOUNT_ROLE_ARN"),
        'SLACK_BOT_TOKEN': os.environ.get("SLACK_BOT_TOKEN"),
        'REQUEST_TABLE_NAME': app.config['REQUEST_TABLE_NAME'],
    }
    thread = threading.Thread(target=process_action, args=(body, logger, "Rejected", config_for_thread))
    thread.start()

# --- 7. FLASK ROUTES ---
@app.route("/slack/events", methods=["POST"])
def slack_events():
    return slack_handler.handle(request)

@app.route('/health')
def health_check():
    return jsonify({"status": "ok", "message": "Backend API is running"})

# --- 8. RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)

