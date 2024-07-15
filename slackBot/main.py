import os
import re
import boto3
import ngrok
from slack_sdk import WebClient
from slack_bolt import App
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

bot_client = WebClient(token=os.environ['SLACK_TOKEN'])

listener = ngrok.forward(addr = "localhost:3001", authtoken = os.getenv('NGROKAUTHTOKEN'),
    domain = os.getenv('DOMAIN'))

# Initialize your app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_TOKEN"),
    signing_secret=os.environ.get("SIGNING_SECRET")
)

#DynamoDb:
requestTable = os.getenv('REQUESTTABLENAME')
approverTable = os.getenv('APPROVERTABLENAME')
accessManagerTable = os.getenv('ACCESSMANAGERMETADATATABLE')
dynamoClient = boto3.client('dynamodb',region_name = 'us-east-1')


@app.event("app_mention")
def appMention(event):
    
    user_id = event['user']
    channel_id = event['channel']
    message_ts = event['ts']

    message = f"Hello <@{user_id}>! Thanks for mentioning me."

    #Scanning Permissions(DisplayName) from dynamoDb table: AccessManagerTable
    response = dynamoClient.scan(
        TableName = accessManagerTable,
        AttributesToGet=['DisplayName']
    )
    display_names = [item['DisplayName']['S'] for item in response['Items']]

    # Update the 'options' field in the 'static_select' block
    static_select_block = {
        "type": "input",
        "element": {
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select an item",
                "emoji": True
            },
            "options": [
                {"text": {"type": "plain_text", "text": display_name, "emoji": True}, "value": f"value-{index}"}
                for index, display_name in enumerate(display_names)
            ],
            "action_id": "static_select-action"
        },
        "label": {"type": "plain_text", "text": "Permission", "emoji": True}
    }
    
    bot_client.chat_postMessage(channel=channel_id, thread_ts=message_ts, text=message)

    bot_client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "CloudKeeper Access Manager",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": "Please fill in your details",
                    "emoji": True
                }
            },
            {"type": "divider"},
            static_select_block,
            {
                "type": "input",
                "element": {
                    "type": "radio_buttons",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Just-in-time", "emoji": True}, "value": "value-0"},
                        {"text": {"type": "plain_text", "text": "Always", "emoji": True}, "value": "value-1"}
                    ],
                    "action_id": "radio_buttons-action"
                },
                "label": {"type": "plain_text", "text": "Access type", "emoji": True},
                "optional": False
            },
            {
                "type": "input",
                "element": {"type": "plain_text_input", "action_id": "plain_text_input-action"},
                "label": {"type": "plain_text", "text": "Time in hours", "emoji": False},
                "optional": True
            },
            {
                "type": "input",
                "element": {"type": "plain_text_input", "multiline": True, "action_id": "plain_text_input-action"},
                "label": {"type": "plain_text", "text": "Reason", "emoji": True}
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Submit", "emoji": True}, "value": "click_me_123", "action_id": "submit"}
                ]
            }
        ]
    )


@app.action("static_select-action")
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)


@app.action("radio_buttons-action")
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)


@app.action("plain_text_input-action")
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)


@app.action("submit")
def submitForm(ack, respond, body, logger):

    ack()
    logger.info(body)
    
    #Getting User ID of user that submitted the request
    user_id = body['user']['id']
    result = bot_client.users_info(user=user_id)

    # Getting BlockIDs of input blocks:
    permissionBlockId = body["message"]["blocks"][3]["block_id"]
    accessBlockId = body["message"]["blocks"][4]["block_id"]
    timeBlockId = body["message"]["blocks"][5]["block_id"]
    reasonBlockId = body["message"]["blocks"][6]["block_id"]

    if body["state"]["values"][permissionBlockId]["static_select-action"]["selected_option"]:
        permission = body["state"]["values"][permissionBlockId]["static_select-action"]["selected_option"]["text"]["text"]
    if body["state"]["values"][accessBlockId]["radio_buttons-action"]["selected_option"]:
        access_type = body["state"]["values"][accessBlockId]["radio_buttons-action"]["selected_option"]["text"]["text"]
        if access_type =='Always':
            jit_time = 0
        elif access_type == 'Just-in-time' and body["state"]["values"][timeBlockId]["plain_text_input-action"]["value"] == '0':
            respond('Invalid value for Just-in-time access.\nPlease retry by mentioning bot again. :bye:')
        elif body["state"]["values"][timeBlockId]["plain_text_input-action"]["value"]:
            jit_time = float(body["state"]["values"][timeBlockId]["plain_text_input-action"]["value"])
    if body["state"]["values"][reasonBlockId]["plain_text_input-action"]["value"]:
        reason = body["state"]["values"][reasonBlockId]["plain_text_input-action"]["value"]

    #Contructing Response message for the submitted form
    response_message = "Request submitted 👍"
    response_message += f"\n*Permissions:*\n\t{permission}"
    response_message += f"\n*Access Type:*\n\t{access_type}"
    response_message += f"\n*JIT time:*\n\t{jit_time} hours"
    response_message += f"\n*Quoted reason:*\n\t\"{reason}\""

    #Preparing variables for dynamoDb put item request
    request_id = body['container']['thread_ts']
    user_name = result['user']['real_name']
    user_email = result['user']['profile']['email']
    request_status = 'Pending'
    duration = jit_time * 3600
    
    #Putting item in dynamoDb table: requestTable
    response = dynamoClient.put_item(
        TableName = requestTable,
        Item={
            'requestId': {
                'S': request_id
            },
            'duration': {
                'N': str(duration)
            },
            'userEmail': {
                'S': user_email
            },
            'userName': {
                'S': user_name
            },
            'permissionType': {
                'S': permission
            },
            'reason': {
                'S': reason
            },
            'requestStatus': {
                'S': request_status
            }
        }
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        postApproveRequest(request_id, user_name, permission, jit_time, reason, access_type)
        respond(response_message)


def postApproveRequest(request_id, user_name, permission, jit_time, reason, access_type):
    #Time of request submission in IST
    ist = timedelta(hours=5, minutes=30)
    utc_now = datetime.utcnow()
    ist_now = (utc_now + ist).strftime("%Y-%m-%d  %H:%M")

    #Block message for Request approval
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*You have a new Access request*"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Requester's name:*\n{user_name}"},
            {"type": "mrkdwn", "text": f"*When:*\n{ist_now}"},
            {"type": "mrkdwn", "text": f"*Request ID:*\n{request_id}"},
            {"type": "mrkdwn", "text": f"*Permission:*\n{permission}"},
            {"type": "mrkdwn", "text": f"*Access type:*\n{access_type}"},
            {"type": "mrkdwn", "text": f"*JIT time:*\n{jit_time} hrs"},
            {"type": "mrkdwn", "text": f"*Reason:*\n\"{reason}\""}
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "emoji": True, "text": "Approve"},
             "style": "primary", "value": "click_me_123", "action_id": "approve"},
            {"type": "button", "text": {"type": "plain_text", "emoji": True, "text": "Deny"},
             "style": "danger", "value": "click_me_123", "action_id": "deny"}
        ]}
    ]

    #Scanning Approver's Slack User ID from dynamoDb table: approverTable
    response = dynamoClient.scan(
        TableName = approverTable,
        AttributesToGet=['slackUserId']
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        for item in response["Items"]:
            userID = item["slackUserId"]["S"]
            bot_client.chat_postMessage(channel=userID, blocks=blocks)


@app.action("approve")
def handle_some_action(ack, body, logger):

    ack()
    logger.info(body)

    #Getting user ID and name of approver
    user_id = body['user']['id']
    result = bot_client.users_info(user=user_id)
    user_name = result['user']['real_name']

    #Message recontruction
    message = body["message"]["text"]
    message = message.replace('\n', '')
    message = message[:-27]

    count = 0
    result = ''
    for char in message:
        if char == '*':
            if count % 2 == 1:
                result += char
                result += ' '
                count += 1
            else:
                count += 1
                result += '\n'
                result += char
        else:
            result += char

    #Using regular expression to extract RequestId from original message
    pattern = r'\b\d+\.\d+\b'
    matches = re.findall(pattern, message)
    request_id = matches[0]

    #Reading request status from dynamoDb table
    request_status = dynamoClient.get_item(
        TableName = requestTable,
        Key = {
            'requestId': {'S': request_id}
        },
        AttributesToGet=['requestStatus']
    )
    
    #Updating request status in dynamoDb table
    if request_status["Item"]["requestStatus"]["S"] == 'Pending':
        dynamoClient.update_item(
            TableName = requestTable,
            
            ExpressionAttributeNames = {
                '#RS': 'requestStatus'
            },
            ExpressionAttributeValues = {
                ':u' : {
                    'S': 'Approved'
                }
            },
            Key = {
                'requestId': {
                    'S': request_id
                }
            },
            UpdateExpression='SET #RS = :u'
        )
        result += f'\nRequest *Approved* by *\'{user_name}\'* 👍'
        bot_client.chat_delete(channel=user_id, ts=body["container"]["message_ts"])
        bot_client.chat_postMessage(channel=user_id, text=result)

        #Notify requester
        requester_email = dynamoClient.get_item(
            TableName = requestTable,
            Key = {
                'requestId': {'S': request_id}
            },
            AttributesToGet=['userEmail']
        )
        requester_email = requester_email["Item"]["userEmail"]["S"]
        requester_id = bot_client.users_lookupByEmail(email=requester_email)
        requester_id = requester_id["user"]["id"]
        result = result[32:]
        bot_client.chat_postMessage(channel=requester_id, text=result)

    #If request is already addressed by someone else
    else:
        result += '\nThis request is either *Approved/Denied* by another admin or has *Expired* '
        bot_client.chat_delete(channel=user_id, ts=body["container"]["message_ts"])
        bot_client.chat_postMessage(channel=user_id, text=result)


@app.action("deny")
def handle_some_action(ack, body, logger):

    ack()
    logger.info(body)

    #Getting user ID and name of approver
    user_id = body['user']['id']
    result = bot_client.users_info(user=user_id)
    user_name = result['user']['real_name']

    #Message recontruction
    message = body["message"]["text"]
    message = message.replace('\n', '')
    message = message[:-27]

    count = 0
    result = ''
    for char in message:
        if char == '*':
            if count % 2 == 1:
                result += char
                result += ' '
                count += 1
            else:
                count += 1
                result += '\n'
                result += char
        else:
            result += char

    #Using regular expression to extract RequestId from original message
    pattern = r'\b\d+\.\d+\b'
    matches = re.findall(pattern, message)
    request_id = matches[0]

    #Reading request status from dynamoDb table
    request_status = dynamoClient.get_item(
        TableName = requestTable,
        Key = {
            'requestId': {'S': request_id}
        },
        AttributesToGet=['requestStatus']
    )
    
    #Updating request status in dynamoDb table
    if request_status["Item"]["requestStatus"]["S"] == 'Pending':
        dynamoClient.update_item(
            TableName = requestTable,
            
            ExpressionAttributeNames = {
                '#RS': 'requestStatus'
            },
            ExpressionAttributeValues = {
                ':u' : {
                    'S': 'Rejected'
                }
            },
            Key = {
                'requestId': {
                    'S': request_id
                }
            },
            UpdateExpression='SET #RS = :u'
        )
        result += f'\nRequest *Denied* by *\'{user_name}\'* :thumbsdown:'
        bot_client.chat_delete(channel=user_id, ts=body["container"]["message_ts"])
        bot_client.chat_postMessage(channel=user_id, text=result)
        
        #Notify requester
        requester_email = dynamoClient.get_item(
            TableName = requestTable,
            Key = {
                'requestId': {'S': request_id}
            },
            AttributesToGet=['userEmail']
        )
        requester_email = requester_email["Item"]["userEmail"]["S"]
        requester_id = bot_client.users_lookupByEmail(email=requester_email)
        requester_id = requester_id["user"]["id"]
        result = result[32:]
        bot_client.chat_postMessage(channel=requester_id, text=result)

    #If request is already addressed by someone else
    else:
        result += '\nThis request is either *Approved/Denied* by another admin or has *Expired* :x:'
        bot_client.chat_delete(channel=user_id, ts=body["container"]["message_ts"])
        bot_client.chat_postMessage(channel=user_id, text=result)


if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3001)))